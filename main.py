import os
os.environ['KIVY_VIDEO'] = 'ffpyplayer'
from game_process import GameScreen
from strategy_ui import StrategyButton
from frontend_ui import FactionChoice, MenuButton
from ui import *
from db_lerdon_connect import *
from generate_map import generate_map_and_cities
from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.scrollview import ScrollView
from kivy.uix.tabbedpanel import TabbedPanel, TabbedPanelItem
from kivy.uix.anchorlayout import AnchorLayout
from kivy.core.window import Window
from kivy.metrics import dp, sp
from kivy.utils import get_color_from_hex
from kivy.app import App
from kivy.uix.spinner import SpinnerOption
from kivy.graphics import Color, RoundedRectangle, Line
from kivy.clock import Clock

import sqlite3
import re

RANK_TO_FILENAME = {
    # Группа 1: Военные
    "Главнокомандующий": "19.png",  # старший
    "Верховный маршал": "18.png",
    "Генерал-фельдмаршал": "17.png",
    "Генерал армии": "16.png",
    "Генерал-полковник": "15.png",
    "Генерал-лейтенант": "14.png",
    "Генерал-майор": "13.png",
    "Бригадный генерал": "12.png",
    "Коммандер": "11.png",
    "Полковник": "10.png",
    "Подполковник": "9.png",
    "Майор": "8.png",
    "Капитан-лейтенант": "7.png",
    "Капитан": "6.png",
    "Платиновый лейтенант": "5.png",
    "Серебряный лейтенант": "4.png",
    "Сержант": "3.png",
    "Прапорщик": "2.png",
    "Рядовой": "1.png",  # младший

    # Группа 2: Тьма
    "Владыка ночи": "19.png",
    "Вечный граф": "18.png",
    "Темный лорд": "17.png",
    "Князь тьмы": "16.png",
    "Старший вампир": "15.png",
    "Ночной страж": "14.png",
    "Теневой охотник": "13.png",
    "Призрачный убийца": "12.png",
    "Темный воитель": "11.png",
    "Ночной рейнджер": "10.png",
    "Младший вампир": "9.png",
    "Темный слуга": "8.png",
    "Младший слуга вампира": "7.png",
    "Ночная тень": "6.png",
    "Плутонический следопыт": "5.png",
    "Серебряный следопыт": "4.png",
    "Вестник смерти": "3.png",
    "Пепел прошлого": "2.png",
    "Укушенный": "1.png",

    # Группа 3: Лесные
    "Верховный правитель": "19.png",
    "Лесной повелитель": "18.png",
    "Вечный страж": "17.png",
    "Магистр природы": "16.png",
    "Лесной воевода": "15.png",
    "Хранитель лесов": "14.png",
    "Мастер стрелы": "13.png",
    "Лесной командир": "12.png",
    "Древесный защитник": "11.png",
    "Мастер лука": "10.png",
    "Ловкий стрелок": "9.png",
    "Юркий воин": "8.png",
    "Стремительный охотник": "7.png",
    "Зеленый страж": "6.png",
    "Природный следопыт": "5.png",
    "Ученик жрицы": "4.png",
    "Начинающий охотник": "3.png",
    "Молодой эльф": "2.png",
    "Младший ученик эльфа": "1.png",

    # Группа 4: Инквизиция
    "Верховный Инквизитор": "19.png",
    "Великий Охотник на Еретиков": "18.png",
    "Магистр Святого Огня": "17.png",
    "Гранд-Инквизитор": "16.png",
    "Судья Правой Руки": "15.png",
    "Главный Следователь": "14.png",
    "Огонь Вердикта": "13.png",
    "Страж Чистоты": "12.png",
    "Палач Ереси": "11.png",
    "Исполнитель Клятвы": "10.png",
    "Сержант Ордена": "9.png",
    "Офицер Инквизиции": "8.png",
    "Кандидат Света": "7.png",
    "Новичок Клятвы": "6.png",
    "Причастный Костра": "5.png",
    "Ученик Веры": "4.png",
    "Искренний": "3.png",
    "Слушающий Слово": "2.png",
    "Пепел Греха": "1.png",

    # Группа 5: Пустыня
    "Повелитель Огня и Пустыни": "19.png",
    "Око Бури": "18.png",
    "Хранитель Песков": "17.png",
    "Гнев Ветров": "16.png",
    "Тень Дракона": "15.png",
    "Жар Пустыни": "14.png",
    "Клинок Вечного Солнца": "13.png",
    "Степной Судья": "12.png",
    "Мастер Ярости": "11.png",
    "Искра Пламени": "10.png",
    "Бегущий по Пескам": "9.png",
    "Вестник Жара": "8.png",
    "Порождение Торнадо": "7.png",
    "Песчаный Странник": "6.png",
    "Пыль Гривы": "5.png",
    "Песчинка": "4.png",
    "Забытый Ветром": "3.png",
    "Проклятый Солнцем": "2.png",
    "Пепел Пустыни": "1.png",
}


def save_last_clicked_city(conn, city_name: str):
    """
    Сохраняет последний выбранный город в базу данных.
    :param conn: Активное соединение с базой данных.
    :param city_name: Название города.
    """
    cur = conn.cursor()
    cur.execute("INSERT OR REPLACE INTO last_click (id, city_name) VALUES (1, ?)", (city_name,))
    conn.commit()


def load_cities_from_db(conn, selected_kingdom):
    """
    Загружает данные о городах для выбранного княжества.
    :param conn: Активное соединение с базой данных.
    :param selected_kingdom: Название княжества.
    :return: Список словарей с данными о городах.
    """
    cursor = conn.cursor()
    try:
        query = (
            "SELECT id, name, coordinates, faction, icon_coordinates, label_coordinates, color_faction FROM cities "
            "WHERE faction = ?")
        cursor.execute(query, (selected_kingdom,))
        rows = cursor.fetchall()
        cities = []
        for row in rows:
            cities.append({
                'id': row[0],
                'name': row[1],
                'coordinates': row[2],
                'faction': row[3],
                'icon_coordinates': row[4],
                'label_coordinates': row[5],
                'color_faction': row[6]
            })
        return cities
    except sqlite3.Error as e:
        print(f"Ошибка при загрузке данных о городах: {e}")
        return []


def restore_from_backup(conn):
    """
    Восстанавливает данные из стандартных таблиц в рабочие.
    :param conn: Активное соединение с базой данных.
    """
    cursor = conn.cursor()
    tables_to_restore = [
        ("diplomacies_default", "diplomacies"),
        ("relations_default", "relations"),
        ("resources_default", "resources"),
        ("units_default", "units"),
        ("artifacts_default", "artifacts"),
        ("artifacts_ai_default", "artifacts_ai")
    ]

    try:
        cursor.execute("BEGIN IMMEDIATE")  # Блокируем на время восстановления

        for default_table, working_table in tables_to_restore:
            cursor.execute(f"DELETE FROM {working_table}")
            cursor.execute(f"INSERT INTO {working_table} SELECT * FROM {default_table}")

        # Сброс инвазии нежити для новой игры (случайный ход 18-26)
        import random as _rnd
        _inv_turn = _rnd.randint(18, 26)
        cursor.execute("""
            UPDATE undead_invasion SET
                invasion_turn = ?,
                invasion_started = 0,
                king_alive = 1,
                army_limit = 250000
            WHERE id = 1
        """, (_inv_turn,))
        # Возвращаем города нежити в нейтральный статус
        cursor.execute("""
            UPDATE cities SET faction = 'Нейтрал', color_faction = '#AAAAAA'
            WHERE is_undead = 1
        """)
        # Убираем гарнизоны нежити
        cursor.execute("""
            DELETE FROM garrisons WHERE city_name IN (
                SELECT name FROM cities WHERE is_undead = 1
            )
        """)

        conn.commit()
        print("Данные успешно восстановлены из бэкапа.")
    except sqlite3.Error as e:
        conn.rollback()
        print(f"Ошибка восстановления данных: {e}")


def clear_tables(conn):
    """
    Очищает данные из указанных таблиц базы данных.
    :param conn: Подключение к базе данных SQLite.
    """
    tables_to_clear = [
        "buildings",
        "cities",
        "diplomacies",
        "garrisons",
        "resources",
        "trade_agreements",
        "turn",
        "turn_save",
        "armies",
        "political_systems",
        "karma",
        "user_faction",
        "units",
        "results",
        "auto_build_settings",
        "interface_coord",
        "hero_equipment",
        "ai_hero_equipment",
        "season",
        "nobles",
        "noble_events",
        "coup_attempts",
        "artifacts",
        "artifacts_ai",
        "artifact_effects_log",
        "player_allies",
        "negotiation_history",
        "faction_victories",
        "battle_smoke",
        "city_war_state",
    ]

    cursor = conn.cursor()

    for table in tables_to_clear:
        try:
            cursor.execute(f"DELETE FROM {table};")
        except sqlite3.Error:
            pass  # Таблица может не существовать
    conn.commit()


class AuthorScreen(Screen):
    def __init__(self, conn, **kwargs):
        super().__init__(**kwargs)
        self.conn = conn
        from frontend_ui import build_author
        build_author(self)

    def go_back(self, instance):
        # Нет видео для остановки, упрощаем функцию
        app = App.get_running_app()
        app.root.clear_widgets()
        app.root.add_widget(MenuWidget(self.conn))

    def open_link(self, instance, url):
        webbrowser.open(url)


