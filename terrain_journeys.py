"""Persistent road waypoints and armies waiting in forests/swamps (no Kivy)."""
import ast
import json
import math
import random
import sqlite3
import heapq

from city_war import current_turn, record_capture
from utils.movement_rules import movement_city_route

DELAYS = {'forest': 2, 'swamp': 3}
NAMES = {'forest': 'Лес', 'swamp': 'Болото'}


def ensure_schema(conn):
    conn.execute('''CREATE TABLE IF NOT EXISTS map_features(
        id INTEGER PRIMARY KEY, kind TEXT NOT NULL, city1 INTEGER NOT NULL,
        city2 INTEGER NOT NULL, fraction REAL NOT NULL, x REAL NOT NULL, y REAL NOT NULL,
        delay INTEGER NOT NULL, UNIQUE(city1,city2))''')
    columns = {r[1] for r in conn.execute('PRAGMA table_info(map_features)')}
    if 'icon_variant' not in columns:
        conn.execute('ALTER TABLE map_features ADD COLUMN icon_variant INTEGER NOT NULL DEFAULT 0')
    from terrain_icons import VARIANTS
    for kind,variants in VARIANTS.items():
        rows = conn.execute('SELECT id,icon_variant FROM map_features WHERE kind=? ORDER BY id',(kind,)).fetchall()
        valid = {v for _,v in rows if 1 <= v <= len(variants)}
        if len(valid) != len(rows):
            chosen = random.sample(range(1,len(variants)+1),len(rows))
            conn.executemany('UPDATE map_features SET icon_variant=? WHERE id=?',
                             [(v,row[0]) for v,row in zip(chosen,rows)])
    conn.execute('''CREATE TABLE IF NOT EXISTS terrain_journeys(
        id INTEGER PRIMARY KEY AUTOINCREMENT, faction TEXT NOT NULL,
        source TEXT NOT NULL,destination TEXT NOT NULL,camp TEXT NOT NULL DEFAULT '',
        mode TEXT NOT NULL,route TEXT NOT NULL,stops TEXT NOT NULL,
        stage INTEGER NOT NULL DEFAULT 0,ready_turn INTEGER NOT NULL)''')
    if 'destination_owner' not in {r[1] for r in conn.execute('PRAGMA table_info(terrain_journeys)')}:
        conn.execute('ALTER TABLE terrain_journeys ADD COLUMN destination_owner TEXT')


def features(conn):
    try:
        columns = {r[1] for r in conn.execute('PRAGMA table_info(map_features)')}
        variant = 'icon_variant' if 'icon_variant' in columns else '0'
        rows = [dict(zip(('id','kind','city1','city2','fraction','x','y','delay','icon_variant'), row))
                for row in conn.execute('SELECT id,kind,city1,city2,fraction,x,y,delay,'+variant+' FROM map_features ORDER BY id')]
        # Read-only compatibility with old maps, until the next schema upgrade.
        used = {'forest':set(),'swamp':set()}
        from terrain_icons import VARIANTS
        for row in rows:
            pool = used[row['kind']]
            if row['icon_variant'] in pool or not 1 <= row['icon_variant'] <= len(VARIANTS[row['kind']]):
                row['icon_variant'] = next(v for v in range(1,len(VARIANTS[row['kind']])+1) if v not in pool)
            pool.add(row['icon_variant'])
        return rows
    except sqlite3.OperationalError:
        return []  # Existing campaigns without waypoints retain ordinary travel.


