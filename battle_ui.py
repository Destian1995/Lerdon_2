"""Battle replay and after-action report. Rendering never rolls combat outcomes."""
import math
import os
import random

from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import (Color, Ellipse, Line, Rectangle, StencilPush,
                           StencilUse, StencilUnUse, StencilPop)
from kivy.metrics import dp, sp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.image import Image
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.widget import Widget

from battle_presentation import replay_frames, result_caption, player_side, army_summary, report_result
from strategy_ui import GOLD, INK, SURFACE, TEXT, MUTED, FACTIONS, StrategyButton, surface, text_label
from utils.helpers import format_number
from window_theme import prepare_custom_popup, center_after_resize

RED = (1, 0.38, 0.27, 1)
GREEN = (0.38, 0.87, 0.57, 1)
PORTRAITS = {'Север': 'people', 'Эльфы': 'elfs', 'Вампиры': 'vampire', 'Адепты': 'adept', 'Элины': 'poly'}


def portrait_path(preferred, faction):
    if preferred and os.path.isfile(preferred):
        return preferred
    path = f'files/sov/{PORTRAITS.get(faction, "")}.jpg'
    if os.path.isfile(path):
        return path
    return 'files/army/death/king_.png' if faction == 'Нежить' else 'files/status/army.png'


def exact_count(value):
    return f'{int(value):,}'.replace(',', ' ')


class ForceBar(Widget):
    """A count bar with a trailing loss band; no canvas rebuild or private timer."""
    def __init__(self, color=GOLD, **kwargs):
        super().__init__(**kwargs)
        self.ratio = self.trail = self.target = 1.0
        with self.canvas:
            Color(0.025, 0.035, 0.055, 1)
            self.back = Rectangle()
            Color(*color[:3], 0.25)
            self.ghost = Rectangle()
            Color(*color[:3], 1)
            self.fill = Rectangle()
            Color(1, 1, 1, 0.15)
            self.shine = Rectangle()
        self.bind(pos=self.draw, size=self.draw)
        self.draw()

    def draw(self, *args):
        self.back.pos, self.back.size = self.pos, self.size
        self.ghost.pos, self.ghost.size = self.pos, (self.width * self.trail, self.height)
        self.fill.pos, self.fill.size = self.pos, (self.width * self.ratio, self.height)
        self.shine.pos = (self.x, self.y + self.height * 0.68)
        self.shine.size = (self.width * self.ratio, self.height * 0.20)

    def advance(self, dt):
        self.ratio += (self.target - self.ratio) * (1 - math.exp(-dt * 13))
        self.trail += (self.target - self.trail) * (1 - math.exp(-dt * 4))
        self.draw()


class CombatSide(BoxLayout):
    def __init__(self, faction, role, image, **kwargs):
        super().__init__(orientation='vertical', padding=dp(8), spacing=dp(4), **kwargs)
        self.accent = FACTIONS.get(faction, GOLD)
        surface(self, SURFACE, self.accent)
        self.add_widget(text_label(f'{faction} · {role}', 13, self.accent,
                                   bold=True, size_hint_y=None, height=dp(24)))
        self.holder = FloatLayout()
        self.image = Image(source=portrait_path(image, faction), size_hint=(None, None),
                           allow_stretch=True, keep_ratio=True, mipmap=True)
        self.holder.add_widget(self.image)
        with self.holder.canvas.after:
            self.flash_color = Color(1, 0.72, 0.35, 0)
            self.flash = Rectangle()
        self.damage = text_label('', 20, RED, bold=True, size_hint=(None, None), height=dp(30))
        self.damage.halign = 'center'
        self.holder.add_widget(self.damage)
        self.add_widget(self.holder)
        self.bar = ForceBar(self.accent, size_hint_y=None, height=dp(12))
        self.add_widget(self.bar)
        self.count = text_label('', 12, TEXT, size_hint_y=None, height=dp(22))
        self.add_widget(self.count)
        self.impact_age = 10
        self.holder.bind(pos=self.layout_portrait, size=self.layout_portrait)

    def layout_portrait(self, *args):
        self.base = self.holder.pos
        self.image.size = self.holder.size
        self.image.pos = self.base
        self.flash.pos, self.flash.size = self.base, self.holder.size
        self.damage.width = self.holder.width
        self.place_damage()

    def place_damage(self):
        y = self.holder.y + self.holder.height * 0.47 + min(self.impact_age, 1) * dp(20)
        self.damage.pos = (self.holder.x, max(self.holder.y, min(y, self.holder.top - self.damage.height)))

    def show_count(self, current, maximum, loss=0):
        self.count.text = f'Бойцы: {format_number(current)} / {format_number(maximum)}'
        self.bar.target = max(0, min(1, current / maximum)) if maximum > 0 else 0
        if loss > 0:
            self.damage.text = '−' + format_number(loss)
            self.impact_age = 0

    def update(self, dt):
        self.bar.advance(dt)
        self.impact_age += dt
        age = self.impact_age
        strength = max(0, 1 - age / 0.32)
        base = getattr(self, 'base', self.holder.pos)
        self.image.pos = (base[0] + math.sin(age * 65) * dp(3) * strength, base[1])
        self.flash_color.a = max(0, 0.30 - age * 1.3)
        self.damage.opacity = max(0, min(1, 1.4 - age * 1.5))
        self.place_damage()