class LoadingScreen(FloatLayout):
    """Стильный экран загрузки с анимированными частицами и glow-эффектами."""

    TIPS = [
        "Чем больше население тем больше доход от налогов(их отсутствие усиливает рост населения)",
        "Вампиры и Эльфы могут одинаково хорошо совладать с любой идеологией",
        "Следите за потреблением армии — голодные солдаты умирают",
        "Торговля с дружественными фракциями приносит больше выгоды чем рынок",
        "Герои усиливают гарнизон",
        "Сезоны влияют на производство ресурсов",
        "Если Ваша армия слабее, но у вас есть ресурсы, вспомните о повстанцах",
        "Кристаллы можно продать за кроны на рынке и наоборот",
        "Артефакты основа силы ваших героев и армии",
        "Чем больше городов — тем выше лимит армии",
        "Чем больше население - тем выше потребление кристаллов!",
    ]

    def __init__(self, conn, selected_map=None, **kwargs):
        super(LoadingScreen, self).__init__(**kwargs)
        self.conn = conn
        self.selected_map = selected_map
        self._particles = []
        self._particle_event = None

        # === Фон ===
        with self.canvas.before:
            Color(0.04, 0.05, 0.1, 1)
            self.bg_fill = Rectangle(pos=self.pos, size=self.size)
            self.bg_rect = Rectangle(
                source='files/menu/loading_bg.jpg',
                pos=self.pos, size=self.size
            )
        self.bind(pos=self._update_bg, size=self._update_bg)

        # === Название игры ===
        self.title_label = Label(
            text="[b]LERDON[/b]",
            markup=True,
            font_size=sp(52),
            color=(0.85, 0.78, 0.55, 1),
            outline_color=(0.15, 0.1, 0.05, 1),
            outline_width=3,
            pos_hint={'center_x': 0.5, 'center_y': 0.65},
            size_hint=(1, None), height=dp(70),
        )
        self.add_widget(self.title_label)

        # Подзаголовок
        self.subtitle = Label(
            text="[i]Легенды Пяти Королевств[/i]",
            markup=True,
            font_size=sp(16),
            color=(0.6, 0.65, 0.75, 0.8),
            pos_hint={'center_x': 0.5, 'center_y': 0.58},
            size_hint=(1, None), height=dp(30),
        )
        self.add_widget(self.subtitle)

        # === Текст прогресса ===
        self.label = Label(
            markup=True,
            text="[color=#8899bb]Инициализация...[/color]",
            font_size=sp(13),
            color=(0.55, 0.6, 0.72, 1),
            pos_hint={'center_x': 0.5, 'center_y': 0.23},
            size_hint=(1, None), height=dp(24),
            halign='center'
        )
        self.add_widget(self.label)

        # === Процент ===
        self.percent_label = Label(
            text="0%",
            font_size=sp(22),
            bold=True,
            color=(0.75, 0.82, 0.95, 1),
            pos_hint={'center_x': 0.5, 'center_y': 0.33},
            size_hint=(1, None), height=dp(30),
        )
        self.add_widget(self.percent_label)

        # === Подсказка ===
        import random
        tip = random.choice(self.TIPS)
        self.tip_label = Label(
            text=f"[i]{tip}[/i]",
            markup=True,
            font_size=sp(12),
            color=(0.45, 0.5, 0.6, 0.7),
            pos_hint={'center_x': 0.5, 'center_y': 0.12},
            size_hint=(0.8, None), height=dp(30),
            halign='center',
        )
        self.add_widget(self.tip_label)

        # === Прогресс ===
        self.current_progress = 0
        self.target_progress = 0
        self._progress_event = Clock.create_trigger(self.smooth_progress_update, 0.016)
        self._completion_scheduled = False

        # === Шаги загрузки ===
        self._step_messages = [
            "Проверка базы данных...",
            "Очистка кэша...",
            "Восстановление данных...",
            "Загрузка ассетов...",
            "Финализация...",
        ]
        self.loading_steps = [
            self.step_check_db,
            self.step_cleanup_cache,
            self.step_restore_backup,
            self.step_load_assets,
            self.step_complete
        ]

        # Анимация появления
        self.opacity = 0
        Animation(opacity=1, duration=0.6).start(self)

        from frontend_ui import restyle_loading
        restyle_loading(self)

        Clock.schedule_once(self.start_loading, 0.3)

    def _animate_title(self):
        """Пульсация названия игры."""
        anim = (Animation(color=(0.95, 0.88, 0.6, 1), duration=1.5, t='in_out_sine') +
                Animation(color=(0.75, 0.68, 0.45, 1), duration=1.5, t='in_out_sine'))
        anim.repeat = True
        anim.start(self.title_label)

    def _spawn_particle(self, dt):
        """Генерирует восходящую светящуюся частицу."""
        if len(self._particles) > 25:
            return
        import random
        w = self.width or Window.width
        h = self.height or Window.height
        px = random.uniform(0, w)
        size = random.uniform(dp(2), dp(5))
        alpha = random.uniform(0.15, 0.4)
        speed = random.uniform(dp(20), dp(50))

        particle = {
            'x': px, 'y': -dp(10), 'size': size,
            'alpha': alpha, 'speed': speed,
            'color': random.choice([
                (0.53, 0.75, 0.92),  # голубой
                (0.85, 0.78, 0.55),  # золотой
                (0.65, 0.55, 0.85),  # фиолетовый
            ])
        }
        self._particles.append(particle)
        if not hasattr(self, '_particle_update_event'):
            self._particle_update_event = Clock.schedule_interval(self._update_particles, 0.033)

    def _update_particles(self, dt):
        """Обновляет и рисует частицы."""
        h = self.height or Window.height
        alive = []
        for p in self._particles:
            p['y'] += p['speed'] * dt
            p['alpha'] *= 0.995  # Постепенное угасание
            if p['y'] < h and p['alpha'] > 0.02:
                alive.append(p)
        self._particles = alive

        # Перерисовка
        if hasattr(self, '_particle_group'):
            self.canvas.after.remove(self._particle_group)
        from kivy.graphics import InstructionGroup, Ellipse as GlEllipse
        group = InstructionGroup()
        for p in self._particles:
            group.add(Color(*p['color'], p['alpha']))
            group.add(GlEllipse(pos=(p['x'], p['y']), size=(p['size'], p['size'])))
        self._particle_group = group
        self.canvas.after.add(group)

    def _draw_progress(self, *args):
        """Update the shared meter without deleting its canvas instructions."""
        self.pb_container.value = self.current_progress / 100.0

    # === Логика загрузки ===
    def start_loading(self, dt):
        self.run_next_step()

    def run_next_step(self, *args):
        if self.loading_steps:
            step = self.loading_steps.pop(0)
            step()
        else:
            self.target_progress = 100
            self.smooth_progress_update()

    def smooth_progress_update(self, dt=0):
        if abs(self.target_progress - self.current_progress) > 0.5:
            self.current_progress += (self.target_progress - self.current_progress) * 0.12
            percent = int(self.current_progress)
            self.percent_label.text = f"{percent}%"
            self._draw_progress()
            self._progress_event()
        else:
            self.current_progress = self.target_progress
            percent = int(self.current_progress)
            self.percent_label.text = f"{percent}%"
            self._draw_progress()

            if self.target_progress >= 100 and not self._completion_scheduled:
                self._completion_scheduled = True
                self.label.text = "[color=#FFD700][b]Готово![/b][/color]"
                self.percent_label.text = "100%"
                # Анимация завершения
                Animation(color=(1, 0.85, 0.3, 1), duration=0.3).start(self.percent_label)
                Clock.schedule_once(self._fade_to_menu, 1.0)

    def _fade_to_menu(self, dt):
        """Плавный переход к меню."""
        anim = Animation(opacity=0, duration=0.5)
        anim.bind(on_complete=lambda *a: self.switch_to_menu(0))
        anim.start(self)

    def update_progress(self, delta, msg_idx=None):
        self.target_progress += delta
        if msg_idx is not None and msg_idx < len(self._step_messages):
            self.label.text = f"[color=#8899bb]{self._step_messages[msg_idx]}[/color]"
        self.smooth_progress_update()

    # === Шаги ===
    def step_check_db(self):
        self.update_progress(20, 0)
        Clock.schedule_once(self.run_next_step, 0.5)

    def step_cleanup_cache(self):
        self.update_progress(0, 1)
        from threading import Thread
        def cleanup_task():
            clear_tables(self.conn)
            Clock.schedule_once(self.run_next_step, 0)
        Thread(target=cleanup_task, daemon=True).start()

    def step_restore_backup(self):
        self.update_progress(20, 2)
        restore_from_backup(self.conn)
        Clock.schedule_once(self.run_next_step, 0.5)

    def step_load_assets(self):
        self.update_progress(20, 3)
        Clock.schedule_once(self.run_next_step, 0.3)

    def step_complete(self):
        self.target_progress = 100
        self.smooth_progress_update()
        if 4 < len(self._step_messages):
            self.label.text = f"[color=#8899bb]{self._step_messages[4]}[/color]"
        Clock.schedule_once(self.run_next_step, 0.3)

    # === Вспомогательные ===
    def _update_bg(self, *args):
        self.bg_fill.pos = self.pos
        self.bg_fill.size = self.size
        self.bg_rect.pos = self.pos
        self.bg_rect.size = self.size

    def switch_to_menu(self, dt):
        self._progress_event.cancel()
        # Останавливаем частицы
        if self._particle_event:
            self._particle_event.cancel()
        if hasattr(self, '_particle_update_event'):
            self._particle_update_event.cancel()
        Animation.cancel_all(self.title_label)

        self.clear_widgets()
        self.canvas.after.clear()
        self.opacity = 1
        self.add_widget(MenuWidget(self.conn, self.selected_map))