def generate_features(conn, terrain=None, rng=None,sprite_scale=1,label_size_provider=None,allow_new_roads=False):
    """Put 1–2 swamps and 3–5 forests on distinct dry links, without duplicate art."""
    from map_roads import build_transport_network
    from map_terrain import TerrainView, FOREST, SWAMP,city_sprite_size
    from terrain_placement import feature_rect,separated,FeaturePlacementError
    from troop_movement import rendered_route
    rng = rng or random
    ensure_schema(conn)
    cities = {cid: tuple(ast.literal_eval(raw)) for cid, raw in conn.execute('SELECT id,coordinates FROM cities')}
    roads = [tuple(r) for r in conn.execute('SELECT city1,city2 FROM roads')]
    original={tuple(sorted(r)) for r in roads}
    degree={cid:sum(cid in r for r in roads) for cid in cities}
    if allow_new_roads:
        from itertools import combinations
        from utils.movement_rules import MAX_MOVE_DISTANCE
        owners=dict(conn.execute('SELECT id,faction FROM cities'))
        for a,b in combinations(sorted(cities),2):
            if (a,b) in original or degree[a]>=5 or degree[b]>=5:
                continue
            if owners[a]!='Нейтрал' and owners[b]!='Нейтрал':
                continue
            if sum(abs(cities[a][i]-cities[b][i]) for i in (0,1))<=MAX_MOVE_DISTANCE:
                roads.append((a,b))
    scale=max(.01,sprite_scale)
    size=city_sprite_size(scale)
    projected={cid:(x*scale,y*scale) for cid,(x,y) in cities.items()}
    labels={}
    if label_size_provider:
        for cid,name,faction in conn.execute('SELECT id,name,faction FROM cities'):
            width,height=label_size_provider(f'{name}({faction})')
            x,y=projected[cid];left=x+(size-width)/2
            labels[cid]=(left-5,y-height-10,left+width+5,y-1)
    network = build_transport_network(projected, roads, labels, tuple(v*scale for v in (30,30,1170,770)),
                                      scale=scale,terrain=TerrainView(terrain,scale=scale) if terrain else None)
    centers = {cid: (x+size/2,y+size*30/77) for cid,(x,y) in projected.items()}
    city_rects=[(x,y,x+size/scale,y+size/scale) for x,y in cities.values()]
    wet = {tuple(sorted((a,b))) for a,b,_ in network.sea}
    candidates = []
    for a,b in roads:
        if tuple(sorted((a,b))) in wet:
            continue
        route = rendered_route(network,[a,b],centers)
        if route:
            x,y,*_ = route.sample(.5)
            x,y=x/scale,y/scale
            if terrain and not terrain.is_land(x,y,clearance=5):
                continue
            if not all(separated(feature_rect(x,y),rect) for rect in city_rects):
                continue
            candidates.append((a,b,x,y,.5))
    rng.shuffle(candidates)
    biomes = {}
    if terrain:
        for kind in (FOREST,SWAMP):
            biomes[kind] = [((x+.5)*terrain.cell,terrain.world_height-(y+.5)*terrain.cell)
                            for y in range(0,terrain.height,3) for x in range(0,terrain.width,3)
                            if terrain.grid[y*terrain.width+x] == kind]
    requested = ['swamp'] * rng.randint(1,2) + ['forest'] * rng.randint(3,5)
    rankings={}
    for kind in set(requested):
        # Forest markers favor existing painted groves when one is available.
        biome = FOREST if kind == 'forest' else SWAMP
        def score(candidate):
            extra=10000 if tuple(sorted(candidate[:2])) not in original else 0
            if not terrain or terrain.kind_at(candidate[2],candidate[3]) == biome:
                return extra
            return extra+min((math.dist(candidate[2:4],p) for p in biomes[biome]),default=10000)
        rankings[kind]=sorted(candidates,key=score)
    visited=0
    def choose(index,chosen):
        nonlocal visited
        visited+=1
        if index==len(requested):
            return chosen
        if visited>20000 or len(candidates)-len(chosen)<len(requested)-index:
            return None
        for option in rankings[requested[index]]:
            if tuple(sorted(option[:2])) not in original and any(
                degree[cid]+sum(cid in p[:2] for p in chosen if tuple(sorted(p[:2])) not in original)>=5
                for cid in option[:2]):
                continue
            if all(option[:2]!=p[:2] and separated(feature_rect(*option[2:4]),feature_rect(*p[2:4])) for p in chosen):
                result=choose(index+1,chosen+[option])
                if result is not None:
                    return result
        return None
    wanted=(requested.count('swamp'),requested.count('forest'))
    plans=[wanted]+sorted(((s,f) for s in (1,2) for f in (3,4,5) if (s,f)!=wanted),
                         key=lambda p:(abs(p[0]-wanted[0])+abs(p[1]-wanted[1]),-sum(p)))
    chosen=None
    for swamp_count,forest_count in plans:
        requested=['swamp']*swamp_count+['forest']*forest_count
        visited=0
        chosen=choose(0,[])
        if chosen is not None:
            break
    if chosen is None:
        raise FeaturePlacementError('Не хватает свободных середин дорог для лесов и болот.')
    # Commit only a complete, non-overlapping plan. No unsafe fallback sites.
    conn.execute("DELETE FROM garrisons WHERE city_name IN (SELECT camp FROM terrain_journeys)")
    conn.execute('DELETE FROM terrain_journeys')
    conn.execute('DELETE FROM map_features')
    road_columns={r[1] for r in conn.execute('PRAGMA table_info(roads)')}
    next_id=conn.execute('SELECT COALESCE(MAX(id),0)+1 FROM roads').fetchone()[0] if 'id' in road_columns else None
    for kind,option in zip(requested,chosen):
        a,b,x,y,fraction = option
        if tuple(sorted((a,b))) not in original:
            if next_id is None:
                conn.execute('INSERT INTO roads(city1,city2) VALUES(?,?)',(a,b))
            else:
                conn.execute('INSERT INTO roads(id,city1,city2) VALUES(?,?,?)',(next_id,a,b))
                next_id+=1
        conn.execute('INSERT INTO map_features(kind,city1,city2,fraction,x,y,delay,icon_variant) VALUES(?,?,?,?,?,?,?,0)',
                     (kind,a,b,fraction,x,y,DELAYS[kind]))
    from terrain_icons import assign_variants
    assigned=assign_variants(features(conn),terrain,rng)
    conn.executemany('UPDATE map_features SET icon_variant=? WHERE id=?',
                     [(site['icon_variant'],site['id']) for site in assigned])
    conn.commit()
    return features(conn)


