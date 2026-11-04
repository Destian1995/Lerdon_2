"""Player marches follow the visible transport network before applying transfers."""
import ast
import bisect
import math
import random
import sys
import sqlite3
from dataclasses import dataclass

from utils.movement_rules import army_size_level, movement_city_route


@dataclass
class MarchRoute:
    points: list
    land: list

    def __post_init__(self):
        self.lengths = [0.]
        for a, b in zip(self.points, self.points[1:]):
            self.lengths.append(self.lengths[-1] + math.dist(a, b))
        self.length = self.lengths[-1]

    def sample(self, progress):
        distance = max(0., min(1., progress)) * self.length
        i = min(len(self.points) - 2, max(0, bisect.bisect_right(self.lengths, distance) - 1))
        a, b = self.points[i:i + 2]
        length = max(1e-9, self.lengths[i + 1] - self.lengths[i])
        t = (distance - self.lengths[i]) / length
        dx, dy = (b[0] - a[0]) / length, (b[1] - a[1]) / length
        return a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, dx, dy, self.land[i]


def rendered_route(network, cities, centers):
    """Stitch real road/bridge/ferry runs, including reverse travel and chains."""
    points, modes = [], []
    for source, target in zip(cities, cities[1:]):
        pieces = [(list(path), dry) for paths, dry in
                  ((network.land, True), (network.bridges, True), (network.sea, False))
                  for a, b, path in paths if {a, b} == {source, target} and len(path) >= 2]
        if not pieces:
            return None
        current = centers[source]
        first_piece = True
        while pieces:
            index, reverse = min(((i, rev) for i in range(len(pieces)) for rev in (False, True)),
                                 key=lambda pair: math.dist(current, pieces[pair[0]][0][-1 if pair[1] else 0]))
            path, dry = pieces.pop(index)
            if reverse:
                path.reverse()
            if not first_piece and math.dist(current, path[0]) > .1:
                return None
            if points and math.dist(points[-1], path[0]) > .1:
                return None
            if not points:
                points.append(path[0])
            for point in path[1:]:
                if math.dist(points[-1], point) > 1e-6:
                    points.append(point)
                    modes.append(dry)
            current, first_piece = path[-1], False
    return MarchRoute(points, modes) if len(points) >= 2 else None


def _screen(owner):
    screen = getattr(sys.modules.get('game_process'), '_active_game_screen', None)
    return screen if screen and getattr(screen, 'conn', None) is owner.conn else None


def rendered_leg(network, chain, centers, start=None, end=None):
    """Crop by road-edge fractions, independent of viewport and detours."""
    start = start or (0,0)
    end = end or (len(chain)-2,1)
    points, modes = [], []
    for i in range(start[0],end[0]+1):
        route = rendered_route(network,chain[i:i+2],centers)
        if route is None:
            return None
        low = start[1] if i == start[0] else 0
        high = end[1] if i == end[0] else 1
        for j,(a,b) in enumerate(zip(route.points,route.points[1:])):
            left,right = max(route.lengths[j],low*route.length), min(route.lengths[j+1],high*route.length)
            if right-left <= 1e-6:
                continue
            first = route.sample(left/route.length)[:2]
            last = route.sample(right/route.length)[:2]
            if not points:
                points.append(first)
            points.append(last)
            modes.append(route.land[j])
    return MarchRoute(points,modes) if len(points)>1 else None


def movement_busy(owner):
    return bool(getattr(_screen(owner), '_troop_movement_busy', False))


def deferred_ai_captures(conn):
    from types import SimpleNamespace
    return set(getattr(_screen(SimpleNamespace(conn=conn)), '_ai_march_destinations', ()))


def queue_ai_march(conn, faction, source, destination, units):
    """Record a committed AI move; no graphics are touched by the AI thread."""
    from types import SimpleNamespace
    screen = _screen(SimpleNamespace(conn=conn))
    if screen is None or source == destination:
        return
    chain = movement_city_route(conn, source, destination, faction)
    if len(chain) < 2:
        return
    count = sum(unit['unit_count'] for unit in units)
    if count <= 0:
        return
    queue_route_march(conn,faction,chain,destination,count,has_hero=marching_hero(conn,units))


def marching_hero(conn,units):
    """Inspect only departing stacks, never heroes left behind in the city."""
    for unit in units:
        if unit.get('unit_count',0)<=0:
            continue
        stats=unit.get('units_stats') or {}
        value=stats.get('Класс юнита',unit.get('unit_class'))
        if value is None and unit.get('unit_name'):
            try:
                row=conn.execute('SELECT unit_class FROM units WHERE unit_name=? LIMIT 1',
                                  (unit['unit_name'],)).fetchone()
                value=row[0] if row else None
            except sqlite3.OperationalError:
                value=None
        parts=str(value or '').split()
        if parts and parts[0] in ('2','3','4'):
            return True
    return False


