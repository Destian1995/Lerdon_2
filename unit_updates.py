"""Small, idempotent unit updates shared by saved games and release packaging."""
MORGANA_NAME = 'Моргана'
MORGANA_IMAGE = 'files/army/death/morgana.png'
MORGANA_ATTACK = 208
LEGACY_GUARDIAN_NAME = 'Наместник'


def canonical_unit_name(name):
    return MORGANA_NAME if name == LEGACY_GUARDIAN_NAME else name


def ensure_morgana_guardian(cursor, city):
    previous = cursor.execute('SELECT unit_count FROM garrisons WHERE city_name=? AND unit_name=?',
                              (city, MORGANA_NAME)).fetchone()
    cursor.execute('''INSERT INTO garrisons(city_name,unit_name,unit_count,unit_image) VALUES (?,?,1,?)
        ON CONFLICT(city_name,unit_name) DO UPDATE SET unit_count=MAX(1,unit_count),unit_image=excluded.unit_image''',
                   (city, MORGANA_NAME, MORGANA_IMAGE))
    return not previous or previous[0] <= 0


def migrate_morgana(conn):
    """Rename the guardian once, preserving every stat except the +200 attack."""
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    changed = 0
    for table in ('units_default', 'units'):
        if table not in tables:
            continue
        columns = {r[1] for r in conn.execute(f'PRAGMA table_info({table})')}
        if not {'unit_name', 'faction', 'attack', 'image_path'} <= columns:
            continue
        changed += conn.execute(f'''
            UPDATE {table} SET unit_name=?, image_path=?, attack=attack+200
            WHERE faction=? AND unit_name=?
        ''', (MORGANA_NAME, MORGANA_IMAGE, 'Нежить', LEGACY_GUARDIAN_NAME)).rowcount
    if 'garrisons' in tables:
        columns = {r[1] for r in conn.execute('PRAGMA table_info(garrisons)')}
        if {'unit_name', 'city_name', 'unit_count', 'unit_image'} <= columns:
            for rowid, city, count in conn.execute(
                    'SELECT rowid,city_name,unit_count FROM garrisons WHERE unit_name=?',
                    (LEGACY_GUARDIAN_NAME,)).fetchall():
                current = conn.execute('SELECT rowid FROM garrisons WHERE city_name=? AND unit_name=?',
                                       (city, MORGANA_NAME)).fetchone()
                if current:
                    conn.execute('UPDATE garrisons SET unit_count=MAX(unit_count,?),unit_image=? WHERE rowid=?',
                                 (count, MORGANA_IMAGE, current[0]))
                    if 'experience' in columns:
                        conn.execute('''UPDATE garrisons SET experience=MAX(COALESCE(experience,0),
                            COALESCE((SELECT experience FROM garrisons WHERE rowid=?),0)) WHERE rowid=?''',
                                     (rowid, current[0]))
                    conn.execute('DELETE FROM garrisons WHERE rowid=?', (rowid,))
                else:
                    conn.execute('UPDATE garrisons SET unit_name=?,unit_image=? WHERE rowid=?',
                                 (MORGANA_NAME, MORGANA_IMAGE, rowid))
    if 'armies' in tables:
        columns = {r[1] for r in conn.execute('PRAGMA table_info(armies)')}
        if {'unit_type', 'unit_image', 'quantity', 'total_attack'} <= columns:
            conn.execute('''UPDATE armies SET unit_type=?,unit_image=?,total_attack=total_attack+200*quantity
                            WHERE unit_type=?''', (MORGANA_NAME, MORGANA_IMAGE, LEGACY_GUARDIAN_NAME))
    return changed