class MapWidget(Widget):
    def __init__(self, selected_kingdom=None, player_kingdom=None, conn=None, **kwargs):
        super(MapWidget, self).__init__(**kwargs)
        self.previous_city_factions = {}  # ← Добавлено для отслеживания изменений
        self.conn = conn
        self.fortress_data_for_canvas = []
        self.fortress_icon_widgets = {}
        self.current_player_kingdom = player_kingdom
        self.player_city_icon_widget = None
        self.has_blinked = False
        self.update_cities_event = None
        self._undead_shield_data = []  # Данные для анимации щитов нежити
        self._map_atmosphere = None
        self._player_territory_colors = []  # (Color, минимум alpha, максимум alpha)
        self._player_pulse_event = None
        self._player_pulse_phase = 0.0
        self._map_snapshot = None
        self._territory_geometry_key = None
        self._territory_geometry = None
        self._city_label_cache = {}
        self._road_geometry_key = None
        self._road_geometry = []
        self._road_group = None

        self.base_map_width = 1200
        self.base_map_height = 800
        self.map_scale = self.calculate_scale()
        self.map_pos = self.calculate_centered_position()

        self.random_map_source = self.get_random_map_source()
        from map_terrain import load_terrain
        self._map_terrain = load_terrain(self.random_map_source)
        generate_map_and_cities(self.conn, terrain=self._map_terrain, sprite_scale=self.map_scale)

        self.initialize_map()
        self._map_snapshot = self._read_map_snapshot()
        self.update_cities_event = Clock.schedule_interval(self.update_cities, 1.0)

    def on_parent(self, widget, parent):
        """Останавливает все эффекты при уходе с карты, возобновляет при возврате."""
        if parent is None:
            if self.update_cities_event:
                self.update_cities_event.cancel()
                self.update_cities_event = None
            if self._player_pulse_event:
                self._player_pulse_event.cancel()
                self._player_pulse_event = None
            if self._map_atmosphere:
                self._map_atmosphere.stop()
        else:
            if not self.update_cities_event:
                self._map_snapshot = None
                self.update_cities_event = Clock.schedule_interval(self.update_cities, 1.0)
            if self._map_atmosphere:
                self._map_atmosphere.start()

    def update_cities(self, dt=None):
        snapshot = self._read_map_snapshot()
        if snapshot is not None and snapshot == self._map_snapshot:
            return
        self.map_scale = self.calculate_scale()
        self.map_pos = self.calculate_centered_position()
        # Останавливаем пульсацию перед очисткой canvas
        if self._player_pulse_event:
            self._player_pulse_event.cancel()
            self._player_pulse_event = None
        self._player_territory_colors = []
        self.canvas.clear()

        with self.canvas:
            Color(1, 1, 1, 1)
            self.map_image = Rectangle(
                source=self.random_map_source,
                pos=self.map_pos,
                size=(self.base_map_width * self.map_scale, self.base_map_height * self.map_scale)
            )
        self.draw_territories()
        self.draw_roads()
        self.draw_fortresses()

        self._map_snapshot = snapshot

    def _read_map_snapshot(self):
        """Проверяет только данные визуализации, исключая записываемые экранные координаты."""
        cursor = self.conn.cursor()
        try:
            cursor.execute('SELECT name, faction, coordinates, COALESCE(is_undead, 0) FROM cities ORDER BY id')
            cities = tuple(cursor.fetchall())
            cursor.execute('SELECT city1, city2 FROM roads ORDER BY id')
            roads = tuple(cursor.fetchall())
            effects = []
            for table in ('undead_invasion', 'plague_effects', 'season',
                          'city_war_state', 'turn', 'buildings'):
                cursor.execute('SELECT name FROM sqlite_master WHERE type = ? AND name = ?', ('table', table))
                if cursor.fetchone():
                    # Имена таблиц заданы константами, не пользовательским вводом.
                    cursor.execute('SELECT * FROM ' + table + ' ORDER BY rowid')
                    effects.append(tuple(cursor.fetchall()))
                else:
                    effects.append(())
            return (cities, roads, tuple(effects), Window.width, Window.height,
                    self.current_player_kingdom, self.random_map_source)
        except sqlite3.Error:
            # При временной ошибке БД не считаем старую картинку актуальной.
            return None
        finally:
            cursor.close()

    def initialize_map(self, schedule_blink=True):
        self.map_scale = self.calculate_scale()
        self.map_pos = self.calculate_centered_position()
        if self._player_pulse_event:
            self._player_pulse_event.cancel()
            self._player_pulse_event = None
        self._player_territory_colors = []
        self.canvas.clear()

        with self.canvas:
            Color(1, 1, 1, 1)
            self.map_image = Rectangle(
                source=self.random_map_source,
                pos=self.map_pos,
                size=(self.base_map_width * self.map_scale, self.base_map_height * self.map_scale)
            )

        self.draw_territories()
        self.draw_roads()
        self.draw_fortresses()

        if schedule_blink:
            Clock.schedule_once(self._schedule_blink, 0.2)

    def _compute_voronoi_cells(self, sites, clip_rect):
        """
        Вычисляет ячейки Вороного для набора точек (sites) внутри clip_rect.
        clip_rect = (x_min, y_min, x_max, y_max)
        Возвращает список полигонов (список точек) для каждого сайта.
        """
        x_min, y_min, x_max, y_max = clip_rect
        cells = []

        for i, (sx, sy) in enumerate(sites):
            # Начинаем с прямоугольника карты как полигон
            poly = [
                (x_min, y_min), (x_max, y_min),
                (x_max, y_max), (x_min, y_max)
            ]

            # Обрезаем полигон каждой серединной перпендикулярной линией
            for j, (ox, oy) in enumerate(sites):
                if i == j:
                    continue
                # Середина отрезка между двумя точками
                mx = (sx + ox) / 2.0
                my = (sy + oy) / 2.0
                # Нормаль от текущего сайта к другому
                dx = ox - sx
                dy = oy - sy
                # Оставляем ту часть полигона, которая ближе к текущему сайту
                poly = self._clip_polygon_by_halfplane(poly, mx, my, dx, dy)
                if not poly:
                    break

            cells.append(poly if poly else [])

        return cells

    def _clip_polygon_by_halfplane(self, polygon, px, py, nx, ny):
        """
        Обрезает полигон полуплоскостью.
        Оставляет часть полигона где dot((point - p), n) <= 0.
        (т.е. сторону ближе к текущему сайту)
        """
        if not polygon:
            return []

        output = []
        n = len(polygon)
        for i in range(n):
            curr = polygon[i]
            nxt = polygon[(i + 1) % n]
            d_curr = (curr[0] - px) * nx + (curr[1] - py) * ny
            d_next = (nxt[0] - px) * nx + (nxt[1] - py) * ny

            if d_curr <= 0:
                output.append(curr)
                if d_next > 0:
                    # Пересечение: curr внутри, next снаружи
                    t = d_curr / (d_curr - d_next)
                    ix = curr[0] + t * (nxt[0] - curr[0])
                    iy = curr[1] + t * (nxt[1] - curr[1])
                    output.append((ix, iy))
            elif d_next <= 0:
                # curr снаружи, next внутри
                t = d_curr / (d_curr - d_next)
                ix = curr[0] + t * (nxt[0] - curr[0])
                iy = curr[1] + t * (nxt[1] - curr[1])
                output.append((ix, iy))

        return output

    def _triangulate_polygon(self, polygon, center):
        """Триангулирует полигон методом веера от центра для Mesh."""
        if len(polygon) < 3:
            return [], []
        # Сортируем вершины по углу от центра
        import math
        cx, cy = center
        def angle_key(p):
            return math.atan2(p[1] - cy, p[0] - cx)
        sorted_poly = sorted(polygon, key=angle_key)

        vertices = []
        indices = []
        # Центр — вершина 0
        vertices.extend([cx, cy, 0, 0])
        for p in sorted_poly:
            vertices.extend([p[0], p[1], 0, 0])

        # Треугольники: (0, i, i+1) для каждого ребра полигона
        n = len(sorted_poly)
        for i in range(n):
            indices.extend([0, i + 1, ((i + 1) % n) + 1])

        return vertices, indices

    def draw_territories(self):
        """Лёгкая политическая заливка и подсвеченные изнутри государственные границы."""
        from design_system import FACTION_COLORS
        cursor = self.conn.cursor()
        try:
            cursor.execute('SELECT name, faction, coordinates FROM cities ORDER BY id')
            cities = cursor.fetchall()
        except sqlite3.Error:
            return
        finally:
            cursor.close()
        city_list = []
        for name, faction, raw_coords in cities:
            try:
                x, y = ast.literal_eval(raw_coords)
                city_list.append((x * self.map_scale + self.map_pos[0] + 38.5,
                                  y * self.map_scale + self.map_pos[1] + 38.5,
                                  faction, name))
            except (ValueError, TypeError, SyntaxError):
                continue
        if not city_list:
            return

        # Отступ удерживает политический слой внутри рамки пергамента.
        inset = 26 * self.map_scale
        x, y = self.map_pos
        clip_rect = (x + inset, y + inset,
                     x + self.base_map_width * self.map_scale - inset,
                     y + self.base_map_height * self.map_scale - inset)
        sites = tuple((city[0], city[1]) for city in city_list)
        geometry_key = (sites, clip_rect)
        if geometry_key != self._territory_geometry_key:
            cells = self._compute_voronoi_cells(sites, clip_rect)
            # Центр веера всегда внутри обрезанной ячейки, даже у края карты.
            meshes = []
            edges = {}
            for index, cell in enumerate(cells):
                if len(cell) < 3:
                    meshes.append(([], []))
                    continue
                center = (sum(p[0] for p in cell) / len(cell),
                          sum(p[1] for p in cell) / len(cell))
                meshes.append(self._triangulate_polygon(cell, center))
                for a, b in zip(cell, cell[1:] + cell[:1]):
                    key = tuple(sorted(((round(a[0], 3), round(a[1], 3)),
                                        (round(b[0], 3), round(b[1], 3)))))
                    edges.setdefault(key, []).append((index, a, b, center))
            self._territory_geometry = (cells, meshes, edges)
            self._territory_geometry_key = geometry_key
        cells, meshes, edges = self._territory_geometry
        if self._player_pulse_event:
            self._player_pulse_event.cancel()
            self._player_pulse_event = None
        self._player_territory_colors = []

        def tint(faction, alpha, highlight=False, pulse_floor=0.35):
            palette = FACTION_COLORS.get(faction)
            rgb = palette['primary'][:3] if palette else (0.65, 0.65, 0.61)
            if highlight:
                rgb = tuple(c * 0.65 + 0.35 for c in rgb)
            color = Color(*rgb, alpha)
            if palette and faction == self.current_player_kingdom:
                self._player_territory_colors.append((color, alpha * pulse_floor, alpha))
            return color

        with self.canvas:
            # Нейтральная земля сохраняет собственный цвет ландшафта.
            for index, city in enumerate(city_list):
                faction = city[2]
                vertices, indices = meshes[index]
                if vertices and FACTION_COLORS.get(faction):
                    tint(faction, 0.30 if faction == self.current_player_kingdom else 0.14)
                    Mesh(vertices=vertices, indices=indices, mode='triangles')

            for owners in edges.values():
                factions = {city_list[owner[0]][2] for owner in owners}
                # Не рисуем сетку между городами одной державы или нейтралами.
                if len(owners) > 1 and len(factions) == 1:
                    continue
                colored_owners = [o for o in owners if FACTION_COLORS.get(city_list[o[0]][2])]
                if not colored_owners:
                    continue
                _, a, b, _ = owners[0]
                player_border = any(city_list[o[0]][2] == self.current_player_kingdom
                                    for o in colored_owners)
                Color(0.08, 0.07, 0.09, 0.50 if player_border else 0.32)
                Line(points=[*a, *b], width=2.7 if player_border else 1.4)
                for index, a, b, center in colored_owners:
                    faction = city_list[index][2]
                    is_player = faction == self.current_player_kingdom
                    dx, dy = b[0] - a[0], b[1] - a[1]
                    length = math.hypot(dx, dy)
                    if length < 0.1:
                        continue
                    nx, ny = -dy / length, dx / length
                    if (center[0] - a[0]) * nx + (center[1] - a[1]) * ny < 0:
                        nx, ny = -nx, -ny
                    # Полупрозрачные полосы лежат только внутри собственной ячейки.
                    # Ограничение глубины не даёт им выйти за узкий угол полигона.
                    def inset_point(point, amount):
                        vx, vy = center[0] - point[0], center[1] - point[1]
                        distance = max(math.hypot(vx, vy), 0.001)
                        factor = min(amount / distance, 0.45)
                        return (point[0] + vx * factor, point[1] + vy * factor)
                    bands = (((22.0, 0.10), (12.0, 0.17), (5.0, 0.26)) if is_player
                             else ((14.0, 0.06), (8.0, 0.10), (3.5, 0.16)))
                    for width, alpha in bands:
                        ia = inset_point(a, width * self.map_scale)
                        ib = inset_point(b, width * self.map_scale)
                        tint(faction, alpha)
                        Mesh(vertices=[*a, 0, 0, *b, 0, 0, *ib, 0, 0, *ia, 0, 0],
                             indices=[0, 1, 2, 0, 2, 3], mode='triangles')
                    # На общей границе два тонких канта лежат по своим сторонам.
                    offset = 0.65 if len(colored_owners) > 1 else 0.0
                    points = [a[0] + nx * offset, a[1] + ny * offset,
                              b[0] + nx * offset, b[1] + ny * offset]
                    if is_player:
                        # Мягкий ореол дышит сильнее, читаемый контур остаётся всегда.
                        for width, alpha in ((7.0, 0.10), (4.0, 0.20)):
                            tint(faction, alpha, highlight=True, pulse_floor=0.08)
                            Line(points=points, width=width)
                    tint(faction, 0.95 if is_player else 0.82, pulse_floor=0.78)
                    Line(points=points, width=2.0 if is_player else 1.4)
                    tint(faction, 0.90 if is_player else 0.50,
                         highlight=True, pulse_floor=0.65)
                    Line(points=points, width=0.85 if is_player else 0.60)
        if self._player_territory_colors:
            self._start_player_pulse()

    def _start_player_pulse(self):
        """Заметное дыхание заливки и ореола с постоянно читаемой границей."""
        if self._player_pulse_event:
            self._player_pulse_event.cancel()
        colors = tuple(self._player_territory_colors)

        def _pulse(dt):
            self._player_pulse_phase = (self._player_pulse_phase + dt) % 2.8
            wave = 0.5 + 0.5 * math.cos(self._player_pulse_phase * 2 * math.pi / 2.8)
            for color, low, high in colors:
                color.a = low + (high - low) * wave

        _pulse(0)
        self._player_pulse_event = Clock.schedule_interval(_pulse, 1 / 30.0)

    def draw_fortresses(self):
        """Рисует крепости на карте с анимацией при смене фракции."""
        from city_war import read_city_war_states
        war_states = read_city_war_states(self.conn)
        self._undead_shield_data = []

        self.clear_widgets()
        self.fortress_icon_widgets.clear()
        self.fortress_data_for_canvas.clear()

        faction_images = {
            'Вампиры': 'files/buildings/vampires.png',
            'Север': 'files/buildings/people.png',
            'Эльфы': 'files/buildings/elfs.png',
            'Адепты': 'files/buildings/adepts.png',
            'Элины': 'files/buildings/poly.png',
            'Нежить': 'files/buildings/castle_death.png',
            'Мятежники': 'files/buildings/keig.png'
        }

        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT name, faction, coordinates, COALESCE(is_undead, 0) FROM cities")
            fortresses_data = cursor.fetchall()
        except sqlite3.Error as e:
            print(f"[ERROR] Ошибка при загрузке данных о городах: {e}")
            return
        finally:
            if 'cursor' in locals():
                cursor.close()

        if not fortresses_data:
            print("[DEBUG] Нет данных о крепостях в базе данных.")
            return

        capital_name = None
        capital_cursor = self.conn.cursor()
        try:
            capital_cursor.execute('SELECT capital_city FROM undead_invasion WHERE id = 1')
            capital_row = capital_cursor.fetchone()
            capital_name = capital_row[0] if capital_row else None
        except sqlite3.Error:
            pass
        finally:
            capital_cursor.close()

        for row in fortresses_data:
            fortress_name, kingdom, coords_str, is_undead_city = row
            try:
                coords = ast.literal_eval(coords_str)
                if len(coords) != 2:
                    raise ValueError(f"Координаты должны быть в формате [x, y], получено: {coords}")
            except Exception as e:
                print(f"[ERROR] Ошибка разбора координат для '{fortress_name}': {e}")
                continue

            fort_x, fort_y = coords
            drawn_x = fort_x * self.map_scale + self.map_pos[0]
            drawn_y = fort_y * self.map_scale + self.map_pos[1]

            # Города нежити всегда отображаются с иконкой castle_death
            if is_undead_city:
                image_path = 'files/buildings/castle_death.png'
            else:
                image_path = faction_images.get(kingdom, 'files/buildings/default.png')

            war_state = war_states.get(fortress_name)
            if war_state and war_state.ruined:
                image_path = ('files/buildings/ruined/undead.png' if is_undead_city or kingdom == 'Нежить'
                              else 'files/buildings/ruined/town.png')

            if not os.path.exists(image_path):
                image_path = 'files/buildings/default.png'

            self.previous_city_factions[fortress_name] = kingdom

            # --- Создание виджета иконки ---
            icon_widget = Image(
                source=image_path,
                size=(77, 77),
                pos=(drawn_x, drawn_y),
                allow_stretch=True,
                keep_ratio=True,
                mipmap=True,
            )
            self.add_widget(icon_widget)
            self.fortress_icon_widgets[fortress_name] = icon_widget

            # --- Анимация щита для городов нежити ---
            if is_undead_city:
                cx = drawn_x + 38.5  # Центр иконки 77x77
                cy = drawn_y + 38.5
                # Определяем столицу нежити
                _is_capital = capital_name == fortress_name
                self._undead_shield_data.append((cx, cy, _is_capital))

            # --- Сохраняем данные для кликов ---
            self.fortress_data_for_canvas.append((fortress_name, kingdom, fort_x, fort_y, drawn_x, drawn_y))  # ← Исправлена скобка

            # --- Рисуем название города с обводкой ---
            display_name = f"{fortress_name}({kingdom})"

            text_texture = self._get_city_label_texture(display_name)
            text_width, text_height = text_texture.size

            text_x = drawn_x + (40 - text_width) / 2
            text_y = drawn_y - text_height - 5

            outline_width = 2

            with self.canvas:  # ← Исправлены отступы
                Color(1, 1, 1, 1)
                offsets = [
                    (-outline_width, -outline_width),
                    (-outline_width, 0),
                    (-outline_width, outline_width),
                    (0, outline_width),
                    (outline_width, outline_width),
                    (outline_width, 0),
                    (outline_width, -outline_width),
                    (0, -outline_width)
                ]

                for offset_x, offset_y in offsets:
                    Rectangle(
                        texture=text_texture,
                        pos=(text_x + offset_x, text_y + offset_y),
                        size=(text_width, text_height)
                    )

                Color(0, 0, 0, 1)
                Rectangle(
                    texture=text_texture,
                    pos=(text_x, text_y),
                    size=(text_width, text_height)
                )

        # Погода, грозовые тучи и чума находятся в одном ограниченном слое.
        self._sync_map_atmosphere()

        # Координаты меняются только при изменении состава городов или масштаба.
        icon_positions = tuple((name, x, y) for name, _, _, _, x, y in self.fortress_data_for_canvas)
        if icon_positions == getattr(self, '_saved_icon_positions', None):
            return
        try:
            cursor2 = self.conn.cursor()
            cursor2.executemany(
                'UPDATE cities SET icon_coordinates = ? WHERE name = ?',
                [(str([x, y]), name) for name, x, y in icon_positions]
            )
            self.conn.commit()
            self._saved_icon_positions = icon_positions
        except (sqlite3.Error, SystemError) as e:
            # Может конфликтовать с фоновым потоком ИИ — не критично
            pass
        except Exception:
            pass
        finally:
            try:
                cursor2.close()
            except Exception:
                pass

    def _sync_map_atmosphere(self):
        """Обновляет данные эффектов; между изменениями работает один общий таймер."""
        from map_atmosphere import MapAtmosphere
        if self._map_atmosphere is None:
            self._map_atmosphere = MapAtmosphere()
        layer = self._map_atmosphere
        layer.configure(self.map_pos, self.map_scale,
                        (self.base_map_width, self.base_map_height))
        if layer.parent is None:
            self.add_widget(layer)
        layer.set_storms(self._undead_shield_data)
        from city_war import read_city_war_states, current_turn
        war_cities = []
        for name, faction, coords in self.conn.execute('SELECT name, faction, coordinates FROM cities'):
            try:
                x, y = ast.literal_eval(coords)
                war_cities.append((name, x, y, faction))
            except (ValueError, TypeError, SyntaxError):
                continue
        layer.city_effects.sync(war_cities, read_city_war_states(self.conn), current_turn(self.conn))
        cursor = self.conn.cursor()
        try:
            cursor.execute('SELECT current_season FROM season WHERE id = 1')
            row = cursor.fetchone()
            layer.set_season(row[0] if row else None)
        except sqlite3.Error:
            layer.set_season(None)
        try:
            cursor.execute('SELECT invasion_started FROM undead_invasion WHERE id = 1')
            row = cursor.fetchone()
            active = bool(row and row[0] == 1)
            effects, sources = [], []
            if active:
                cursor.execute('SELECT city_name, losses, coord_x, coord_y FROM plague_effects ORDER BY city_name')
                effects = [tuple(row) for row in cursor.fetchall()]
                cursor.execute('SELECT name, coordinates, faction FROM cities ORDER BY name')
                eligible_names = set()
                for name, coords, faction in cursor.fetchall():
                    if faction not in (None, 'Нейтрал'):
                        eligible_names.add(name)
                    if faction != 'Нежить':
                        continue
                    try:
                        x, y = ast.literal_eval(coords)
                        sources.append((name, x, y))
                    except (ValueError, TypeError, SyntaxError):
                        continue
                effects = [effect for effect in effects if effect[0] in eligible_names]
            layer.set_plague(effects, sources, active=active)
        except sqlite3.Error:
            layer.set_plague([], [], active=False)
        finally:
            cursor.close()

    def animate_city_capture(self, city_data):
        """Compatibility entry point; effects never resize or move the city icon."""
        if self._map_atmosphere is not None:
            self._map_atmosphere.city_effects.play(
                city_data['name'], city_data.get('kind', 'peace'), city_data['new_faction'])

    def find_and_set_player_city_icon(self):
        """Ищет и устанавливает ссылку на виджет иконки города игрока."""
        if not self.current_player_kingdom or not self.fortress_icon_widgets:
            print("[MapWidget] Не могу найти иконку: нет данных об игроке или городах (find_and_set).")
            return False

        # Получаем города игрока из БД
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT name FROM cities WHERE faction = ?", (self.current_player_kingdom,))
            player_cities = cursor.fetchall()
        except sqlite3.Error as e:
            print(f"[MapWidget] Ошибка при поиске городов игрока: {e}")
            return False
        finally:
            cursor.close()

        if not player_cities:
            print(f"[MapWidget] У игрока ({self.current_player_kingdom}) нет городов.")
            return False

        # Берем первый город игрока
        player_city_name = player_cities[0][0]
        if player_city_name in self.fortress_icon_widgets:
            self.player_city_icon_widget = self.fortress_icon_widgets[player_city_name]
            print(f"[MapWidget] Иконка города игрока '{player_city_name}' найдена и установлена.")
            return True
        else:
            print(f"[MapWidget] Виджет иконки для города игрока '{player_city_name}' не найден.")
            return False

    def blink_player_city_icon(self, times=5, duration=0.3):
        """Анимирует мигание виджета иконки города игрока."""
        if not self.player_city_icon_widget:
            print("[MapWidget] Иконка города игрока не найдена для мигания.")
            return

        print(f"[MapWidget] Запуск анимации мигания ({times} раз) для виджета {self.player_city_icon_widget}")

        # Создаем цепочку анимаций
        anim = Animation(opacity=0.0, duration=duration)  # Исчезновение 1
        for i in range(times - 1):  # Остальные (times-1) циклов
            anim += Animation(opacity=1.0, duration=duration)  # Появление
            anim += Animation(opacity=0.0, duration=duration)  # Исчезновение
        anim += Animation(opacity=1.0, duration=duration)  # Последнее появление

        # Запускаем анимацию
        anim.start(self.player_city_icon_widget)
        print("[MapWidget] Анимация мигания запущена для иконки города игрока.")

    def _schedule_blink(self, dt):
        """Вспомогательный метод для планирования мигания."""
        if not self.has_blinked:  # Проверяем флаг
            if self.find_and_set_player_city_icon():
                self.blink_player_city_icon()
                self.has_blinked = True  # Устанавливаем флаг после запуска
            else:
                print("[MapWidget] Повторная попытка найти иконку через 1 секунду...")
                Clock.schedule_once(
                    lambda dt: (
                            not self.has_blinked and
                            self.find_and_set_player_city_icon() and
                            (self.blink_player_city_icon(), setattr(self, 'has_blinked', True)) or
                            print("[MapWidget] Повторная попытка не удалась.")
                    ), 1.0
                )

    def get_random_map_source(self):
        """Выбирает случайную карту из папки files/map/generate"""
        map_dir = 'files/map/generate'
        map_files = [f for f in os.listdir(map_dir) if f.startswith('map_') and f.endswith('.png')]
        if not map_files:
            raise FileNotFoundError("Не найдено файлов с картами в директории.")
        print("Выбор случайной карты...")
        chosen_map = random.choice(map_files)
        print(f"Карта выбрана: {chosen_map}")
        return os.path.join(map_dir, chosen_map)

    def calculate_scale(self):
        """Рассчитывает масштаб карты под текущий экран"""
        scale_width = Window.width / self.base_map_width
        scale_height = Window.height / self.base_map_height
        return min(scale_width, scale_height) * 0.9  # Добавляем небольшой отступ

    def calculate_centered_position(self):
        """Вычисляет центрированную позицию карты"""
        scaled_width = self.base_map_width * self.map_scale
        scaled_height = self.base_map_height * self.map_scale
        x = (Window.width - scaled_width) / 2
        y = (Window.height - scaled_height) / 2
        return [x, y]

    def _get_city_label_texture(self, display_name):
        texture = self._city_label_cache.get(display_name)
        if texture is None:
            label = CoreLabel(text=display_name, font_size=25, color=(1, 1, 1, 1))
            label.refresh()
            texture = label.texture
            if len(self._city_label_cache) >= 128:
                self._city_label_cache.clear()
            self._city_label_cache[display_name] = texture
        return texture

    def draw_roads(self):
        """Рисует грунтовые тракты под зданиями и подписями, сохраняя игровой граф."""
        from map_roads import build_transport_network, draw_transport_layer
        from map_terrain import TerrainView
        cursor = self.conn.cursor()
        try:
            cursor.execute('SELECT id, name, faction, coordinates FROM cities ORDER BY id')
            rows = cursor.fetchall()
            cursor.execute('SELECT city1, city2 FROM roads ORDER BY id')
            roads = tuple(tuple(row) for row in cursor.fetchall())
        except sqlite3.Error as error:
            print(f'Ошибка при загрузке дорог: {error}')
            return
        finally:
            cursor.close()
        cities, labels = {}, {}
        for city_id, name, faction, raw_coords in rows:
            try:
                x, y = ast.literal_eval(raw_coords)
            except (ValueError, TypeError, SyntaxError):
                continue
            x, y = x * self.map_scale + self.map_pos[0], y * self.map_scale + self.map_pos[1]
            cities[city_id] = (x, y)
            width, height = self._get_city_label_texture(f'{name}({faction})').size
            left = x + (40 - width) / 2
            labels[city_id] = (left - 5, y - height - 10, left + width + 5, y - 1)
        inset = 30 * self.map_scale
        bounds = (self.map_pos[0] + inset, self.map_pos[1] + inset,
                  self.map_pos[0] + self.base_map_width * self.map_scale - inset,
                  self.map_pos[1] + self.base_map_height * self.map_scale - inset)
        terrain_data = getattr(self, '_map_terrain', None)
        terrain = TerrainView(terrain_data, self.map_pos, self.map_scale) if terrain_data else None
        key = (tuple(cities.items()), roads, tuple(labels.items()), bounds, self.map_scale, id(terrain_data))
        if key != self._road_geometry_key:
            self._road_geometry = build_transport_network(cities, roads, labels, bounds, self.map_scale, terrain)
            self._road_geometry_key = key
        if self._road_group is not None:
            # Do not clear canvas.after: other map effects may own instructions there.
            if self._road_group in self.canvas.children:
                self.canvas.remove(self._road_group)
        self._road_group = draw_transport_layer(self._road_geometry, self.map_scale)
        self.canvas.add(self._road_group)

    def calculate_manhattan_distance(self, source_coords, destination_coords):
        """Вычисляет манхэттенское расстояние между точками"""
        return abs(source_coords[0] - destination_coords[0]) + abs(source_coords[1] - destination_coords[1])

    def check_fortress_click(self, touch):
        """Проверяет нажатие на крепость (использует сохранённые оригинальные координаты)."""
        # self.fortress_data_for_canvas: [(name, kingdom, fort_x, fort_y, drawn_x, drawn_y), ...]
        for fortress_name, kingdom, fort_x, fort_y, drawn_x, drawn_y in self.fortress_data_for_canvas:
            icon_widget = self.fortress_icon_widgets.get(fortress_name)
            if icon_widget and icon_widget.collide_point(*touch.pos):
                # Используем оригинальные координаты (числа), а не строку из БД
                city_coords_for_popup = (fort_x, fort_y)

                # Сохраняем последний кликнутый город (по имени)
                save_last_clicked_city(self.conn, fortress_name)

                # Создаём popup и передаём координаты как tuple (как в старой версии)
                popup = FortressInfoPopup(
                    ai_fraction=kingdom,
                    city_coords=city_coords_for_popup,
                    player_fraction=self.current_player_kingdom,
                    conn=self.conn
                )
                popup.open()

                print(
                    f"Крепость '{fortress_name}' (координаты: {city_coords_for_popup}) принадлежит "
                    f"{'вашему' if kingdom == self.current_player_kingdom else 'чужому'} королевству ({kingdom})!"
                )
                return

    def on_touch_up(self, touch):
        """Обрабатывает нажатия на карту"""
        self.check_fortress_click(touch)