def queue_route_march(conn, faction, chain, destination, count, start=None, end=None, camp='', capture=True,has_hero=False):
    from types import SimpleNamespace
    screen = _screen(SimpleNamespace(conn=conn))
    if screen is None or count <= 0:
        return
    total = conn.execute('''SELECT COALESCE(SUM(g.unit_count),0) FROM garrisons g
        JOIN units u ON u.unit_name=g.unit_name WHERE u.faction=?''', (faction,)).fetchone()[0]
    if not hasattr(screen, '_ai_march_queue'):
        screen._ai_march_queue = []
    if not hasattr(screen, '_ai_march_destinations'):
        screen._ai_march_destinations = set()
    if capture:
        screen._ai_march_destinations.add((destination, faction))
    if not hasattr(screen,'_terrain_moving_camps'):
        screen._terrain_moving_camps = set()
    if camp:
        screen._terrain_moving_camps.add(camp)
    screen._ai_march_queue.append((tuple(chain), faction, count, max(total,count), destination,
                                   tuple(start) if start else None,tuple(end) if end else None,camp,capture,bool(has_hero)))


def play_ai_marches(screen):
    """Replay AI routes once the turn overlay has left the map."""
    pending = getattr(screen, '_ai_march_queue', [])
    screen._ai_march_queue = []
    if not pending:
        from terrain_encounter_ui import show_pending
        show_pending(screen)
        return
    if not screen.parent:
        screen._ai_march_destinations.clear()
        getattr(screen,'_terrain_moving_camps',set()).clear()
        return
    map_widget = next((w for w in screen.parent.children
                       if getattr(w, '_map_atmosphere', None) is not None), None)
    if map_widget is None:
        screen._ai_march_destinations.clear()
        getattr(screen,'_terrain_moving_camps',set()).clear()
        return
    from map_terrain import city_sprite_size
    coords = {cid: ast.literal_eval(raw) for cid, raw in screen.conn.execute('SELECT id,coordinates FROM cities')}
    grouped = {}
    for chain, faction, count, total, destination, start, end, camp, capture, has_hero in pending:
        key = (chain, faction, destination, start, end, camp, capture)
        previous = grouped.get(key, (0, total,False))
        grouped[key] = (previous[0] + count, max(previous[1], total),previous[2] or has_hero)
    refresh_military_presence(screen,map_widget)
    remaining = [len(grouped)]
    end_turn = getattr(screen, 'end_turn_button', None)
    was_disabled = end_turn.disabled if end_turn else False
    screen._troop_movement_busy = True
    if end_turn:
        end_turn.disabled = True
    for (chain, faction, destination, start, end, camp, capture), (count, total,has_hero) in grouped.items():
        def provider(chain=chain, start=start, end=end):
            if chain[0]=='@monster':
                import json
                path=json.loads(chain[1])
                path=path+list(reversed(path[:-1]))
                projected=[(map_widget.map_pos[0]+x*map_widget.map_scale,
                            map_widget.map_pos[1]+y*map_widget.map_scale) for x,y in path]
                return MarchRoute(projected,[True]*(len(projected)-1))
            size = city_sprite_size(map_widget.map_scale)
            centers = {cid: (map_widget.map_pos[0] + x * map_widget.map_scale + size / 2,
                             map_widget.map_pos[1] + y * map_widget.map_scale + size * 30 / 77)
                       for cid, (x, y) in coords.items()}
            return rendered_leg(map_widget._road_geometry, chain, centers, start, end)
        def arrive(destination=destination, faction=faction, camp=camp, capture=capture, completed=[False]):
            if completed[0]:
                return
            completed[0] = True
            if capture:
                screen._ai_march_destinations.discard((destination, faction))
                map_widget._map_atmosphere.city_effects.release_capture(destination, faction)
            screen._terrain_moving_camps.discard(camp)
            if hasattr(map_widget,'draw_terrain_features'):
                map_widget.draw_terrain_features()
            remaining[0] -= 1
            if remaining[0] == 0:
                screen._troop_movement_busy = False
                if end_turn:
                    end_turn.disabled = was_disabled
                from terrain_encounter_ui import show_pending
                show_pending(screen)
        if provider() is not None:
            spec = (provider, max(1, army_size_level(total, count)), faction, count,has_hero)
            map_widget._map_atmosphere.marches.play_batch([spec], arrive, arrive)
        else:
            arrive()


