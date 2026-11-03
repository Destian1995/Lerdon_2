"""Map-authored geography, persistent city relief and local economic perks."""
import ast
from collections import deque
from dataclasses import dataclass
import sqlite3

MOUNTAIN_DEFENSE = .30
LOWLAND_DEFENSE_PENALTY = .20
LOWLAND_CROWNS = .15
WATERSIDE_CRYSTALS = .20
WATER_REACH = 80


@dataclass(frozen=True)
class CityTerrain:
    city: str
    landform: str = 'plains'
    elevation: int = 1
    waterside: bool = False
    water_distance: object = None

    @property
    def defense_multiplier(self):
        if self.landform == 'highland':
            return 1+MOUNTAIN_DEFENSE
        if self.landform == 'lowland':
            return 1-LOWLAND_DEFENSE_PENALTY
        return 1.0

    @property
    def badges(self):
        badges=[]
        if self.landform == 'highland':
            badges.append('Горы: +30% ЗАЩ')
        elif self.landform == 'lowland':
            badges.append('Низина: −20% ЗАЩ; +15% крон')
        if self.waterside:
            badges.append('Берег: +20% крист.')
        return badges

    @property
    def description(self):
        rows=[]
        if self.landform == 'highland':
            rows.append('Горный город: +30% к боевой защите всего гарнизона, включая героев. Действует при обороне.')
        elif self.landform == 'lowland':
            rows.append('Низина: −20% к боевой защите всего гарнизона, включая героев. Действует при обороне.')
            rows.append('+15% к доле города в положительном доходе крон фракции.')
        else:
            rows.append('Равнина: обычная высота, без бонуса к защите или доходу крон.')
        if self.waterside:
            rows.append('Близость к реке, озеру или морю: +20% к выработке кристаллов фабрик этого города.')
        if self.landform == 'lowland' or self.waterside:
            rows.append('Экономические бонусы действуют при наличии снабжения. Доли городов в доходе крон равны.')
        return '\n'.join(rows)


def ensure_schema(conn):
    conn.execute('''CREATE TABLE IF NOT EXISTS city_terrain(
        city_name TEXT PRIMARY KEY, landform TEXT NOT NULL, elevation INTEGER NOT NULL,
        waterside INTEGER NOT NULL DEFAULT 0, water_distance REAL)''')


def read_all(conn):
    try:
        return {r[0]:CityTerrain(r[0],r[1],r[2],bool(r[3]),r[4]) for r in
                conn.execute('SELECT city_name,landform,elevation,waterside,water_distance FROM city_terrain')}
    except sqlite3.OperationalError:
        return {}


def city_terrain(conn, city):
    return read_all(conn).get(city,CityTerrain(city))


def defense_multiplier(conn, city):
    return city_terrain(conn,city).defense_multiplier


def _distance_field(terrain, kinds):
    distances=[float('inf')]*len(terrain.grid)
    queue=deque()
    for index,value in enumerate(terrain.grid):
        if value in kinds:
            distances[index]=0
            queue.append(index)
    while queue:
        index=queue.popleft()
        y,x=divmod(index,terrain.width)
        distance=distances[index]+1
        for dx,dy in ((-1,-1),(-1,0),(-1,1),(0,-1),(0,1),(1,-1),(1,0),(1,1)):
            nx,ny=x+dx,y+dy
            if 0<=nx<terrain.width and 0<=ny<terrain.height:
                neighbor=ny*terrain.width+nx
                if distances[neighbor]>distance:
                    distances[neighbor]=distance
                    queue.append(neighbor)
    return distances


def classify_city(terrain, city, x, y, sprite_scale=1):
    if terrain is None:
        return CityTerrain(city)
    from map_terrain import WATER, MOUNTAIN, SNOW
    fields=getattr(terrain,'_city_relief_fields',None)
    if fields is None:
        fields=terrain._city_relief_fields=(_distance_field(terrain,{WATER}),
                                          _distance_field(terrain,{MOUNTAIN}))
    scale=max(.8,sprite_scale)
    points=[(x+dx/scale,y+dy/scale) for dx,dy in
            ((12,8),(38.5,8),(65,8),(12,30),(38.5,30),(65,30),(38.5,48))]
    indices=[terrain.index_at(*p) for p in points]
    indices=[i for i in indices if i is not None]
    if not indices:
        return CityTerrain(city)
    water=min(fields[0][i] for i in indices)*terrain.cell
    mountain=min(fields[1][i] for i in indices)*terrain.cell
    high=sum(terrain.grid[i] == MOUNTAIN or
             (terrain.grid[i] == SNOW and fields[1][i]*terrain.cell<=48) for i in indices)
    if high>=3:
        landform,elevation='highland',2
    elif water<=48 and mountain>80:
        landform,elevation='lowland',0
    else:
        landform,elevation='plains',1
    return CityTerrain(city,landform,elevation,water<=WATER_REACH,None if water==float('inf') else water)


def assign_city_terrain(conn, terrain, sprite_scale=1):
    ensure_schema(conn)
    conn.execute('DELETE FROM city_terrain')
    result=[]
    for name,raw in conn.execute('SELECT name,coordinates FROM cities'):
        x,y=ast.literal_eval(raw)
        info=classify_city(terrain,name,x,y,sprite_scale)
        result.append((name,info.landform,info.elevation,int(info.waterside),info.water_distance))
    conn.executemany('INSERT INTO city_terrain VALUES(?,?,?,?,?)',result)
    conn.commit()
    return read_all(conn)


def economic_bonuses(conn, faction, crown_income, factory_yield):
    """Apply local perks once, before spending/upkeep; cut-off towns contribute zero."""
    from utils.faction_bonuses import supplied_cities
    info=read_all(conn)
    if not info:
        return dict(crowns=0,crystals=0,lowlands=0,waterside=0)
    owned={r[0] for r in conn.execute('SELECT name FROM cities WHERE faction=?',(faction,))}
    supplied=supplied_cities(conn,faction)
    lowlands={name for name in owned & supplied if name in info and info[name].landform=='lowland'}
    coastal={name for name in owned & supplied if name in info and info[name].waterside}
    crowns=int(max(0,crown_income)*LOWLAND_CROWNS*len(lowlands)/max(1,len(owned)))
    factories=0
    for city,count in conn.execute("SELECT city_name,count FROM buildings WHERE faction=? AND building_type='Фабрика'",(faction,)):
        if city in coastal:
            factories+=count or 0
    crystals=int(max(0,factories)*max(0,factory_yield)*WATERSIDE_CRYSTALS)
    return dict(crowns=crowns,crystals=crystals,lowlands=len(lowlands),waterside=len(coastal))
