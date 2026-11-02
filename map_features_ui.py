"""Terrain waypoints and saved waiting armies, projected onto visible roads."""
import ast


def draw_waypoints(widget):
    from kivy.graphics import Color, InstructionGroup, Rectangle,RoundedRectangle
    from kivy.core.text import Label as CoreLabel
    from map_terrain import city_sprite_size
    from troop_movement import rendered_route, _screen
    from types import SimpleNamespace
    from terrain_journeys import features, waiting_armies, NAMES
    from terrain_icons import icon_texture, icon_name, site_palette
    from terrain_placement import FEATURE_SIZE
    group = getattr(widget,'_terrain_features_group',None)
    if group is not None and group in widget.canvas.children:
        widget.canvas.remove(group)
    group = widget._terrain_features_group = InstructionGroup()
    widget.canvas.add(group)
    widget._terrain_feature_hits = []
    network = getattr(widget,'_road_geometry',None)
    if network is None:
        return
    size = city_sprite_size(widget.map_scale)
    centers = {cid: (widget.map_pos[0]+x*widget.map_scale+size/2,
                     widget.map_pos[1]+y*widget.map_scale+size*30/77)
               for cid,raw in widget.conn.execute('SELECT id,coordinates FROM cities')
               for x,y in [ast.literal_eval(raw)]}
    screen = _screen(SimpleNamespace(conn=widget.conn))
    moving = getattr(screen,'_terrain_moving_camps',set())
    camps = waiting_armies(widget.conn)
    def label(text,x,y,color,backing=False):
        core = CoreLabel(text=text,font_size=12,bold=True,color=color,
                         outline_width=1,outline_color=(.02,.03,.04,1))
        core.refresh()
        w,h = core.texture.size
        x = min(widget.map_pos[0]+widget.base_map_width*widget.map_scale-w-4,
                max(widget.map_pos[0]+4,x-w/2))
        if backing:
            group.add(Color(.025,.04,.035,.86))
            group.add(RoundedRectangle(pos=(x-4,y-2),size=(w+8,h+4),radius=[4]))
        group.add(Color(1,1,1,1))
        group.add(Rectangle(texture=core.texture,pos=(x,y),size=(w,h)))
    for site in features(widget.conn):
        palette=site['icon_palette']=site_palette(getattr(widget,'_map_terrain',None),site)
        route = rendered_route(network,[site['city1'],site['city2']],centers)
        if route is None:
            continue
        x,y,*_ = route.sample(site['fraction'])
        sprite_size = FEATURE_SIZE*widget.map_scale
        group.add(Color(1,1,1,1))
        group.add(Rectangle(texture=icon_texture(site['kind'],site['icon_variant'],palette),
                            pos=(x-sprite_size/2,y-sprite_size*.38),size=(sprite_size,sprite_size)))
        title='Болото' if site['kind']=='swamp' else icon_name(site['kind'],site['icon_variant'],palette)
        label(f"{title} · {site['delay']} х.",x,y+sprite_size*.64,(.94,.89,.67,1),backing=site['kind']=='swamp')
        waiting = [c for c in camps if c['feature']['id'] == site['id'] and c['camp'] not in moving]
        if waiting:
            total = sum(c['count'] for c in waiting)
            days = max(c['remaining'] for c in waiting)
            label(f"Войска: {total} · ещё {days} х.",x,y-sprite_size*.38-18,(.72,.88,1,1))
        widget._terrain_feature_hits.append((x,y,site,waiting))


def inspect_waypoint(widget, touch):
    for x,y,site,camps in getattr(widget,'_terrain_feature_hits',[]):
        if (touch.x-x)**2+(touch.y-y)**2 <= 32**2:
            from terrain_site_ui import open_terrain_site
            open_terrain_site(widget,site)
            return True
    return False