def close_transfer_windows(owner):
    """Hide both selection and city windows as soon as a march is accepted."""
    popup=getattr(owner,'current_popup',None)
    if popup is not None:
        popup.dismiss()
        owner.current_popup=None
    owner.dismiss()


def refresh_military_presence(screen,map_widget):
    """Refresh the map's flags and military badges in the departure frame."""
    if not screen.parent or (hasattr(map_widget,'parent') and map_widget.parent is None):return
    screen._prev_star_levels=None
    update=getattr(screen,'update_army_rating',None)
    if update:update()
    sync=getattr(map_widget,'_sync_map_atmosphere',None)
    if sync:sync()


def animate_transfer(owner, grouped):
    screen = _screen(owner)
    if not screen or not screen.parent:
        return False  # Headless callers retain the ordinary validated transfer.
    map_widget = next((widget for widget in screen.parent.children
                       if getattr(widget, '_map_atmosphere', None) is not None), None)
    if map_widget is None:
        return False
    conn, faction = owner.conn, owner.player_fraction
    from map_terrain import city_sprite_size
    city_coords = {cid: ast.literal_eval(raw) for cid, raw in conn.execute('SELECT id,coordinates FROM cities')}
    total = conn.execute('''SELECT COALESCE(SUM(g.unit_count*u.consumption),0)
        FROM garrisons g JOIN units u ON u.unit_name=g.unit_name WHERE u.faction=?''', (faction,)).fetchone()[0]
    network = map_widget._road_geometry
    visible = {tuple(sorted((a, b))) for paths in (network.land, network.bridges, network.sea)
               for a, b, _ in paths}
    specs = []
    for source, units in grouped.items():
        chain = movement_city_route(conn, source, owner.city_name, faction, visible)

        def provider(chain=chain):
            size = city_sprite_size(map_widget.map_scale)
            centers = {cid: (map_widget.map_pos[0] + x * map_widget.map_scale + size / 2,
                             map_widget.map_pos[1] + y * map_widget.map_scale + size * 30 / 77)
                       for cid, (x, y) in city_coords.items()}
            return rendered_route(map_widget._road_geometry, chain, centers)

        route = provider()
        if route is None:
            raise ValueError(f'Не удалось построить маршрут по дорогам из {source} в {owner.city_name}.')
        weight, count = 0, 0
        for name, amount in units.items():
            row = conn.execute('''SELECT g.unit_count,u.consumption FROM garrisons g
                JOIN units u ON u.unit_name=g.unit_name WHERE g.city_name=? AND g.unit_name=?''',
                               (source, name)).fetchone()
            if not row or amount <= 0 or amount > row[0]:
                raise ValueError(f'Недостаточно войск в городе {source}.')
            weight += amount * (row[1] or 0)
            count += amount
        has_hero=marching_hero(conn,[dict(unit_name=name,unit_count=amount) for name,amount in units.items()])
        specs.append((provider, max(1, army_size_level(total, weight)), faction, count,has_hero))

    selected = [dict(unit) for unit in owner.selected_group]
    departures={(source,name):count for source,units in grouped.items() for name,count in units.items()}
    end_turn = getattr(screen, 'end_turn_button', None)
    was_disabled = end_turn.disabled if end_turn else False
    screen._troop_movement_busy = True
    if end_turn:
        end_turn.disabled = True
    finished = False

    def release():
        screen._march_departures={}
        screen._troop_movement_busy = False
        if end_turn:
            end_turn.disabled = was_disabled
        refresh_military_presence(screen,map_widget)

    def arrive():
        nonlocal finished
        if finished:
            return
        finished = True
        screen._march_departures={}
        owner.selected_group = selected
        owner._movement_arrived = True
        try:
            owner.move_selected_group_to_city()
        finally:
            owner._movement_arrived = False
            release()

    def cancel():
        nonlocal finished
        if not finished:
            finished = True
            owner.selected_group.clear()
            release()

    try:
        screen._march_departures=departures
        map_widget._map_atmosphere.marches.play_batch(specs, arrive, cancel)
        refresh_military_presence(screen,map_widget)
        close_transfer_windows(owner)
    except Exception:
        map_widget._map_atmosphere.marches.cancel_all()
        cancel()
        raise
    return True


