"""The common per-soldier stat calculation for quick and tactical combat.

Equipment/seasons/walls are already in units_stats. Matchups, battlefield
positions, random rolls and casualties are applied by the combat mode later.
"""
from utils.faction_bonuses import NORTH_MULTIPLIER,ADEPT_MULTIPLIER


def integer_stat(unit,key,default=0):
    try:return int(float((unit.get('units_stats') or {}).get(key,default)))
    except (TypeError,ValueError):return default


def unit_class(unit):
    try:return int(str((unit.get('units_stats') or {}).get('Класс юнита',1)).split()[0])
    except (TypeError,ValueError,IndexError):return 1


def base_power(unit,hero_bonus=(0,0,0),faction='',season_multiplier=1):
    attack=max(0,integer_stat(unit,'Урон'))
    defense=max(1,integer_stat(unit,'Защита')+integer_stat(unit,'Живучесть')/2)
    raw_defense=defense
    regular=unit_class(unit)==1
    if regular and faction=='Мятежники':attack*=.6;defense*=.6
    threshold_attack=unit.get('_faction_base_attack',attack)
    threshold_defense=unit.get('_faction_base_defense',raw_defense)
    if regular and unit.get('unit_name')!='Зомби':
        attack+=hero_bonus[0]
        defense+=hero_bonus[1]+hero_bonus[2]/2
    if regular and faction=='Север' and threshold_attack>0 and attack/threshold_attack>=20:
        attack=int(attack*(NORTH_MULTIPLIER*season_multiplier))
    if regular and faction=='Адепты' and threshold_defense>0 and defense/threshold_defense>=20:
        defense=int(defense*(ADEPT_MULTIPLIER*season_multiplier))
    experience=unit.get('_experience_multiplier',1)
    return attack*experience,defense*experience*unit.get('_terrain_defense_multiplier',1)
