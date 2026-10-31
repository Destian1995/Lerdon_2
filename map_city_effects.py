"""City smoke and capture celebrations, driven by MapAtmosphere's single clock."""
import math
import random

from kivy.core.text import Label as CoreLabel
from kivy.core.window import Window
from kivy.graphics import Color, Ellipse, InstructionGroup, Line, Rectangle
from kivy.uix.modalview import ModalView


FACTION_RGB = {
    'Север': (0.32, 0.68, 1.0), 'Эльфы': (0.25, 0.95, 0.48),
    'Вампиры': (0.78, 0.32, 0.94), 'Адепты': (1.0, 0.61, 0.20),
    'Элины': (1.0, 0.87, 0.25), 'Нежить': (0.42, 0.72, 0.88),
    'Мятежники': (0.96, 0.35, 0.20),
}


class CityEffects:
    def __init__(self, atmosphere):
        self.atmosphere = atmosphere
        self.group = InstructionGroup()
        self.smoke_group = InstructionGroup()
        self.group.add(self.smoke_group)
        self._seen = None
        self._owners = {}
        self._cities = {}
        self._smoke_key = None
        self.smoke = []
        self.captures = []
        self.time = 0.0
        self.capture_time = 0.0

    def _sprite(self, group, rgb, alpha=0):
        color = Color(*rgb, alpha)
        shape = Rectangle(texture=self.atmosphere.mist_texture())
        group.add(color)
        group.add(shape)
        return color, shape

    def sync(self, cities, states, turn):
        """Baseline saved events on first view; redraws never replay celebrations."""
        self._cities = {name: (x, y, faction) for name, x, y, faction in cities}
        revisions = {name: state.revision for name, state in states.items()}
        if self._seen is not None:
            for name, (x, y, faction) in self._cities.items():
                state = states.get(name)
                changed = name in self._owners and self._owners[name] != faction
                new_event = state and state.revision != self._seen.get(name, 0)
                if new_event and state.turn == turn:
                    self.play(name, state.kind, faction)
                elif changed:
                    self.play(name, 'peace', faction)
        self._seen = revisions
        self._owners = {name: value[2] for name, value in self._cities.items()}
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
            density = 0.55 if turn < until else 0.36
            if ruined and turn > until:
                density = 0.25
            for i in range(12 if ruined else 9):
                rgb = (0.18, 0.16, 0.15) if i % 3 else (0.49, 0.46, 0.42)
                color, shape = self._sprite(self.smoke_group, rgb)
                self.smoke.append(dict(city=name, phase=rng.random(),
                    speed=rng.uniform(0.12, 0.22), dx=rng.uniform(-15, 15),
                    width=rng.uniform(19, 33), color=color, shape=shape, alpha=density))

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
        title = {'peace': 'Мирное присоединение', 'battle_capture': 'Город захвачен',
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
        # Battle reports/animations cover the map: show the celebration once visible.
        if not any(isinstance(widget, ModalView) for widget in Window.children):
            self.capture_time += dt
        scale = self.atmosphere._scale
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