def route_stops(conn, chain):
    by_edge = {frozenset((f['city1'],f['city2'])): f for f in features(conn)}
    stops = []
    for i,(a,b) in enumerate(zip(chain,chain[1:])):
        item = by_edge.get(frozenset((a,b)))
        if item:
            stops.append(dict(item, edge=i, ratio=item['fraction'] if a == item['city1'] else 1-item['fraction']))
    return stops


def _experience(conn):
    return 'experience' in {r[1] for r in conn.execute('PRAGMA table_info(garrisons)')}


def _credit(conn, city, name, count, image, exp=0):
    if _experience(conn):
        conn.execute('''INSERT INTO garrisons(city_name,unit_name,unit_count,unit_image,experience)
            VALUES(?,?,?,?,?) ON CONFLICT(city_name,unit_name) DO UPDATE SET
            experience=CAST((COALESCE(garrisons.experience,0)*garrisons.unit_count+
                             excluded.experience*excluded.unit_count)*1.0/
                            (garrisons.unit_count+excluded.unit_count) AS INTEGER),
            unit_count=garrisons.unit_count+excluded.unit_count''', (city,name,count,image,exp))
    else:
        conn.execute('''INSERT INTO garrisons(city_name,unit_name,unit_count,unit_image)
            VALUES(?,?,?,?) ON CONFLICT(city_name,unit_name) DO UPDATE SET
            unit_count=garrisons.unit_count+excluded.unit_count''', (city,name,count,image))


def _camp_units(conn, camp):
    exp = 'COALESCE(g.experience,0)' if _experience(conn) else '0'
    return conn.execute(f'''SELECT g.unit_name,g.unit_count,g.unit_image,{exp},
        u.attack,u.defense,u.durability,u.unit_class FROM garrisons g
        JOIN units u ON u.unit_name=g.unit_name WHERE g.city_name=? AND g.unit_count>0''', (camp,)).fetchall()


