"""Validated rebel orders shared by the map picker and the campaign AI."""
from rebel_campaign import offensive_route, declare_war


def available_targets(conn, player):
    return [(name, owner) for name, owner in conn.execute(
        'SELECT name,faction FROM cities ORDER BY name').fetchall()
        if owner not in (None, '', 'Нейтрал', 'Мятежники', player)
        and offensive_route(conn, name, owner)]


def issue_order(conn, player, city):
    targets = dict(available_targets(conn, player))
    if city not in targets:
        raise ValueError('Этот город больше недоступен для атаки мятежников.')
    enemy = targets[city]
    with conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS rebel_attack_order(
            id INTEGER PRIMARY KEY, target_city TEXT,target_faction TEXT)''')
        conn.execute('INSERT OR REPLACE INTO rebel_attack_order VALUES(1,?,?)', (city, enemy))
        declare_war(conn, enemy)
    return enemy