class ModernButton(StrategyButton):
    pass


class RectangularButton(Button):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.background_color = (0, 0, 0, 0)  # Отключаем стандартный фон

    def update_rect(self, *args):
        self.rect.pos = self.pos
        self.rect.size = self.size

        self.border_rect.pos = (
            self.pos[0] - self.border_width / 2,
            self.pos[1] - self.border_width / 2
        )
        self.border_rect.size = (
            self.size[0] + self.border_width,
            self.size[1] + self.border_width
        )

    def show_border(self, show=True):
        """Показываем/скрываем рамку"""
        self.border_rect_color.a = 1 if show else 0


class FactionButton(FactionChoice):
    pass


class ModernSpinnerOption(SpinnerOption):
    """Стилизованный элемент выпадающего списка."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.background_normal = ''
        self.background_down = ''
        self.background_color = (0.14, 0.20, 0.30, 1)
        self.color = (0.92, 0.95, 1.0, 1)
        self.bold = False
        self.halign = 'center'

        with self.canvas.before:
            self._sep_color = Color(0.25, 0.35, 0.50, 0.6)
            self._sep_line = Line(points=[], width=dp(1))

        self.bind(pos=self._update_sep, size=self._update_sep)
        self.bind(on_press=self._on_press, on_release=self._on_release)

    def _update_sep(self, *_):
        self._sep_line.points = [self.x, self.y, self.right, self.y]

    def _on_press(self, *_):
        Animation(background_color=(0.20, 0.40, 0.65, 1), duration=0.10).start(self)

    def _on_release(self, *_):
        Animation(background_color=(0.14, 0.20, 0.30, 1), duration=0.15).start(self)


class ModernSpinner(Spinner):
    """Стилизованный выпадающий список"""
    bg_color = ListProperty([0.16, 0.24, 0.36, 1])

    def __init__(self, **kwargs):
        kwargs.setdefault('option_cls', ModernSpinnerOption)
        super().__init__(**kwargs)
        self.background_normal = ''
        self.background_down = ''
        self.background_color = self.bg_color
        self.color = (0.92, 0.95, 1.0, 1)
        self.bold = False

        # Подгоняем высоту дропдауна под содержимое
        self.bind(on_is_open=self._style_dropdown)

        # Анимация при наведении (для ПК)
        if platform != 'android' and platform != 'ios':
            self.bind(
                on_enter=self.on_hover_enter,
                on_leave=self.on_hover_leave
            )

    def _style_dropdown(self, _, is_open):
        if is_open and self._dropdown:
            dd = self._dropdown
            dd.background = ''
            with dd.canvas.before:
                Color(0.10, 0.15, 0.24, 0.97)
                RoundedRectangle(pos=dd.pos, size=dd.size, radius=[dp(10)])
                Color(0.25, 0.45, 0.72, 0.7)
                Line(rounded_rectangle=[dd.x, dd.y, dd.width, dd.height, dp(10)], width=dp(1.2))

    def on_hover_enter(self, *args):
        Animation(background_color=[min(c * 1.25, 1.0) for c in self.bg_color[:3]] + [1], duration=0.15).start(self)

    def on_hover_leave(self, *args):
        Animation(background_color=self.bg_color, duration=0.15).start(self)


class KingdomSelectionWidget(MDFloatLayout):
    def __init__(self, conn, selected_map=None, **kwargs):
        super().__init__(**kwargs)
        self.conn, self.selected_map = conn, selected_map
        from frontend_ui import build_campaign_setup
        build_campaign_setup(self)

    def on_ideology_selected(self, spinner, text):
        """Обработка выбора идеологии"""
        if text == 'Случайная':
            self.selected_ideology = 'random'
            # Обновляем текст, цвет и иконку
            self.ideology_bonus_label.text = "Идеология будет выбрана случайно"
            self.ideology_bonus_label.color = (0.8, 0.8, 0.8, 1)
            self.ideology_bonus_icon.source = 'files/pict/menu/bonus_icon.png'
        elif text == 'Смирение':
            self.selected_ideology = 'Смирение'
            # Обновляем текст, цвет и иконку
            self.ideology_bonus_label.text = "+700% к доходам от налогов"
            self.ideology_bonus_label.color = (0.5, 0.8, 1.0, 1)  # Голубой цвет
            self.ideology_bonus_icon.source = 'files/status/resource_box/coin.png'
            # Важно: перезагрузить текстуру изображения
            self.ideology_bonus_icon.reload()
        elif text == 'Борьба':
            self.selected_ideology = 'Борьба'
            # Обновляем текст, цвет и иконку
            self.ideology_bonus_label.text = "+550% к добыче кристаллов"
            self.ideology_bonus_label.color = (1.0, 0.5, 0.5, 1)  # Красноватый цвет
            self.ideology_bonus_icon.source = 'files/status/resource_box/crystal.png'
            # Важно: перезагрузить текстуру изображения
            self.ideology_bonus_icon.reload()
        print(f"Выбрана идеология: {self.selected_ideology}")

    def on_allies_selected(self, spinner, text):
        """Обработка выбора количества союзников"""
        if text == 'Случайное количество':
            self.selected_allies = 'random'
            # Обновляем текст и цвет в self.allies_count_label
            self.allies_count_label.text = "Случайно 1 или 2 союзника"
            self.allies_count_label.color = (0.8, 0.8, 0.8, 1)
        elif text == '1':
            self.selected_allies = 1
            # Обновляем текст и цвет в self.allies_count_label
            self.allies_count_label.text = "1 фракция с такой же идеологией"
            self.allies_count_label.color = (0.5, 1.0, 0.5, 1)  # Зеленый
        elif text == '2':
            self.selected_allies = 2
            # Обновляем текст и цвет в self.allies_count_label
            self.allies_count_label.text = "2 фракции с такой же идеологией"
            self.allies_count_label.color = (0.5, 1.0, 0.5, 1)  # Зеленый
        print(f"Выбрано союзников: {self.selected_allies}")

    def animate_in(self):
        from ui_motion import enter
        enter(self.main_container)

    def loop_video(self, instance):
        if not instance:
            return
        instance.state = 'stop'
        Clock.schedule_once(lambda dt: setattr(instance, 'state', 'play'), 0.1)

    def calculate_panel_height(self, btn_height, spacing, padding):
        num_buttons = len(self.faction_data)
        return (btn_height * num_buttons) + (spacing * (num_buttons - 1)) + (padding[1] + padding[3])

    def back_to_menu(self, instance):
        if getattr(self, 'buttons_locked', False):
            return
        # Останавливаем видео и отменяем проверку
        if self._video_check_event:
            self._video_check_event.cancel()
        if self.bg_video:
            self.bg_video.state = 'stop'
        from kivy.app import App
        app = App.get_running_app()
        app.root.clear_widgets()
        app.root.add_widget(MenuWidget(self.conn))

    def load_factions_from_db(self):
        """Загрузка фракций из БД"""
        factions = []
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT DISTINCT faction1 
                FROM diplomacies_default
                WHERE faction1 != 'Мятежники'
            """)
            rows = cursor.fetchall()
            for row in rows:
                faction_name = row[0]
                if faction_name:
                    factions.append({"name": faction_name})
        except sqlite3.Error as e:
            print(f"Ошибка при загрузке данных из базы данных: {e}")
        return factions

    def select_kingdom(self, instance):
        """Выбор фракции"""
        if getattr(self, 'buttons_locked', False):
            return

        # Сбрасываем предыдущую выбранную кнопку
        if self.selected_button and self.selected_button is not instance:
            if hasattr(self.selected_button, 'set_selected'):
                self.selected_button.set_selected(False)

        # Выделяем новую кнопку
        self.selected_button = instance
        if hasattr(instance, 'set_selected'):
            instance.set_selected(True)

        kingdom_name = instance.text
        self._switch_faction_bg(kingdom_name)
        self.update_faction_stats(kingdom_name)
        from kivy.app import App
        app = App.get_running_app()
        app.selected_kingdom = kingdom_name

    def _switch_faction_bg(self, faction_name):
        from frontend_ui import switch_faction_art
        switch_faction_art(self, faction_name)

    FACTION_ABILITIES = {
        'Север': '[b]Шквал[/b] — если бонусы увеличили урон в 20+ раз, x1.7 к урону',
        'Эльфы': '[b]Природное исцеление[/b] — 10% погибших возвращаются в строй',
        'Вампиры': '[b]Вампиризм[/b] — 5% убитых врагов воскресают как ваши юниты',
        'Адепты': '[b]Оплот[/b] — если бонусы увеличили защиту в 20+ раз, +35% к защите',
        'Элины': '[b]Торговая империя[/b] — 2 перемещения/атаки за ход, +35% кристаллы, +25% торговля',
    }

    def update_faction_stats(self, kingdom):
        """Обновляет полосы-бары характеристик и способность выбранной фракции."""
        # Шкала от 0.0 до 1.0 (5 уровней: 0.2, 0.4, 0.6, 0.8, 1.0)
        # Баланс по economic.py: tax_rate, money_loss, food_loss, buildings_info,
        # фракционные бонусы (Элины: кристаллы; Адепты: защита; и т.д.)
        stats = {
            "Север":   {"Экономика": 0.8, "Кристаллы": 0.3, "Армия": 0.6},
            "Эльфы":   {"Экономика": 0.55, "Кристаллы": 0.55, "Армия": 0.5},
            "Вампиры": {"Экономика": 0.45, "Кристаллы": 0.5, "Армия": 0.8},
            "Элины":   {"Экономика": 0.3, "Кристаллы": 0.9, "Армия": 0.3},
            "Адепты":  {"Экономика": 0.35, "Кристаллы": 0.5, "Армия": 0.8},
        }
        data = stats.get(kingdom)
        if not data:
            return

        for stat_name, bar_info in self._stat_bars.items():
            target = data.get(stat_name, 0.0)
            bar_info['ratio'][0] = target
            bar_info['updater']()

        ability_text = self.FACTION_ABILITIES.get(kingdom, '')
        if hasattr(self, 'faction_ability_label'):
            self.faction_ability_label.text = ability_text

    def start_game(self, instance):
        """Начало игры с сохранением выбора игрока"""
        if getattr(self, 'buttons_locked', False):
            return
        if not getattr(self, 'selected_button', None):
            print("Фракция не выбрана.")
            return
        # Блокируем кнопки
        self.buttons_locked = True
        self.disable_all_buttons(True)
        # Останавливаем фоновое видео и отменяем проверку
        if self._video_check_event:
            self._video_check_event.cancel()
        if self.bg_video:
            self.bg_video.state = 'stop'

        self.start_video = None
        self.overlay = None
        Clock.schedule_once(lambda _: self.cleanup_and_start_game(), 0)

    def on_start_video_end(self, instance, value):
        if value or (self.start_video and self.start_video.state == 'stop'):
            print("Видео завершено, начинаем игру...")
            self.cleanup_and_start_game()

    def force_start_game(self, dt):
        print("Резервный таймер сработал")
        if self.start_video:
            self.start_video.state = 'stop'
        self.cleanup_and_start_game()

    def cleanup_and_start_game(self):
        """Показывает загрузку до подготовки базы и создания карты."""
        if getattr(self, '_game_loading', None) is not None:
            return
        from game_loading import GameLoadingPanel
        app = App.get_running_app()
        selected_kingdom = app.selected_kingdom
        self.buttons_locked = True
        self.disable_all_buttons(True)
        state = {}

        def prepare_world():
            clear_tables(self.conn)
            self.conn.commit()
            restore_from_backup(self.conn)
            text = self.ideology_spinner.text if hasattr(self, 'ideology_spinner') else 'Случайная'
            self.selected_ideology = text if text in ('Смирение', 'Борьба') else 'random'

        def prepare_map():
            state['map'] = MapWidget(selected_kingdom=selected_kingdom,
                                     player_kingdom=selected_kingdom, conn=self.conn)

        def prepare_interface():
            cities = load_cities_from_db(self.conn, selected_kingdom)
            state['screen'] = GameScreen(
                selected_kingdom, cities,
                player_ideology=self.selected_ideology,
                player_allies=self.selected_allies,
                tutorial_enabled=self.tutorial_enabled, conn=self.conn)

        def reveal_map():
            # The modal belongs to Window, so replacing root children keeps it visible.
            app.root.clear_widgets()
            app.root.add_widget(state['map'])
            app.root.add_widget(state['screen'])

        def finished():
            self._game_loading = None
            if hasattr(state['map'], 'blink_player_city_icon'):
                Clock.schedule_once(lambda dt: state['map'].blink_player_city_icon(), 1.0)

        def failed(error):
            map_widget = state.get('map')
            if map_widget is not None and map_widget.parent is None:
                map_widget.on_parent(map_widget, None)
            self.buttons_locked = False
            self.disable_all_buttons(False)
            # Keep the error modal until the player closes it, then allow another attempt.
            self._game_loading.bind(on_dismiss=lambda *_: setattr(self, '_game_loading', None))

        self._game_loading = GameLoadingPanel([
            ('Подготавливаем новый мир…', prepare_world),
            ('Создаём города, территории и дороги…', prepare_map),
            ('Подготавливаем интерфейс…', prepare_interface),
            ('Открываем карту…', reveal_map),
        ], on_complete=finished, on_error=failed)
        self._game_loading.start()

    def disable_all_buttons(self, disabled=True):
        for child in self.main_container.walk():
            if isinstance(child, (Button, Spinner)):
                child.disabled = disabled