class MarchLayer:
    """Fixed particle pools, updated by the atmosphere's existing single clock."""
    def __init__(self, atmosphere):
        from kivy.graphics import InstructionGroup
        self.atmosphere = atmosphere
        self.group = InstructionGroup()
        self.marches = []
        from terrain_arrival_effects import TerrainArrivalEffects
        self.terrain_arrivals=TerrainArrivalEffects(atmosphere)
        self.group.add(self.terrain_arrivals.group)

    def play_batch(self, specs, arrive, cancel):
        batch = dict(remaining=len(specs), arrive=arrive, cancel=cancel, done=False)
        for provider, level, faction, count, *extra in specs:
            march = March(self, provider, level, faction, count, batch,has_hero=bool(extra and extra[0]))
            self.marches.append(march)
            self.group.add(march.group)

    def update(self, dt):
        for march in list(self.marches):
            if march.update(dt) and march in self.marches:
                self.group.remove(march.group)
                self.marches.remove(march)
        self.terrain_arrivals.update(dt)

    def cancel_all(self):
        for march in self.marches:
            batch = march.batch
            if not batch['done']:
                batch['done'] = True
                batch['cancel']()
        self.marches.clear()
        self.group.clear()
        self.terrain_arrivals.clear()
        self.group.add(self.terrain_arrivals.group)


class MarchFlag:
    """A small cloth standard on the existing march clock, with faction art."""
    def __init__(self,group,faction):
        from kivy.graphics import Color,InstructionGroup,Line,Mesh,Ellipse
        from map_city_effects import faction_emblem,FACTION_RGB
        self.group=InstructionGroup()
        group.add(self.group)
        self.colors=[]
        def color(*rgba):
            c=Color(*rgba);self.colors.append((c,rgba[3]));self.group.add(c)
        color(.03,.025,.02,.9)
        self.pole_shadow=Line(width=2.2);self.group.add(self.pole_shadow)
        color(.96,.78,.43,1)
        self.pole=Line(width=1.1);self.group.add(self.pole)
        self.finial=Ellipse();self.group.add(self.finial)
        rgb=FACTION_RGB.get(faction,(.8,.75,.6))
        color(*(v*.34+.025 for v in rgb),1)
        self.cloth=Mesh(vertices=[0.]*72,indices=[v for i in range(8) for v in
                          (2*i,2*i+1,2*i+2,2*i+1,2*i+3,2*i+2)],mode='triangles')
        self.group.add(self.cloth)
        color(1,1,1,1)
        self.emblem=Mesh(texture=faction_emblem(faction),vertices=[0.]*56,
                         indices=list(range(14)),mode='triangle_strip')
        self.group.add(self.emblem)
        color(.98,.8,.44,1)
        self.edge=Line(width=.8);self.group.add(self.edge)

    def update(self,x,y,scale,time,visible,bounds=None):
        for color,alpha in self.colors:
            color.a=alpha if visible else 0
        width,height=36*scale,24*scale
        left,top=x+9*scale,y+49*scale
        if bounds:
            bx,by,bw,bh=bounds
            left=max(bx+3,min(left,bx+bw-width-3))
            top=min(top,by+bh-4)
        def point(u,v):
            ripple=(math.sin(time*5-u*6)*2.4+math.sin(time*7-u*9)*.6)*u*scale
            return left+u*width,top+ripple-v*height-u*scale
        self.pole.points=self.pole_shadow.points=(left,y+3*scale,left,top+4*scale)
        self.finial.pos,self.finial.size=(left-1.8*scale,top+3*scale),(3.6*scale,3.6*scale)
        vertices=[];upper=[];lower=[]
        for i in range(9):
            u=i/8;a,b=point(u,0),point(u,1)
            vertices.extend((*a,0,0,*b,0,0));upper.append(a);lower.append(b)
        self.cloth.vertices=vertices
        self.edge.points=[v for p in (*upper,*reversed(lower),upper[0]) for v in p]
        uv=self.emblem.texture.tex_coords
        vertices=[]
        for i in range(7):
            u=i/6;tx=uv[0]+(uv[2]-uv[0])*u
            for v,ty in ((.12,uv[5]),(.88,uv[1])):
                vertices.extend((*point(.15+u*.7,v),tx,ty))
        self.emblem.vertices=vertices


