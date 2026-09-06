import os
os.environ['KIVY_VIDEO'] = 'ffpyplayer'
from game_process import GameScreen
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
    ]

    cursor = conn.cursor()

    try:
        for table in tables_to_clear:
            # Используем TRUNCATE или DELETE для очистки таблицы
            cursor.execute(f"DELETE FROM {table};")
            print(f"Таблица '{table}' успешно очищена.")

        # Фиксируем изменения
        conn.commit()
    except sqlite3.Error as e:
        print(f"Ошибка при очистке таблиц: {e}")
        conn.rollback()  # Откат изменений в случае ошибки


class AuthorScreen(Screen):
    def __init__(self, conn, **kwargs):
        super(AuthorScreen, self).__init__(**kwargs)
        self.conn = conn
        root = FloatLayout()

        # === Статичный фон ===
        # Замените 'files/menu/author.jpg' на путь к вашему изображению-фону.
        # Рекомендуется использовать изображение в формате .jpg или .png.
        self.bg_image = Image(
            source='files/menu/author.jpg',  # <- Укажите путь к вашему изображению
            allow_stretch=True,  # Растягивать под размер виджета
            keep_ratio=False,  # Игнорировать соотношение сторон
            size_hint=(1, 1),  # Занимает весь родительский контейнер
            pos_hint={'center_x': 0.5, 'center_y': 0.5}
        )
        root.add_widget(self.bg_image)
        # ---

        # Прозрачный слой с контентом (остается без изменений)
        layout = BoxLayout(orientation='vertical',
                           padding=dp(20),
                           spacing=dp(20),
                           size_hint=(0.9, 0.8),
                           pos_hint={'center_x': 0.5, 'center_y': 0.5})

        # Заголовок (остается без изменений)
        title_label = Label(
            text="[b]Сообщество Лэрдона[/b]",
            markup=True,
            font_size='28sp',
            size_hint_y=None,
            height=dp(50),
            outline_color=(0, 0, 0, 1),
            outline_width=2,
            color=(1, 1, 1, 1),
            halign="center"
        )
        layout.add_widget(title_label)

        top_layout = BoxLayout(
            orientation='vertical',
            size_hint=(1, None),
            height=dp(60),  # Высота окантовки
            pos_hint={'top': 1}  # Прижимаем к верху экрана
        )

        # Создаем фон для окантовки (остается без изменений)
        from kivy.graphics import Color, Rectangle
        with top_layout.canvas.before:
            Color(0, 0, 0, 0.5)  # Черный цвет с 50% прозрачностью
            self.top_bg_rect = Rectangle(size=top_layout.size, pos=top_layout.pos)

        # Обновляем размер и позицию фона при изменении размера виджета (остается без изменений)
        def update_top_bg_rect(instance, value):
            self.top_bg_rect.pos = instance.pos
            self.top_bg_rect.size = instance.size

        top_layout.bind(pos=update_top_bg_rect, size=update_top_bg_rect)

        # Создаем саму надпись (остается без изменений)
        greeting_label = Label(
            text="[b][color=#FFD700]Желаю Вам приятно провести время в моем мире![/color][/b]",
            markup=True,
            font_size='18sp',
            outline_color=(0, 0, 0, 1),
            outline_width=1.5,
            halign="center",
            valign="middle"
        )
        greeting_label.bind(size=greeting_label.setter('text_size'))
        top_layout.add_widget(greeting_label)
        root.add_widget(top_layout)

        # Ссылки-карточки (остается без изменений)
        link_box = BoxLayout(orientation='vertical', spacing=dp(10), size_hint_y=None, height=dp(100))

        vk_label = Label(
            text="[ref=https://vk.com/destianfarbius  ][color=#00aaff]Страница автора ВКонтакте[/color][/ref]",
            markup=True,
            font_size='18sp',
            size_hint_y=None,
            height=dp(40),
            outline_color=(0, 0, 0, 1),
            outline_width=2,
            halign="center",
            valign="middle"
        )
        vk_label.bind(on_ref_press=self.open_link)

        tg_label = Label(
            text="[ref=https://t.me/+scOGK6ph6r03YmU6  ][color=#00aaff]Присоединиться к Telegram[/color][/ref]",
            markup=True,
            font_size='18sp',
            size_hint_y=None,
            height=dp(40),
            outline_color=(0, 0, 0, 1),
            outline_width=2,
            halign="center",
            valign="middle"
        )
        tg_label.bind(on_ref_press=self.open_link)

        link_box.add_widget(vk_label)
        link_box.add_widget(tg_label)
        layout.add_widget(link_box)

        # Новая желтая подпись внизу (остается без изменений)
        credits_label = Label(
            text="[color=#FFD700]Все иконки и изображения были разработаны с использованием ресурсов: \n Flaticon.com, Qwen, ChatGPT, а так же Шедеврума.[/color]",
            markup=True,
            font_size='12sp',
            size_hint_y=None,
            height=dp(40),
            outline_color=(0, 0, 0, 1),
            outline_width=2,
            halign="center",
            valign="middle"
        )
        layout.add_widget(credits_label)

        # Кнопка "Назад"
        back_button = RoundedButton(
            text="Назад",
            size_hint=(0.3, None),
            height=dp(44),
            pos_hint={'center_x': 0.5},
            font_size='14sp'
        )
        back_button.bind(on_press=self.go_back)
        layout.add_widget(back_button)

        root.add_widget(layout)
        self.add_widget(root)

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
        "Стройте больницы для роста населения",
        "Фабрики — основа экономики, но требуют рабочих",
        "Следите за потреблением армии — голодные солдаты дезертируют",
        "Торговля с дружественными фракциями приносит больше выгоды",
        "Герои усиливают гарнизон города в бою",
        "Сезоны влияют на производство ресурсов",
        "Дипломатия может быть сильнее армии",
        "Кристаллы можно продать за кроны на рынке",
        "Артефакты дают бонусы вашим героям",
        "Чем больше городов — тем выше лимит армии",
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

        # === Прогресс-бар с glow ===
        self.pb_container = FloatLayout(
            size_hint=(0.6, None), height=dp(8),
            pos_hint={'center_x': 0.5, 'center_y': 0.28}
        )
        self.pb_container.bind(pos=self._draw_progress, size=self._draw_progress)
        self.add_widget(self.pb_container)

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
        self.tip_label.bind(size=self.tip_label.setter('text_size'))
        self.add_widget(self.tip_label)

        # === Прогресс ===
        self.current_progress = 0
        self.target_progress = 0

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

        # Анимация title glow
        self._animate_title()

        # Частицы
        self._particle_event = Clock.schedule_interval(self._spawn_particle, 0.15)

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
        """Рисует стильный прогресс-бар с glow."""
        self.pb_container.canvas.clear()
        cx, cy = self.pb_container.pos
        cw, ch = self.pb_container.size
        fill_w = max(0, (self.current_progress / 100.0) * cw)

        t = self.current_progress / 100.0
        # Цвет: от тёмно-синего к золотому
        r = 0.2 + t * 0.65
        g = 0.3 + t * 0.48
        b = 0.8 - t * 0.35

        with self.pb_container.canvas:
            # Фоновый трек
            Color(0.15, 0.17, 0.25, 0.6)
            RoundedRectangle(pos=(cx, cy), size=(cw, ch), radius=[dp(4)])

            # Glow под баром
            if fill_w > dp(4):
                Color(r, g, b, 0.25)
                RoundedRectangle(
                    pos=(cx - dp(2), cy - dp(3)),
                    size=(fill_w + dp(4), ch + dp(6)),
                    radius=[dp(6)]
                )

            # Заполнение
            if fill_w > dp(2):
                Color(r, g, b, 0.9)
                RoundedRectangle(pos=(cx, cy), size=(fill_w, ch), radius=[dp(4)])

                # Блик сверху
                Color(1, 1, 1, 0.15)
                RoundedRectangle(
                    pos=(cx + dp(2), cy + ch * 0.55),
                    size=(max(dp(2), fill_w - dp(4)), ch * 0.3),
                    radius=[dp(2)]
                )

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
            Clock.schedule_once(self.smooth_progress_update, 0.016)
        else:
            self.current_progress = self.target_progress
            percent = int(self.current_progress)
            self.percent_label.text = f"{percent}%"
            self._draw_progress()

            if self.target_progress >= 100:
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
        self.update_progress(10, 3)
        from threading import Thread
        def load_task():
            time.sleep(0.3)
            Clock.schedule_once(lambda dt: self.update_progress(10), 0)
            time.sleep(0.3)
            Clock.schedule_once(self.run_next_step, 0)
        Thread(target=load_task, daemon=True).start()

    def step_complete(self):
        self.update_progress(20, 4)
        Clock.schedule_once(self.run_next_step, 0.3)

    # === Вспомогательные ===
    def _update_bg(self, *args):
        self.bg_fill.pos = self.pos
        self.bg_fill.size = self.size
        self.bg_rect.pos = self.pos
        self.bg_rect.size = self.size

    def switch_to_menu(self, dt):
        # Останавливаем частицы
        if self._particle_event:
            self._particle_event.cancel()
        if hasattr(self, '_particle_update_event'):
            self._particle_update_event.cancel()
        Animation.cancel_all(self.title_label)

        self.bg_rect.source = 'files/menu/main_fon.jpg'
        self.bg_rect.texture = CoreImage('files/menu/main_fon.jpg').texture
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
        self._undead_shield_group = None
        self._undead_anim_event = None
        # === Сезонный оверлей ===
        self.season_overlay = None
        self.add_season_overlay()

        self.base_map_width = 1200
        self.base_map_height = 800
        self.map_scale = self.calculate_scale()
        self.map_pos = self.calculate_centered_position()

        generate_map_and_cities(self.conn)
        self.random_map_source = self.get_random_map_source()

        self.initialize_map()
        self.update_cities_event = Clock.schedule_interval(self.update_cities, 1.0)

    def add_season_overlay(self):
        """Добавляет сезонный оверлей"""
        try:
            self.season_overlay = SeasonalOverlay(self.conn)
            self.season_overlay.size_hint = (1, 1)
            self.season_overlay.pos_hint = {'x': 0, 'y': 0}
            # НЕ добавляем сейчас - сделаем это в on_parent
            print("[SEASON] Сезонный оверлей создан")
        except Exception as e:
            print(f"[ERROR] Не удалось создать сезонный оверлей: {e}")
            import traceback
            traceback.print_exc()

    def on_parent(self, widget, parent):
        """Обработка удаления/добавления виджета"""
        if parent is None:
            if self.update_cities_event:
                Clock.unschedule(self.update_cities_event)
            if self.season_overlay:
                self.season_overlay.stop_season_animation()
        else:
            # Добавляем оверлей только когда есть parent
            if self.season_overlay and self.season_overlay.parent is None:
                parent.add_widget(self.season_overlay)
                print("[SEASON] Сезонный оверлей добавлен в parent")

    # 3. Измените update_cities - НЕ очищайте canvas.after:
    def update_cities(self, dt=None):
        self.map_scale = self.calculate_scale()
        self.map_pos = self.calculate_centered_position()
        self.canvas.clear()
        # УДАЛИТЕ или закомментируйте эту строку:
        # self.canvas.after.clear()  # ← Это удаляет сезонную анимацию!

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

    def initialize_map(self, schedule_blink=True):
        self.map_scale = self.calculate_scale()
        self.map_pos = self.calculate_centered_position()
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
        """Рисует секторные зоны территорий фракций на карте (диаграмма Вороного)."""
        from design_system import FACTION_COLORS
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT name, faction, coordinates FROM cities")
            cities = cursor.fetchall()
        except Exception:
            return

        if not cities:
            return

        # Собираем все города с их позициями
        city_list = []  # (drawn_x, drawn_y, faction, name)
        for name, faction, coords_str in cities:
            try:
                coords = ast.literal_eval(coords_str)
                drawn_x = coords[0] * self.map_scale + self.map_pos[0] + 38
                drawn_y = coords[1] * self.map_scale + self.map_pos[1] + 38
                city_list.append((drawn_x, drawn_y, faction, name))
            except Exception:
                continue

        if not city_list:
            return

        # Границы карты для обрезки ячеек Вороного
        map_x = self.map_pos[0]
        map_y = self.map_pos[1]
        map_w = self.base_map_width * self.map_scale
        map_h = self.base_map_height * self.map_scale
        clip_rect = (map_x, map_y, map_x + map_w, map_y + map_h)

        # Вычисляем ячейки Вороного для ВСЕХ городов
        sites = [(c[0], c[1]) for c in city_list]
        cells = self._compute_voronoi_cells(sites, clip_rect)

        # Строим карту: для каждого ребра определяем, какие фракции граничат
        # Ключ — отсортированная пара округлённых точек, значение — set фракций
        edge_factions = {}
        for idx, (cx, cy, faction, name) in enumerate(city_list):
            cell = cells[idx]
            if not cell or len(cell) < 3:
                continue
            n_pts = len(cell)
            for i in range(n_pts):
                p1 = (round(cell[i][0], 1), round(cell[i][1], 1))
                p2 = (round(cell[(i + 1) % n_pts][0], 1), round(cell[(i + 1) % n_pts][1], 1))
                edge_key = (min(p1, p2), max(p1, p2))
                if edge_key not in edge_factions:
                    edge_factions[edge_key] = set()
                edge_factions[edge_key].add(faction)

        with self.canvas:
            for idx, (cx, cy, faction, name) in enumerate(city_list):
                cell = cells[idx]
                if not cell or len(cell) < 3:
                    continue

                # Определяем цвет по фракции
                fc = FACTION_COLORS.get(faction)
                if fc:
                    color = fc['primary']
                    # Полупрозрачная заливка сектора (чуть темнее)
                    Color(color[0], color[1], color[2], 0.25)
                elif faction == 'Нейтрал':
                    Color(0.6, 0.6, 0.6, 0.12)
                else:
                    Color(0.5, 0.5, 0.5, 0.12)

                # Рисуем заполненный полигон через Mesh (triangle fan)
                vertices, indices = self._triangulate_polygon(cell, (cx, cy))
                if vertices and indices:
                    Mesh(vertices=vertices, indices=indices, mode='triangles')

                # Рисуем границы сектора — жирные для межфракционных, тонкие для своих
                n_pts = len(cell)
                for i in range(n_pts):
                    p1_raw = cell[i]
                    p2_raw = cell[(i + 1) % n_pts]
                    p1 = (round(p1_raw[0], 1), round(p1_raw[1], 1))
                    p2 = (round(p2_raw[0], 1), round(p2_raw[1], 1))
                    edge_key = (min(p1, p2), max(p1, p2))
                    factions_on_edge = edge_factions.get(edge_key, set())
                    is_border = len(factions_on_edge) > 1

                    if is_border:
                        # Жирная граница между разными фракциями
                        if fc:
                            Color(color[0], color[1], color[2], 0.7)
                        else:
                            Color(0.7, 0.7, 0.7, 0.5)
                        Line(points=[p1_raw[0], p1_raw[1], p2_raw[0], p2_raw[1]], width=2.5)
                    else:
                        # Тонкая граница внутри фракции
                        if fc:
                            Color(color[0], color[1], color[2], 0.35)
                        elif faction == 'Нейтрал':
                            Color(0.7, 0.7, 0.7, 0.15)
                        else:
                            Color(0.5, 0.5, 0.5, 0.15)
                        Line(points=[p1_raw[0], p1_raw[1], p2_raw[0], p2_raw[1]], width=1.2)

    def draw_fortresses(self):
        """Рисует крепости на карте с анимацией при смене фракции."""
        # Останавливаем анимацию щитов нежити перед перерисовкой
        if self._undead_anim_event:
            self._undead_anim_event.cancel()
            self._undead_anim_event = None
        if self._undead_shield_group:
            try:
                self.canvas.after.remove(self._undead_shield_group)
            except Exception:
                pass
            self._undead_shield_group = None
        self._undead_shield_data = []

        self.clear_widgets()
        self.fortress_icon_widgets.clear()
        self.fortress_data_for_canvas.clear()

        faction_images = {
            'Вампиры': 'files/buildings/giperion.png',
            'Север': 'files/buildings/arkadia.png',
            'Эльфы': 'files/buildings/celestia.png',
            'Адепты': 'files/buildings/eteria.png',
            'Элины': 'files/buildings/halidon.png',
            'Нежить': 'files/buildings/castle_death.png'
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

        # ← Список изменённых городов (ВНЕ основного цикла)
        changed_cities = []

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

            # --- Проверка изменения фракции ---
            previous_faction = self.previous_city_factions.get(fortress_name)
            # Города нежити всегда отображаются с иконкой castle_death
            if is_undead_city:
                image_path = 'files/buildings/castle_death.png'
            else:
                image_path = faction_images.get(kingdom, 'files/buildings/default.png')

            if not os.path.exists(image_path):
                image_path = 'files/buildings/default.png'

            # ← Если фракция изменилась — добавляем в список
            if previous_faction is not None and previous_faction != kingdom:
                changed_cities.append({
                    'name': fortress_name,
                    'new_image': image_path,
                    'pos': (drawn_x, drawn_y),
                    'old_faction': previous_faction,
                    'new_faction': kingdom
                })

            self.previous_city_factions[fortress_name] = kingdom

            # --- Создание виджета иконки ---
            icon_widget = Image(
                source=image_path,
                size=(77, 77),
                pos=(drawn_x, drawn_y),
                allow_stretch=True,
                keep_ratio=True,
            )
            self.add_widget(icon_widget)
            self.fortress_icon_widgets[fortress_name] = icon_widget

            # --- Анимация щита для городов нежити ---
            if is_undead_city:
                cx = drawn_x + 38.5  # Центр иконки 77x77
                cy = drawn_y + 38.5
                self._undead_shield_data.append((cx, cy))

            # --- Сохраняем данные для кликов ---
            self.fortress_data_for_canvas.append((fortress_name, kingdom, fort_x, fort_y, drawn_x, drawn_y))  # ← Исправлена скобка

            # --- Рисуем название города с обводкой ---
            display_name = f"{fortress_name}({kingdom})"

            label = CoreLabel(text=display_name, font_size=25, color=(1, 1, 1, 1))
            label.refresh()
            text_texture = label.texture
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

        # ← Запуск анимаций (ВНЕ цикла по городам)
        for city_data in changed_cities:
            Clock.schedule_once(
                lambda dt, data=city_data: self.animate_city_capture(data),
                0.05
            )

        # --- Запуск анимации щитов нежити ---
        self._start_undead_shield_animation()

        # --- Обновляем icon_coordinates в БД ---
        try:
            cursor2 = self.conn.cursor()
            for fortress_name, _, _, _, drawn_x, drawn_y in self.fortress_data_for_canvas:
                cursor2.execute(
                    "UPDATE cities SET icon_coordinates = ? WHERE name = ?",
                    (str([drawn_x, drawn_y]), fortress_name)
                )
            self.conn.commit()
        except sqlite3.Error as e:
            print(f"[DB ERROR] Не удалось обновить icon_coordinates: {e}")
        finally:
            cursor2.close()

    def _start_undead_shield_animation(self):
        """Рисует статичные щиты и анимирует молнии вокруг городов нежити."""
        if self._undead_anim_event:
            self._undead_anim_event.cancel()
            self._undead_anim_event = None
        if self._undead_shield_group:
            try:
                self.canvas.after.remove(self._undead_shield_group)
            except Exception:
                pass
            self._undead_shield_group = None
        # Очищаем статичный щит
        if hasattr(self, '_undead_static_group') and self._undead_static_group:
            try:
                self.canvas.after.remove(self._undead_static_group)
            except Exception:
                pass

        if not self._undead_shield_data:
            return

        import math
        import random as _rnd
        from kivy.graphics import InstructionGroup, Ellipse as GlEllipse, Line as GlLine

        # --- Статичный щит (рисуется один раз) ---
        static = InstructionGroup()
        shield_r = 52
        for cx, cy in self._undead_shield_data:
            # Внешнее свечение
            static.add(Color(0.2, 0.0, 0.3, 0.1))
            static.add(GlEllipse(
                pos=(cx - shield_r - 6, cy - shield_r - 6),
                size=(shield_r * 2 + 12, shield_r * 2 + 12)
            ))
            # Основной купол
            static.add(Color(0.06, 0.0, 0.1, 0.15))
            static.add(GlEllipse(
                pos=(cx - shield_r, cy - shield_r),
                size=(shield_r * 2, shield_r * 2)
            ))
            # Кольцо
            static.add(Color(0.3, 0.0, 0.45, 0.3))
            static.add(GlLine(
                ellipse=(cx - shield_r, cy - shield_r, shield_r * 2, shield_r * 2),
                width=1.5
            ))
        self._undead_static_group = static
        self.canvas.after.add(static)

        # --- Молнии (анимируются) ---
        # Кеш молний: для каждого города свой набор
        self._lightning_per_city = [[] for _ in self._undead_shield_data]

        def _gen_bolt(cx, cy):
            """Генерирует одну реалистичную молнию с ветвлением."""
            angle = _rnd.uniform(0, 2 * math.pi)
            length = _rnd.uniform(35, 60)
            # Основной ствол
            segments = _rnd.randint(5, 8)
            trunk = []
            px, py = cx, cy
            for s in range(segments):
                t = (s + 1) / segments
                # Основное направление + случайное отклонение (уменьшается к концу)
                jitter = (1.0 - t * 0.4) * 6
                nx = cx + math.cos(angle) * length * t + _rnd.uniform(-jitter, jitter)
                ny = cy + math.sin(angle) * length * t + _rnd.uniform(-jitter, jitter)
                trunk.append((px, py, nx, ny))
                px, py = nx, ny

            # Ветвления (1-2 штуки от случайных точек ствола)
            branches = []
            num_branches = _rnd.randint(1, 2)
            for _ in range(num_branches):
                if len(trunk) < 3:
                    break
                branch_idx = _rnd.randint(1, len(trunk) - 2)
                bx, by = trunk[branch_idx][2], trunk[branch_idx][3]
                b_angle = angle + _rnd.uniform(-0.8, 0.8)
                b_len = length * _rnd.uniform(0.2, 0.4)
                b_segs = _rnd.randint(2, 3)
                bpx, bpy = bx, by
                branch = []
                for bs in range(b_segs):
                    bt = (bs + 1) / b_segs
                    bnx = bx + math.cos(b_angle) * b_len * bt + _rnd.uniform(-4, 4)
                    bny = by + math.sin(b_angle) * b_len * bt + _rnd.uniform(-4, 4)
                    branch.append((bpx, bpy, bnx, bny))
                    bpx, bpy = bnx, bny
                branches.append(branch)

            return trunk, branches

        def _update_lightning(dt):
            # Удаляем старые молнии
            if self._undead_shield_group:
                try:
                    self.canvas.after.remove(self._undead_shield_group)
                except Exception:
                    pass

            group = InstructionGroup()

            for i, (cx, cy) in enumerate(self._undead_shield_data):
                # Перегенерируем 2-3 молнии
                bolts = []
                for _ in range(_rnd.randint(2, 3)):
                    bolts.append(_gen_bolt(cx, cy))

                for trunk, branches in bolts:
                    # Ствол: свечение + основная линия
                    trunk_pts = []
                    for x1, y1, x2, y2 in trunk:
                        trunk_pts.extend([x1, y1, x2, y2])

                    # Свечение (тёмно-фиолетовое, широкое)
                    group.add(Color(0.15, 0.0, 0.2, 0.35))
                    group.add(GlLine(points=trunk_pts, width=3.0))
                    # Основной разряд
                    group.add(Color(0.02, 0.0, 0.05, 0.9))
                    group.add(GlLine(points=trunk_pts, width=1.3))
                    # Яркий центр
                    group.add(Color(0.2, 0.0, 0.35, 0.5))
                    group.add(GlLine(points=trunk_pts, width=0.7))

                    # Ветвления (тоньше)
                    for branch in branches:
                        b_pts = []
                        for x1, y1, x2, y2 in branch:
                            b_pts.extend([x1, y1, x2, y2])
                        group.add(Color(0.05, 0.0, 0.1, 0.6))
                        group.add(GlLine(points=b_pts, width=1.0))
                        group.add(Color(0.2, 0.0, 0.3, 0.3))
                        group.add(GlLine(points=b_pts, width=0.5))

            self._undead_shield_group = group
            self.canvas.after.add(group)

        # Молнии обновляются 3 раза в секунду
        self._undead_anim_event = Clock.schedule_interval(_update_lightning, 0.3)

    def animate_city_capture(self, city_data):
        """Анимация вспышки при захвате города."""
        icon_widget = self.fortress_icon_widgets.get(city_data['name'])
        if not icon_widget:
            return

        print(f"[ANIMATION] Запуск вспышки для города {city_data['name']} "
              f"({city_data['old_faction']} → {city_data['new_faction']})")

        # ← Исправлено: opacity + scale для эффекта "вспышки"
        anim = Animation(
            opacity=0.4,
            duration=0.1
        ) & Animation(
            size=(90, 90),  # Увеличение иконки
            duration=0.1
        )

        anim += Animation(
            opacity=1.0,
            duration=0.15
        ) & Animation(
            size=(77, 77),  # Возврат к норме
            duration=0.15
        )

        anim.start(icon_widget)

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

    def draw_roads(self):
        """Рисует явные дороги из таблицы roads для более ясной географии карты."""
        self.canvas.after.clear()

        try:
            cursor = self.conn.cursor()
            # Загружаем города с их координатами
            cursor.execute("SELECT id, coordinates FROM cities")
            cities_data = cursor.fetchall()
            cities_coords = {city_id: ast.literal_eval(coords) for city_id, coords in cities_data}
            
            # Загружаем явные дороги из таблицы roads
            cursor.execute("SELECT city1, city2 FROM roads")
            roads_data = cursor.fetchall()
        except sqlite3.Error as e:
            print(f"Ошибка при загрузке дорог: {e}")
            return

        if not roads_data:
            print("[WARN] Таблица roads пуста, дороги не рисуются")
            return

        with self.canvas.after:
            # Основные дороги - серый цвет, толщина 2
            Color(0.4, 0.4, 0.4, 0.8)
            
            for city1_id, city2_id in roads_data:
                if city1_id not in cities_coords or city2_id not in cities_coords:
                    continue
                    
                coords1 = cities_coords[city1_id]
                coords2 = cities_coords[city2_id]
                
                drawn_x1 = coords1[0] * self.map_scale + self.map_pos[0]
                drawn_y1 = coords1[1] * self.map_scale + self.map_pos[1]
                drawn_x2 = coords2[0] * self.map_scale + self.map_pos[0]
                drawn_y2 = coords2[1] * self.map_scale + self.map_pos[1]
                
                # Рисуем линию дороги с тенью для глубины
                Color(0.2, 0.2, 0.2, 0.4)  # Тень
                Line(points=[drawn_x1 + 1, drawn_y1 + 1, drawn_x2 + 1, drawn_y2 + 1], width=3)
                
                # Основная линия дороги
                Color(0.55, 0.52, 0.45, 1)  # Песочно-бежевый цвет дороги
                Line(points=[drawn_x1, drawn_y1, drawn_x2, drawn_y2], width=2)

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


class ModernButton(Button):
    """Стилизованная кнопка с современным дизайном"""

    bg_color = ListProperty([0.2, 0.3, 0.4, 1])

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.background_normal = ''
        self.background_down = ''

        # Анимация при наведении (для ПК)
        if platform != 'android' and platform != 'ios':
            self.bind(
                on_enter=self.on_hover_enter,
                on_leave=self.on_hover_leave
            )

    def on_hover_enter(self, *args):
        Animation(background_color=[c * 1.2 for c in self.bg_color[:3]] + [1], duration=0.2).start(self)

    def on_hover_leave(self, *args):
        Animation(background_color=self.bg_color, duration=0.2).start(self)


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


class FactionButton(Button):
    """Кнопка выбора фракции с цветовой полоской и иконкой."""
    _DEFAULT_COLOR = [0.10, 0.14, 0.24, 0.95]
    _SELECTED_COLOR = [0.18, 0.22, 0.35, 1]

    # Цвета акцентных полосок
    _FACTION_ACCENTS = {
        'Север': (0.25, 0.52, 0.92, 1),
        'Эльфы': (0.22, 0.76, 0.32, 1),
        'Вампиры': (0.78, 0.10, 0.16, 1),
        'Адепты': (0.62, 0.22, 0.88, 1),
        'Элины': (0.92, 0.70, 0.10, 1),
    }

    _FACTION_ICONS = {
        'Север': 'files/sov/people.jpg',
        'Эльфы': 'files/sov/elfs.jpg',
        'Вампиры': 'files/sov/vampire.jpg',
        'Адепты': 'files/sov/adept.jpg',
        'Элины': 'files/sov/poly.jpg',
    }

    def __init__(self, **kwargs):
        btn_color = list(kwargs.pop('background_color', self._DEFAULT_COLOR))
        super().__init__(**kwargs)
        self.background_normal = ''
        self.background_down = ''
        self.background_color = (0, 0, 0, 0)
        self._default_color = btn_color
        self.halign = 'left'
        self.padding = [dp(48), 0]

        accent = self._FACTION_ACCENTS.get(self.text, (0.4, 0.4, 0.5, 1))

        with self.canvas.before:
            # Тень
            Color(0, 0, 0, 0.2)
            self._shadow = RoundedRectangle(
                pos=(self.x + dp(2), self.y - dp(1)),
                size=self.size, radius=[dp(10)]
            )
            # Фон
            self._ci = Color(*btn_color)
            self._rr = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(10)])
            # Акцентная полоска слева
            Color(*accent)
            self._accent = RoundedRectangle(
                pos=self.pos,
                size=(dp(5), self.height),
                radius=[dp(10), 0, 0, dp(10)]
            )

        # Иконка фракции
        icon_path = self._FACTION_ICONS.get(self.text, '')
        if icon_path:
            self._icon = Image(
                source=icon_path,
                size_hint=(None, None),
                size=(dp(32), dp(32)),
                pos=(self.x + dp(8), self.center_y - dp(16)),
                allow_stretch=True, keep_ratio=True,
            )
            self.add_widget(self._icon)
        else:
            self._icon = None

        self.bind(pos=self._update_gfx, size=self._update_gfx)

    def _update_gfx(self, *args):
        self._rr.pos = self.pos
        self._rr.size = self.size
        self._shadow.pos = (self.x + dp(2), self.y - dp(1))
        self._shadow.size = self.size
        self._accent.pos = self.pos
        self._accent.size = (dp(5), self.height)
        if self._icon:
            self._icon.pos = (self.x + dp(8), self.center_y - dp(16))


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
        super(KingdomSelectionWidget, self).__init__(**kwargs)
        is_android = platform == 'android'
        self.selected_map = selected_map
        self.selected_button = None
        self.conn = conn
        # Инициализируем выборы игрока
        self.selected_ideology = 'random'
        self.selected_allies = 'random'

        # Определяем, какая это ориентация
        is_landscape = Window.width > Window.height

        # Определяем базовые размеры в зависимости от платформы и ориентации
        screen_height = Window.height
        screen_width = Window.width

        if is_android:
            if is_landscape:
                # Для альбомной ориентации Android
                self.base_font_size = max(dp(10), min(dp(16), screen_height * 0.025))
                self.panel_height_ratio = 0.85  # Увеличиваем высоту панелей в альбомной ориентации
                self.panel_y_offset = 0.08  # Поднимаем панели еще выше
            else:
                # Для портретной ориентации Android
                self.base_font_size = max(dp(12), min(dp(18), screen_height * 0.022))
                self.panel_height_ratio = 0.80  # Увеличиваем высоту панелей
                self.panel_y_offset = 0.06  # Смещаем панели выше
        else:
            self.base_font_size = max(dp(14), min(dp(24), screen_height * 0.03))
            self.panel_height_ratio = 0.6
            self.panel_y_offset = 0.0

        # ======== ФОН ВИДЕО ========
        self.bg_video = Video(
            source='files/menu/choice.mp4',
            state='play',
            options={'eos': 'loop'},
            allow_stretch=True,
            keep_ratio=False,
            size_hint=(1, 1),
            pos_hint={'x': 0, 'y': 0}
        )
        self.bg_video.bind(on_eos=self.loop_video)
        self.add_widget(self.bg_video)

        # ======== ОБЩИЙ КОНТЕЙНЕР ДЛЯ ВСЕХ ЭЛЕМЕНТОВ ========
        self.main_container = MDFloatLayout()
        self.add_widget(self.main_container)

        # ======== ЗАГОЛОВОК «Выберите сторону» ========
        if is_android:
            if is_landscape:
                title_size = self.base_font_size * 1.5
                title_height = dp(35)
                title_top = 0.96  # Поднимаем заголовок выше
            else:
                title_size = self.base_font_size * 1.8
                title_height = dp(40)  # Уменьшаем высоту заголовка для портретной
                title_top = 0.97  # Поднимаем заголовок
        else:
            title_size = self.base_font_size * 1.5
            title_height = dp(60)
            title_top = 0.97

        self.select_side_label = MDLabel(
            text="Выберите сторону",
            font_style="H5",
            theme_text_color="Custom",
            text_color=(1.0, 0.88, 0.50, 1),
            outline_color=(0, 0, 0, 1),
            outline_width=2,
            halign='center',
            valign='middle',
            size_hint=(0.8, None),
            height=title_height,
            font_size=title_size,
            bold=True,
            pos_hint={'center_x': 0.22, 'top': 0.88 if is_android else 0.88}
        )
        self.add_widget(self.select_side_label)

        # ======== ПАНЕЛЬ КНОПОК ФРАКЦИЙ (левая часть) ========
        panel_height = self.panel_height_ratio
        panel_y_center = 0.5 + self.panel_y_offset

        # Адаптируем ширину панелей в зависимости от ориентации
        if is_landscape:
            panel_width = 0.35  # Уже в альбомной ориентации
        else:
            panel_width = 0.4

        self.faction_panel_container = MDFloatLayout(
            size_hint=(panel_width, panel_height),
            pos_hint={'x': 0.05, 'center_y': panel_y_center}
        )

        # Фон для панели фракций
        with self.faction_panel_container.canvas.before:
            Color(0.05, 0.06, 0.11, 0.92)
            self.faction_bg = RoundedRectangle(
                pos=self.faction_panel_container.pos,
                size=self.faction_panel_container.size,
                radius=[dp(20)]
            )

        def update_faction_bg(instance, value):
            self.faction_bg.pos = instance.pos
            self.faction_bg.size = instance.size

        self.faction_panel_container.bind(pos=update_faction_bg, size=update_faction_bg)

        # ======== ЗАГРУЗКА ДАННЫХ ИЗ БД ========
        self.faction_data = self.load_factions_from_db()

        # ======== КНОПКИ ФРАКЦИЙ ========
        # Увеличиваем размер кнопок для Android
        if is_android:
            if is_landscape:
                button_height = dp(38)  # УМЕНЬШИЛ на 2dp
                spacing_val = dp(3)      # УМЕНЬШИЛ spacing
                button_font_size = self.base_font_size * 0.95  # УМЕНЬШИЛ шрифт
            else:
                button_height = dp(40)   # УМЕНЬШИЛ на 2dp
                spacing_val = dp(3)      # УМЕНЬШИЛ spacing
                button_font_size = self.base_font_size * 1.0   # Немного уменьшил шрифт
        else:
            button_height = dp(42)        # УМЕНЬШИЛ на 3dp
            spacing_val = dp(4)           # УМЕНЬШИЛ spacing
            button_font_size = self.base_font_size

        # Рассчитываем общую высоту для панели
        num_factions = len(self.faction_data)
        total_height = button_height * num_factions + spacing_val * (num_factions - 1) + dp(15)  # УМЕНЬШИЛ padding

        self.kingdom_buttons = MDBoxLayout(
            orientation='vertical',
            spacing=spacing_val,
            size_hint=(0.85, None),
            height=total_height,
            pos_hint={'center_x': 0.5, 'center_y': 0.5}
        )

        # Сохраняем кнопки в словаре для быстрого доступа
        self.kingdom_button_widgets = {}
        try:
            for faction in self.faction_data:
                kingdom = faction.get('name', 'Неизвестная фракция')
                btn = FactionButton(
                    text=kingdom,
                    size_hint_y=None,
                    height=button_height,
                    font_size=button_font_size,
                    background_color=FactionButton._DEFAULT_COLOR,
                    color=(1, 1, 1, 1),
                    bold=True,
                    opacity=1,
                    padding=[dp(8), 0]
                )
                btn.bind(on_release=self.select_kingdom)
                self.kingdom_buttons.add_widget(btn)
                self.kingdom_button_widgets[kingdom] = btn
        except Exception as e:
            print(f"Ошибка при создании кнопок фракций: {e}")

        self.faction_panel_container.add_widget(self.kingdom_buttons)
        self.main_container.add_widget(self.faction_panel_container)

        # ======== ПАНЕЛЬ НАСТРОЕК (правая часть) ========
        self.settings_panel_container = MDFloatLayout(
            size_hint=(0.4, panel_height),
            pos_hint={'right': 0.95, 'center_y': panel_y_center}
        )

        # Фон для панели настроек
        with self.settings_panel_container.canvas.before:
            Color(0.05, 0.06, 0.11, 0.92)
            self.settings_bg = RoundedRectangle(
                pos=self.settings_panel_container.pos,
                size=self.settings_panel_container.size,
                radius=[dp(20)]
            )

        def update_settings_bg(instance, value):
            self.settings_bg.pos = instance.pos
            self.settings_bg.size = instance.size

        self.settings_panel_container.bind(pos=update_settings_bg, size=update_settings_bg)

        # Рассчитываем высоту для каждого контейнера в настройках
        if is_android:
            ideology_container_height = dp(90)   # УМЕНЬШИЛ еще на 5dp
            allies_container_height = dp(95)      # УМЕНЬШИЛ на 5dp
            faction_info_container_height = dp(80) # УМЕНЬШИЛ на 5dp
            spinner_height = dp(32)                # УМЕНЬШИЛ на 3dp
            bonus_height = dp(28)                   # УМЕНЬШИЛ на 2dp
            label_height = dp(18)                    # УМЕНЬШИЛ на 2dp
            stat_row_height = dp(16)                 # УМЕНЬШИЛ на 2dp
        else:
            ideology_container_height = dp(115)
            allies_container_height = dp(115)
            faction_info_container_height = dp(95)
            spinner_height = dp(38)
            bonus_height = dp(38)
            label_height = dp(23)
            stat_row_height = dp(18)

        total_settings_height = ideology_container_height + allies_container_height + faction_info_container_height + dp(25)  # УМЕНЬШИЛ общий отступ

        # Основной контейнер для вертикального расположения всех блоков
        self.settings_content_container = MDBoxLayout(
            orientation='vertical',
            spacing=dp(4) if is_android else dp(12),  # ЕЩЕ УМЕНЬШИЛ spacing
            size_hint=(0.85, 0.9),
            pos_hint={'center_x': 0.5, 'center_y': 0.5}
        )
        self.settings_panel_container.add_widget(self.settings_content_container)

        # ======== ВЫБОР ИДЕОЛОГИИ ========
        ideology_container = MDBoxLayout(
            orientation='vertical',
            spacing=dp(2) if is_android else dp(6),  # ЕЩЕ УМЕНЬШИЛ spacing
            size_hint=(1, None),
            height=ideology_container_height,
        )

        # Заголовок идеологии
        ideology_label = MDLabel(
            text="Идеология:",
            font_style="Body1",
            theme_text_color="Custom",
            text_color=(0.75, 0.55, 0.15, 1),
            size_hint_y=None,
            height=label_height,
            halign='left',
            bold=True,
            font_size=self.base_font_size * 0.85
        )
        ideology_label.bind(size=ideology_label.setter('text_size'))
        ideology_container.add_widget(ideology_label)

        # Выпадающий список идеологии
        self.ideology_spinner = ModernSpinner(
            text='Случайная',
            values=('Случайная', 'Смирение', 'Борьба'),
            size_hint=(1, None),
            height=spinner_height,
            background_color=(0.2, 0.3, 0.4, 1),
            color=(1, 1, 1, 1),
            font_size=self.base_font_size * 0.75  # УМЕНЬШИЛ шрифт
        )
        self.ideology_spinner.bind(text=self.on_ideology_selected)
        ideology_container.add_widget(self.ideology_spinner)

        # КОНТЕЙНЕР ДЛЯ БОНУСОВ ИДЕОЛОГИИ
        self.ideology_bonus_container = MDFloatLayout(
            size_hint=(1, None),
            height=bonus_height,
        )

        # Фон для бонуса
        with self.ideology_bonus_container.canvas.before:
            Color(0.10, 0.14, 0.22, 0.90)
            self.ideology_bonus_bg = RoundedRectangle(
                pos=self.ideology_bonus_container.pos,
                size=self.ideology_bonus_container.size,
                radius=[4]  # УМЕНЬШИЛ радиус
            )

        def update_ideology_bonus_bg(instance, value):
            self.ideology_bonus_bg.pos = instance.pos
            self.ideology_bonus_bg.size = instance.size

        self.ideology_bonus_container.bind(pos=update_ideology_bonus_bg, size=update_ideology_bonus_bg)

        # Иконка и текст бонуса
        ideology_bonus_layout = MDBoxLayout(
            orientation='horizontal',
            spacing=dp(6),  # УМЕНЬШИЛ spacing
            size_hint=(0.95, 0.85),
            pos_hint={'center_x': 0.5, 'center_y': 0.5}
        )

        # Создаем Image-виджет для иконки бонуса
        self.ideology_bonus_icon = Image(
            source='files/pict/menu/bonus_icon.png',
            size_hint=(None, None),
            size=(dp(18) if is_android else dp(22), dp(18) if is_android else dp(22)),  # УМЕНЬШИЛ размер
            allow_stretch=True,
            keep_ratio=True
        )

        self.ideology_bonus_label = MDLabel(
            text="Бонус не выбран",
            font_style="Caption",
            theme_text_color="Custom",
            text_color=(0.8, 0.9, 1.0, 1),
            halign='left',
            valign='middle',
            font_size=self.base_font_size * 0.65  # УМЕНЬШИЛ шрифт
        )
        self.ideology_bonus_label.bind(size=self.ideology_bonus_label.setter('text_size'))

        ideology_bonus_layout.add_widget(self.ideology_bonus_icon)
        ideology_bonus_layout.add_widget(self.ideology_bonus_label)
        self.ideology_bonus_container.add_widget(ideology_bonus_layout)
        ideology_container.add_widget(self.ideology_bonus_container)
        self.settings_content_container.add_widget(ideology_container)

        # ======== ВЫБОР КОЛИЧЕСТВА СОЮЗНИКОВ ========
        allies_container = MDBoxLayout(
            orientation='vertical',
            spacing=dp(2) if is_android else dp(6),  # УМЕНЬШИЛ spacing
            size_hint=(1, None),
            height=allies_container_height,
        )

        # Заголовок союзников
        allies_label = MDLabel(
            text="Единомышленники:",
            font_style="Body1",
            theme_text_color="Custom",
            text_color=(0.75, 0.55, 0.15, 1),
            size_hint_y=None,
            height=label_height,
            halign='left',
            bold=True,
            font_size=self.base_font_size * 0.85
        )
        allies_label.bind(size=allies_label.setter('text_size'))
        allies_container.add_widget(allies_label)

        # Выпадающий список союзников
        self.allies_spinner = ModernSpinner(
            text='Случайное количество',
            values=('Случайное количество', '1', '2'),
            size_hint=(1, None),
            height=spinner_height,
            background_color=(0.2, 0.3, 0.4, 1),
            color=(1, 1, 1, 1),
            font_size=self.base_font_size * 0.75  # УМЕНЬШИЛ шрифт
        )
        self.allies_spinner.bind(text=self.on_allies_selected)
        allies_container.add_widget(self.allies_spinner)

        # КОНТЕЙНЕР ДЛЯ ИНФОРМАЦИИ О СОЮЗНИКАХ
        self.allies_info_container = MDFloatLayout(
            size_hint=(1, None),
            height=bonus_height,
        )

        # Фон для информации о союзниках
        with self.allies_info_container.canvas.before:
            Color(0.10, 0.14, 0.22, 0.90)
            self.allies_info_bg = RoundedRectangle(
                pos=self.allies_info_container.pos,
                size=self.allies_info_container.size,
                radius=[4]  # УМЕНЬШИЛ радиус
            )

        def update_allies_info_bg(instance, value):
            self.allies_info_bg.pos = instance.pos
            self.allies_info_bg.size = instance.size

        self.allies_info_container.bind(pos=update_allies_info_bg, size=update_allies_info_bg)

        # Иконки и текст союзников
        allies_info_layout = MDBoxLayout(
            orientation='horizontal',
            spacing=dp(8),  # УМЕНЬШИЛ spacing
            size_hint=(0.95, 0.85),
            pos_hint={'center_x': 0.5, 'center_y': 0.5}
        )

        self.allies_count_label = MDLabel(
            text="Случайно 1 или 2 союзника",
            font_style="Caption",
            theme_text_color="Custom",
            text_color=(0.8, 0.9, 1.0, 1),
            halign='left',
            valign='middle',
            font_size=self.base_font_size * 0.65  # УМЕНЬШИЛ шрифт
        )
        self.allies_count_label.bind(size=self.allies_count_label.setter('text_size'))

        allies_info_layout.add_widget(self.allies_count_label)
        self.allies_info_container.add_widget(allies_info_layout)
        allies_container.add_widget(self.allies_info_container)
        self.settings_content_container.add_widget(allies_container)

        # ======== ИНФОРМАЦИЯ О ФРАКЦИИ ========
        self.faction_info_container = MDBoxLayout(
            orientation='vertical',
            spacing=dp(2) if is_android else dp(4),  # УМЕНЬШИЛ spacing
            size_hint=(1, None),
            height=faction_info_container_height,
        )

        self.stats_labels = {}
        stats_names = ["Доход Крон:", "Доход Кристаллов:", "Армия:"]

        for stat_name in stats_names:
            stat_row = MDBoxLayout(
                orientation='horizontal',
                size_hint_y=None,
                height=stat_row_height,
                spacing=dp(2)  # УМЕНЬШИЛ spacing
            )

            label = MDLabel(
                text=stat_name,
                font_style="Caption",
                theme_text_color="Custom",
                text_color=(0.9, 0.9, 0.9, 1),
                size_hint_x=0.6,
                halign='left',
                font_size=self.base_font_size * 0.65  # УМЕНЬШИЛ шрифт
            )
            label.bind(size=label.setter('text_size'))

            icons_box = MDBoxLayout(
                orientation='horizontal',
                size_hint_x=0.4,
                spacing=dp(1)  # УМЕНЬШИЛ spacing
            )

            # Заполняем серыми иконками по умолчанию
            icon_size = dp(10) if is_android else dp(12)  # УМЕНЬШИЛ размер иконок
            for i in range(3):
                img = Image(
                    source='files/pict/menu/grey.png',
                    size_hint=(None, None),
                    size=(icon_size, icon_size)
                )
                icons_box.add_widget(img)

            stat_row.add_widget(label)
            stat_row.add_widget(icons_box)
            self.faction_info_container.add_widget(stat_row)
            self.stats_labels[stat_name] = icons_box

        # Описание уникальной способности фракции
        self.faction_ability_label = MDLabel(
            text="",
            font_style="Caption",
            theme_text_color="Custom",
            text_color=(0.85, 0.75, 0.4, 1),
            size_hint_y=None,
            height=dp(36),
            halign='left',
            valign='middle',
            font_size=self.base_font_size * 0.6,
            markup=True,
        )
        self.faction_ability_label.bind(size=self.faction_ability_label.setter('text_size'))
        self.faction_info_container.add_widget(self.faction_ability_label)

        self.settings_content_container.add_widget(self.faction_info_container)
        self.main_container.add_widget(self.settings_panel_container)
        # ======== ЧЕКБОКС "ОБУЧЕНИЕ" ========
        tutorial_container = MDBoxLayout(
            orientation='vertical',
            spacing=dp(3) if is_android else dp(6),  # УМЕНЬШИЛ spacing
            size_hint=(1, None),
            height=dp(45) if is_android else dp(55),  # УМЕНЬШИЛ высоту
        )

        # Контейнер для чекбокса и надписи
        checkbox_row = MDBoxLayout(
            orientation='horizontal',
            spacing=dp(6),  # УМЕНЬШИЛ spacing
            size_hint=(1, None),
            height=dp(28) if is_android else dp(32),  # УМЕНЬШИЛ высоту
            padding=[dp(3), 0, 0, 0]  # УМЕНЬШИЛ padding
        )

        # Чекбокс
        self.tutorial_checkbox = MDCheckbox(
            size_hint=(None, None),
            size=(dp(26), dp(26)) if is_android else (dp(30), dp(30)),  # УМЕНЬШИЛ размер
            active=False
        )

        # Надпись рядом с чекбоксом
        tutorial_text = MDLabel(
            text="ОБУЧЕНИЕ(Рекомендуется: 2 союзника)",
            font_style="Caption",
            theme_text_color="Custom",
            text_color=(0.9, 0.9, 0.9, 1),
            size_hint_y=None,
            height=dp(28),
            halign='left',
            valign='middle',
            font_size=self.base_font_size * 0.7  # УМЕНЬШИЛ шрифт
        )
        tutorial_text.bind(size=tutorial_text.setter('text_size'))

        checkbox_row.add_widget(self.tutorial_checkbox)
        checkbox_row.add_widget(tutorial_text)
        tutorial_container.add_widget(checkbox_row)
        self.settings_content_container.add_widget(tutorial_container)

        # Сохраняем состояние обучения
        self.tutorial_enabled = False
        self.tutorial_checkbox.bind(active=self.on_tutorial_toggled)
        # ======== КНОПКИ ВНИЗУ ========
        # Определяем размеры кнопок в зависимости от платформы
        if is_android:
            button_container_width = 0.4
            back_btn_width = dp(85)   # УМЕНЬШИЛ ширину
            start_btn_width = dp(160)  # УМЕНЬШИЛ ширину
            button_height = dp(38)     # УМЕНЬШИЛ высоту
            button_font_size = self.base_font_size * 0.85  # УМЕНЬШИЛ шрифт
            buttons_y_pos = 0.02  # Опустил чуть ниже
        else:
            button_container_width = 0.4
            back_btn_width = dp(95)
            start_btn_width = dp(180)
            button_height = dp(42)
            button_font_size = self.base_font_size * 0.85
            buttons_y_pos = 0.02

        # Контейнер для кнопок
        self.bottom_buttons_container = MDBoxLayout(
            orientation='horizontal',
            size_hint=(None, None),
            size=(Window.width * button_container_width, button_height + dp(3)),  # УМЕНЬШИЛ общую высоту
            spacing=dp(6) if is_android else dp(8),  # УМЕНЬШИЛ spacing
            padding=[dp(3), 0, dp(3), 0],  # УМЕНЬШИЛ padding
            pos_hint={'x': 0.05, 'y': buttons_y_pos}
        )

        # КНОПКА «Вернуться в главное меню»
        self.back_btn = ModernButton(
            text="В меню",
            size_hint=(None, None),
            size=(back_btn_width, button_height),
            color=(1, 1, 1, 1),
            bold=True,
            font_size=button_font_size,
            background_color=(0.52, 0.12, 0.12, 1)
        )
        self.back_btn.bind(on_release=self.back_to_menu)

        # КНОПКА «Начать игру»
        self.start_game_button = ModernButton(
            text="Начать игру",
            size_hint=(None, None),
            size=(start_btn_width, button_height),
            font_size=button_font_size * 1.05,
            bold=True,
            color=(1, 1, 1, 1),
            background_color=(0.14, 0.52, 0.18, 1),
            opacity=1
        )
        self.start_game_button.bind(on_release=self.start_game)

        # Добавляем кнопки в контейнер
        self.bottom_buttons_container.add_widget(self.back_btn)
        self.bottom_buttons_container.add_widget(self.start_game_button)

        # Добавляем контейнер в основной контейнер
        self.main_container.add_widget(self.bottom_buttons_container)

        # ======== Запускаем анимацию появления ========
        Clock.schedule_once(lambda dt: self.animate_in(), 0.3)

    def on_tutorial_toggled(self, checkbox, value):
        """Обработка переключения режима обучения"""
        self.tutorial_enabled = value
        print(f"Режим обучения: {'ВКЛЮЧЕН' if value else 'ВЫКЛЮЧЕН'}")

    def on_ideology_selected(self, spinner, text):
        """Обработка выбора идеологии"""
        if text == 'Случайная':
            self.selected_ideology = 'random'
            # Обновляем текст, цвет и иконку
            self.ideology_bonus_label.text = "Идеология будет выбрана случайно"
            self.ideology_bonus_label.color = (0.8, 0.8, 0.8, 1)
            # Устанавливаем иконку по умолчанию или оставляем текущей
            # self.ideology_bonus_icon.source = 'files/pict/menu/bonus_icon.png' # Пример иконки по умолчанию
            # Если не хотите менять иконку для 'Случайная', просто не изменяйте self.ideology_bonus_icon.source
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
        """Анимация появления элементов"""
        # Начальные позиции для анимации
        self.faction_panel_container.pos_hint = {'x': -0.5, 'center_y': 0.5}
        self.settings_panel_container.pos_hint = {'right': 1.5, 'center_y': 0.5}
        self.start_game_button.opacity = 0
        self.back_btn.opacity = 0
        # Анимация панелей
        anim_faction = Animation(pos_hint={'x': 0.05, 'center_y': 0.5}, duration=0.8, t='out_back')
        anim_settings = Animation(pos_hint={'right': 0.95, 'center_y': 0.5}, duration=0.8, t='out_back')
        anim_faction.start(self.faction_panel_container)
        anim_settings.start(self.settings_panel_container)
        # Появление кнопок
        Clock.schedule_once(lambda dt: Animation(opacity=1, duration=0.5).start(self.start_game_button), 0.8)
        Clock.schedule_once(lambda dt: Animation(opacity=1, duration=0.5).start(self.back_btn), 0.9)
        # Появление кнопок фракций
        faction_buttons = list(self.kingdom_buttons.children)[::-1]
        for idx, btn in enumerate(faction_buttons):
            Clock.schedule_once(
                lambda dt, widget=btn: Animation(opacity=1, duration=0.3).start(widget),
                0.5 + idx * 0.1
            )
        self.buttons_locked = True
        Clock.schedule_once(lambda dt: setattr(self, 'buttons_locked', False), 1.5)

    def loop_video(self, instance):
        instance.state = 'stop'
        instance.state = 'play'

    def calculate_panel_height(self, btn_height, spacing, padding):
        num_buttons = len(self.faction_data)
        return (btn_height * num_buttons) + (spacing * (num_buttons - 1)) + (padding[1] + padding[3])

    def back_to_menu(self, instance):
        if getattr(self, 'buttons_locked', False):
            return
        # Останавливаем видео
        if hasattr(self, 'bg_video'):
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

        # Сбрасываем цвет предыдущей выбранной кнопки
        if self.selected_button and self.selected_button is not instance:
            self.selected_button._ci.rgba = FactionButton._DEFAULT_COLOR

        # Устанавливаем новую выбранную кнопку (золотой цвет)
        self.selected_button = instance
        instance._ci.rgba = FactionButton._SELECTED_COLOR

        kingdom_name = instance.text
        self.update_faction_stats(kingdom_name)
        from kivy.app import App
        app = App.get_running_app()
        app.selected_kingdom = kingdom_name

    FACTION_ABILITIES = {
        'Север': '[b]Шквал[/b] — если бонусы увеличили урон в 5+ раз, ещё +60%',
        # Примечание: символ → убран из описания, только текст
        'Эльфы': '[b]Лесная хитрость[/b] — +10% инициатива всех юнитов в бою',
        'Вампиры': '[b]Вампиризм[/b] — 5% убитых врагов воскресают как ваши юниты',
        'Адепты': '[b]Святое благословение[/b] — +20% защита при обороне городов',
        'Элины': '[b]Торговая империя[/b] — +15% доход крон (стакается с Рынком)',
    }

    def update_faction_stats(self, kingdom):
        """Обновляет статистику и способность выбранной фракции"""
        stats = {
            "Север": {"Доход Крон:": 3, "Доход Кристаллов:": 1, "Армия:": 2},
            "Эльфы": {"Доход Крон:": 2, "Доход Кристаллов:": 2, "Армия:": 2},
            "Вампиры": {"Доход Крон:": 2, "Доход Кристаллов:": 2, "Армия:": 3},
            "Элины": {"Доход Крон:": 1, "Доход Кристаллов:": 3, "Армия:": 1},
            "Адепты": {"Доход Крон:": 1, "Доход Кристаллов:": 2, "Армия:": 3}
        }
        data = stats.get(kingdom)
        if not data:
            return
        # Обновляем иконки для каждой характеристики
        for stat_name, icons_box in self.stats_labels.items():
            value = data.get(stat_name, 0)
            # Очищаем старые иконки
            icons_box.clear_widgets()
            # Добавляем новые иконки
            for i in range(3):
                if i < value:
                    img = Image(
                        source='files/pict/menu/full.png',
                        size_hint=(None, None),
                        size=(dp(16), dp(16))
                    )
                else:
                    img = Image(
                        source='files/pict/menu/grey.png',
                        size_hint=(None, None),
                        size=(dp(16), dp(16))
                    )
                icons_box.add_widget(img)

        # Обновляем описание уникальной способности
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
        self.disable_all_buttons(True)
        # Останавливаем фоновое видео
        if hasattr(self, 'bg_video'):
            self.bg_video.state = 'stop'

        # Создаем оверлей с видео
        overlay = MDFloatLayout(size=Window.size)
        self.overlay = overlay
        self.add_widget(overlay)
        self.start_video = Video(
            source='files/menu/start_game.mp4',
            state='play',
            options={'eos': 'stop'},
            allow_stretch=True,
            keep_ratio=False,
            size=Window.size,
            pos=(0, 0)
        )
        overlay.add_widget(self.start_video)
        self.start_video.bind(on_eos=self.on_start_video_end)
        Clock.schedule_once(self.force_start_game, 3)

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
        """Очистка и запуск игры"""
        restore_from_backup(self.conn)
        # Очищаем оверлей
        if hasattr(self, 'overlay') and self.overlay in self.children:
            self.remove_widget(self.overlay)
        self.disable_all_buttons(False)
        try:
            from kivy.app import App
            app = App.get_running_app()
            selected_kingdom = app.selected_kingdom
            MapWidget = globals().get('MapWidget')
            GameScreen = globals().get('GameScreen')
            if not MapWidget or not GameScreen:
                # Попробуем импортировать из текущего модуля
                import sys
                current_module = sys.modules[__name__]
                MapWidget = getattr(current_module, 'MapWidget', None)
                GameScreen = getattr(current_module, 'GameScreen', None)
            if MapWidget and GameScreen:
                # Создаем виджет карты
                map_widget = MapWidget(selected_kingdom=selected_kingdom, player_kingdom=selected_kingdom,
                                       conn=self.conn)
                # Загружаем города (нужно реализовать load_cities_from_db)
                cities = load_cities_from_db(self.conn, selected_kingdom)
                # Создаем экран игры
                game_screen = GameScreen(
                    selected_kingdom,
                    cities,
                    player_ideology=self.selected_ideology,
                    player_allies=self.selected_allies,
                    tutorial_enabled=self.tutorial_enabled,
                    conn=self.conn
                )
                app.root.clear_widgets()
                app.root.add_widget(map_widget)
                app.root.add_widget(game_screen)
                # Запускаем анимацию мигания города
                if hasattr(map_widget, 'blink_player_city_icon'):
                    Clock.schedule_once(lambda dt: map_widget.blink_player_city_icon(), 1.0)
            else:
                print("Ошибка: не найден MapWidget или GameScreen")
                # Создаем простой экран игры без карты
                cities = []
                game_screen = GameScreen(
                    selected_kingdom,
                    cities,
                    conn=self.conn,
                    player_ideology=self.selected_ideology,
                    player_allies=self.selected_allies
                )
                app.root.clear_widgets()
                app.root.add_widget(game_screen)
        except Exception as e:
            print(f"Ошибка при запуске игры: {e}")
            import traceback
            traceback.print_exc()

    def disable_all_buttons(self, disabled=True):
        """Блокировка/разблокировка всех кнопок"""
        for child in self.main_container.walk():
            if isinstance(child, (ModernButton, MDFlatButton, ModernSpinner)):
                child.disabled = disabled


