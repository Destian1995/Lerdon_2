"""Authored geography and exclusive goods of the Mirror Realm."""
ROOT='files/otherworld/'
BACKGROUND=ROOT+'map/mirror_realm.png'
CITY_ART=('gate','harbor','sanctuary','moon','market','dawn','stars')
CITY_POSITIONS=((245,410),(1010,290),(420,615),(865,550),(380,235),(650,430),(760,200))
CITY_ROADS=((1,3),(3,4),(2,4),(2,7),(5,7),(1,5),(1,6),(4,6),(6,7))
FACTION_UNIT_TYPES={'Север':'archer','Эльфы':'infantry','Вампиры':'beast',
                    'Адепты':'cavalry','Элины':'mage'}


def city_art(city_id,faction=None):
    if faction:
        from otherworld_themes import image_path
        return image_path(faction,'cities','city_'+str(city_id))
    return ROOT+'cities/'+CITY_ART[(int(city_id)-1)%len(CITY_ART)]+'.png'


_UNITS=(
    ('Зеркальный страж','sentinel',70,145,28,140,2.0,'infantry'),
    ('Астральный лучник','archer',135,55,16,180,1.8,'archer'),
    ('Лунный всадник','rider',155,100,35,260,3.0,'cavalry'),
    ('Проводник эфира','weaver',210,65,20,340,3.0,'mage'),
    ('Кристальный голем','golem',115,250,80,420,4.5,'infantry'),
)

# Each role has its own faction profile, rather than a shared roster multiplier.
UNIT_PROFILES={
    'Север': ((78,190),(152,72),(180,128),(225,112),(140,340)),
    'Эльфы': ((98,135),(218,62),(210,105),(265,88),(155,285)),
    'Вампиры': ((125,148),(195,70),(255,118),(310,76),(185,265)),
    'Адепты': ((86,175),(182,98),(192,150),(285,124),(165,320)),
    'Элины': ((108,162),(202,84),(235,138),(248,106),(172,305)),
}

# Share of the combat budget spent on attack. Even a faction with one ordinary
# recruit gets five distinct offensive/defensive alternatives in the Mirror.
MIRROR_ATTACK_SHARES={
    'Север':(.20,1.0,.70,.50,0.0),
    'Эльфы':(.25,1.0,.75,.50,0.0),
    'Вампиры':(.30,1.0,.80,.50,0.0),
    'Адепты':(.15,1.0,.65,.50,0.0),
    'Элины':(.25,1.0,.75,.50,0.0),
}
MIRROR_TIER_SCALES=('1','1.4','1.9','2.5','3.3')


def balance_mirror_unit(item,base,faction):
    """Price one A/D point from the ordinary recruit, then redistribute it.

    Every faction uses one ordinary reference recruit, so different original
    role costs cannot invert the five tiers. Price, combat budget, durability
    and upkeep grow together while each tier retains its own A/D allocation.
    """
    from decimal import Decimal,ROUND_HALF_UP,ROUND_CEILING
    number=lambda value:Decimal(str(value or 0))
    points=max(Decimal(0),number(base.get('attack'))+number(base.get('defense')))
    money=max(Decimal(1),number(base.get('cost_money')))
    tier=int(item['id'])
    scale=number(MIRROR_TIER_SCALES[tier-1])
    budget=(points*Decimal('1.45')*scale).quantize(Decimal('.01'),rounding=ROUND_HALF_UP)
    share=number(MIRROR_ATTACK_SHARES.get(faction,MIRROR_ATTACK_SHARES['Адепты'])[item['id']-1])
    attack=(budget*share).quantize(Decimal('.01'),rounding=ROUND_HALF_UP)
    item.update(attack=float(attack),defense=float(budget-attack),
                durability=float((number(base.get('durability'))*scale).quantize(Decimal('.01'),rounding=ROUND_HALF_UP)),
                cost_money=max(int((money*Decimal('1.15')*scale).to_integral_value(rounding=ROUND_CEILING)),
                               int((money*Decimal('1.15')).to_integral_value(rounding=ROUND_CEILING))+tier-1),
                consumption=round(float(number(base.get('consumption'))*Decimal('1.15')*scale),3),
                base_unit_name=base['unit_name'],base_cost_money=float(money),
                base_combat_points=float(points),combat_budget=float(budget),
                tier=tier,tier_multiplier=float(scale),
                crowns_per_stat=float(money/points) if points else 0,
                role_label='Атака' if share==1 else 'Защита' if share==0 else 'Баланс' if share==Decimal('.5') else 'Штурмовик' if share>Decimal('.5') else 'Страж')
    return item


def unit_catalog(faction=None):
    result=[dict(id=i,unit_name=name,faction='Зазеркалье',image_path=ROOT+'units/'+key+'.png',
                 attack=attack,defense=defense,durability=hp,cost_money=cost,cost_time=1,
                 unit_class='1',consumption=food,unit_type=kind,initiative=50,morale=100,
                 aura_attack=0,aura_defense=0,crit_chance=5)
            for i,(name,key,attack,defense,hp,cost,food,kind) in enumerate(_UNITS,1)]
    if faction:
        from otherworld_themes import theme,image_path
        skin=theme(faction)
        for item,(_,key,*_) in zip(result,_UNITS):
            attack,defense=UNIT_PROFILES.get(faction,UNIT_PROFILES['Адепты'])[item['id']-1]
            item.update(unit_name=skin['units'][item['id']-1],image_path=image_path(faction,'units',key),
                        attack=attack,defense=defense,unit_type=FACTION_UNIT_TYPES.get(faction,'cavalry'))
    return result


_ARTIFACTS=(
    ('Клинок отражений','blade',210,80,180000),
    ('Венец созвездий','crown',110,160,160000),
    ('Поступь междумирья','boots',70,140,140000),
    ('Доспех эфира','armor',55,310,260000),
    ('Перстень междумирья','ring',180,120,200000),
)


def artifact_catalog():
    return [dict(id=i,name=name,image_url=ROOT+'artifacts/'+key+'.png',attack=attack,
                 defense=defense,cost=cost,season_name='Все',artifact_type=i-1,is_created=0)
            for i,(name,key,attack,defense,cost) in enumerate(_ARTIFACTS,1)]