class ClashFX(Widget):
    """A clipped reusable particle pool. Its random stream is presentation-only."""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.rng = random.Random(73)
        self.particles = []
        self.slash_age = 10
        with self.canvas:
            StencilPush()
            self.mask = Rectangle()
            StencilUse()
            self.slash_color = Color(1, 0.83, 0.41, 0)
            self.slash = Line(width=dp(2))
            for _ in range(48):
                color = Color(1, 0.7, 0.3, 0)
                shape = Ellipse(size=(0, 0))
                self.particles.append(dict(color=color, shape=shape, life=0))
            StencilUnUse()
            self.unmask = Rectangle()
            StencilPop()
        self.bind(pos=self.layout, size=self.layout)

    def layout(self, *args):
        for rect in (self.mask, self.unmask):
            rect.pos, rect.size = self.pos, self.size

    def burst(self, x, y, color, count=14):
        self.slash_age = 0
        self.slash.points = (x - dp(28), y - dp(19), x, y + dp(7), x + dp(24), y + dp(28))
        for particle in self.particles:
            if particle['life'] > 0:
                continue
            angle = self.rng.uniform(0, math.tau)
            speed = self.rng.uniform(dp(45), dp(135))
            particle.update(x=x, y=y, vx=math.cos(angle) * speed, vy=math.sin(angle) * speed,
                            life=self.rng.uniform(0.3, 0.65), ttl=0.65, size=self.rng.uniform(dp(2), dp(4)))
            particle['color'].rgb = color[:3]
            count -= 1
            if count <= 0:
                break

    def update(self, dt):
        self.slash_age += dt
        self.slash_color.a = max(0, 1 - self.slash_age / 0.22)
        for p in self.particles:
            p['life'] = max(0, p['life'] - dt)
            if p['life'] <= 0:
                p['color'].a = 0
                continue
            p['x'] += p['vx'] * dt
            p['y'] += p['vy'] * dt
            p['vy'] -= dp(160) * dt
            p['shape'].pos, p['shape'].size = (p['x'], p['y']), (p['size'], p['size'])
            p['color'].a = min(1, p['life'] / 0.3)

    def on_touch_down(self, touch):
        return False

    def on_touch_up(self, touch):
        return False