class RoundedButton(Button):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.background_normal = ''
        self.background_color = (0, 0, 0, 0)
        self.color = (1, 1, 1, 1)  # Белый текст по умолчанию
        self.bind(pos=self.update_canvas, size=self.update_canvas)

    def update_canvas(self, *args):
        self.canvas.before.clear()
        with self.canvas.before:
            # Основной цвет кнопки
            Color(0.1, 0.1, 0.3, 0.85)
            RoundedRectangle(
                pos=self.pos,
                size=self.size,
                radius=[25]
            )
            # Рамка с эффектом свечения
            Color(0.3, 0.3, 0.8, 0.7)
            Line(
                rounded_rectangle=(self.x, self.y, self.width, self.height, 25),
                width=1.2
            )


from kivy.graphics import Color, RoundedRectangle, Line, Ellipse, Rectangle
from kivy.properties import ListProperty, NumericProperty, BooleanProperty
import math
import random


class GameButton(Button):
    """Стильная игровая кнопка для мобильных устройств (тач-интерфейс)"""

    # Свойства Kivy для анимаций
    base_color = ListProperty([0.15, 0.15, 0.35, 0.95])
    accent_color = ListProperty([0.3, 0.6, 0.9, 1])
    hover_scale = NumericProperty(1.0)
    glow_intensity = NumericProperty(0.0)
    press_depth = NumericProperty(0.0)
    is_touched = BooleanProperty(False)

    def __init__(self, **kwargs):
        # Извлекаем button_type из kwargs
        self.button_type = kwargs.pop('button_type', 'default')

        # Устанавливаем цвета в зависимости от типа кнопки
        self.set_colors_by_type()

        super().__init__(**kwargs)

        # Настройки кнопки С ЧЕРНОЙ ОБВОДКОЙ
        self.background_normal = ''
        self.background_color = (0, 0, 0, 0)
        self.color = (1, 1, 1, 1)  # Белый текст
        self.font_size = '20sp'
        self.bold = True

        # НАСТРОЙКИ ОБВОДКИ ТЕКСТА
        self.outline_color = (0, 0, 0, 1)  # ЧЕРНАЯ обводка
        self.outline_width = 2  # Толщина обводки

        # Для эффектов
        self.energy = 0.0
        self.particles = []
        self.active_particles = []
        self.touch_ripples = []

        # Для мобильного интерфейса
        self.touch_down_time = 0
        self.is_long_press = False

        self.bind(
            pos=self.update_canvas,
            size=self.update_canvas
        )

        # Создаем начальные частицы
        self.create_particles()

        # Отключаем hover-эффекты для мобильных
        self.always_release = True

    def set_colors_by_type(self):
        """Устанавливаем цвета в зависимости от типа кнопки"""
        color_schemes = {
            "start": {
                "base": [0.15, 0.25, 0.45, 0.95],
                "accent": [0.4, 0.7, 1.0, 1]
            },
            "rating": {
                "base": [0.15, 0.35, 0.25, 0.95],
                "accent": [0.4, 0.9, 0.6, 1]
            },
            "help": {
                "base": [0.35, 0.25, 0.15, 0.95],
                "accent": [1.0, 0.8, 0.4, 1]
            },
            "author": {
                "base": [0.35, 0.15, 0.35, 0.95],
                "accent": [0.9, 0.4, 0.9, 1]
            },
            "exit": {
                "base": [0.35, 0.15, 0.15, 0.95],
                "accent": [1.0, 0.4, 0.4, 1]
            },
            "default": {
                "base": [0.15, 0.15, 0.35, 0.95],
                "accent": [0.3, 0.6, 0.9, 1]
            }
        }

        scheme = color_schemes.get(self.button_type, color_schemes["default"])
        self.base_color = scheme["base"]
        self.accent_color = scheme["accent"]

    def create_particles(self):
        """Создаем фоновые частицы"""
        for _ in range(6):
            particle = {
                'x': random.uniform(0.1, 0.9),
                'y': random.uniform(0.1, 0.9),
                'size': random.uniform(2, 4),
                'speed_x': random.uniform(-0.1, 0.1),
                'speed_y': random.uniform(-0.1, 0.1),
                'color': (
                    random.uniform(0.3, 0.7),
                    random.uniform(0.3, 0.7),
                    random.uniform(0.7, 1.0),
                    random.uniform(0.05, 0.15)
                ),
                'phase': random.uniform(0, math.pi * 2)
            }
            self.particles.append(particle)

    def on_touch_down(self, touch):
        """Обработка касания"""
        if self.collide_point(*touch.pos):
            self.touch_down_time = Clock.get_time()
            self.is_touched = True

            # Анимация нажатия
            anim = Animation(
                press_depth=0.95,
                glow_intensity=0.7,
                duration=0.1,
                t='out_quad'
            )
            anim.start(self)

            # Эффект волны
            self.create_touch_ripple(touch.x, touch.y)

            # Лёгкий выброс частиц
            self.emit_touch_particles(touch.x, touch.y)

            # Вибрация (если поддерживается)
            if hasattr(self, 'vibrate'):
                self.vibrate(10)

            return super().on_touch_down(touch)
        return super().on_touch_down(touch)

    def on_touch_up(self, touch):
        """Обработка отпускания"""
        if self.is_touched:
            self.is_touched = False

            # Проверяем не долгое ли это нажатие
            touch_duration = Clock.get_time() - self.touch_down_time
            self.is_long_press = touch_duration > 0.5

            # Анимация отпускания
            if self.collide_point(*touch.pos):
                # Если палец все еще на кнопке - эффект клика
                Animation(
                    press_depth=1.0,
                    glow_intensity=0.3,
                    duration=0.15,
                    t='out_back'
                ).start(self)

                # Усиленный выброс частиц при клике
                self.explode_particles(touch.x, touch.y)

                # Звук клика (если есть)
                if hasattr(self, 'play_click_sound'):
                    self.play_click_sound()
            else:
                # Если палец ушел с кнопки - просто возвращаем
                Animation(
                    press_depth=1.0,
                    glow_intensity=0.0,
                    duration=0.2
                ).start(self)

        return super().on_touch_up(touch)

    def create_touch_ripple(self, x, y):
        """Эффект волны от касания"""
        ripple = {
            'x': x,
            'y': y,
            'radius': 5,
            'max_radius': min(self.width, self.height) * 0.7,
            'alpha': 0.6,
            'color': self.accent_color[:],
            'width': 1.5
        }
        self.touch_ripples.append(ripple)

        Clock.schedule_once(lambda dt: self.remove_ripple(ripple), 0.6)

    def remove_ripple(self, ripple):
        """Удаление эффекта волны"""
        if ripple in self.touch_ripples:
            self.touch_ripples.remove(ripple)
            self.update_canvas()

    def emit_touch_particles(self, x, y):
        """Лёгкий выброс частиц при касании"""
        for _ in range(4):
            angle = random.uniform(0, math.pi * 2)
            speed = random.uniform(0.5, 1.5)

            particle = {
                'x': x,
                'y': y,
                'size': random.uniform(2, 4),
                'speed_x': math.cos(angle) * speed,
                'speed_y': math.sin(angle) * speed,
                'color': (
                    self.accent_color[0] + random.uniform(-0.1, 0.1),
                    self.accent_color[1] + random.uniform(-0.1, 0.1),
                    self.accent_color[2] + random.uniform(-0.1, 0.1),
                    0.8
                ),
                'life': 1.0,
                'decay': random.uniform(0.02, 0.04)
            }
            self.active_particles.append(particle)

    def explode_particles(self, x, y):
        """Выброс частиц при клике"""
        for _ in range(8):
            angle = random.uniform(0, math.pi * 2)
            speed = random.uniform(1, 3)

            particle = {
                'x': x,
                'y': y,
                'size': random.uniform(3, 6),
                'speed_x': math.cos(angle) * speed,
                'speed_y': math.sin(angle) * speed,
                'color': (
                    self.accent_color[0] + random.uniform(-0.2, 0.2),
                    self.accent_color[1] + random.uniform(-0.2, 0.2),
                    self.accent_color[2] + random.uniform(-0.2, 0.2),
                    random.uniform(0.7, 1.0)
                ),
                'life': 1.0,
                'decay': random.uniform(0.03, 0.06)
            }
            self.active_particles.append(particle)

    def update_canvas(self, *args):
        """Отрисовка кнопки"""
        self.canvas.before.clear()
        self.canvas.after.clear()

        # Координаты с учетом анимаций
        scale = self.hover_scale * self.press_depth
        width = self.width * scale
        height = self.height * scale
        x = self.center_x - width / 2
        y = self.center_y - height / 2

        with self.canvas.before:
            # ===== ОСНОВНОЙ ФОН =====

            # Тень
            if self.press_depth >= 0.98:
                PushMatrix()
                Color(0, 0, 0, 0.2)
                RoundedRectangle(
                    pos=(x - 2, y - 5),
                    size=(width, height),
                    radius=[25]
                )
                PopMatrix()

            # Основной цвет
            Color(*self.base_color)
            RoundedRectangle(
                pos=(x, y),
                size=(width, height),
                radius=[25]
            )

            # Градиент сверху
            r, g, b, a = self.base_color
            Color(r + 0.1, g + 0.1, b + 0.1, a * 0.5)
            RoundedRectangle(
                pos=(x, y + height * 0.6),
                size=(width, height * 0.4),
                radius=[25, 25, 0, 0]
            )
            # Фоновые частицы
            time = Clock.get_time()
            for particle in self.particles:
                px = x + particle['x'] * width
                py = y + particle['y'] * height

                # Плавное движение
                px += math.sin(time * 0.5 + particle['phase']) * 2
                py += math.cos(time * 0.7 + particle['phase']) * 2

                Color(*particle['color'])
                Ellipse(
                    pos=(px - particle['size'] / 2, py - particle['size'] / 2),
                    size=(particle['size'], particle['size'])
                )

        with self.canvas.after:
            # ===== ЭФФЕКТЫ =====

            # Эффекты волн от касаний
            for ripple in self.touch_ripples:
                Color(ripple['color'][0], ripple['color'][1],
                      ripple['color'][2], ripple['alpha'])
                Line(
                    circle=(ripple['x'], ripple['y'], ripple['radius']),
                    width=ripple['width']
                )

                # Анимация волны
                ripple['radius'] += 3
                ripple['alpha'] -= 0.02

            # Свечение
            if self.glow_intensity > 0:
                Color(
                    self.accent_color[0],
                    self.accent_color[1],
                    self.accent_color[2],
                    self.glow_intensity * 0.3
                )
                Line(
                    rounded_rectangle=(
                        x - 3, y - 3,
                        width + 6, height + 6,
                        28
                    ),
                    width=2
                )

            # Активные частицы
            for particle in list(self.active_particles):
                Color(*particle['color'])
                Ellipse(
                    pos=(
                        particle['x'] - particle['size'] / 2,
                        particle['y'] - particle['size'] / 2
                    ),
                    size=(particle['size'], particle['size'])
                )

                # Обновление частиц
                particle['x'] += particle['speed_x']
                particle['y'] += particle['speed_y']
                particle['life'] -= particle['decay']
                particle['size'] *= 0.97

                # Замедление
                particle['speed_x'] *= 0.92
                particle['speed_y'] *= 0.92

            # Удаление старых частиц
            self.active_particles = [
                p for p in self.active_particles
                if p['life'] > 0.1 and p['size'] > 0.3
            ]

            # Контур кнопки
            Color(1, 1, 1, 0.4)
            Line(
                rounded_rectangle=(x, y, width, height, 25),
                width=1
            )

            # Внутренняя тень для объема
            Color(0, 0, 0, 0.15)
            Line(
                rounded_rectangle=(
                    x + 1, y + 1,
                    width - 2, height - 2,
                    24
                ),
                width=0.8
            )

    def on_is_touched(self, instance, value):
        """Обновление canvas при изменении состояния касания"""
        self.update_canvas()


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


