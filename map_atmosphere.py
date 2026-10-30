"""Map-bound weather, undead storms and plague; one clock, reusable graphics."""

import math
import random

from kivy.clock import Clock
from kivy.core.text import Label as CoreLabel
from kivy.graphics import (
    Color, Ellipse, InstructionGroup, Line, Rectangle,
    StencilPop, StencilPush, StencilUnUse, StencilUse,
)
from kivy.graphics.texture import Texture
from kivy.uix.widget import Widget


def plague_routes(effects, sources, radius=200):
    """Choose a real nearby undead source for each city with recorded losses.

    Coordinates stay in game units; zoom cannot change eligibility. This draws
    an illustrative route, not a new infection rule or a road connection.
    """
    routes = []
    source_names = {source for source, sx, sy in sources}
    for name, losses, x, y in effects:
        if losses <= 0 or name in source_names:
            continue
        eligible = [(math.hypot(x - sx, y - sy), source, sx, sy)
                    for source, sx, sy in sources if source != name]
        if not eligible:
            continue
        distance, source, sx, sy = min(eligible)
        if distance <= radius:
            routes.append((source, name, (sx, sy), (x, y), losses))
    return routes


def stream_point(start, end, progress, bend=18):
    """A curved stream with fixed endpoints and a smooth transverse drift."""
    dx, dy = end[0] - start[0], end[1] - start[1]
    length = max(math.hypot(dx, dy), 0.001)
    offset = math.sin(math.pi * progress) * bend
    return (start[0] + dx * progress - dy / length * offset,
            start[1] + dy * progress + dx / length * offset)


