"""City smoke and capture celebrations, driven by MapAtmosphere's single clock."""
import math
import random
import sqlite3
from functools import lru_cache

from kivy.core.image import Image as CoreImage
from kivy.core.text import Label as CoreLabel
from kivy.core.window import Window
from kivy.graphics import (Canvas, Color, Ellipse, InstructionGroup, Line, Mesh, Rectangle,
                           StencilPush, StencilUse, StencilUnUse, StencilPop)

from city_war import SMOKE_TURNS
from kivy.uix.modalview import ModalView


FACTION_RGB = {
    'Север': (0.32, 0.68, 1.0), 'Эльфы': (0.25, 0.95, 0.48),
    'Вампиры': (0.78, 0.32, 0.94), 'Адепты': (1.0, 0.61, 0.20),
    'Элины': (1.0, 0.87, 0.25), 'Нежить': (0.42, 0.72, 0.88),
    'Мятежники': (0.96, 0.35, 0.20),
}

FACTION_EMBLEMS = {
    'Север': 'people', 'Эльфы': 'elfs', 'Вампиры': 'vampires',
    'Адепты': 'adepts', 'Элины': 'poly', 'Нежить': 'skull', 'Мятежники': 'keig',
}


@lru_cache(maxsize=16)
def faction_emblem(faction):
    source = f"files/status/army_in_city/standards/{FACTION_EMBLEMS.get(faction, 'default')}.png"
    return CoreImage(source, mipmap=True).texture


def standard_layout(center, scale, slot=0, bounds=None, unknown=False):
    """Screen geometry above the existing 68×28 garrison badge, at every zoom."""
    from map_terrain import city_sprite_size
    ui_scale = min(1.15, max(.85, scale))
    width, height = 48 * ui_scale, 32 * ui_scale
    # The legacy badge uses a fixed 77-pixel city box, even on small maps.
    cx = center[0] + (77 - city_sprite_size(scale)) / 2
    badge_top = center[1] + 77 - city_sprite_size(scale) / 2 + 30
    x, y = cx - width / 2 + slot * (width + 6), badge_top + 5
    if unknown:y=badge_top-28
    if bounds:
        left, bottom, map_width, map_height = bounds
        ceiling = bottom + map_height - 6
        if y + height + 4 > ceiling:
            # Edge cities get their standard beside the badge, within the frame.
            x = cx - 34 - width - 7 - slot * (width + 6)
            if x < left + 6:
                x = cx + 34 + 7 + slot * (width + 6)
            y = min(badge_top - 26, ceiling - height - 4)
        x = max(left + 6, min(x, left + map_width - width - 6))
        y = max(bottom + 6, y)
    return x, y, width, height


def read_hero_garrisons(conn):
    """Only living heroes, grouped by city and their own faction, not city owner."""
    try:
        from utils.garrison_presence import military_presence
        return military_presence(conn)['heroes']
    except sqlite3.OperationalError:
        return ()