class BattleViewer(Popup):
    def __init__(self, rounds, attacking, defending, winner, user, source_city, city,
                 callback=None, attacker_image=None, defender_image=None, **kwargs):
        self.frames = replay_frames(rounds, 16)
        self.attacking, self.defending, self.winner, self.user = attacking, defending, winner, user
        self.callback, self.city = callback, city
        self.clock_event = None
        self.closed = self.callback_sent = self.paused = self.finished = False
        self.speed, self.index, self.elapsed = 1, -1, 0.4
        root = surface(BoxLayout(orientation='vertical', padding=dp(12), spacing=dp(8)), INK)
        header = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8))
        header._responsive_stack_below = dp(480)
        heading = BoxLayout(orientation='vertical')
        heading.add_widget(text_label('БОЕВОЕ СТОЛКНОВЕНИЕ', 10, GOLD))
        self.title_label = text_label(city, 19, TEXT, bold=True)
        heading.add_widget(self.title_label)
        header.add_widget(heading)
        self.speed_button = StrategyButton(text='×1', size_hint_x=None, width=dp(48))
        self.pause_button = StrategyButton(text='Пауза', size_hint_x=None, width=dp(84))
        self.finish_button = StrategyButton(text='Итоги', primary=True, size_hint_x=None, width=dp(84))
        self.speed_button.bind(on_release=self.change_speed)
        self.pause_button.bind(on_release=self.toggle_pause)
        self.finish_button.bind(on_release=self.close_to_report)
        controls = BoxLayout(size_hint_x=None, width=dp(232), spacing=dp(8))
        for button in (self.speed_button, self.pause_button, self.finish_button):
            controls.add_widget(button)
        header.add_widget(controls)
        root.add_widget(header)
        arena = FloatLayout()
        arena._responsive_min_height = dp(170)
        self.arena = arena
        self.attacker_panel = CombatSide(attacking, 'Атака', attacker_image, size_hint=(0.46, 1), pos_hint={'x': 0, 'y': 0})
        self.defender_panel = CombatSide(defending, 'Оборона', defender_image, size_hint=(0.46, 1), pos_hint={'right': 1, 'y': 0})
        arena.add_widget(self.attacker_panel)
        arena.add_widget(self.defender_panel)
        vs = text_label('VS', 18, GOLD, bold=True, size_hint=(0.08, 1), pos_hint={'x': 0.46, 'y': 0})
        vs.halign = 'center'
        arena.add_widget(vs)
        self.fx = ClashFX(pos_hint={'x': 0, 'y': 0})
        arena.add_widget(self.fx)
        self.result_ribbon = surface(BoxLayout(orientation='vertical', padding=dp(8), size_hint=(0.78, None),
                                    height=dp(80), pos_hint={'center_x': 0.5, 'center_y': 0.5}), INK)
        self.result_label = text_label('', 25, GOLD, bold=True)
        self.result_label.halign = 'center'
        self.result_detail = text_label('', 13, TEXT)
        self.result_detail.halign = 'center'
        self.result_ribbon.add_widget(self.result_label)
        self.result_ribbon.add_widget(self.result_detail)
        self.result_ribbon.opacity = 0
        arena.add_widget(self.result_ribbon)
        root.add_widget(arena)
        footer = BoxLayout(orientation='vertical', size_hint_y=None, height=dp(48))
        self.round_label = text_label(f'{source_city} → {city}', 12, GOLD)
        self.event_label = text_label('Армии занимают позиции…', 12, MUTED)
        footer.add_widget(self.round_label)
        footer.add_widget(self.event_label)
        root.add_widget(footer)
        super().__init__(title='', content=root, size_hint=(None, None), auto_dismiss=False, **kwargs)
        prepare_custom_popup(self)
        self.bind(on_open=self.start, on_dismiss=self.cleanup)
        Window.bind(on_resize=self.fit)
        self.fit()
        initial = self.frames[0] if self.frames else {}
        self.attacker_panel.show_count(initial.get('atk_max', 0), initial.get('atk_max', 0))
        self.defender_panel.show_count(initial.get('def_max', 0), initial.get('def_max', 0))

    def fit(self, *args):
        width, height = args[1:3] if len(args) >= 3 else Window.size
        self.size = (min(dp(1080), width - dp(16)), min(dp(720), height - dp(16)))
        center_after_resize(self)

    def start(self, *args):
        if self.clock_event is None and not self.closed:
            self.clock_event = Clock.schedule_interval(self.update, 1 / 30)

    def toggle_pause(self, *args):
        self.paused = not self.paused
        self.pause_button.text = 'Далее' if self.paused else 'Пауза'

    def change_speed(self, *args):
        self.speed = 2 if self.speed == 1 else 1
        self.speed_button.text = f'×{self.speed}'

    def show_frame(self, index):
        record = self.frames[index]
        self.attacker_panel.show_count(record.get('atk_total', 0), record.get('atk_max', 0), record['atk_loss'])
        self.defender_panel.show_count(record.get('def_total', 0), record.get('def_max', 0), record['def_loss'])
        start, end = record['from_round'], record['round']
        self.round_label.text = f'Раунд {end}' if start == end else f'Раунды {start}–{end}'
        self.round_label.text += f'  /  {self.frames[-1]["round"]}'
        events = []
        for side, loss, crits, faction in ((self.attacker_panel, record['atk_loss'], record['def_crits'], self.defending),
                                           (self.defender_panel, record['def_loss'], record['atk_crits'], self.attacking)):
            if loss > 0:
                self.fx.burst(side.holder.center_x, side.holder.center_y, GOLD if crits else side.accent,
                              20 if crits else 12)
            if crits:
                events.append(f'{faction}: критические удары ×{crits}')
        for hero in record['heroes']:
            events.append(f'Вступает в бой: {hero["unit_name"]}')
        self.event_label.text = ' · '.join(events) if events else (
            f'Потери: атака −{format_number(record["atk_loss"])}  ·  оборона −{format_number(record["def_loss"])}')

    def reveal_result(self):
        self.finished = True
        self.result_age = 0
        caption, won = result_caption(self.winner, self.user, self.attacking, self.defending)
        self.result_label.text, self.result_label.color = caption, RED if won is False else GOLD
        winner = self.attacking if self.winner in ('attacker', 'attacking') else self.defending
        self.result_detail.text = winner + (' захватывает город' if self.winner in ('attacker', 'attacking') else ' удерживает город')
        self.result_ribbon.opacity = 1
        self.finish_button.text = 'Отчёт'
        self.pause_button.disabled = self.speed_button.disabled = True
        self.event_label.text = 'Сражение завершено. Потери и восстановление — в отчёте.'
        self.fx.burst(self.arena.center_x, self.arena.center_y, GOLD if won is not False else RED, 28)

    def update(self, dt):
        if self.closed:
            return False
        dt = min(0.1, max(0, dt)) * self.speed
        self.attacker_panel.update(dt)
        self.defender_panel.update(dt)
        self.fx.update(dt)
        if self.finished:
            self.result_age += dt
            if self.result_age > 1.5 and self.clock_event:
                self.clock_event.cancel()
                self.clock_event = None
        if not self.paused and not self.finished:
            self.elapsed += dt
            if self.elapsed >= 0.6:
                self.elapsed = 0
                self.index += 1
                if self.index < len(self.frames):
                    self.show_frame(self.index)
                else:
                    self.reveal_result()

    def close_to_report(self, *args):
        if not self.closed:
            self.dismiss(animation=False)

    def cleanup(self, *args):
        if self.closed:
            return
        self.closed = True
        if self.clock_event:
            self.clock_event.cancel()
            self.clock_event = None
        Window.unbind(on_resize=self.fit)
        if self.callback and not self.callback_sent:
            self.callback_sent = True
            Clock.schedule_once(lambda dt: self.callback(), 0)