class RoundedButton(StrategyButton):
    pass


from kivy.graphics import Color, RoundedRectangle, Line, Ellipse, Rectangle
from kivy.properties import ListProperty, NumericProperty, BooleanProperty
import math
import random


class GameButton(MenuButton):
    pass


class AnimatedLabel(Label):
    """Метка с анимацией и черной обводкой"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.animation = None
        # Устанавливаем черную обводку по умолчанию
        if 'outline_color' not in kwargs:
            self.outline_color = (0, 0, 0, 1)  # Черная обводка
        if 'outline_width' not in kwargs:
            self.outline_width = 3  # Толстая обводка для заголовка

    def start_glow_animation(self):
        if self.animation:
            self.animation.cancel(self)

        # Анимация с черной обводкой, которая становится светлее
        anim = Animation(
            outline_color=(0.8, 0.8, 1, 1),  # Светло-синее свечение
            duration=2.0
        ) + Animation(
            outline_color=(0, 0, 0, 1),  # Возврат к черной обводке
            duration=2.0
        )
        anim.repeat = True
        anim.start(self)


class TutorialFactionScreen(FloatLayout):
    """Экран выбора фракции для обучения"""

    FACTIONS = ['Вампиры', 'Эльфы', 'Север', 'Адепты', 'Элины']
    FACTION_IMAGES = {
        'Вампиры': 'files/buildings/vampires.png',
        'Север': 'files/buildings/people.png',
        'Эльфы': 'files/buildings/elfs.png',
        'Адепты': 'files/buildings/adepts.png',
        'Элины': 'files/buildings/poly.png',
    }
    FACTION_COLORS = {
        'Вампиры': (0.40, 0.10, 0.50, 1),
        'Эльфы': (0.2, 0.7, 0.3, 1),
        'Север': (0.2, 0.4, 0.9, 1),
        'Адепты': (0.85, 0.45, 0.10, 1),
        'Элины': (0.95, 0.90, 0.15, 1),
    }
    FACTION_IDEOLOGY = {
        'Север': 'Смирение',
        'Вампиры': 'Смирение',
        'Эльфы': 'Смирение',
        'Адепты': 'Борьба',
        'Элины': 'Борьба',
    }
    FACTION_HINT = {
        'Север': 'Смирение: +700% к доходам от налогов',
        'Вампиры': 'Смирение: +700% к доходам от налогов',
        'Эльфы': 'Смирение: +700% к доходам от налогов',
        'Адепты': 'Борьба: +550% к добыче кристаллов',
        'Элины': 'Борьба: +550% к добыче кристаллов',
    }

    def __init__(self, conn, **kwargs):
        super().__init__(**kwargs)
        self.conn = conn
        self.selected_faction = None
        self.selected_btn = None

        # Фон
        with self.canvas.before:
            self._bg = Rectangle(
                source='files/menu/vampire.jpg',
                pos=self.pos, size=self.size
            )
            Color(0, 0, 0, 0.6)
            self._overlay = Rectangle(pos=self.pos, size=self.size)
        self.bind(
            pos=self._update_bg, size=self._update_bg
        )

        self._build_ui()

    def _update_bg(self, *args):
        self._bg.pos = self.pos
        self._bg.size = self.size
        self._overlay.pos = self.pos
        self._overlay.size = self.size

    def _build_ui(self):
        from frontend_ui import build_tutorial_picker
        build_tutorial_picker(self)

    def _select_faction(self, faction):
        self.selected_faction = faction
        for name, button in self._faction_btns.items():
            button.set_selected(name == faction)
        self.start_btn.disabled = False

    def _go_back(self, instance):
        app = App.get_running_app()
        app.root.clear_widgets()
        app.root.add_widget(MenuWidget(self.conn))

    def _start_tutorial(self, instance):
        if not self.selected_faction:
            return

        restore_from_backup(self.conn)

        app = App.get_running_app()
        app.selected_kingdom = self.selected_faction

        MapWidget = globals().get('MapWidget')
        GameScreen = globals().get('GameScreen')
        if not MapWidget or not GameScreen:
            import sys
            current_module = sys.modules[__name__]
            MapWidget = getattr(current_module, 'MapWidget', None)
            GameScreen = getattr(current_module, 'GameScreen', None)

        if MapWidget and GameScreen:
            map_widget = MapWidget(
                selected_kingdom=self.selected_faction,
                player_kingdom=self.selected_faction,
                conn=self.conn
            )
            cities = load_cities_from_db(self.conn, self.selected_faction)
            tutorial_ideology = self.FACTION_IDEOLOGY.get(self.selected_faction, 'Смирение')
            game_screen = GameScreen(
                self.selected_faction,
                cities,
                player_ideology=tutorial_ideology,
                player_allies=['Случайно 1 или 2 союзника'],
                tutorial_enabled=True,
                conn=self.conn
            )
            app.root.clear_widgets()
            app.root.add_widget(map_widget)
            app.root.add_widget(game_screen)
            if hasattr(map_widget, 'blink_player_city_icon'):
                Clock.schedule_once(lambda dt: map_widget.blink_player_city_icon(), 1.0)


class MenuWidget(FloatLayout):
    def __init__(self, conn, selected_map=None, **kwargs):
        super().__init__(**kwargs)
        self.conn, self.selected_map = conn, selected_map
        self._particles, self._particle_event = [], None
        from frontend_ui import build_main_menu
        build_main_menu(self)

    def _spawn_particle(self, dt):
        """Атмосферные частицы на фоне."""
        if len(self._particles) > 15:
            return
        import random as _rnd
        w = self.width or Window.width
        h = self.height or Window.height
        p = {
            'x': _rnd.uniform(0, w), 'y': -dp(5),
            'size': _rnd.uniform(dp(1.5), dp(4)),
            'alpha': _rnd.uniform(0.08, 0.25),
            'speed': _rnd.uniform(dp(10), dp(30)),
            'color': _rnd.choice([
                (0.85, 0.75, 0.45),
                (0.5, 0.65, 0.9),
                (0.7, 0.5, 0.8),
            ])
        }
        self._particles.append(p)
        if not hasattr(self, '_ptcl_evt'):
            self._ptcl_evt = Clock.schedule_interval(self._update_particles, 0.033)

    def _update_particles(self, dt):
        h = self.height or Window.height
        self._particles = [p for p in self._particles if p['y'] < h and p['alpha'] > 0.01]
        for p in self._particles:
            p['y'] += p['speed'] * dt
            p['alpha'] *= 0.997

        if hasattr(self, '_ptcl_group'):
            self.canvas.after.remove(self._ptcl_group)
        from kivy.graphics import InstructionGroup, Ellipse as _Ell
        grp = InstructionGroup()
        for p in self._particles:
            grp.add(Color(*p['color'], p['alpha']))
            grp.add(_Ell(pos=(p['x'], p['y']), size=(p['size'], p['size'])))
        self._ptcl_group = grp
        self.canvas.after.add(grp)

    def on_parent(self, widget, parent):
        if parent is None:
            if self._particle_event:
                self._particle_event.cancel()
            if hasattr(self, '_ptcl_evt'):
                self._ptcl_evt.cancel()

    def select_button(self, button):
        """Выделяет выбранную кнопку"""
        if self.selected_button and self.selected_button is not button:
            self.selected_button.glow_intensity = 0.0
            self.selected_button.update_canvas()

        button.glow_intensity = 0.9
        button.update_canvas()
        self.selected_button = button

    def on_button_press(self, button):
        """Обработка нажатия на кнопку мышью"""
        self.select_button(button)

    def activate_selected_button(self):
        """Активирует выбранную кнопку"""
        if self.selected_button:
            # Находим действие для этой кнопки
            for btn in self.buttons:
                if btn == self.selected_button:
                    # Запускаем действие кнопки
                    self.selected_button.dispatch('on_release')
                    break

    # === Методы действий кнопок ===
    def open_dossier(self, instance):
        app = App.get_running_app()
        app.root.clear_widgets()
        app.root.add_widget(DossierScreen(self.conn))

    def open_how_to_play(self, instance):
        app = App.get_running_app()
        app.root.clear_widgets()
        app.root.add_widget(Lor(self.conn))

    def open_author(self, instance):
        app = App.get_running_app()
        app.root.clear_widgets()
        app.root.add_widget(AuthorScreen(self.conn))

    def start_game(self, instance):
        app = App.get_running_app()
        app.root.clear_widgets()
        app.root.add_widget(KingdomSelectionWidget(self.conn))

    def open_tutorial(self, instance):
        app = App.get_running_app()
        app.root.clear_widgets()
        app.root.add_widget(TutorialFactionScreen(self.conn))

    def exit_game(self, instance):
        app = App.get_running_app()
        app.on_stop()
        app.stop()


def ui_scale():
    base_width = 400
    scale = Window.width / base_width
    return max(0.85, min(scale, 1.4))


def sdp(x):
    return dp(x * ui_scale())


def ssp(x):
    return sp(x * ui_scale())


class DossierScreen(Screen):

    FACTION_COLORS = {
        'Вампиры': (0.40, 0.10, 0.50, 1),
        'Север':   (0.10, 0.50, 0.85, 1),
        'Эльфы':   (0.15, 0.72, 0.35, 1),
        'Адепты':  (0.85, 0.45, 0.10, 1),
        'Элины':   (0.95, 0.90, 0.15, 1),
    }

    def __init__(self, conn, **kwargs):
        super().__init__(**kwargs)
        self.conn = conn
        self.tabs = None

        # Фоновое изображение
        with self.canvas.before:
            self._dossier_bg = Rectangle(
                source='files/menu/vampire.jpg',
                pos=self.pos,
                size=self.size
            )
            Color(0, 0, 0, 0.55)
            self._dossier_overlay = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._upd_dossier_bg, size=self._upd_dossier_bg)

        self.build_ui()
        Window.bind(on_resize=self.on_window_resize)

    def _upd_dossier_bg(self, *args):
        self._dossier_bg.pos = self.pos
        self._dossier_bg.size = self.size
        self._dossier_overlay.pos = self.pos
        self._dossier_overlay.size = self.size

    # Таблицы званий для каждой фракции
    RANK_TABLES = {
        'Вампиры': [
            ("Повелитель ночи", 1),
            ("Вечный граф", 2),
            ("Темный лорд", 3),
            ("Князь тьмы", 4),
            ("Старший вампир", 5),
            ("Ночной страж", 6),
            ("Теневой охотник", 7),
            ("Призрачный убийца", 8),
            ("Темный воитель", 9),
            ("Ночной рейнджер", 10),
            ("Младший вампир", 11),
            ("Темный слуга", 12),
            ("Послушник вампира", 13),
            ("Жнец", 14),
            ("Капитан следопытов", 15),
            ("Багровый следопыт", 16),
            ("Вестник смерти", 17),
            ("Пепел прошлого", 18),
            ("Укушенный", 19),
        ],
        'Север': [
            ("Министр Войны", 1),
            ("Верховный маршал", 2),
            ("Генерал-фельдмаршал", 3),
            ("Генерал армии", 4),
            ("Генерал-полковник", 5),
            ("Генерал-лейтенант", 6),
            ("Генерал-майор", 7),
            ("Бригадный генерал", 8),
            ("Коммандер", 9),
            ("Полковник", 10),
            ("Подполковник", 11),
            ("Майор", 12),
            ("Капитан-лейтенант", 13),
            ("Капитан", 14),
            ("Платиновый лейтенант", 15),
            ("Серебряный лейтенант", 16),
            ("Сержант", 17),
            ("Прапорщик", 18),
            ("Рядовой", 19),
        ],
        'Эльфы': [
            ("Верховный правитель", 1),
            ("Лесной повелитель", 2),
            ("Вечный страж", 3),
            ("Магистр природы", 4),
            ("Лесной воевода", 5),
            ("Хранитель лесов", 6),
            ("Мастер стрелы", 7),
            ("Лесной командир", 8),
            ("Древесный защитник", 9),
            ("Мастер лука", 10),
            ("Ловкий стрелок", 11),
            ("Юркий воин", 12),
            ("Стремительный охотник", 13),
            ("Лесной страж", 14),
            ("Природный следопыт", 15),
            ("Ученик жрицы", 16),
            ("Начинающий охотник", 17),
            ("Молодой эльф", 18),
            ("Младший ученик эльфа", 19),
        ],
        'Адепты': [
            ("Верховный Инквизитор", 1),
            ("Великий Охотник", 2),
            ("Магистр Аббатства", 3),
            ("Гранд-Инквизитор", 4),
            ("Судья Правой Руки", 5),
            ("Главный Следователь", 6),
            ("Огонь Вердикта", 7),
            ("Страж Чистоты", 8),
            ("Палач Ереси", 9),
            ("Исполнитель Клятвы", 10),
            ("Сержант Ордена", 11),
            ("Офицер Инквизиции", 12),
            ("Кандидат Света", 13),
            ("Новичок Клятвы", 14),
            ("Причастный Костра", 15),
            ("Ученик Веры", 16),
            ("Искренний", 17),
            ("Слушающий Слово", 18),
            ("Пепел Греха", 19),
        ],
        'Элины': [
            ("Повелитель Пламени", 1),
            ("Око Бури", 2),
            ("Хранитель Песков", 3),
            ("Гнев Ветров", 4),
            ("Тень Дракона", 5),
            ("Жар Пустыни", 6),
            ("Клинок Солнца", 7),
            ("Пустынный Судья", 8),
            ("Мастер Ярости", 9),
            ("Искра Пламени", 10),
            ("Бегущий по Пескам", 11),
            ("Вестник Жара", 12),
            ("Порождение Торнадо", 13),
            ("Песчаный Странник", 14),
            ("Пыль Гривы", 15),
            ("Песчинка", 16),
            ("Забытый Ветром", 17),
            ("Проклятый Солнцем", 18),
            ("Пепел Пустыни", 19),
        ],
    }

    # -------------------------
    # РЕКУРСИВНЫЕ ФУНКЦИИ АДАПТАЦИИ
    # -------------------------

    def _get_orientation_params(self):
        """Возвращает параметры для текущей ориентации экрана"""
        is_landscape = Window.width > Window.height
        is_small = Window.width < 400

        return {
            'is_landscape': is_landscape,
            'is_small': is_small,
            'window_width': Window.width,
            'window_height': Window.height
        }

    def _get_font_sizes(self, base_size, is_landscape=False):
        """Возвращает адаптивные размеры шрифтов"""
        if is_landscape:
            return {
                'title': ssp(base_size * 0.9),
                'normal': ssp(base_size * 0.85),
                'small': ssp(base_size * 0.75)
            }
        return {
            'title': ssp(base_size),
            'normal': ssp(base_size * 0.9),
            'small': ssp(base_size * 0.8)
        }

    def _get_spacing(self, base_spacing, is_landscape=False):
        """Возвращает адаптивные отступы"""
        return sdp(base_spacing * 0.8 if is_landscape else base_spacing)

    # -------------------------
    # RANK HELPERS
    # -------------------------

    def _color_to_hex(self, color_tuple):
        """Конвертирует RGBA tuple (0-1) в hex строку без #"""
        r, g, b = color_tuple[:3]
        return '{:02X}{:02X}{:02X}'.format(int(r * 255), int(g * 255), int(b * 255))

    def _priority_to_roman(self, priority):
        """Конвертирует числовой приоритет (1-19) в римскую цифру"""
        romans = {
            1: 'I', 2: 'II', 3: 'III', 4: 'IV', 5: 'V',
            6: 'VI', 7: 'VII', 8: 'VIII', 9: 'IX', 10: 'X',
            11: 'XI', 12: 'XII', 13: 'XIII', 14: 'XIV',
            15: 'XV', 16: 'XVI', 17: 'XVII', 18: 'XVIII', 19: 'XIX'
        }
        return romans.get(priority, 'XIX')

    def _rank_color(self, rank_num):
        """Определяет цвет ранга на основе приоритета"""
        if rank_num == 1:
            return '#FFD700'  # Золотой для самого высокого ранга
        elif rank_num <= 5:
            return '#FF6A00'  # Оранжевый для топ-5
        elif rank_num <= 10:
            return '#32CD32'  # Зеленый для топ-10
        elif rank_num <= 15:
            return '#1E90FF'  # Синий для топ-15
        else:
            return '#AAAAAA'  # Серый для остальных

    def _get_rank_info(self, rank_text, faction):
        """Возвращает полную информацию о ранге"""
        if not rank_text or not faction:
            # Возвращаем информацию по умолчанию
            return {
                'original_text': rank_text or "Нет звания",
                'faction': faction or "Неизвестно",
                'priority': 19,
                'roman': 'XIX',
                'color': '#AAAAAA',
                'rank_name': "Нет звания"
            }

        rank_text = str(rank_text).strip()
        faction = str(faction).strip()

        # Получаем таблицу званий для фракции
        rank_table = self.RANK_TABLES.get(faction)
        if not rank_table:
            return {
                'original_text': rank_text,
                'faction': faction,
                'priority': 19,
                'roman': 'XIX',
                'color': '#AAAAAA',
                'rank_name': rank_text  # Показываем оригинальный текст
            }

        # Ищем звание в таблице
        for rank_name, priority in rank_table:
            if rank_name.lower() == rank_text.lower():
                roman = self._priority_to_roman(priority)
                color = self._rank_color(priority)
                return {
                    'original_text': rank_text,
                    'faction': faction,
                    'priority': priority,
                    'roman': roman,
                    'color': color,
                    'rank_name': rank_name
                }

        # Если звание не найдено, пытаемся найти частичное совпадение
        for rank_name, priority in rank_table:
            if rank_text.lower() in rank_name.lower():
                roman = self._priority_to_roman(priority)
                color = self._rank_color(priority)
                return {
                    'original_text': rank_text,
                    'faction': faction,
                    'priority': priority,
                    'roman': roman,
                    'color': color,
                    'rank_name': rank_name
                }

        # Если совсем не нашли, показываем оригинальный текст
        return {
            'original_text': rank_text,
            'faction': faction,
            'priority': 19,
            'roman': 'XIX',
            'color': '#AAAAAA',
            'rank_name': rank_text  # Показываем то, что есть в базе
        }

    # -------------------------
    # ROOT UI
    # -------------------------

    def build_ui(self):
        from frontend_ui import build_rating
        build_rating(self)

    def _create_title_bar(self, params):
        is_landscape = params['is_landscape']

        bar_height = sdp(46 if is_landscape else 56)
        font_sizes = self._get_font_sizes(20, is_landscape)

        bar = BoxLayout(
            size_hint_y=None,
            height=bar_height,
            padding=[sdp(12), 0],
            spacing=sdp(8)
        )

        with bar.canvas.before:
            Color(0, 0, 0, 0.65)
            _bar_bg = Rectangle(pos=bar.pos, size=bar.size)
            Color(0.75, 0.55, 0.15, 0.9)
            _bar_accent = Rectangle(pos=bar.pos, size=(bar.width, dp(3)))

        def _upd_bar(instance, value):
            _bar_bg.pos = instance.pos
            _bar_bg.size = instance.size
            _bar_accent.pos = instance.pos
            _bar_accent.size = (instance.width, dp(3))

        bar.bind(pos=_upd_bar, size=_upd_bar)

        title = Label(
            text=" [b]Рейтинг[/b]",
            markup=True,
            font_size=font_sizes['title'],
            color=get_color_from_hex('#FFD700'),
            outline_color=(0, 0, 0, 1),
            outline_width=2,
            halign='left',
            valign='middle',
            size_hint_x=None,
            width=params['window_width'] - sdp(24)
        )

        bar.add_widget(title)
        return bar

    # -------------------------
    # TABS PANEL
    # -------------------------

    def _create_tabs_panel(self, params):
        is_landscape = params['is_landscape']

        tab_height = sdp(30 if is_landscape else 38)
        self.tabs = TabbedPanel(
            do_default_tab=False,
            tab_height=tab_height,
            tab_width=sdp(150),
            background_color=(0.05, 0.07, 0.12, 1),
        )
        self._load_dossier_data_to_tabs(self.tabs, params)
        return self.tabs

    # -------------------------
    # BOTTOM PANEL
    # -------------------------

    def _create_bottom_panel(self, params):
        is_landscape = params['is_landscape']
        is_small = params['is_small']

        # Определяем компоновку
        if is_landscape:
            orientation = 'horizontal'
            height = sdp(40)
        else:
            orientation = 'vertical' if is_small else 'horizontal'
            height = sdp(80 if is_small else 50)

        panel = BoxLayout(
            orientation=orientation,
            size_hint_y=None,
            height=height,
            spacing=self._get_spacing(6, is_landscape),
            padding=self._get_spacing(6, is_landscape)
        )

        # Параметры кнопок
        if is_landscape:
            btn_config = {
                'height': sdp(32),
                'font_size': ssp(13),
                'size_hint_x': 0.5
            }
        elif is_small:
            btn_config = {
                'height': sdp(30),
                'font_size': ssp(14),
                'size_hint_x': 1
            }
        else:
            btn_config = {
                'height': sdp(30),
                'font_size': ssp(14),
                'size_hint_x': 0.5
            }

        # Создаем кнопки
        buttons = [
            {
                'text': "Назад",
                'btn_type': 'start',
                'action': self.go_back
            },
            {
                'text': "Очистить все",
                'btn_type': 'exit',
                'action': self.clear_dossier
            }
        ]

        for btn_info in buttons:
            btn = GameButton(
                text=btn_info['text'],
                button_type=btn_info['btn_type'],
                size_hint_y=None,
                height=btn_config['height'],
                size_hint_x=btn_config['size_hint_x'],
            )
            btn.font_size = btn_config['font_size']
            btn.bind(on_release=btn_info['action'])
            panel.add_widget(btn)

        return panel

    # -------------------------
    # EMPTY STATE
    # -------------------------

    def _create_empty_state(self, params):
        """Создает стилизованное сообщение об отсутствии данных"""
        is_landscape = params['is_landscape']
        font_sizes = self._get_font_sizes(16, is_landscape)

        container = BoxLayout(
            orientation='vertical',
            padding=self._get_spacing(30, is_landscape),
            spacing=self._get_spacing(12, is_landscape)
        )

        with container.canvas.before:
            Color(0.06, 0.08, 0.14, 0.85)
            _emp_bg = RoundedRectangle(pos=container.pos, size=container.size, radius=[dp(16)])
            Color(0.3, 0.3, 0.5, 0.4)
            _emp_border = Line(
                rounded_rectangle=(container.x, container.y, container.width, container.height, dp(16)),
                width=dp(1)
            )

        def _upd_emp(instance, value):
            _emp_bg.pos = instance.pos
            _emp_bg.size = instance.size
            _emp_border.rounded_rectangle = (instance.x, instance.y, instance.width, instance.height, dp(16))

        container.bind(pos=_upd_emp, size=_upd_emp)

        main_label = Label(
            text="[b]Вы ещё не воевали...[/b]",
            markup=True,
            font_size=font_sizes['title'],
            halign='center',
            valign='middle',
            color=(0.85, 0.85, 1.0, 1),
            size_hint_y=None,
            height=ssp(30)
        )

        sub_label = Label(
            text="Начните игру, чтобы здесь появилась статистика",
            font_size=font_sizes['small'],
            halign='center',
            valign='middle',
            color=(0.55, 0.55, 0.65, 1),
            size_hint_y=None,
            height=ssp(20)
        )

        for w in (main_label, sub_label):
            w.bind(size=w.setter('text_size'))
            container.add_widget(w)

        return container

    # -------------------------
    # CHARACTER CARD
    # -------------------------

    def _create_character_card(self, data, params, faction=None):
        """Создает стилизованную карточку персонажа с фракционным цветом"""
        is_landscape = params['is_landscape']

        card_padding = self._get_spacing(8 if is_landscape else 12, is_landscape)
        card_spacing = self._get_spacing(6 if is_landscape else 8, is_landscape)

        # Получаем звание и фракцию
        raw_rank = data.get('military_rank') or "Еще не признан..."
        if faction is None:
            faction = data.get('faction', 'Неизвестно')

        rank_info = self._get_rank_info(raw_rank, faction)
        fc = self.FACTION_COLORS.get(faction, (0.3, 0.3, 0.5, 1))

        # Внешняя обёртка — добавим отступ слева для цветной полосы
        outer = BoxLayout(
            orientation='horizontal',
            size_hint_y=None,
            size_hint_x=1,
            spacing=0,
        )
        outer.bind(minimum_height=outer.setter('height'))

        # Цветная левая полоса
        accent_bar = BoxLayout(size_hint=(None, 1), width=dp(5))
        with accent_bar.canvas.before:
            Color(*fc)
            _ab_rect = RoundedRectangle(pos=accent_bar.pos, size=accent_bar.size, radius=[dp(4), 0, 0, dp(4)])
        accent_bar.bind(
            pos=lambda i, v: setattr(_ab_rect, 'pos', v),
            size=lambda i, v: setattr(_ab_rect, 'size', v)
        )

        # Основной контейнер карточки
        card = BoxLayout(
            orientation='vertical',
            spacing=card_spacing,
            padding=[card_padding, card_padding * 0.8, card_padding, card_padding * 0.8],
            size_hint=(1, None),
        )
        card.bind(minimum_height=card.setter('height'))

        with card.canvas.before:
            Color(0.06, 0.08, 0.14, 0.92)
            _card_bg = RoundedRectangle(pos=card.pos, size=card.size, radius=[0, dp(10), dp(10), 0])
            Color(fc[0] * 0.4, fc[1] * 0.4, fc[2] * 0.4, 0.5)
            _card_border = Line(
                rounded_rectangle=(card.x, card.y, card.width, card.height, dp(10)),
                width=dp(1)
            )

        def _upd_card_bg(instance, value):
            _card_bg.pos = instance.pos
            _card_bg.size = instance.size
            _card_border.rounded_rectangle = (instance.x, instance.y, instance.width, instance.height, dp(10))

        card.bind(pos=_upd_card_bg, size=_upd_card_bg)

        top_row = self._create_card_top_row(data, rank_info, params)
        card.add_widget(top_row)

        # Дата последней игры
        last_data = data.get('last_data')
        if last_data:
            date_label = Label(
                text=f"[color=#888888]Последняя игра: {last_data}[/color]",
                markup=True,
                font_size=ssp(10),
                halign='right',
                valign='middle',
                size_hint_y=None,
                height=ssp(14)
            )
            date_label.bind(size=date_label.setter('text_size'))
            card.add_widget(date_label)

        outer.add_widget(accent_bar)
        outer.add_widget(card)

        # Привязываем высоту outer к высоте card
        card.bind(height=lambda i, v: setattr(outer, 'height', v + dp(4)))

        return outer

    def _create_card_top_row(self, data, rank_info, params):
        """Создает верхнюю строку карточки с адаптивной компоновкой"""
        is_landscape = params['is_landscape']
        is_small = params['is_small']

        if is_landscape:
            # Горизонтальная компоновка для альбомной ориентации
            return self._create_horizontal_layout(data, rank_info, params)
        else:
            # Адаптивная компоновка для портретной ориентации
            return self._create_adaptive_portrait_layout(data, rank_info, params)

    def _create_horizontal_layout(self, data, rank_info, params):
        """Горизонтальная компоновка (3 колонки)"""
        row = BoxLayout(
            orientation='horizontal',
            spacing=self._get_spacing(8, True),
            size_hint_y=None,
            height=sdp(80),
            size_hint_x=1
        )

        # Панели с динамическими размерами
        row.add_widget(self._create_info_panel(data, 0.3, True))
        row.add_widget(self._create_rank_panel(rank_info, 0.4, True))
        row.add_widget(self._create_battles_panel(data, 0.3, True))

        return row

    def _create_adaptive_portrait_layout(self, data, rank_info, params):
        """Адаптивная компоновка для портретной ориентации"""
        is_small = params['is_small']

        if is_small:
            # Вертикальная компоновка для маленьких экранов
            row = BoxLayout(
                orientation='vertical',
                spacing=self._get_spacing(8, False),
                size_hint_y=None,
                size_hint_x=1
            )

            # Ранг по центру
            rank_panel = self._create_rank_panel(rank_info, 1, False)
            rank_panel.size_hint_y = None
            rank_panel.height = sdp(60)

            # Информация в 2 колонки
            info_row = BoxLayout(
                orientation='horizontal',
                spacing=self._get_spacing(10, False),
                size_hint_y=None,
                height=sdp(60)
            )

            info_row.add_widget(self._create_info_panel(data, 0.5, False))
            info_row.add_widget(self._create_battles_panel(data, 0.5, False))

            row.add_widget(rank_panel)
            row.add_widget(info_row)

        else:
            # Горизонтальная компоновка для нормальных экранов
            row = BoxLayout(
                orientation='horizontal',
                spacing=self._get_spacing(10, False),
                size_hint_y=None,
                height=sdp(100),
                size_hint_x=1
            )

            row.add_widget(self._create_info_panel(data, 0.3, False))
            row.add_widget(self._create_rank_panel(rank_info, 0.4, False))
            row.add_widget(self._create_battles_panel(data, 0.3, False))

        return row

    # -------------------------
    # PANEL CREATORS
    # -------------------------

    def _create_info_panel(self, data, size_hint_x, is_landscape):
        """Информационная панель"""
        font_sizes = self._get_font_sizes(12, is_landscape)

        panel = BoxLayout(
            orientation='vertical',
            size_hint_x=size_hint_x,
            spacing=self._get_spacing(2, is_landscape),
            padding=[0, self._get_spacing(2, is_landscape)]
        )

        # Добавляем элементы с адаптивными шрифтами
        self._add_panel_label(panel, "[b]Боевой рейтинг:[/b]",
                              font_sizes['small'], ssp(14))
        self._add_panel_label(panel, str(data.get('avg_military_rating', 0)),
                              font_sizes['normal'], ssp(16))
        self._add_panel_label(panel, "[b]Голод:[/b]",
                              font_sizes['small'], ssp(14))
        self._add_panel_label(panel, str(data.get('avg_soldiers_starving', 0)),
                              font_sizes['normal'], ssp(16))

        return panel

    def _create_rank_panel(self, rank_info, size_hint_x, is_landscape):
        """Панель с рангом - показывает римскую цифру и название звания"""
        font_sizes = self._get_font_sizes(36, is_landscape)

        panel = BoxLayout(
            orientation='vertical',
            size_hint_x=size_hint_x,
            spacing=self._get_spacing(1, is_landscape),
            padding=[0, self._get_spacing(1, is_landscape)]
        )

        # Римская цифра (приоритет)
        roman_label = Label(
            text=f"[b][color={rank_info['color']}]{rank_info['roman']}[/color][/b]",
            markup=True,
            font_size=font_sizes['title'] * (0.9 if is_landscape else 1),
            halign='center',
            valign='middle',
            size_hint_y=None,
            height=ssp(40 if not is_landscape else 36)
        )
        panel.add_widget(roman_label)

        # Название звания
        rank_name = rank_info['rank_name']
        if len(rank_name) > 20:
            rank_name = rank_name[:18] + "..."

        rank_label = Label(
            text=rank_name,
            font_size=font_sizes['small'] * 0.7,
            color=get_color_from_hex(rank_info['color']),
            halign='center',
            valign='top',
            size_hint_y=None,
            height=ssp(12),
            text_size=(Window.width * size_hint_x - sdp(10), None)
        )
        panel.add_widget(rank_label)

        return panel

    def _create_battles_panel(self, data, size_hint_x, is_landscape):
        from battle_ui import battle_career_panel
        return battle_career_panel(data, size_hint_x, is_landscape)

    def _add_panel_label(self, panel, text, font_size, height):
        """Вспомогательный метод для добавления меток"""
        label = Label(
            text=text,
            markup='[' in text,
            font_size=font_size,
            halign='center',
            valign='middle',
            size_hint_y=None,
            height=height
        )
        panel.add_widget(label)

    # -------------------------
    # DATA LOADING
    # -------------------------

    def _load_dossier_data_to_tabs(self, tabs_widget, params):
        """Загружает данные с учетом фракции для правильной конвертации званий"""
        # Очищаем все существующие вкладки
        for tab in list(tabs_widget.get_tab_list()):
            tabs_widget.remove_widget(tab)

        try:
            cur = self.conn.cursor()
            cur.execute("SELECT * FROM dossier")
            rows = cur.fetchall()
        except:
            rows = []

        # Если нет данных - создаем адаптивное пустое состояние
        if not rows:
            tab = TabbedPanelItem(text="Инфо")
            empty_container = self._create_empty_state(params)
            tab.add_widget(empty_container)
            tabs_widget.add_widget(tab)
            return

        # Группируем данные по фракциям
        factions = {}
        for row in rows:
            faction = row[1]
            data = {
                'faction': faction,
                'military_rank': row[2],
                'avg_military_rating': row[3],
                'avg_soldiers_starving': row[4],
                'victories': row[5],
                'defeats': row[6],
                'matches_won': row[7],
                'matches_lost': row[8],
                'last_data': row[9]
            }
            factions.setdefault(faction, []).append(data)

        # Создаем вкладки для каждой фракции
        for faction, items in factions.items():
            fc = self.FACTION_COLORS.get(faction, (0.3, 0.3, 0.5, 1))
            tab = TabbedPanelItem(
                text=faction,
                color=(1, 1, 1, 1),
                bold=True,
                background_normal='',
                background_down='',
                background_color=(fc[0] * 0.4, fc[1] * 0.4, fc[2] * 0.4, 1),
            )

            scroll = ScrollView(
                bar_width=dp(6),
                bar_color=(fc[0], fc[1], fc[2], 0.8),
                bar_inactive_color=(fc[0] * 0.5, fc[1] * 0.5, fc[2] * 0.5, 0.4),
                scroll_type=['bars', 'content']
            )
            grid = GridLayout(
                cols=1,
                spacing=self._get_spacing(8, params['is_landscape']),
                padding=self._get_spacing(12, params['is_landscape']),
                size_hint_y=None,
                size_hint_x=1
            )
            grid.bind(minimum_height=grid.setter('height'))

            # Заголовок фракции в начале списка
            faction_header = Label(
                text=f"[b][color=#{self._color_to_hex(fc)}]{faction}[/color][/b]  — история сражений",
                markup=True,
                font_size=ssp(16),
                halign='center',
                valign='middle',
                size_hint_y=None,
                height=ssp(28),
                outline_color=(0, 0, 0, 1),
                outline_width=1
            )
            faction_header.bind(size=faction_header.setter('text_size'))
            grid.add_widget(faction_header)

            # Сортировка по приоритету звания
            sorted_items = []
            for d in items:
                rank_info = self._get_rank_info(d.get('military_rank'), faction)
                sorted_items.append((rank_info['priority'], d))

            sorted_items.sort(key=lambda x: x[0])

            # Создаем карточки
            for _, data in sorted_items:
                card = self._create_character_card(data, params, faction)
                grid.add_widget(card)

            scroll.add_widget(grid)
            tab.add_widget(scroll)
            tabs_widget.add_widget(tab)

    # -------------------------
    # ACTIONS
    # -------------------------

    def load_dossier_data(self):
        """Загружает данные с адаптивными параметрами"""
        params = self._get_orientation_params()
        self._load_dossier_data_to_tabs(self.tabs, params)

    def clear_dossier(self, instance):
        """Очищает все данные досье"""
        try:
            cur = self.conn.cursor()
            cur.execute("DELETE FROM dossier")
            self.conn.commit()
        except Exception as e:
            print(f"Ошибка при очистке досье: {e}")

        # Перезагружаем вкладки после очистки
        self._reload_tabs()

    def _reload_tabs(self):
        self.refresh_rating()

    def go_back(self, instance):
        """Возврат в главное меню"""
        app = App.get_running_app()
        app.root.clear_widgets()
        app.root.add_widget(MenuWidget(self.conn))

    # -------------------------
    # ОБРАБОТКА ИЗМЕНЕНИЯ РАЗМЕРА ЭКРАНА
    # -------------------------

    def on_window_resize(self, window, width, height):
        if self.parent and hasattr(self, '_front_page'):
            self._front_page.fit()

    def _refresh_ui(self, dt):
        """Обновляет UI с небольшой задержкой"""
        try:
            # Перестраиваем весь интерфейс с новыми параметрами
            self.clear_widgets()
            self.build_ui()
        except Exception as e:
            print(f"Ошибка при обновлении UI: {e}")

    # -------------------------
    # ПУБЛИЧНЫЙ МЕТОД ДЛЯ ОБНОВЛЕНИЯ ДАННЫХ
    # -------------------------

    def refresh_data(self):
        """Публичный метод для обновления данных из других частей приложения"""
        self._reload_tabs()