def _queue_leg(conn, row, start, end, capture=False):
    from troop_movement import queue_route_march,marching_hero
    count = conn.execute('SELECT COALESCE(SUM(unit_count),0) FROM garrisons WHERE city_name=?', (row['camp'],)).fetchone()[0]
    units=[dict(unit_name=name,unit_count=count) for name,count in
           conn.execute('SELECT unit_name,unit_count FROM garrisons WHERE city_name=?',(row['camp'],))]
    queue_route_march(conn,row['faction'],json.loads(row['route']),row['destination'],count,
                      start=start,end=end,camp=row['camp'],capture=capture,has_hero=marching_hero(conn,units))


def start_journey(conn, faction, source, destination, units, mode='move'):
    if not features(conn):
        return None
    chain = movement_city_route(conn,source,destination,faction)
    stops = route_stops(conn,chain)
    if not stops:
        return None
    ensure_schema(conn)
    counts = {}
    for unit in units:
        name, count = unit['unit_name'], int(unit['unit_count'])
        if count <= 0:
            raise ValueError('Нельзя отправить пустой отряд.')
        counts[name] = counts.get(name,0) + count
    if not counts:
        return None
    with conn:
        snapshots = []
        exp = 'COALESCE(experience,0)' if _experience(conn) else '0'
        for name,count in counts.items():
            row = conn.execute(f'SELECT unit_count,unit_image,{exp} FROM garrisons WHERE city_name=? AND unit_name=?',
                               (source,name)).fetchone()
            if row is None or count > row[0]:
                raise ValueError(f'В городе {source} недостаточно войск {name}.')
            snapshots.append((name,count,row[1] or '',row[2]))
        owner=conn.execute('SELECT faction FROM cities WHERE name=?',(destination,)).fetchone()
        if mode=='move' and owner and owner[0]!=faction:
            allied=conn.execute('''SELECT 1 FROM diplomacies WHERE relationship='союз'
                AND ((faction1=? AND faction2=?) OR (faction1=? AND faction2=?))''',
                (faction,owner[0],owner[0],faction)).fetchone()
            mode='escort' if allied else 'attack'
        cur = conn.execute('''INSERT INTO terrain_journeys(faction,source,destination,mode,route,stops,ready_turn,destination_owner)
            VALUES(?,?,?,?,?,?,?,?)''', (faction,source,destination,mode,json.dumps(chain),json.dumps(stops),
                                      current_turn(conn)+stops[0]['delay'],owner[0] if owner else None))
        camp = '@terrain:' + str(cur.lastrowid)
        conn.execute('UPDATE terrain_journeys SET camp=? WHERE id=?',(camp,cur.lastrowid))
        for name,count,image,exp in snapshots:
            conn.execute('UPDATE garrisons SET unit_count=unit_count-? WHERE city_name=? AND unit_name=?', (count,source,name))
            _credit(conn,camp,name,count,image,exp)
        conn.execute('DELETE FROM garrisons WHERE unit_count<=0')
    journey = dict(faction=faction,camp=camp,route=json.dumps(chain),destination=destination)
    _queue_leg(conn,journey,(0,0),(stops[0]['edge'],stops[0]['ratio']))
    return cur.lastrowid


def waiting_armies(conn):
    try:
        rows = conn.execute('''SELECT j.id,j.faction,j.camp,j.destination,j.stops,j.stage,j.ready_turn,
            COALESCE(SUM(g.unit_count),0),j.mode FROM terrain_journeys j LEFT JOIN garrisons g ON g.city_name=j.camp
            GROUP BY j.id ORDER BY j.id''').fetchall()
    except sqlite3.OperationalError:
        return []
    return [dict(id=r[0],faction=r[1],camp=r[2],destination=r[3],feature=json.loads(r[4])[r[5]],
                 remaining=max(0,r[6]-current_turn(conn)),count=r[7],returning=r[8]=='return') for r in rows]


