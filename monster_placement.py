"""Dedicated dry, dead-end branches. Monster sites never enter the city graph."""
import ast
import json
import math
import random

from map_roads import _bend, _clear, build_transport_network
from map_terrain import TerrainView, city_sprite_size
from terrain_placement import feature_rect, separated, FeaturePlacementError


def _intersects(a,b,c,d):
    def cross(p,q,r):
        return (q[0]-p[0])*(r[1]-p[1])-(q[1]-p[1])*(r[0]-p[0])
    return cross(a,b,c)*cross(a,b,d)<0 and cross(c,d,a)*cross(c,d,b)<0


def _segment_distance(point,a,b):
    dx,dy=b[0]-a[0],b[1]-a[1]
    length=dx*dx+dy*dy
    t=max(0,min(1,((point[0]-a[0])*dx+(point[1]-a[1])*dy)/length)) if length else 0
    return math.dist(point,(a[0]+t*dx,a[1]+t*dy))


def generate_sites(conn, terrain=None, rng=None, sprite_scale=1, label_size_provider=None):
    from monster_sites import ensure_schema, sites
    from terrain_journeys import features
    ensure_schema(conn)
    rng=rng or random
    columns={r[1] for r in conn.execute('PRAGMA table_info(cities)')}
    hidden='COALESCE(is_undead,0)' if 'is_undead' in columns else '0'
    rows=conn.execute(f'SELECT id,name,faction,coordinates,{hidden} FROM cities').fetchall()
    size=city_sprite_size(sprite_scale)/max(.01,sprite_scale)
    cities={r[0]:tuple(ast.literal_eval(r[3])) for r in rows}
    centers={cid:(x+size/2,y+size*30/77) for cid,(x,y) in cities.items()}
    bounds=(42,42,1158,758)
    view=TerrainView(terrain) if terrain else None
    roads=list(conn.execute('SELECT city1,city2 FROM roads'))
    network=build_transport_network(cities,roads,{},(30,30,1170,770),terrain=view)
    road_segments=[(a,b) for _,_,path in network.land+network.bridges
                   for a,b in zip(path,path[1:])]
    city_rects={cid:(x-5,y-5,x+size+5,y+size+5) for cid,(x,y) in cities.items()}
    label_rects={}
    if label_size_provider:
        for cid,name,owner,*_ in rows:
            w,h=label_size_provider(f'{name}({owner})')
            x,y=cities[cid]
            w,h=w/max(.01,sprite_scale),h/max(.01,sprite_scale)
            label_rects[cid]=(x+(size-w)/2-5,y-h-24,x+(size+w)/2+5,y-3)
    occupied=[feature_rect(s['x'],s['y']) for s in features(conn)]
    candidates=[(x,y) for x in range(70,1140,25) for y in range(75,740,25)]
    rng.shuffle(candidates)
    # Long city names can cover most of a phone's world-space map. Prefer
    # their free areas, while keeping sprite clearance a hard constraint.
    candidates.sort(key=lambda p:sum(not separated((p[0]-60,p[1]-35,p[0]+60,p[1]+72),r)
                                     for r in label_rects.values()))
    selected=[]
    parents=[r[0] for r in rows if not r[4]]
    for x,y in candidates:
        # Hard clearance covers the actual 72px sprite. Captions are ranked
        # separately so long names cannot forbid every clearing on the map.
        rect=feature_rect(x,y,72)
        if not all(separated(rect,r) for r in list(city_rects.values())+occupied):
            continue
        if any(_segment_distance((x,y),a,b)<24 for a,b in road_segments):
            continue
        if terrain and not all(terrain.is_land(x+dx,y+dy,clearance=3)
                               for dx,dy in ((0,0),(-23,-12),(23,-12),(0,20))):
            continue
        for parent in sorted(parents,key=lambda cid:math.dist(centers[cid],(x,y))):
            start=centers[parent]
            distance=math.dist(start,(x,y))
            if not 85<=distance<=280:
                continue
            obstacles=[r for cid,r in city_rects.items() if cid!=parent]+occupied
            path=_bend(start,(x,y),rng.choice((-9,9)))
            if not _clear(path,obstacles,bounds,view):
                continue
            if any(_intersects(a,b,c,d) for a,b in zip(path,path[1:])
                   if math.dist(a,start)>size*.7 for c,d in road_segments):
                continue
            selected.append((parent,x,y,path))
            occupied.append(rect)
            road_segments.extend(zip(path,path[1:]))
            break
        if len(selected)==7:
            break
    if len(selected)<6:
        raise FeaturePlacementError(f'Не хватает свободных тупиковых дорог для логов монстров: найдено {len(selected)} из 6.')
    tiers=rng.sample(list(range(1,7)),len(selected)-1)+[7]
    rng.shuffle(tiers)
    conn.execute('DELETE FROM monster_sites')
    conn.execute('DELETE FROM monster_progress')
    conn.execute('DELETE FROM monster_expeditions')
    conn.execute('DELETE FROM monster_artifact_upgrades')
    conn.execute('DELETE FROM monster_training_ranks')
    for tier,(parent,x,y,path) in zip(tiers,selected):
        conn.execute('INSERT INTO monster_sites(parent_city,tier,x,y,road,ready_turn,variant) VALUES(?,?,?,?,?,0,?)',
                     (parent,tier,x,y,json.dumps(path),rng.randint(1,5)))
    conn.commit()
    return sites(conn)