class Lor(Screen):
    def __init__(self, conn, **kwargs):
        super().__init__(**kwargs)
        self.conn = conn
        with self.canvas.before:
            self.bg_rect = Rectangle(
                source='files/menu/lor.jpg',  # путь к фону экрана обучения
                pos=self.pos,
                size=self.size
            )
        self.bind(pos=self._update_bg, size=self._update_bg)
        self.build_ui()

    def build_ui(self):
        layout = BoxLayout(orientation='vertical', padding=dp(20), spacing=dp(20))

        with layout.canvas.before:
            Color(0, 0, 0, 0.58)
            _layout_bg = RoundedRectangle(pos=layout.pos, size=layout.size, radius=[dp(10)])

        def _upd_layout_bg(instance, value):
            _layout_bg.pos = instance.pos
            _layout_bg.size = instance.size

        layout.bind(pos=_upd_layout_bg, size=_upd_layout_bg)

        title = Label(
            text="[b]История Лэрдона[/b]",
            markup=True,
            font_size='34sp',
            size_hint=(1, None),
            height=dp(65),
            halign='center',
            valign='middle',
            color=(1, 0.85, 0.3, 1),
            outline_color=(0, 0, 0, 1),
            outline_width=2
        )
        layout.add_widget(title)

        scroll = ScrollView(size_hint=(1, 1), bar_width=dp(12), scroll_type=['bars', 'content'], bar_color=(1, 1, 0, 1),
                            bar_inactive_color=(1, 1, 0, 0.4))
        content = BoxLayout(orientation='vertical', size_hint_y=None, spacing=dp(10), padding=dp(10))
        content.bind(minimum_height=content.setter('height'))

        how_to_text = (
            "[color=#AAAAAA][i]XVI Вторая полная луна с начала сезона.[/i][/color]\n\n"

            "Никто не думал что они придут, тысячи исследователей всматривались в долину теней, "
            "пытаясь обнаружить хоть какой-то признак жизни...\n\n"

            "Первая атака была разрушительной и уничтожила половину Лэрдона... "
            "Но мы так и не узнали что напало на нас, единственное что им было нужно "
            "для того чтобы выжить это наша кровь. Агилар пытаясь найти хоть какую-то информацию "
            "наткнулся на завет Иоана, кажется раньше таких существ называли вампиры, "
            "проблема в том что их давно уже никто не встречал и мало кто понимал как с ними бороться. "
            "Откуда они взялись так и не ясно.\n\n"

            "Хуже всего другое, по слухам от наших разведчиков назревает что то похуже вампиров, "
            "люди давно уже не спускаются в шахты и пещеры для добычи кристаллов. "
            "Наши запасы кристаллов иссякают, мы потеряли шахту номер 8 и 3 чертог "
            "теперь мы полностью зависимы от внешних поставок, лишь в пустыне остались достаточно крупные залежи, "
            "но Элинская империя впаяла такую цену что проще спустится в долину теней для поиска ресурсов.\n\n"

            "Вшивые фанатики наживаются на нашем горе. Две полные луны назад клан Молдарии "
            "пытался отбить шахты у Элинов чтобы восстановить баланс ресурсов, "
            "но их гребаный дракон выжег все поселения клана до единого, "
            "и война закончилась не успев начаться.\n\n"

            "Эльфы тоже не намерены нам помогать, Валерия считает что все что происходит в Лэрдоне "
            "их вообще не касается. Эти остроухие обезьяны, залезли на свои деревья "
            "и считают что они особенные. А тем временем во многих северных городах стала ощущаться "
            "острая нехватка кристаллов, люди стали убивать друг друга за лишние полкристалла. "
            "Лишь экстренные закупки кристаллов по заоблачным ценам решили ситуацию, "
            "хорошо хоть денег у нас много.\n\n"

            "Но голод еще не самое страшное для Севера, хуже всего то почему люди перестали "
            "спускаться шахты, по слухам там больше не безопасно, своды то и дело обваливаются "
            "в разных местах забирая жизни храбрецов решивших спустится туда. "
            "Кто то говорит как оттуда доносились стоны и вопли не похожие на человеческие. "
            "Кто или что там теперь обитает неизвестно.\n\n"

            "Но кажется это что-то скоро поднимется и на поверхность, хватит ли нам сил отбится "
            "от новой напасти? А недавно я слышал как один из шахтеров заболел неизвестной болезнью, "
            "она оказалась настолько сильной что выкосила крупный поселок за пару ночей.\n\n"

            "Когда я об этом написал Сестре Милосердия она лишь развела руками, понятное дело "
            "что под влиянием Агилара Сестра не рвется нам помогать, Агилар считает что в своей "
            "крепости он неуязвим и по этому болезни и монстры его не касаются, но это иллюзия.\n\n"

            "Я предупреждал что надо искать новые источники кристаллов, сразу после окончания "
            "войны с вампирами, но наш князь Фагот никого не слушает, он слишком горд чтобы "
            "с кем-то договариваться.\n\n"

            "Нам пришлось экстренно разрабатывать с нашими мастерами новое оружие, кажется "
            "оно работает и наносит невероятный урон. Это поможет нам пробиться к шахтам кристаллов, "
            "вопрос лишь в том хватит ли у нас времени до того как Лэрдон погрузится в новую войну...\n\n"

            "[color=#888888]Если мы не успеем....то рассвета люди не увидят....[/color]\n\n"

            "[color=#AAAAAA][i]Командующий 9-й армией Владислав.[/i][/color]"
        )

        label = Label(
            text=how_to_text,
            markup=True,
            font_size='18sp',
            halign='left',
            valign='top',
            size_hint_y=None,
            text_size=(Window.width * 0.9, None)
        )
        label.bind(texture_size=lambda instance, value: setattr(label, 'height', value[1]))

        content.add_widget(label)
        scroll.add_widget(content)

        # Пульсация полосы прокрутки
        from kivy.animation import Animation
        def animate_bar():
            anim = Animation(bar_color=(1, 0.6, 0, 1), duration=0.5) + Animation(bar_color=(1, 1, 0, 1), duration=0.5)
            anim.repeat = True
            anim.start(scroll)

        layout.add_widget(scroll)

        back_button = RoundedButton(
            text="Назад",
            size_hint=(0.3, None),
            height=dp(50),
            pos_hint={'center_x': 0.5},
            font_size='16sp'
        )
        back_button.bind(on_release=self.go_back)
        layout.add_widget(back_button)

        from frontend_ui import finish_legacy_page
        finish_legacy_page(self, layout)

    def _update_bg(self, *args):
        self.bg_rect.pos = self.pos
        self.bg_rect.size = self.size

    def go_back(self, instance):
        app = App.get_running_app()
        app.root.clear_widgets()
        app.root.add_widget(MenuWidget(self.conn))