def _destination_policy(conn,row):
    """Recheck current diplomacy and the owner recorded when the order was sent."""
    faction=row['faction']
    target=conn.execute('SELECT faction FROM cities WHERE name=?',(row['destination'],)).fetchone()
    owner=target[0] if target else None
    relations={r[0] for r in conn.execute('''SELECT relationship FROM diplomacies
        WHERE (faction1=? AND faction2=?) OR (faction1=? AND faction2=?)''',(faction,owner,owner,faction))}
    hostile=owner!=faction and (owner=='Нейтрал' or 'война' in relations)
    allied=owner!=faction and not hostile and 'союз' in relations
    original=row.get('destination_owner')
    intended_ally=allied and ((original==owner and row['mode'] in ('escort','gift')) or
                            (original is None and row['mode']=='gift'))
    must_return=owner!=faction and not hostile and not intended_ally
    return owner,allied,hostile,must_return


def _return_route(conn,row,stop):
    """Exit the current road toward an owned city over safe roads, without teleporting."""
    faction=row['faction']
    cities={cid:(name,owner,tuple(ast.literal_eval(raw))) for cid,name,owner,raw in
            conn.execute('SELECT id,name,faction,coordinates FROM cities')}
    allies={faction}
    for first,second in conn.execute("SELECT faction1,faction2 FROM diplomacies WHERE relationship='союз'"):
        if first==faction:
            allies.add(second)
        elif second==faction:
            allies.add(first)
    for first,second in conn.execute("SELECT faction1,faction2 FROM diplomacies WHERE relationship='война'"):
        if first==faction:
            allies.discard(second)
        elif second==faction:
            allies.discard(first)
    chain=json.loads(row['route'])
    first,last=chain[stop['edge']:stop['edge']+2]
    blocked={first,last}
    adjacency={cid:[] for cid,data in cities.items() if data[1] in allies}
    for a,b in conn.execute('SELECT city1,city2 FROM roads'):
        if a not in adjacency or b not in adjacency or {a,b}==blocked:
            continue
        distance=math.dist(cities[a][2],cities[b][2])
        adjacency[a].append((b,distance));adjacency[b].append((a,distance))
    options=[]
    for anchor,other,ratio in ((first,last,1-stop['ratio']),(last,first,stop['ratio'])):
        if anchor not in adjacency:
            continue
        x,y=cities[anchor][2]
        distance=math.dist((stop['x'],stop['y']),(x+38.5,y+30))
        queue=[(distance,anchor,[anchor])];visited=set()
        while queue:
            cost,city,path=heapq.heappop(queue)
            if city in visited:
                continue
            visited.add(city)
            name,owner,_=cities[city]
            if owner==faction:
                options.append((0 if name==row['source'] else 1,cost,name,[other]+path,ratio))
            for neighbor,weight in adjacency[city]:
                if neighbor not in visited:
                    heapq.heappush(queue,(cost+weight,neighbor,path+[neighbor]))
    if not options:
        return None
    _,_,target,route,ratio=min(options)
    return target,route,(0,ratio)


def _start_return(conn,row,stop,turn):
    plan=_return_route(conn,row,stop)
    if plan is None:
        return False  # Keep the real camp and retry when a safe route exists.
    target,chain,start=plan
    stops=[s for s in route_stops(conn,chain) if (s['edge'],s['ratio'])>(start[0],start[1]+1e-7)]
    returning=dict(row,destination=target,mode='return',route=json.dumps(chain),stops=json.dumps(stops),
                   stage=0,destination_owner=row['faction'])
    if stops:
        ready=turn+stops[0]['delay']
        conn.execute('''UPDATE terrain_journeys SET destination=?,mode='return',route=?,stops=?,stage=0,
            ready_turn=?,destination_owner=? WHERE id=?''',
            (target,returning['route'],returning['stops'],ready,row['faction'],row['id']))
        _queue_leg(conn,returning,start,(stops[0]['edge'],stops[0]['ratio']))
        return True
    _queue_leg(conn,returning,start,(len(chain)-2,1))
    if _finish(conn,returning):
        conn.execute('DELETE FROM terrain_journeys WHERE id=?',(row['id'],))
        return True
    return False


