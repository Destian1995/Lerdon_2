"""Authored geography and exclusive goods of the Mirror Realm."""
ROOT='files/otherworld/'
BACKGROUND=ROOT+'map/mirror_realm.png'
CITY_ART=('gate','harbor','sanctuary','moon','market','dawn','stars')
CITY_POSITIONS=((245,410),(1010,290),(420,615),(865,550),(380,235),(650,430),(760,200))
CITY_ROADS=((1,3),(3,4),(2,4),(2,7),(5,7),(1,5),(1,6),(4,6),(6,7))


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
            item.update(unit_name=skin['units'][item['id']-1],image_path=image_path(faction,'units',key),
                        attack=round(item['attack']*skin['attack']),defense=round(item['defense']*skin['defense']))
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