from kivy.animation import Animation
from kivy.clock import Clock
from kivy.graphics import Color, Rectangle, Rotate, Scale
from kivy.graphics.context_instructions import PushMatrix, PopMatrix
import random
import math


class Lerdon(MDApp):
    def __init__(self, **kwargs):
        super(Lerdon, self).__init__(**kwargs)
        print("app starting...")
        # Флаг, что мы на мобильной платформе Android
        self.is_mobile = (platform == 'android')
        # Можно завести другие глобальные настройки здесь
        self.selected_kingdom = None  # Атрибут для хранения выбранного королевства

        # Инициализация соединения с базой данных
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL;")
        self.conn.execute("PRAGMA synchronous=NORMAL;")
        self.conn.execute("PRAGMA busy_timeout=5000;")

    def build(self):
        """Создает начальный интерфейс приложения."""
        return LoadingScreen(self.conn)

    def restart_app(self):
        """Перезапуск игры — очистка БД, восстановление бэкапа, пересоздание интерфейса."""
        try:
            # Очистка таблиц
            clear_tables(self.conn)
            self.conn.commit()
            print("Таблицы успешно очищены.")
        except sqlite3.Error as e:
            print(f"Ошибка при очистке таблиц: {e}")
            self.conn.rollback()

        # Восстановление из бэкапа
        restore_from_backup(self.conn)

        # Сброс состояния приложения
        self.selected_kingdom = None

        # Полная очистка корневого виджета
        if self.root:
            self.root.clear_widgets()

        # Пересоздание главного меню
        Clock.schedule_once(self.recreate_main_menu, 0.2)

    def recreate_main_menu(self, dt):
        """Пересоздание главного меню после очистки."""
        self.root.add_widget(MenuWidget(self.conn))
        print("Главное меню полностью пересоздано")

    def on_stop(self):
        print("Завершение работы приложения...")

        # 1) Делаем checkpoint и сразу закрываем — без переключения journal_mode
        try:
            self.conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
        except sqlite3.Error as e:
            print(f"[WARNING] Не удалось сделать WAL checkpoint: {e}")

        try:
            self.conn.close()
            print("Соединение с БД закрыто корректно.")
        except sqlite3.Error as e:
            print(f"Ошибка при закрытии соединения с БД: {e}")

        # 2) Удаляем файлы WAL/SHM (опционально)
        for ext in (".db-wal", ".db-shm"):
            path = db_path + ext
            if os.path.exists(path):
                try:
                    os.remove(path)
                    print(f"Удалён файл {path}")
                except OSError as e:
                    print(f"Не удалось удалить {path}: {e}")

        print("Приложение завершило работу.")

    def get_connection(self):
        """Возвращает текущее соединение с БД."""
        return self.conn


if __name__ == '__main__':
    Lerdon().run()
