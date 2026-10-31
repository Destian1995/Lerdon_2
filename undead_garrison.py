"""Undead capital archers, including upgrades of existing campaigns."""
ARCHER_NAME = 'Лучник нежити'
ARCHER_IMAGE = 'files/army/death/archer.png'
CAPITAL_GUARD_COUNT = 250000


def ensure_archer_units(conn):
    """Copy ghost defaults once; retain all stats except attack, defense and type."""
    for table in ('units_default', 'units'):
        columns = [row[1] for row in conn.execute(f'PRAGMA table_info({table})')]
        if not {'faction', 'unit_name', 'image_path', 'attack', 'defense'} <= set(columns):
            continue
        if conn.execute(f'SELECT 1 FROM {table} WHERE faction=? AND unit_name=?',
                        ('Нежить', ARCHER_NAME)).fetchone():
            continue
        row = conn.execute(f'SELECT * FROM {table} WHERE faction=? AND unit_name=?',
                           ('Нежить', 'Призрак')).fetchone()
        if row is None:
            continue
        values = dict(zip(columns, row))
        values.update(unit_name=ARCHER_NAME, image_path=ARCHER_IMAGE, attack=10,
                      defense=values['defense'] + 15, unit_type='archer')
        if 'id' in values:
            values['id'] = conn.execute(f'SELECT COALESCE(MAX(id),0)+1 FROM {table}').fetchone()[0]
        conn.execute(f'INSERT INTO {table} ({",".join(columns)}) VALUES ({",".join("?" for _ in columns)})',
                     [values[column] for column in columns])


def _migration_table(conn):
    conn.execute('CREATE TABLE IF NOT EXISTS undead_guard_migrations(capital_city TEXT PRIMARY KEY)')


def migrate_capital_archers(conn):
    """Replace only the stationary ghost reserve, once per capital in old saves."""
    ensure_archer_units(conn)
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if not {'undead_invasion', 'cities', 'garrisons'} <= tables:
        return
    if 'capital_city' not in {r[1] for r in conn.execute('PRAGMA table_info(undead_invasion)')}:
        return
    row = conn.execute('''SELECT c.name FROM undead_invasion i JOIN cities c ON c.name=i.capital_city
                          WHERE i.id=1 AND c.faction='Нежить' ''').fetchone()
    if not row:
        return
    capital = row[0]
    _migration_table(conn)
    if conn.execute('SELECT 1 FROM undead_guard_migrations WHERE capital_city=?', (capital,)).fetchone():
        return
    existing = conn.execute('SELECT 1 FROM garrisons WHERE city_name=? AND unit_name=?',
                            (capital, ARCHER_NAME)).fetchone()
    if not existing:
        ghost = conn.execute('SELECT unit_count FROM garrisons WHERE city_name=? AND unit_name=?',
                             (capital, 'Призрак')).fetchone()
        reserve = min(CAPITAL_GUARD_COUNT, max(0, ghost[0])) if ghost else 0
        if reserve:
            conn.execute('''INSERT INTO garrisons(city_name,unit_name,unit_count,unit_image)
                            VALUES (?,?,?,?)''', (capital, ARCHER_NAME, reserve, ARCHER_IMAGE))
            if 'experience' in {r[1] for r in conn.execute('PRAGMA table_info(garrisons)')}:
                conn.execute('''UPDATE garrisons SET experience=(SELECT experience FROM garrisons
                                WHERE city_name=? AND unit_name='Призрак')
                                WHERE city_name=? AND unit_name=?''', (capital, capital, ARCHER_NAME))
            conn.execute('''UPDATE garrisons SET unit_count=unit_count-?
                            WHERE city_name=? AND unit_name='Призрак' ''', (reserve, capital))
    conn.execute('INSERT INTO undead_guard_migrations VALUES (?)', (capital,))


def ensure_capital_archers(cursor, capital):
    """Replenish the stationary reserve without consuming marching ghosts."""
    _migration_table(cursor.connection)
    cursor.execute('INSERT OR IGNORE INTO undead_guard_migrations VALUES (?)', (capital,))
    cursor.execute('''INSERT INTO garrisons(city_name,unit_name,unit_count,unit_image) VALUES (?,?,?,?)
        ON CONFLICT(city_name,unit_name) DO UPDATE SET
            unit_count=MAX(unit_count,excluded.unit_count), unit_image=excluded.unit_image''',
                   (capital, ARCHER_NAME, CAPITAL_GUARD_COUNT, ARCHER_IMAGE))