class BattleReport(Popup):
    def __init__(self, rows, user=None, attacking=None, defending=None, bonuses=None, rounds=None, **kwargs):
        self.rows = rows
        caption, won = report_result(rows, user, attacking, defending)
        city = rows[0].get('city', '—') if rows else '—'
        root = surface(BoxLayout(orientation='vertical', padding=dp(12), spacing=dp(10)), INK)
        header = BoxLayout(size_hint_y=None, height=dp(52), spacing=dp(8))
        title = BoxLayout(orientation='vertical')
        heading = 'БОЕВАЯ СВОДКА  /  ' + city
        if rounds:
            heading += f'  ·  Раундов: {rounds[-1].get("round", len(rounds))}'
        title.add_widget(text_label(heading, 10, MUTED))
        title.add_widget(text_label(caption, 23, RED if won is False else GOLD, bold=True))
        header.add_widget(title)
        close = StrategyButton(text='×', size_hint_x=None, width=dp(48))
        close._strategy_close = True
        header.add_widget(close)
        root.add_widget(header)
        scroll = ScrollView(do_scroll_x=False, bar_width=dp(3), bar_color=GOLD)
        content = BoxLayout(orientation='vertical', size_hint_y=None, spacing=dp(10))
        content.bind(minimum_height=content.setter('height'))
        armies = [(attacking or 'Атакующий', 'attacking', 'Атака'),
                  (defending or 'Защитник', 'defending', 'Оборона')]
        self.summaries = {}
        overview = BoxLayout(size_hint_y=None, height=dp(114), spacing=dp(8))
        for faction, side, role in armies:
            units = [row for row in rows if row.get('side') == side]
            summary = army_summary(units)
            self.summaries[side] = summary
            card = surface(BoxLayout(orientation='vertical', padding=dp(9), spacing=dp(2)),
                           SURFACE, FACTIONS.get(faction, GOLD))
            card.add_widget(text_label(faction + (' · Вы' if player_side(user, attacking, defending) == side else ''), 14,
                                       FACTIONS.get(faction, GOLD), bold=True))
            card.add_widget(text_label(f'Было {format_number(summary["initial"])} → осталось {format_number(summary["remaining"])}', 12))
            card.add_widget(text_label('Безвозвратные: ' + format_number(summary['net_losses']), 12,
                                       RED if summary['net_losses'] else MUTED))
            recovered = 'Вернулось: ' + format_number(summary['recovered'])
            if summary['reinforcements']:
                recovered += ' · +' + format_number(summary['reinforcements']) + ' новых'
            card.add_widget(text_label(recovered, 12, GREEN if summary['recovered'] or summary['reinforcements'] else MUTED))
            overview.add_widget(card)
        content.add_widget(overview)
        content.add_widget(text_label('Потери в бою показаны до исцеления; остаток — после восстановления.',
                                      11, MUTED, size_hint_y=None, height=dp(32)))
        for faction, side, role in armies:
            section_title = f'{role}  /  {faction}'
            if rounds and any('atk_crits' in record for record in rounds):
                key = 'atk_crits' if side == 'attacking' else 'def_crits'
                section_title += f'  ·  Критов: {sum(record.get(key, 0) for record in rounds)}'
            content.add_widget(text_label(section_title, 15, GOLD, bold=True,
                                          size_hint_y=None, height=dp(28)))
            units = [row for row in rows if row.get('side') == side]
            for row in units:
                card = surface(BoxLayout(size_hint_y=None, height=dp(60), padding=dp(7), spacing=dp(8)), SURFACE,
                               (0.30, 0.37, 0.45, 1))
                image = row.get('unit_image', '')
                card.add_widget(Image(source=image if image and os.path.isfile(image) else 'files/pict/hire/class.png',
                                      size_hint_x=None, width=dp(40), mipmap=True))
                detail = BoxLayout(orientation='vertical')
                detail.add_widget(text_label(row.get('unit_name', '—'), 13, bold=True))
                status = f'Было {exact_count(row.get("initial_count", 0))} · Осталось {exact_count(row.get("final_count", 0))}'
                if row.get('initial_count') == 1:
                    status = 'Погиб в бою' if not row.get('final_count') else 'Вернулся после исцеления' if row.get('healed') else 'Выжил'
                detail.add_widget(text_label(status, 11, MUTED))
                card.add_widget(detail)
                losses = BoxLayout(orientation='vertical', size_hint_x=0.5)
                losses.add_widget(text_label('Потери: ' + exact_count(row.get('losses', 0)), 12, RED if row.get('losses') else MUTED))
                losses.add_widget(text_label('Вернулось: ' + exact_count(row.get('healed', 0)), 11, GREEN if row.get('healed') else MUTED))
                card.add_widget(losses)
                content.add_widget(card)
        for message in bonuses or []:
            label = text_label(message, 13, GREEN, markup=True, size_hint_y=None, height=dp(48))
            content.add_widget(label)
        scroll.add_widget(content)
        root.add_widget(scroll)
        super().__init__(title='', content=root, size_hint=(None, None), auto_dismiss=False, **kwargs)
        prepare_custom_popup(self)
        close.bind(on_release=self.dismiss)
        self.bind(on_dismiss=lambda *_: Window.unbind(on_resize=self.fit))
        Window.bind(on_resize=self.fit)
        self.fit()

    def fit(self, *args):
        width, height = args[1:3] if len(args) >= 3 else Window.size
        self.size = (min(dp(1000), width - dp(16)), min(dp(720), height - dp(16)))
        center_after_resize(self)


def battle_career_panel(data, size_hint_x, is_landscape):
    panel = surface(BoxLayout(orientation='vertical', padding=dp(8), spacing=dp(4), size_hint_x=size_hint_x), SURFACE)
    won, lost = data.get('victories', 0), data.get('defeats', 0)
    panel.add_widget(text_label('БОЕВАЯ СТАТИСТИКА', 11, GOLD, bold=True))
    panel.add_widget(text_label(f'Сражения: {won} побед / {lost} пораж.', 12))
    rate = f'{won / (won + lost):.0%}' if won + lost else '—'
    panel.add_widget(text_label('Доля побед: ' + rate, 12, GREEN))
    panel.add_widget(text_label(f'Кампании (В/П): {data.get("matches_won", 0)} / {data.get("matches_lost", 0)}', 11, MUTED))
    return panel