class CityEffects:
    def __init__(self, atmosphere):
        self.atmosphere = atmosphere
        self.group = InstructionGroup()
        self.smoke_group = InstructionGroup()
        self.battle_group = InstructionGroup()
        self.flag_group = InstructionGroup()
        self.group.add(self.smoke_group)
        self.group.add(self.battle_group)
        self.group.add(self.flag_group)
        self.portal_group=InstructionGroup()
        self.group.add(self.portal_group)
        self.portal_shields=[]
        self._portal_key=None
        self._standard_host = None
        self._standard_canvas = None
        self._seen = None
        self._owners = {}
        self._cities = {}
        self._smoke_key = None
        self.smoke = []
        self.battle_clouds = []
        self.flags = []
        self._battle_key = self._flag_key = None
        self.captures = []
        self._deferred_captures = {}
        self.time = 0.0
        self.capture_time = 0.0

    def release_capture(self, city, faction):
        kind = self._deferred_captures.pop((city, faction), None)
        current = self._cities.get(city)
        if kind and current and current[2] == faction:
            self.play(city, kind, faction)

    def _sprite(self, group, rgb, alpha=0):
        color = Color(*rgb, alpha)
        shape = Rectangle(texture=self.atmosphere.mist_texture())
        group.add(color)
        group.add(shape)
        return color, shape

    def attach_standards(self, host):
        """Draw flags above military symbols, beneath interactive panels.

        The military overlay lives in another widget above the map. Its canvas
        before contains badges/ideology icons; children contain UI windows.
        Keep the flag instructions between those two, using the map's clock.
        """
        if host is self._standard_host:
            return
        if self._standard_host is not None:
            self._standard_host.canvas.remove(self._standard_canvas)
            self._standard_canvas.remove(self.flag_group)
        elif host is not None:
            self.group.remove(self.flag_group)
        self._standard_host = host
        if host is None:
            self.group.add(self.flag_group)
            return
        if self._standard_canvas is None:
            self._standard_canvas = Canvas()
            with self._standard_canvas:
                StencilPush()
                self._standard_mask = Rectangle()
                StencilUse()
            with self._standard_canvas:
                self._standard_end = StencilUnUse()
                self._standard_unmask = Rectangle()
                StencilPop()
        self._standard_canvas.insert(self._standard_canvas.children.index(self._standard_end), self.flag_group)
        # Existing panels and canvas.after remain above flags. New child panels
        # naturally append above this canvas as well.
        after = host.canvas.after
        indices = [host.canvas.children.index(after)]
        indices.extend(host.canvas.children.index(child.canvas) for child in host.children
                       if child.canvas in host.canvas.children)
        host.canvas.insert(min(indices), self._standard_canvas)
        self._fit_standard_mask()

    def _fit_standard_mask(self):
        if self._standard_canvas is not None and self.atmosphere._bounds:
            x, y, width, height = self.atmosphere._bounds
            for mask in (self._standard_mask, self._standard_unmask):
                mask.pos, mask.size = (x, y), (width, height)

    def sync(self, cities, states, turn, heroes=(), deferred=(), portals=(), unknown=()):
        self._unknown_flags=set(unknown)
        """Baseline saved events on first view; redraws never replay celebrations."""
        self._cities = {name: (x, y, faction) for name, x, y, faction in cities}
        revisions = {name: state.revision for name, state in states.items()}
        if self._seen is not None:
            for name, (x, y, faction) in self._cities.items():
                state = states.get(name)
                changed = name in self._owners and self._owners[name] != faction
                new_event = state and state.revision != self._seen.get(name, 0)
                if new_event and state.turn == turn:
                    if (name, faction) in deferred:
                        self._deferred_captures[name, faction] = state.kind
                    else:
                        self.play(name, state.kind, faction)
                elif changed:
                    if (name, faction) in deferred:
                        self._deferred_captures[name, faction] = 'peace'
                    else:
                        self.play(name, 'peace', faction)
        self._seen = revisions
        self._owners = {name: value[2] for name, value in self._cities.items()}
        self._sync_flags(heroes)
        key=tuple(sorted(portals))
        if key!=self._portal_key:
            self._portal_key=key;self.portal_group.clear();self.portal_shields=[]
            for city,faction in key:
                from portal_dome import PortalDome
                dome=PortalDome()
                self.portal_group.add(dome.group)
                self.portal_shields.append((city,dome))
            self.atmosphere.refresh_frame_rate()
        # smoke_until is written only by real combat. Peaceful transfers retain
        # the previous deadline, so neither start nor prolong battle effects.
        burning = tuple(sorted(name for name, state in states.items()
                               if name in self._cities and state.smoke_until >= 0
                               and 0 <= state.smoke_until - turn <= SMOKE_TURNS))
        if burning != self._battle_key:
            self._battle_key = burning
            self.battle_group.clear()
            self.battle_clouds = []
            for name in burning:
                rng = random.Random('battle-smoke:' + name)
                halo = self._sprite(self.battle_group, (.96, .62, .32))
                core = self._sprite(self.battle_group, (1, .91, .72))
                ring_color, ring = Color(.95, .77, .52, 0), Line(width=.65)
                self.battle_group.add(ring_color)
                self.battle_group.add(ring)
                self.battle_clouds.append(dict(city=name, rng=rng, halo=halo, core=core,
                    ring=(ring_color, ring), wait=rng.uniform(.7, 2.6), age=1.,
                    duration=.48, offset=(0, 28), intensity=0.))
        smoking = [(name, state.ruined, state.smoke_until)
                   for name, state in states.items()
                   if name in self._cities and (state.ruined or turn <= state.smoke_until)]
        key = (tuple(sorted(smoking)), tuple(sorted(self._cities.items())), turn,
               self.atmosphere._bounds)
        if key == self._smoke_key:
            return
        self._smoke_key = key
        self.smoke_group.clear()
        self.smoke = []
        for name, ruined, until in smoking:
            rng = random.Random(name)
            density = 0.65 if turn < until else 0.48
            if ruined and turn > until:
                density = 0.25
            for i in range(15 if ruined else 12):
                rgb = (0.14, 0.15, 0.16) if i % 3 else (0.32, 0.33, 0.34)
                color, shape = self._sprite(self.smoke_group, rgb)
                self.smoke.append(dict(city=name, phase=rng.random(),
                    speed=rng.uniform(0.12, 0.22), dx=rng.uniform(-15, 15),
                    width=rng.uniform(28, 42), rgb=rgb, color=color, shape=shape, alpha=density))

    def _sync_flags(self, heroes):
        key = tuple(sorted(set((city, faction or self._cities[city][2])
                               for city, faction in heroes if city in self._cities)))
        if key == self._flag_key:
            return
        self._flag_key = key
        self.flag_group.clear()
        self.flags = []
        slots = {}
        for city, faction in key:
            slot = slots.get(city, 0)
            slots[city] = slot + 1
            pole_shadow_color, pole_shadow = Color(.035, .025, .02, .9), Line(width=2.4)
            pole_color, pole = Color(.92, .73, .39, 1), Line(width=1.1)
            finial = Ellipse()
            rgb = FACTION_RGB.get(faction, (.8, .75, .6))
            cloth_rgb = (.035, .038, .045) if faction == 'Нежить' else tuple(value * .34 + .025 for value in rgb)
            cloth_color = Color(*cloth_rgb, 1)
            indices = [value for i in range(7) for value in
                       (i * 2, i * 2 + 1, i * 2 + 2, i * 2 + 1, i * 2 + 3, i * 2 + 2)]
            indices.extend((14, 16, 18, 14, 18, 15, 15, 18, 17))
            cloth = Mesh(vertices=[0.] * 76, indices=indices, mode='triangles')
            fold_color = Color(0, 0, 0, .14)
            folds = [Line(width=2) for _ in range(3)]
            texture = faction_emblem(faction)
            emblem_color = Color(1, 1, 1, 1)
            emblem = Mesh(texture=texture, vertices=[0.] * 56, indices=list(range(14)), mode='triangle_strip')
            edge_shadow_color, edge_shadow = Color(.03, .025, .02, .95), Line(width=2.2)
            edge_color, edge = Color(.98, .79, .42, 1), Line(width=.9)
            for instruction in (pole_shadow_color, pole_shadow, pole_color, pole, finial,
                                cloth_color, cloth, fold_color, *folds, emblem_color, emblem,
                                edge_shadow_color, edge_shadow, edge_color, edge):
                self.flag_group.add(instruction)
            self.flags.append(dict(city=city, faction=faction, slot=slot, pole=pole,
                                   pole_shadow=pole_shadow, finial=finial, folds=folds,
                                   cloth=cloth, edge=edge, edge_shadow=edge_shadow, emblem=emblem,
                                   phase=random.Random(city + faction).random() * math.tau))

    def _update_standards_and_bursts(self, scale, dt):
        self._fit_standard_mask()
        for flag in self.flags:
            center = self.atmosphere.project(self._cities[flag['city']][:2])
            x, y, width, height = standard_layout(center, scale, flag['slot'], self.atmosphere._bounds,
                unknown=(flag['city'],flag['faction']) in getattr(self,'_unknown_flags',set()))
            top = y + height

            def cloth_point(u, v):
                ripple = math.sin(self.time * 4.2 + flag['phase'] - u * 5.5) * 3.2 * u
                ripple += math.sin(self.time * 6 - u * 9 + flag['phase']) * .8 * u
                return x + u * width, top + ripple - u * 1.5 - v * height

            pole_points = (x, y - 9, x, top + 5)
            flag['pole'].points = flag['pole_shadow'].points = pole_points
            flag['finial'].pos, flag['finial'].size = (x - 2, top + 4), (4, 4)
            vertices, upper, lower = [], [], []
            for i in range(9):
                u = i / 8
                a, b = cloth_point(u, 0), cloth_point(u, 1)
                vertices.extend((*a, 0, 0, *b, 0, 0))
                upper.append(a)
                lower.append(b)
            notch = cloth_point(.85, .5)
            vertices.extend((*notch, 0, 0))
            flag['cloth'].vertices = vertices
            border = [value for point in (*upper, notch, *reversed(lower), upper[0]) for value in point]
            flag['edge'].points = flag['edge_shadow'].points = border
            for fold, u in zip(flag['folds'], (.22, .5, .78)):
                fold.points = [value for v in (0, .25, .5, .75, 1)
                               for value in cloth_point(u + math.sin(v * math.pi) * .025, v)]
            uv = flag['emblem'].texture.tex_coords
            emblem_vertices = []
            for i in range(7):
                u = i / 6
                tx = uv[0] + (uv[2] - uv[0]) * u
                for v, ty in ((.10, uv[5]), (.90, uv[1])):
                    emblem_vertices.extend((*cloth_point(.14 + u * .62, v), tx, ty))
            flag['emblem'].vertices = emblem_vertices
        for burst in self.battle_clouds:
            burst['wait'] -= dt
            if burst['wait'] <= 0:
                rng = burst['rng']
                burst['wait'] = rng.uniform(1.8, 4.)
                burst['age'] = 0.
                burst['offset'] = (rng.uniform(-12, 18), rng.uniform(20, 43))
            burst['age'] += dt
            u = min(1., burst['age'] / burst['duration'])
            # Quick ignition and a quiet afterglow, like the necropolis flashes.
            intensity = math.sin(math.pi * u) ** 2 * (1 - u)
            burst['intensity'] = intensity
            cx, cy = self.atmosphere.project(self._cities[burst['city']][:2])
            bx, by = cx + burst['offset'][0] * scale, cy + burst['offset'][1] * scale
            for (color, shape), width, alpha in ((burst['halo'], 46, .7), (burst['core'], 17, .8)):
                size = width * (1 + u * .4) * scale
                shape.pos, shape.size = (bx - size / 2, by - size / 2), (size, size)
                color.a = intensity * alpha
            color, ring = burst['ring']
            radius = (4 + u * 14) * scale
            ring.ellipse = (bx - radius, by - radius * .6, radius * 2, radius * 1.2)
            color.a = intensity * .22

    def play(self, city, kind, faction):
        if city not in self._cities:
            return
        # A large AI turn cannot accumulate unbounded particle groups.
        if len(self.captures) >= 8:
            expired = self.captures.pop(0)
            self.group.remove(expired['group'])
        rgb = FACTION_RGB.get(faction, (0.88, 0.82, 0.58))
        battle = kind in ('battle', 'battle_capture')
        group = InstructionGroup()
        self.group.add(group)
        glow_color, glow = self._sprite(group, (1, 0.52, 0.13) if battle else rgb)
        rings = []
        for i in range(3):
            color = Color(*(rgb if i != 1 else (1, 0.85, 0.42)), 0)
            line = Line(width=1.6)
            group.add(color)
            group.add(line)
            rings.append((color, line))
        particles = []
        rng = random.Random(city + kind + str(self.time))
        for i in range(28):
            shade = (1, 0.44 + rng.random() * 0.35, 0.12) if battle else (rgb if i % 3 else (1, 0.91, 0.58))
            color = Color(*shade, 0)
            shape = Ellipse(size=(3, 3))
            group.add(color)
            group.add(shape)
            particles.append((color, shape, rng.random() * math.tau, rng.uniform(0.65, 1.3), rng.random()))
        title = {'peace': f'{city} захвачен', 'battle_capture': f'{city} захвачен',
                 'battle': 'Битва завершена', 'rebuild': 'Город восстановлен'}.get(kind, 'Новый владелец')
        label = CoreLabel(text=title, font_size=14, bold=True, color=(1, 0.92, 0.72, 1),
                          outline_width=1, outline_color=(0.03, 0.04, 0.06, 1))
        label.refresh()
        text_color = Color(1, 1, 1, 0)
        text_shape = Rectangle(texture=label.texture, size=label.texture.size)
        group.add(text_color)
        group.add(text_shape)
        self.captures.append(dict(city=city, kind=kind, battle=battle, born=self.capture_time,
            group=group, glow=(glow_color, glow), rings=rings, particles=particles,
            text=(text_color, text_shape), duration=3.2 if battle else 3.8))

    def update(self, dt):
        self.time += dt
        for city,dome in self.portal_shields:
            center=self.atmosphere.project(self._cities[city][:2]) if city in self._cities else None
            dome.update(center,self.atmosphere._scale,self.time)
        # Battle reports/animations cover the map: show the celebration once visible.
        if not any(isinstance(widget, ModalView) for widget in Window.children):
            self.capture_time += dt
        scale = self.atmosphere._scale
        self._update_standards_and_bursts(scale, dt)
        flashes = {burst['city']: burst['intensity'] for burst in self.battle_clouds}
        for p in self.smoke:
            city = self._cities.get(p['city'])
            if city is None:
                continue
            cx, cy = self.atmosphere.project(city[:2])
            u = (self.time * p['speed'] + p['phase']) % 1
            size = (p['width'] + u * 30) * scale
            drift = (u * 22 + math.sin(self.time * 0.65 + p['phase'] * 6) * 7) * scale
            p['shape'].pos = (cx + p['dx'] * scale + drift - size / 2,
                              cy + 5 + u * 67 * scale - size / 2)
            p['shape'].size = (size, size * 0.85)
            p['color'].a = math.sin(math.pi * u) * p['alpha']
            flash = flashes.get(p['city'], 0.)
            p['color'].rgb = tuple(min(1., value + flash * tint)
                                   for value, tint in zip(p['rgb'], (.55, .36, .18)))
        for effect in list(self.captures):
            age = self.capture_time - effect['born']
            city = self._cities.get(effect['city'])
            if age >= effect['duration'] or city is None:
                self.group.remove(effect['group'])
                self.captures.remove(effect)
                continue
            u = age / effect['duration']
            fade = min(1, age * 4) * min(1, (1 - u) * 4)
            cx, cy = self.atmosphere.project(city[:2])
            color, shape = effect['glow']
            width = (100 + 50 * math.sin(math.pi * u)) * scale
            shape.pos, shape.size = (cx - width / 2, cy - 38 * scale), (width, 105 * scale)
            color.a = fade * (0.55 if effect['battle'] else 0.38)
            for i, (color, line) in enumerate(effect['rings']):
                phase = (u * 1.7 + i * 0.27) % 1
                radius = (20 + phase * 60) * scale
                line.ellipse = (cx - radius, cy - 20 * scale - radius * 0.32,
                                radius * 2, radius * 0.64)
                color.a = (1 - phase) * fade * 0.9
            for color, shape, angle, speed, phase in effect['particles']:
                if effect['battle']:
                    radius = (18 + age * speed * 26) * scale
                    px = cx + math.cos(angle) * radius
                    py = cy + math.sin(angle) * radius * 0.6 + age * 13 * scale
                else:
                    theta = angle + age * speed * 1.8
                    radius = (24 + phase * 22) * scale
                    px = cx + math.cos(theta) * radius
                    py = cy + math.sin(theta) * radius * 0.3 + u * 65 * scale
                size = (2 + math.sin(age * 5 + phase * 6) ** 2 * 2) * scale
                shape.pos, shape.size = (px, py), (size, size)
                color.a = fade * (0.55 + phase * 0.45)
            color, shape = effect['text']
            left, bottom, width, height = self.atmosphere._bounds
            shape.pos = (max(left, min(cx - shape.size[0] / 2, left + width - shape.size[0])),
                         min(cy + 57 + u * 14, bottom + height - shape.size[1]))
            color.a = fade