def _finish(conn, row):
    faction,camp,target = row['faction'],row['camp'],row['destination']
    units = _camp_units(conn,camp)
    owner,allied,hostile,must_return=_destination_policy(conn,row)
    if must_return:
        return False
    if owner == faction or allied:
        if allied and row['mode'] == 'gift':
            substitute = conn.execute("SELECT unit_name,image_path FROM units WHERE faction=? AND CAST(unit_class AS INTEGER)=1 LIMIT 1", (owner,)).fetchone()
            if not substitute:
                return False
            for name,count,image,exp,*_ in units:
                _credit(conn,target,substitute[0],count,substitute[1],exp)
        else:
            for name,count,image,exp,*_ in units:
                _credit(conn,target,name,count,image,exp)
    elif units:
        defenders = _camp_units(conn,target)
        def army(rows):
            return [dict(unit_name=n,unit_count=c,unit_image=im,
                         units_stats={'Урон':a,'Защита':d,'Живучесть':hp,'Класс юнита':str(cls)})
                    for n,c,im,e,a,d,hp,cls in rows]
        if defenders:
            from fight import fight
            fight(camp,target,army(defenders),army(units),faction,owner,conn)
        else:
            for name,count,image,exp,*_ in units:
                _credit(conn,target,name,count,image,exp)
            conn.execute('UPDATE cities SET faction=? WHERE name=?',(faction,target))
            conn.execute('UPDATE buildings SET faction=? WHERE city_name=?',(faction,target))
            record_capture(conn,target,faction)
    conn.execute('DELETE FROM garrisons WHERE city_name=?',(camp,))
    return True


def advance_journeys(conn, turn):
    """Advance once per global turn; a second call cannot consume another day."""
    ensure_schema(conn)
    columns = ('id','faction','source','destination','camp','mode','route','stops','stage','ready_turn','destination_owner')
    rows = [dict(zip(columns,r)) for r in conn.execute('SELECT '+','.join(columns)+
            ' FROM terrain_journeys WHERE ready_turn<=? ORDER BY id',(turn,))]
    for row in rows:
        stops = json.loads(row['stops'])
        previous = stops[row['stage']]
        start = (previous['edge'],previous['ratio'])
        if _destination_policy(conn,row)[3]:
            if not _start_return(conn,row,previous,turn):
                conn.execute('UPDATE terrain_journeys SET ready_turn=? WHERE id=?',(turn+1,row['id']))
            conn.commit()
            continue
        if row['stage'] + 1 < len(stops):
            nxt = stops[row['stage']+1]
            conn.execute('UPDATE terrain_journeys SET stage=stage+1,ready_turn=? WHERE id=?',
                         (turn+nxt['delay'],row['id']))
            _queue_leg(conn,row,start,(nxt['edge'],nxt['ratio']))
        else:
            chain = json.loads(row['route'])
            _queue_leg(conn,row,start,(len(chain)-2,1),capture=_destination_policy(conn,row)[2])
            if _finish(conn,row):
                conn.execute('DELETE FROM terrain_journeys WHERE id=?',(row['id'],))
            else:
                conn.execute('UPDATE terrain_journeys SET ready_turn=? WHERE id=?',(turn+1,row['id']))
        conn.commit()


def available_attack_units(conn, city, units):
    """Staging cannot attack with reinforcements still waiting in terrain."""
    available = dict(conn.execute('SELECT unit_name,unit_count FROM garrisons WHERE city_name=?',(city,)))
    result = []
    for unit in units:
        name = unit['unit_name']
        count = min(unit['unit_count'],available.get(name,0))
        if count > 0:
            result.append(dict(unit,unit_count=count,city_name=city))
            available[name] -= count
    return result