class MapAtmosphere(Widget):
    """Transparent, non-interactive layer, clipped inside the map's frame."""

    _mist_texture = None

    def __init__(self, **kwargs):
        super().__init__(size_hint=(None, None), **kwargs)
        self._event = None
        self._time = 0.0
        self._bounds = None
        self._origin = (0, 0)
        self._scale = 1.0
        self._season = None
        self._weather = []
        self._storm_key = None
        self._storms = []
        self._plague_key = None
        self._plague_signature = None
        self._plague_seen = {}
        self._fog = []
        self._streams = []
        self._outbreaks = []
        self._rng = random.Random()
        with self.canvas:
            StencilPush()
            self._mask = Rectangle()
            StencilUse()
        self._weather_group = InstructionGroup()
        self._plague_group = InstructionGroup()
        self._storm_group = InstructionGroup()
        for group in (self._weather_group, self._plague_group, self._storm_group):
            self.canvas.add(group)
        with self.canvas:
            StencilUnUse()
            self._unmask = Rectangle()
            StencilPop()

    @classmethod
    def mist_texture(cls):
        if cls._mist_texture is None:
            # Small procedural alpha texture, shared by all clouds and spores.
            size = 64
            pixels = bytearray()
            for y in range(size):
                for x in range(size):
                    nx, ny = (x + 0.5) / size * 2 - 1, (y + 0.5) / size * 2 - 1
                    radius = nx * nx + ny * ny
                    grain = 0.86 + 0.14 * math.sin(nx * 15 + math.sin(ny * 11))
                    alpha = max(0.0, 1 - radius) ** 2 * grain
                    pixels.extend((255, 255, 255, int(alpha * 255)))
            texture = Texture.create(size=(size, size), colorfmt='rgba')
            texture.blit_buffer(bytes(pixels), colorfmt='rgba', bufferfmt='ubyte')
            cls._mist_texture = texture
        return cls._mist_texture

    def _sprite(self, group, rgb, alpha, size):
        color = Color(*rgb, alpha)
        shape = Rectangle(texture=self.mist_texture(), size=size)
        group.add(color)
        group.add(shape)
        return color, shape

    def configure(self, origin, scale, map_size=(1200, 800)):
        bounds = (origin[0] + 26 * scale, origin[1] + 26 * scale,
                  (map_size[0] - 52) * scale, (map_size[1] - 52) * scale)
        if bounds == self._bounds:
            return
        self._origin, self._scale = tuple(origin), scale
        self._bounds = bounds
        x, y, w, h = bounds
        self.pos, self.size = (x, y), (w, h)
        for mask in (self._mask, self._unmask):
            mask.pos, mask.size = (x, y), (w, h)
        self._build_weather()
        # The caller supplies freshly projected city positions after resizing.
        self._storm_key = self._plague_key = None

    def project(self, point):
        return (self._origin[0] + point[0] * self._scale + 38.5,
                self._origin[1] + point[1] * self._scale + 38.5)

    def set_season(self, season):
        if season != self._season:
            self._season = season
            self._build_weather()

    def _build_weather(self):
        self._weather_group.clear()
        self._weather = []
        if self._bounds is None or self._season not in ('Зима', 'Весна', 'Лето', 'Осень'):
            return
        x, y, w, h = self._bounds
        rng = self._rng
        winter, summer = self._season == 'Зима', self._season == 'Лето'
        autumn = self._season == 'Осень'
        rgb = ((0.66, 0.79, 0.94) if winter else (1, 0.78, 0.43) if summer
               else (0.65, 0.48, 0.29) if autumn else (0.45, 0.57, 0.65))
        self._weather_group.add(Color(*rgb, 0.035 if winter else 0.018))
        self._weather_group.add(Rectangle(pos=(x, y), size=(w, h)))
        # Broad diffuse cloud shadows travel across terrain, never across the UI.
        for index in range(6 if summer else 8):
            size = (rng.uniform(160, 280) * self._scale, rng.uniform(65, 115) * self._scale)
            shade = ((0.10, 0.15, 0.22) if summer else (0.37, 0.32, 0.27)
                     if autumn else (0.33, 0.39, 0.44))
            color, shape = self._sprite(self._weather_group, shade, 0, size)
            self._weather.append({'kind': 'cloud', 'color': color, 'shape': shape,
                                  'u': rng.random(), 'v': rng.random(),
                                  'speed': rng.uniform(0.007, 0.016),
                                  'alpha': 0.16 if summer else 0.23, 'phase': rng.random() * 6.28})
        count = 130 if winter else (22 if summer else 110)
        for index in range(count):
            if winter:
                color = Color(0.88, 0.94, 1, rng.uniform(0.4, 0.8))
                size = rng.uniform(1.8, 3.6) * self._scale
                shape = Ellipse(size=(size, size))
                kind = 'snow'
            elif summer:
                color = Color(1, 0.86, 0.52, 0)
                shape = Ellipse(size=(1.5 * self._scale, 1.5 * self._scale))
                kind = 'dust'
            else:
                color = Color(0.70, 0.82, 0.88, 0)
                shape = Line(points=[0, 0, 0, 0], width=0.65)
                kind = 'rain'
            self._weather_group.add(color)
            self._weather_group.add(shape)
            self._weather.append({'kind': kind, 'color': color, 'shape': shape,
                                  'u': rng.random(), 'v': rng.random(),
                                  'speed': (rng.uniform(0.04, 0.10) if winter else
                                            rng.uniform(0.006, 0.018) if summer else rng.uniform(0.32, 0.52)),
                                  'phase': rng.random() * 6.28})
        if autumn:
            for index in range(14):
                color = Color(0.69, 0.37, 0.12, rng.uniform(0.25, 0.45))
                shape = Ellipse(size=(2.5 * self._scale, 1.3 * self._scale))
                self._weather_group.add(color)
                self._weather_group.add(shape)
                self._weather.append({'kind': 'leaf', 'color': color, 'shape': shape,
                                      'u': rng.random(), 'v': rng.random(),
                                      'speed': rng.uniform(0.015, 0.03), 'phase': rng.random() * 6.28})
        if not winter and not summer:
            for index in range(10):
                color = Color(0.66, 0.79, 0.83, 0)
                ring = Line(ellipse=(0, 0, 1, 1), width=0.55)
                self._weather_group.add(color)
                self._weather_group.add(ring)
                self._weather.append({'kind': 'ripple', 'color': color, 'shape': ring,
                                      'u': rng.random(), 'v': rng.random(), 'phase': rng.random()})

    def set_storms(self, cities):
        key = tuple(tuple(city) for city in cities)
        if key == self._storm_key:
            return
        self._storm_key = key
        self._storm_group.clear()
        self._storms = []
        rng = self._rng
        for cx, cy, capital in key:
            storm = {'center': (cx, cy), 'capital': capital, 'clouds': [],
                     'bolts': [], 'wait': rng.uniform(0.15, 1.1), 'flash': 0.0}
            for index in range(8):
                # A bank of overlapping soft lobes hovers just above the spires.
                width, height = rng.uniform(32, 53), rng.uniform(18, 29)
                rgb = (0.17, 0.11, 0.19) if capital else (0.13, 0.15, 0.22)
                color, shape = self._sprite(self._storm_group, rgb, 0.52, (width, height))
                storm['clouds'].append({'color': color, 'shape': shape,
                                        'offset': (rng.uniform(-32, 32), rng.uniform(29, 42)),
                                        'phase': rng.random() * 6.28, 'rgb': rgb})
            self._storms.append(storm)

    def _channel(self, start, end, roughness=8, depth=4):
        points = [start, end]
        for level in range(depth):
            result = [points[0]]
            for a, b in zip(points, points[1:]):
                dx, dy = b[0] - a[0], b[1] - a[1]
                length = max(math.hypot(dx, dy), 0.001)
                offset = self._rng.uniform(-roughness, roughness)
                result.extend([((a[0] + b[0]) / 2 - dy / length * offset,
                                (a[1] + b[1]) / 2 + dx / length * offset), b])
            points = result
            roughness *= 0.48
        return points

    def _strike(self, storm):
        cx, cy = storm['center']
        start = (cx + self._rng.uniform(-25, 25), cy + 40)
        end = (cx + self._rng.uniform(-17, 17), cy + self._rng.uniform(8, 24))
        trunk = self._channel(start, end, roughness=5)
        paths = [(trunk, 1.0)]
        for index in self._rng.sample(range(3, 13), 2):
            point = trunk[index]
            tip = (point[0] + self._rng.choice((-1, 1)) * self._rng.uniform(8, 17),
                   point[1] - self._rng.uniform(7, 15))
            paths.append((self._channel(point, tip, 3, 2), 0.45))
        red = storm['capital'] and self._rng.random() < 0.5
        glow = (1, 0.16, 0.24) if red else (0.51, 0.37, 1)
        core = (1, 0.90, 0.86) if red else (0.92, 0.95, 1)
        visual = InstructionGroup()
        colors = []
        for rgb, width, alpha in ((glow, 3.5, 0.12), (glow, 1.35, 0.8), (core, 0.55, 1)):
            for points, strength in paths:
                color = Color(*rgb, 0)
                visual.add(color)
                visual.add(Line(points=[v for point in points for v in point],
                                width=width * (0.65 if strength < 1 else 1)))
                colors.append((color, alpha * strength))
        self._storm_group.add(visual)
        storm['bolts'].append({'visual': visual, 'colors': colors, 'age': 0.0})

    def set_plague(self, effects, sources, active=True):
        signature = (tuple(tuple(row) for row in effects), tuple(tuple(row) for row in sources), active)
        key = (signature, self._bounds)
        if key == self._plague_key:
            return
        new_event = signature != self._plague_signature
        self._plague_signature = signature
        self._plague_key = key
        self._plague_group.clear()
        self._fog, self._streams, self._outbreaks = [], [], []
        if not active:
            self._plague_seen.clear()
            return
        routes = plague_routes(effects, sources)
        infected = {row[1] for row in routes}
        source_names = {row[0] for row in sources}
        for name, losses, x, y in effects:
            if name not in source_names and name not in infected:
                continue
            center = self.project((x, y))
            for index in range(5):
                color, shape = self._sprite(self._plague_group, (0.26, 0.39, 0.08), 0,
                                            (55 * self._scale, 24 * self._scale))
                self._fog.append({'center': center, 'color': color, 'shape': shape,
                                  'phase': self._rng.random() * 6.28, 'offset': index * 1.25})
            # An outbreak is displayed once per changed loss report, not per resize.
            if losses > 0 and name in infected and new_event and self._plague_seen.get(name) != losses:
                color = Color(0.75, 0.87, 0.23, 0)
                ring = Line(ellipse=(*center, 1, 1), width=1.2)
                self._plague_group.add(color)
                self._plague_group.add(ring)
                label = CoreLabel(text='−' + str(losses), font_size=15, color=(0.85, 0.94, 0.53, 1))
                label.refresh()
                text_color = Color(1, 1, 1, 0)
                text = Rectangle(texture=label.texture, size=label.texture.size)
                self._plague_group.add(text_color)
                self._plague_group.add(text)
                self._outbreaks.append({'center': center, 'born': self._time,
                                        'color': color, 'shape': ring,
                                        'text_color': text_color, 'text': text})
        self._plague_seen = {name: losses for name, losses, x, y in effects if losses > 0}
        for source, target, start, end, losses in routes:
            start, end = self.project(start), self.project(end)
            for index in range(7):
                color, shape = self._sprite(self._plague_group, (0.65, 0.78, 0.16), 0,
                                            (16 * self._scale, 9 * self._scale))
                core_color = Color(0.85, 0.92, 0.39, 0)
                core = Ellipse(size=(2 * self._scale, 2 * self._scale))
                self._plague_group.add(core_color)
                self._plague_group.add(core)
                self._streams.append({'start': start, 'end': end, 'phase': index / 7,
                                      'color': color, 'shape': shape,
                                      'core_color': core_color, 'core': core,
                                      'bend': self._rng.uniform(-18, 18) * self._scale})

    def _update_weather(self, dt):
        x, y, w, h = self._bounds
        t = self._time
        for p in self._weather:
            kind = p['kind']
            if kind == 'cloud':
                p['u'] = (p['u'] + dt * p['speed']) % 1
                width, height = p['shape'].size
                p['shape'].pos = (x + p['u'] * (w + width) - width,
                                   y + p['v'] * h + math.sin(t * 0.12 + p['phase']) * 5)
                p['color'].a = p['alpha'] * (0.8 + 0.2 * math.sin(t * 0.2 + p['phase']))
            elif kind == 'ripple':
                phase = (t * 0.65 + p['phase']) % 1
                radius = (1 + phase * 5) * self._scale
                p['shape'].ellipse = (x + p['u'] * w - radius, y + p['v'] * h - radius / 3,
                                       radius * 2, radius * 0.66)
                front = (t * 0.022) % 1
                gap = abs((p['u'] - front + 0.5) % 1 - 0.5)
                p['color'].a = math.sin(phase * math.pi) * 0.14 * max(0, 1 - gap / 0.25)
            else:
                p['v'] = (p['v'] - dt * p['speed']) % 1
                p['u'] = (p['u'] + dt * (0.015 if kind == 'snow' else -0.025)) % 1
                px = x + p['u'] * w + math.sin(t * 0.8 + p['phase']) * 3
                py = y + p['v'] * h
                if kind == 'rain':
                    # A moving rain front, rather than a uniform screen overlay.
                    front = (t * 0.022) % 1
                    gap = abs((p['u'] - front + 0.5) % 1 - 0.5)
                    p['color'].a = max(0, 1 - gap / 0.25) * 0.38
                    p['shape'].points = [px, py, px - 4 * self._scale, py - 16 * self._scale]
                else:
                    p['shape'].pos = (px, py)
                    if kind == 'dust':
                        p['color'].a = (0.5 + 0.5 * math.sin(t * 0.6 + p['phase'])) * 0.28

    def _update_storms(self, dt):
        for storm in self._storms:
            storm['wait'] -= dt
            if storm['wait'] <= 0:
                self._strike(storm)
                storm['wait'] = self._rng.uniform(0.65, 1.4) if storm['capital'] else self._rng.uniform(0.9, 2.0)
            flash = 0.0
            for bolt in storm['bolts'][:]:
                age = bolt['age']
                bolt['age'] += dt
                if age > 0.3:
                    self._storm_group.remove(bolt['visual'])
                    storm['bolts'].remove(bolt)
                    continue
                intensity = math.exp(-age / 0.032)
                if age >= 0.085:
                    intensity += 0.8 * math.exp(-(age - 0.085) / 0.045)
                intensity = min(1, intensity)
                flash = max(flash, intensity)
                for color, alpha in bolt['colors']:
                    color.a = intensity * alpha
            cx, cy = storm['center']
            for cloud in storm['clouds']:
                dx, dy = cloud['offset']
                width, height = cloud['shape'].size
                cloud['shape'].pos = (cx + dx - width / 2 + math.sin(self._time * 0.3 + cloud['phase']) * 4,
                                       cy + dy - height / 2 + math.cos(self._time * 0.22 + cloud['phase']) * 2)
                cloud['color'].rgb = tuple(min(1, value + flash * 0.40) for value in cloud['rgb'])
                cloud['color'].a = 0.48 + 0.08 * math.sin(self._time * 0.4 + cloud['phase'])

    def _update_plague(self):
        for p in self._fog:
            phase = self._time * 0.28 + p['phase']
            cx, cy = p['center']
            width, height = p['shape'].size
            p['shape'].pos = (cx + math.sin(phase + p['offset']) * 27 * self._scale - width / 2,
                               cy - 19 + math.cos(phase * 0.8 + p['offset']) * 9 - height / 2)
            p['color'].a = 0.13 + 0.045 * math.sin(phase)
        for p in self._streams:
            progress = (self._time / 4.2 + p['phase']) % 1
            px, py = stream_point(p['start'], p['end'], progress, p['bend'])
            width, height = p['shape'].size
            p['shape'].pos = (px - width / 2, py - height / 2)
            alpha = math.sin(progress * math.pi) ** 0.7
            p['color'].a = alpha * 0.6
            p['core'].pos = (px - self._scale, py - self._scale)
            p['core_color'].a = alpha * 0.65
        for p in self._outbreaks:
            age = self._time - p['born']
            fade = max(0, 1 - age / 3.2)
            radius = (15 + min(age, 3.2) * 18) * self._scale
            cx, cy = p['center']
            p['shape'].ellipse = (cx - radius, cy - radius * 0.48, radius * 2, radius * 0.96)
            p['color'].a = fade * 0.45
            p['text'].pos = (cx - p['text'].size[0] / 2, cy + 26 + min(age, 3.2) * 9)
            p['text_color'].a = min(1, age * 4) * fade

    def update(self, dt):
        if self._bounds is None:
            return
        dt = min(max(dt, 0), 0.1)
        self._time += dt
        self._update_weather(dt)
        self._update_storms(dt)
        self._update_plague()

    def start(self):
        if self._event is None:
            self._event = Clock.schedule_interval(self.update, 1 / 30.0)

    def stop(self):
        if self._event:
            self._event.cancel()
            self._event = None

    def on_parent(self, instance, parent):
        if parent is None:
            self.stop()
        else:
            self.start()

    def on_touch_down(self, touch):
        return False

    def on_touch_move(self, touch):
        return False

    def on_touch_up(self, touch):
        return False
