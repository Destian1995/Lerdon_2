"""Read-only opening combat strength of a whole city garrison."""
import sqlite3

from utils.faction_bonuses import combat_bonus_status, combat_multiplier,battle_spirit_multiplier


def garrison_profiles(conn, city, faction=None):
    columns = {r[1] for r in conn.execute('PRAGMA table_info(garrisons)')}
    experience = 'COALESCE(g.experience,0)' if 'experience' in columns else '0'
    rows = conn.execute(f'''SELECT u.unit_class,u.attack,u.defense,u.durability,
        g.unit_count,{experience},u.unit_name FROM garrisons g JOIN units u ON u.unit_name=g.unit_name
        WHERE g.city_name=? AND g.unit_count>0''', (city,)).fetchall()
    owner = conn.execute('SELECT faction FROM cities WHERE name=?', (city,)).fetchone()
    faction = faction if faction is not None else (owner[0] if owner else '')
    walls = 0
    try:
        for kind, count in conn.execute('SELECT building_type,count FROM buildings WHERE city_name=?', (city,)):
            if kind == 'Стена':
                walls += count or 0
    except sqlite3.OperationalError:
        pass
    undead = 1
    capital_bonus = False
    try:
        row = conn.execute('SELECT COALESCE(is_undead,0) FROM cities WHERE name=?', (city,)).fetchone()
        if faction == 'Нежить' and row and row[0]:
            undead = 1.65
            capital = conn.execute('SELECT capital_city FROM undead_invasion WHERE id=1').fetchone()
            if capital and capital[0] == city:
                capital_bonus = True
    except sqlite3.OperationalError:
        pass
    prepared=[]
    raw_stats={r[6]:(int(r[1] or 0),int(r[2] or 0),int(r[3] or 0)) for r in rows}
    for cls,attack,defense,durability,count,exp,name in rows:
        prepared.append((str(cls).split()[0],int(attack or 0),
                         int((defense or 0)*(1+walls*.15)*undead),int(durability or 0),count,exp,name))
    heroes=tuple(sum(int(r[i]) for r in prepared if r[0] in ('2','3')) for i in (1,2,3))
    if capital_bonus:
        heroes=(heroes[0]+100,heroes[1]+850,heroes[2])
    from utils.city_terrain import defense_multiplier
    relief=defense_multiplier(conn,city)
    spirit=battle_spirit_multiplier(conn,faction)
    profiles={}
    for cls, attack, defense, durability, count, exp, unit_name in prepared:
        from monster_sites import experience_multiplier
        attack, defense, durability = attack or 0, defense or 0, durability or 0
        exp_mult = experience_multiplier(conn,faction,exp,city,unit_name) if str(cls) == '1' else 1
        base_defense = max(defense + durability / 2, 1)
        if faction=='Мятежники' and cls=='1':
            attack*=.6
            base_defense*=.6
        bonus_name,active='',False
        if str(cls) == '1' and unit_name != 'Зомби':
            raw_attack,raw_defense,raw_durability=raw_stats[unit_name]
            bonuses=(heroes[0]+attack-raw_attack,heroes[1]+defense-raw_defense,heroes[2])
            name, active, _, boosted = combat_bonus_status(faction,raw_attack,raw_defense,raw_durability,bonuses)
            bonus_name=name
            attack += heroes[0]
            base_defense += heroes[1] + heroes[2] / 2
            if active:
                if name == 'Шквал':
                    attack = int(attack*combat_multiplier(faction, conn))
                elif name == 'Оплот':
                    base_defense = int(base_defense*combat_multiplier(faction, conn))
        profiles[unit_name]=dict(attack=round(attack*exp_mult*spirit,8),defense=round(base_defense*exp_mult*relief,8),
                                 count=count,bonus_name=bonus_name,bonus_active=active)
    return profiles


def garrison_totals(conn, city, profiles=None):
    profiles=garrison_profiles(conn,city) if profiles is None else profiles
    return dict(attack=int(sum(p['attack']*p['count'] for p in profiles.values())),
                defense=int(sum(p['defense']*p['count'] for p in profiles.values())),
                count=sum(p['count'] for p in profiles.values()))