class MenuWidget(FloatLayout):
    def __init__(self, conn, selected_map=None, **kwargs):
        super(MenuWidget, self).__init__(**kwargs)
        self.conn = conn
        self._particles = []
        self._particle_event = None

        # ======== Фоновое изображение ========
        self.bg_image = Image(
            source='files/menu/vampire.jpg',
            allow_stretch=True,
            keep_ratio=False,
            size_hint=(1, 1),
            pos_hint={'x': 0, 'y': 0}
        )
        self.add_widget(self.bg_image)

        # ======== Затемнение для читабельности ========
        overlay = Widget(size_hint=(1, 1))
        with overlay.canvas:
            Color(0, 0, 0, 0.35)
            overlay._rect = Rectangle(pos=overlay.pos, size=overlay.size)
        overlay.bind(
            pos=lambda i, v: setattr(i._rect, 'pos', v),
            size=lambda i, v: setattr(i._rect, 'size', v)
        )
        self.add_widget(overlay)

        # ======== Логотип ========
        self.title_label = AnimatedLabel(
            text="[b]LERDON[/b]",
            font_size=sp(56),
            bold=True,
            color=(0.92, 0.82, 0.52, 1),
            outline_color=(0.1, 0.06, 0.02, 1),
            outline_width=3,
            halign='center',
            valign='middle',
            size_hint=(0.8, None),
            height=dp(70),
            pos_hint={'center_x': 0.5, 'top': 0.94},
            markup=True
        )
        self.add_widget(self.title_label)
        self.title_label.start_glow_animation()

        # ======== Подзаголовок ========
        subtitle = Label(
            text="[i]Легенды Пяти Королевств[/i]",
            markup=True,
            font_size=sp(16),
            color=(0.7, 0.72, 0.8, 0.7),
            size_hint=(0.8, None),
            height=dp(24),
            pos_hint={'center_x': 0.5, 'top': 0.83},
            halign='center',
        )
        self.add_widget(subtitle)

        # ======== Декоративная линия ========
        deco_line = Widget(size_hint=(0.3, None), height=dp(1), pos_hint={'center_x': 0.5, 'top': 0.80})
        with deco_line.canvas:
            Color(0.85, 0.75, 0.45, 0.5)
            deco_line._r = Rectangle(pos=deco_line.pos, size=deco_line.size)
        deco_line.bind(
            pos=lambda i, v: setattr(i._r, 'pos', v),
            size=lambda i, v: setattr(i._r, 'size', v)
        )
        self.add_widget(deco_line)

        # ======== Контейнер для кнопок ========
        self.button_container = FloatLayout(size_hint=(1, 0.65), pos_hint={'center_x': 0.5, 'y': 0.10})
        self.add_widget(self.button_container)

        # ======== Кнопки ========
        button_configs = [
            {"text": "Начать игру",       "y_pos": 0.78, "type": "start",  "action": self.start_game},
            {"text": "Рейтинг",           "y_pos": 0.60, "type": "rating", "action": self.open_dossier},
            {"text": "История Лэрдона",   "y_pos": 0.42, "type": "help",   "action": self.open_how_to_play},
            {"text": "Об авторе",         "y_pos": 0.24, "type": "author", "action": self.open_author},
            {"text": "Выход",             "y_pos": 0.06, "type": "exit",   "action": self.exit_game}
        ]

        self.buttons = []
        self.selected_button = None

        for i, config in enumerate(button_configs):
            btn = GameButton(
                text=config["text"],
                button_type=config["type"],
                size_hint=(0.35, 0.11),
                pos_hint={'center_x': 0.5, 'y': config["y_pos"]},
            )
            btn.font_size = sp(18)

            btn.bind(
                on_press=lambda instance, b=btn: self.on_button_press(b),
                on_release=config["action"]
            )

            # Анимация появления с задержкой
            btn.opacity = 0
            anim = Animation(opacity=1, duration=0.4, t='out_quad')
            Clock.schedule_once(lambda dt, b=btn, a=anim: a.start(b), 0.15 * i)

            self.buttons.append(btn)
            self.button_container.add_widget(btn)

        if self.buttons:
            self.select_button(self.buttons[0])

        # ======== Версия внизу ========
        version_label = Label(
            text="v2.0",
            font_size=sp(11),
            color=(0.5, 0.5, 0.55, 0.5),
            size_hint=(None, None),
            size=(dp(50), dp(16)),
            pos_hint={'right': 0.98, 'y': 0.01},
        )
        self.add_widget(version_label)

        # ======== Частицы ========
        self._particle_event = Clock.schedule_interval(self._spawn_particle, 0.25)

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
        'Вампиры': (0.55, 0.10, 0.75, 1),
        'Север':   (0.10, 0.50, 0.85, 1),
        'Эльфы':   (0.15, 0.72, 0.35, 1),
        'Адепты':  (0.90, 0.62, 0.10, 1),
        'Элины':   (0.90, 0.32, 0.10, 1),
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
        params = self._get_orientation_params()

        root = BoxLayout(
            orientation='vertical',
            spacing=self._get_spacing(6, params['is_landscape'])
        )

        root.add_widget(self._create_title_bar(params))
        root.add_widget(self._create_tabs_panel(params))
        root.add_widget(self._create_bottom_panel(params))

        self.add_widget(root)

    # -------------------------
    # TITLE BAR
    # -------------------------

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
        """Панель с боями"""
        font_sizes = self._get_font_sizes(12, is_landscape)

        panel = BoxLayout(
            orientation='vertical',
            size_hint_x=size_hint_x,
            spacing=self._get_spacing(2, is_landscape),
            padding=[0, self._get_spacing(2, is_landscape)]
        )

        # Добавляем элементы
        self._add_panel_label(panel, "[b]Сражения (В/П):[/b]",
                              font_sizes['small'], ssp(14))

        battles_text = f"[color=#00FF00]{data.get('victories', 0)}[/color]/" \
                       f"[color=#FF4444]{data.get('defeats', 0)}[/color]"
        self._add_panel_label(panel, battles_text,
                              font_sizes['normal'], ssp(16))

        self._add_panel_label(panel, "[b]Матчи (В/П):[/b]",
                              font_sizes['small'], ssp(14))

        matches_text = f"[color=#00FF00]{data.get('matches_won', 0)}[/color]/" \
                       f"[color=#FF4444]{data.get('matches_lost', 0)}[/color]"
        self._add_panel_label(panel, matches_text,
                              font_sizes['normal'], ssp(16))

        return panel

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
        """Перезагружает вкладки с адаптивными параметрами"""
        params = self._get_orientation_params()
        self.tabs.clear_widgets()
        self._load_dossier_data_to_tabs(self.tabs, params)

    def go_back(self, instance):
        """Возврат в главное меню"""
        app = App.get_running_app()
        app.root.clear_widgets()
        app.root.add_widget(MenuWidget(self.conn))

    # -------------------------
    # ОБРАБОТКА ИЗМЕНЕНИЯ РАЗМЕРА ЭКРАНА
    # -------------------------

    def on_window_resize(self, window, width, height):
        """Вызывается при изменении размера окна"""
        # Обновляем UI при изменении ориентации с небольшой задержкой
        Clock.schedule_once(self._refresh_ui, 0.1)

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
            "Никто уже не помнит, когда пришли они… вампиры. Но в тот миг, когда началась их жатва, мир изменился навсегда.\n\n"

            "Города гасли один за другим. Ночи стали длиннее, чем дни. Люди исчезали целыми поселениями, "
            "а выжившие шепотом рассказывали о тенях, что пьют кровь и оставляют после себя только пепел и безмолвие.\n\n"

            "Когда надежда почти угасла, появился человек по имени Агилар. Он собрал Орден первых защитников людей — "
            "воинов, которых позже назовут паладинами. В их руках сверкала новая сталь, способная выдержать нечеловеческую силу.\n"
            "Секрет этой стали хранился строже священных реликвий.\n\n"

            "Но предательство пришло изнутри.\n"
            "Мерсис, один из посвящённых, попытался продать тайну элинам — магам Кристол, изучавшим разрушительную силу огня.\n"
            "Его выследил и убил Дариус прежде, чем секрет покинул руки людей.\n\n"

            "С этого дня Агилар перестал верить царству людей.\n"
            "Он объявил о создании Ордена Адептов в старом аббатстве неподалёку от Кирсалиса.\n"
            "Вскоре к нему присоединился Дариус.\n"
            "Орден стал настолько независим, что порой поднимал меч и против людей — особенно тех, кто искал милости у вампиров.\n\n"

            "Вскоре царство людей пало под натиском Бальтазара.\n"
            "Агилар отвёл паладинов в Рыжие земли, где вместе с Патриархом основал новый город среди выжженной почвы.\n\n"

            "Остатки людей бежали дальше на север.\n"
            "Лишь бывший командующий восточной армией Владислав сумел собрать разрозненные отряды выживших.\n\n"

            "Когда людей стало достаточно, Ольга — последняя волшебница Ребийской академии — предложила основать город у горы Тарнас.\n"
            "Но во время строительства на поселение обрушился чудовищный ураган.\n"
            "Люди готовились умереть в ледяной буре.\n"
            "И тогда Ольга, истощив последние силы, воссоздала гипитовый щит, который укрыл и согрел северян.\n\n"

            "После бури не нашли полководца Фагота.\n"
            "Его сочли погибшим и оставили тело в снегу рядом с мёртвой лошадью.\n\n"

            "На третий день снег разверзся.\n"
            "Фагот поднялся из ледяной могилы.\n"
            "Он поднял мёртвую лошадь на плечи — и она ожила под его рукой.\n"
            "В заброшенном доме он нашёл косу и, преобразив её, направился к новому городу.\n\n"

            "Северяне открыли по нему огонь.\n"
            "Сотни выстрелов не оставили на нём ни следа.\n"
            "Он стоял неподвижно и улыбался.\n\n"

            "Лишь прибытие Владислава остановило стрельбу.\n"
            "Фагот бросил косу в снег и попросил принять его.\n"
            "Он сказал, что не враг.\n"
            "Ольга посоветовала не отвергать того, кто вернулся из смерти.\n\n"

            "Пока вампиры косили людей как траву, эльфы строили своё царство под властью лесной владычицы Валерии.\n"
            "Северо-восток Лэрдона и войны смертных их почти не тревожили.\n"
            "Их защитник, владыка Люци, поклялся хранить Валерию и её народ от любых угроз.\n"
            "Эльфы предпочли рост и тишину лесов кровавым войнам мира.\n\n"

            "Элины Кристол избрали иной путь.\n"
            "Они торговали кристаллами с людьми, получая сведения и золото.\n"
            "С вампирами они устраивали вылазки против адептов, создавая иллюзию союза.\n"
            "Кристол служила лишь собственным интересам.\n\n"

            "Её маги, фанатично изучавшие стихию огня, научились извергать молнии и пламя, "
            "выжигая всё на своём пути.\n\n"

            "Когда слухи об их силе распространились по миру, дракон Арн-гот решил испытать их.\n"
            "Он обрушил на них своё пламя… но маги устояли под защитой Кристол.\n"
            "Поражённый, дракон назвал элинов драконорожденными.\n"
            "И вскоре он примкнул к ним.\n\n"

            "Так Лэрдон погрузился в эпоху крови, пепла и ледяных ветров.\n"
            "Никто не знает, кто станет спасителем мира.\n"
            "Но каждый знает — тьма ещё не достигла своего предела."
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

        animate_bar()
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

        self.add_widget(layout)

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