class March:
    def __init__(self, layer, provider, level, faction, count, batch,has_hero=False):
        from kivy.graphics import Color, Ellipse, InstructionGroup, Line, Rectangle
        from map_city_effects import faction_emblem
        self.layer, self.provider, self.level, self.batch = layer, provider, level, batch
        self.route = provider()
        self.geometry_key = None
        self.age, self.arrived, self.emit = 0., False, 0.
        a=layer.atmosphere
        self._terrain_previous=((self.route.points[0][0]-a._origin[0])/a._scale,
                                (self.route.points[0][1]-a._origin[1])/a._scale)
        from terrain_placement import FEATURE_SIZE
        self._terrain_seen={key for key,site in layer.terrain_arrivals.sites.items()
                            if math.dist(self._terrain_previous,(site['x'],site['y']))<=FEATURE_SIZE*.35}
        self.duration = max(1.8, min(5., self.route.length / max(1, 85 * layer.atmosphere._scale)))
        self.group = InstructionGroup()
        self.rng = random.Random(faction + str(count) + str(self.route.points[0]))
        self.dust = []
        for _ in range((12, 24, 40)[level - 1]):
            color, shape = Color(.64, .56, .43, 0), Rectangle(texture=layer.atmosphere.mist_texture())
            self.group.add(color)
            self.group.add(shape)
            self.dust.append(dict(color=color, shape=shape, age=2., life=1., pos=(0, 0), drift=(0, 0)))
        self.marker_color, self.marker = Color(.05, .07, .10, 1), Ellipse()
        self.outline_color, self.outline = Color(.98, .8, .44, 1), Line(width=1.)
        self.emblem_color, self.emblem = Color(1, 1, 1, 1), Rectangle(texture=faction_emblem(faction))
        for instruction in (self.marker_color, self.marker, self.outline_color, self.outline,
                            self.emblem_color, self.emblem):
            self.group.add(instruction)
        self.hero_flag=MarchFlag(self.group,faction) if has_hero else None

    def update(self, dt):
        self.age += dt
        atmosphere = self.layer.atmosphere
        # Reproject onto the rebuilt visible roads after a resize.
        key = (atmosphere._bounds, atmosphere._scale)
        if key != self.geometry_key:
            self.route = self.provider() or self.route
            self.geometry_key = key
        progress = min(1., self.age / self.duration)
        x, y, dx, dy, dry = self.route.sample(progress)
        point=((x-atmosphere._origin[0])/atmosphere._scale,(y-atmosphere._origin[1])/atmosphere._scale)
        if not self.arrived and dry:
            from terrain_arrival_effects import reaches_site
            from terrain_placement import FEATURE_SIZE
            for key,site in self.layer.terrain_arrivals.sites.items():
                if key not in self._terrain_seen and reaches_site(self._terrain_previous,point,(site['x'],site['y']),FEATURE_SIZE*.35):
                    self._terrain_seen.add(key)
                    self.layer.terrain_arrivals.enter(site)
        self._terrain_previous=point
        size = min(1.15, max(.75, atmosphere._scale))
        if not self.arrived and progress >= 1:
            self.arrived = True
            self.batch['remaining'] -= 1
            if self.batch['remaining'] == 0 and not self.batch['done']:
                self.batch['done'] = True
                self.batch['arrive']()
        for color in (self.marker_color, self.outline_color, self.emblem_color):
            color.a = 0 if self.arrived else 1
        self.marker.pos, self.marker.size = (x - 11 * size, y - 11 * size), (22 * size, 22 * size)
        self.outline.circle = (x, y, 11 * size)
        self.emblem.pos, self.emblem.size = (x - 8 * size, y - 8 * size), (16 * size, 16 * size)
        if self.hero_flag:
            self.hero_flag.update(x,y,size,self.age,not self.arrived,atmosphere._bounds)
        self.emit += dt
        interval = 1 / (8, 16, 26)[self.level - 1]
        while self.emit >= interval:
            self.emit -= interval
            if not self.arrived and dry and progress > .02:
                particle = next((p for p in self.dust if p['age'] >= p['life']), None)
                if particle:
                    lateral = self.rng.uniform(-3, 3) * size
                    px, py = x - dx * 10 * size - dy * lateral, y - dy * 10 * size + dx * lateral
                    particle.update(age=0., life=self.rng.uniform(.55, .85),
                        pos=((px - atmosphere._origin[0]) / atmosphere._scale,
                             (py - atmosphere._origin[1]) / atmosphere._scale),
                        drift=(self.rng.uniform(-4, 4) - dx * 3, self.rng.uniform(-3, 3) - dy * 3))
        for p in self.dust:
            p['age'] += dt
            u = min(1., p['age'] / p['life'])
            width = (9 + self.level * 4 + u * 16) * size
            px = atmosphere._origin[0] + p['pos'][0] * atmosphere._scale + p['drift'][0] * u
            py = atmosphere._origin[1] + p['pos'][1] * atmosphere._scale + p['drift'][1] * u
            height = width * .65
            p['shape'].pos, p['shape'].size = (px - width / 2, py - height / 2), (width, height)
            p['color'].a = math.sin(math.pi * u) * (.32, .50, .72)[self.level - 1]
        return self.arrived and all(p['age'] >= p['life'] for p in self.dust)
