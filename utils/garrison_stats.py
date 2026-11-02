"""Read-only opening combat strength of a whole city garrison."""
import sqlite3

from utils.faction_bonuses import combat_bonus_status, combat_multiplier


def garrison_totals(conn, city):
    columns = {r[1] for r in conn.execute('PRAGMA table_info(garrisons)')}
    experience = 'COALESCE(g.experience,0)' if 'experience' in columns else '0'
    rows = conn.execute(f'''SELECT u.unit_class,u.attack,u.defense,u.durability,
        g.unit_count,{experience},u.unit_name FROM garrisons g JOIN units u ON u.unit_name=g.unit_name
        WHERE g.city_name=? AND g.unit_count>0''', (city,)).fetchall()
    owner = conn.execute('SELECT faction FROM cities WHERE name=?', (city,)).fetchone()
    faction = owner[0] if owner else ''
    heroes = tuple(sum((r[i] or 0) for r in rows if str(r[0]) in ('2', '3')) for i in (1, 2, 3))
    walls = smithies = 0
    try:
        for kind, count in conn.execute('SELECT building_type,count FROM buildings WHERE city_name=?', (city,)):
            if kind == 'Стена':
                walls += count or 0
            elif kind == 'Кузница':
                smithies += count or 0
    except sqlite3.OperationalError:
        pass
    undead = 1
    try:
        row = conn.execute('SELECT COALESCE(is_undead,0) FROM cities WHERE name=?', (city,)).fetchone()
        if faction == 'Нежить' and row and row[0]:
            undead = 1.65
            capital = conn.execute('SELECT capital_city FROM undead_invasion WHERE id=1').fetchone()
            if capital and capital[0] == city:
                heroes = (heroes[0] + 100, heroes[1] + 850, heroes[2])
    except sqlite3.OperationalError:
        pass
    attack_total = defense_total = count_total = 0
    for cls, attack, defense, durability, count, exp, unit_name in rows:
        attack, defense, durability = attack or 0, defense or 0, durability or 0
        exp_mult = (1.25 if exp >= 7 else 1.15 if exp >= 3 else 1.05 if exp >= 1 else 1) if str(cls) == '1' else 1
        attack *= exp_mult * (1 + smithies * .05)
        defense *= exp_mult * (1 + walls * .15) * undead
        base_defense = max(defense + durability / 2, 1)
        if str(cls) == '1' and unit_name != 'Зомби':
            name, active, _, boosted = combat_bonus_status(faction, attack, defense, durability, heroes)
            attack += heroes[0]
            base_defense += heroes[1] + heroes[2] / 2
            if active:
                if name == 'Шквал':
                    attack *= combat_multiplier(faction, conn)
                elif name == 'Оплот':
                    base_defense *= combat_multiplier(faction, conn)
        attack_total += attack * count
        defense_total += base_defense * count
        count_total += count
    from utils.city_terrain import defense_multiplier
    return dict(attack=int(attack_total), defense=int(defense_total*defense_multiplier(conn,city)), count=count_total)