class SeasonalOverlay(FloatLayout):
    """Оверлей для сезонных анимаций"""

    SEASON_NAMES = ['Зима', 'Весна', 'Лето', 'Осень']
    SEASON_ICONS = {
        'Зима': 'files/status/icons/icon_for_animate/season 1.png',
        'Весна': 'files/status/icons/icon_for_animate/season 2.png',
        'Лето': None,  # Генерируем лучи
        'Осень': 'files/status/icons/icon_for_animate/season 4.png'
    }

    def __init__(self, conn, **kwargs):
        super(SeasonalOverlay, self).__init__(**kwargs)
        self.conn = conn
        self.current_season = None
        self.particles = []
        self.sun_rays = []
        self.animation_event = None
        self.season_update_event = None

        # Настройки частиц
        self.max_particles = {
            'Зима': 30,  # Редкий снег
            'Весна': 25,  # Листья слева направо
            'Лето': 0,  # Лучи света
            'Осень': 40  # Падающие листья
        }

        # Инициализация
        self.load_current_season()
        self.start_season_animation()

    def load_current_season(self):
        """Загружает текущий сезон из БД"""
        season_data = self.get_current_season_from_db(self.conn)
        if season_data:
            old_season = self.current_season
            self.current_season = season_data['name']

            if old_season != self.current_season:
                print(f"[SEASON] Смена сезона: {old_season} → {self.current_season}")
                self.recreate_particles()
        else:
            # ← Если сезон не определён — отключаем анимацию
            print("[SEASON] Сезон не определён в БД — анимация отключена")
            self.current_season = None
            self.clear_season_animation()

    def clear_season_animation(self):
        """Очищает все частицы и лучи"""
        self.particles.clear()
        self.sun_rays.clear()
        self.canvas.after.clear()

    def recreate_particles(self):
        """Пересоздаёт частицы для текущего сезона"""
        self.particles.clear()
        self.sun_rays.clear()

        # ← Если сезона нет — ничего не создаём
        if not self.current_season:
            self.canvas.after.clear()
            return

        if self.current_season == 'Лето':
            self.create_sun_rays()
        else:
            self.create_season_particles()

    def update_animation(self, dt):
        """Обновляет анимацию каждый кадр"""
        self.canvas.after.clear()

        # ← Если сезона нет — пропускаем отрисовку
        if not self.current_season:
            return

        if self.current_season == 'Лето':
            self.update_sun_rays()
        else:
            self.update_particles()

    def get_current_season_from_db(self, conn):
        """Получает текущий сезон из БД"""
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT current_season, season_index FROM season WHERE id = 1")
            result = cursor.fetchone()
            if result:
                return {'name': result[0], 'index': result[1]}
            return None
        except sqlite3.Error as e:
            print(f"[ERROR] Ошибка при получении сезона из БД: {e}")
            return None

    def start_season_animation(self):
        """Запускает анимацию сезона"""
        self.recreate_particles()
        # Обновление каждые 0.03 секунды (30 FPS)
        self.animation_event = Clock.schedule_interval(self.update_animation, 0.03)
        # Проверка смены сезона каждые 5 секунд
        self.season_update_event = Clock.schedule_interval(
            lambda dt: self.load_current_season(), 5.0
        )

    def stop_season_animation(self):
        """Останавливает анимацию"""
        if self.animation_event:
            Clock.unschedule(self.animation_event)
            self.animation_event = None
        if self.season_update_event:
            Clock.unschedule(self.season_update_event)
            self.season_update_event = None

    def create_season_particles(self):
        """Создаёт частицы для Зимы/Весны/Осени"""
        max_count = self.max_particles.get(self.current_season, 20)

        for i in range(max_count):
            particle = self.create_particle(i)
            self.particles.append(particle)

    def create_particle(self, index):
        """Создаёт одну частицу"""
        if self.current_season == 'Зима':
            return {
                'x': random.uniform(0, Window.width),
                'y': random.uniform(0, Window.height),
                'speed_y': random.uniform(-20, -5),  # Падает вниз
                'speed_x': random.uniform(-5, 5),  # Лёгкий ветер
                'size': random.uniform(23, 36),
                'opacity': random.uniform(0.4, 0.8),
                'rotation': 0,
                'rotation_speed': random.uniform(-10, 10),
                'image': self.SEASON_ICONS['Зима']
            }

        elif self.current_season == 'Весна':
            return {
                'x': random.uniform(-50, 0),  # Начинают слева
                'y': random.uniform(0, Window.height),
                'speed_x': random.uniform(30, 60),  # Летят вправо
                'speed_y': random.uniform(-10, 10),
                'size': random.uniform(25, 35),
                'opacity': random.uniform(0.5, 0.9),
                'rotation': random.uniform(0, 360),
                'rotation_speed': random.uniform(-30, 30),
                'image': self.SEASON_ICONS['Весна']
            }

        elif self.current_season == 'Осень':
            return {
                'x': random.uniform(0, Window.width),
                'y': random.uniform(Window.height, Window.height + 50),  # Начинают сверху
                'speed_y': random.uniform(-40, -20),  # Быстрее падают
                'speed_x': random.uniform(-15, 15),  # Сильный ветер
                'size': random.uniform(30, 35),
                'opacity': random.uniform(0.6, 0.95),
                'rotation': random.uniform(0, 360),
                'rotation_speed': random.uniform(-50, 50),
                'image': self.SEASON_ICONS['Осень']
            }

        return {}

    def create_sun_rays(self):
        """Создаёт лучи света для Лета — много тонких лучей"""
        num_rays = 80  # Огромное количество
        center_x = Window.width  # Правый край
        center_y = Window.height  # Верхний край

        for i in range(num_rays):
            # Базовый угол в диапазоне 180-270 градусов (правый верхний квадрант)
            base_angle = random.uniform(190, 260)  # Чуть уже чем 180-270 для запаса
            length = random.uniform(300, 600)
            width = random.uniform(1, 3)  # Очень тонкие

            self.sun_rays.append({
                'center_x': center_x,
                'center_y': center_y,
                'base_angle': base_angle,  # Базовый угол
                'current_angle': base_angle,  # Текущий угол
                'length': length,
                'width': width,
                'opacity': random.uniform(0.08, 0.20),
                'oscillation_speed': random.uniform(0.09, 0.2),  # Скорость колебания
                'oscillation_amplitude': random.uniform(15, 35),  # Амплитуда качания (градусы)
                'pulse_phase': random.uniform(0, math.pi * 2),
                'oscillation_phase': random.uniform(0, math.pi * 2)  # Фаза колебания
            })

    def update_sun_rays(self):
        """Обновляет и рисует солнечные лучи с колебанием туда-обратно"""
        time = Clock.get_time()

        with self.canvas.after:
            for ray in self.sun_rays:
                # Пульсация яркости
                pulse = math.sin(time * 2 + ray['pulse_phase']) * 0.1 + 0.2
                ray['opacity'] = pulse

                # Колебание угла туда-обратно (синусоида)
                # Лучи качаются в пределах base_angle ± amplitude
                oscillation = math.sin(time * ray['oscillation_speed'] + ray['oscillation_phase'])
                ray['current_angle'] = ray['base_angle'] + (oscillation * ray['oscillation_amplitude'])

                # Ограничиваем угол в пределах 180-270 градусов (чтобы не уходили за экран)
                ray['current_angle'] = max(180, min(270, ray['current_angle']))

                # Вычисление конца луча
                rad = math.radians(ray['current_angle'])
                end_x = ray['center_x'] + math.cos(rad) * ray['length']
                end_y = ray['center_y'] + math.sin(rad) * ray['length']

                # Отрисовка луча
                Color(1, 0.9, 0.3, ray['opacity'])  # Золотистый цвет

                PushMatrix()
                Rotate(angle=ray['current_angle'], origin=(ray['center_x'], ray['center_y']))
                Rectangle(
                    pos=(ray['center_x'], ray['center_y'] - ray['width'] / 2),
                    size=(ray['length'], ray['width'])
                )
                PopMatrix()

    def update_particles(self):
        """Обновляет и рисует частицы"""
        with self.canvas.after:
            for particle in self.particles:
                # Обновление позиции
                particle['x'] += particle.get('speed_x', 0) * 0.03
                particle['y'] += particle.get('speed_y', 0) * 0.03
                particle['rotation'] += particle.get('rotation_speed', 0) * 0.03

                # Респаун частиц
                self.respawn_particle(particle)

                # Отрисовка
                Color(1, 1, 1, particle['opacity'])

                # Загрузка текстуры
                texture = CoreImage(particle['image']).texture

                PushMatrix()
                Rotate(angle=particle['rotation'], origin=(particle['x'], particle['y']))
                Rectangle(
                    texture=texture,
                    pos=(particle['x'] - particle['size'] / 2,
                         particle['y'] - particle['size'] / 2),
                    size=(particle['size'], particle['size'])
                )
                PopMatrix()

    def respawn_particle(self, particle):
        """Возвращает частицу в начало пути при выходе за границы"""
        if self.current_season == 'Зима':
            if particle['y'] < -10:
                particle['y'] = Window.height + 10
                particle['x'] = random.uniform(0, Window.width)

        elif self.current_season == 'Весна':
            if particle['x'] > Window.width + 50:
                particle['x'] = -50
                particle['y'] = random.uniform(0, Window.height)

        elif self.current_season == 'Осень':
            if particle['y'] < -50:
                particle['y'] = Window.height + 50
                particle['x'] = random.uniform(0, Window.width)

    def on_parent(self, instance, parent):
        """Очистка при удалении"""
        if parent is None:
            self.stop_season_animation()

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
