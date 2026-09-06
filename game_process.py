from kivy.graphics import Triangle

from ai_models.lerdon_ai.ultralight_ai import DiplomacyAIFactory
from economic import *
import economic
import army
import politic
from db_lerdon_connect import *
from ii import AIController
from ai_models import AdvisorView
from event_manager import EventManager
from results_game import ResultsGame
from seasons import SeasonManager
from nobles_generator import generate_initial_nobles
from nobles_generator import process_nobles_turn
from ui_components import TutorialHint, DiplomacyMailbox


from utils.helpers import parse_formatted_number
from undead_invasion import (
    initialize_undead_invasion, check_and_trigger_invasion,
    process_undead_turn, is_invasion_active, UNDEAD_FACTION_NAME
)

# Глобальная ссылка на активный GameScreen для обновления карты из других модулей
_active_game_screen = None

def refresh_map():
    """Принудительное обновление карты и индикаторов. Вызывать после боя/перемещения."""
    gs = _active_game_screen
    if gs:
        gs._prev_star_levels = None
        gs.update_army_rating()


# Список всех фракций
FACTIONS = ["Север", "Эльфы", "Вампиры", "Элины", "Адепты"]
global_resource_manager = {}
translation_dict = {
    "Север": "people",
    "Эльфы": "elfs",
    "Адепты": "adept",
    "Вампиры": "vampire",
    "Элины": "poly",
}



def transform_filename(file_path):
    path_parts = file_path.split('/')
    for i, part in enumerate(path_parts):
        for ru_name, en_name in translation_dict.items():
            if ru_name in part:
                path_parts[i] = part.replace(ru_name, en_name)
    return '/'.join(path_parts)

# Класс для кнопки с изображением
class ImageButton(ButtonBehavior, Image):
    pass


from kivy.animation import Animation
from kivy.uix.popup import Popup
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.graphics import Color, Rectangle, RoundedRectangle, Line
from kivy.metrics import dp, sp


class BlinkingImageButton(ImageButton):
    """ImageButton с поддержкой мигания."""

    def __init__(self, **kwargs):
        super(BlinkingImageButton, self).__init__(**kwargs)
        self.blinking = False
        self.blink_event = None
        self.original_source = self.source

    def start_blinking(self):
        """Запускает мигание кнопки."""
        if not self.blinking:
            self.blinking = True
            self.blink_event = Clock.schedule_interval(self._blink, 0.5)

    def stop_blinking(self):
        """Останавливает мигание кнопки."""
        if self.blinking:
            self.blinking = False
            if self.blink_event:
                self.blink_event.cancel()
            self.source = self.original_source

    def _blink(self, dt):
        """Переключает видимость кнопки для эффекта мигания."""
        if self.source == '':
            self.source = self.original_source
        else:
            self.source = ''

    def cleanup(self):
        """Очистка ресурсов."""
        self.stop_blinking()

class GameStateManager:
    def __init__(self, conn):
        self.faction = None  # Объект фракции
        self.resource_box = None  # Объект ResourceBox
        self.game_area = None  # Центральная область игры
        self.conn = conn  # Соединение с базой данных
        self.cursor = None  # Курсор для работы с БД
        self.turn_counter = 1  # Счетчик ходов

    def initialize(self, selected_faction):
        """Инициализация объектов игры."""
        self.faction = Faction(selected_faction, self.conn)  # Создаем объект фракции
        # Включаем WAL для повышения параллелизма
        self.conn.execute("PRAGMA journal_mode=WAL;")
        self.conn.execute("PRAGMA synchronous=NORMAL;")
        self.conn.execute("PRAGMA busy_timeout=5000;")  # Ждать до 5 секунд при блокировке

        self.cursor = self.conn.cursor()
        self.turn_counter = self.load_turn(selected_faction)  # Загружаем счетчик ходов

    def load_turn(self, faction):
        """Загружает текущее значение счетчика ходов из базы данных."""
        try:
            self.cursor.execute('''
                SELECT turn_count
                FROM turn
                WHERE faction = ?
            ''', (faction,))
            row = self.cursor.fetchone()
            return row[0] if row else 1
        except sqlite3.Error as e:
            print(f"Ошибка при загрузке счетчика ходов: {e}")
            return 0

    def save_turn(self, faction, turn_count):
        """Сохраняет текущее значение счетчика ходов в базу данных."""
        try:
            self.cursor.execute('''
                INSERT OR REPLACE INTO turn (faction, turn_count)
                VALUES (?, ?)
            ''', (faction, turn_count))
            self.conn.commit()
        except sqlite3.Error as e:
            print(f"Ошибка при сохранении счетчика ходов: {e}")

    def close_connection(self):
        pass

def show_floating_bonus(label, bonus, overlay):
    if not label or not overlay:
        return

    color = (0, 1, 0, 1) if bonus > 0 else (1, 0, 0, 1)
    bonus_text = f"{'+' if bonus > 0 else ''}{format_number(bonus)}"

    bonus_label = Label(
        text=bonus_text,
        font_size=sp(16),
        color=color,
        size_hint=(None, None),
        size=(dp(120), dp(44)),
        halign='left',
        valign='middle',
        opacity=1
    )
    bonus_label.text_size = bonus_label.size

    # Получаем координаты label в окне → в overlay
    win_x, win_y = label.to_window(*label.pos)
    layout_x, layout_y = overlay.to_widget(win_x, win_y)

    bonus_label.pos = (layout_x + label.width + dp(4), layout_y)
    overlay.add_widget(bonus_label)

    anim = Animation(opacity=0, duration=2.0)

    def cleanup(*_):
        if bonus_label.parent:
            bonus_label.parent.remove_widget(bonus_label)

    anim.bind(on_complete=cleanup)
    anim.start(bonus_label)



class ResourceBox(BoxLayout):
    """
    ResourceBox, «приклеенный» к левому верхнему углу,
    с каждой строкой:
      ----------
      [иконка] : [значение]   (шрифт sp(16), иконка dp(16))
      ----------
    Ширина контейнера = dp(72). Текст и иконки не уменьшаются.
    """
    ICON_MAP = {
        "Кроны":      "files/status/resource_box/coin.png",
        "Рабочие":     "files/status/resource_box/workers.png",
        "Кристаллы":       "files/status/resource_box/crystal.png",
        "Население":   "files/status/resource_box/population.png",
        "Потребление": "files/status/resource_box/consumption.png",
        "Лимит Армии": "files/status/resource_box/army_limit.png",
    }

    def __init__(self, resource_manager, overlay, **kwargs):
        super(ResourceBox, self).__init__(**kwargs)
        self.resource_manager = resource_manager
        self.overlay = overlay
        # --- Словарь для хранения таймеров ---
        self.scheduled_animate_event = None
        # верт. бокс
        self.orientation = 'vertical'

        # фиксированная узкая ширина, привязка к левому верху
        self.size_hint = (None, None)
        self.pos_hint = {'x': 0, 'top': 1}
        self.width = dp(150)  # сокращённая ширина

        # Отступы внутри: [left, top, right, bottom]
        self.padding = [dp(2), dp(2), dp(2), dp(2)]
        # spacing = 0, поскольку сами рисуем разделители
        self.spacing = 0

        # фон с закруглёнными углами
        with self.canvas.before:
            Color(0.11, 0.15, 0.21, 0.9)
            self._bg_rect = RoundedRectangle(radius=[6,])

        self.bind(pos=self._update_bg, size=self._update_bg)

        # Словарь, чтобы хранить метки значений (обновлять при tick)
        self._label_values = {}

        # Сразу строим содержимое
        self.update_resources()

        # При изменении высоты/ширины пересобираем (нужно для корректного рисования линий)
        self.bind(size=lambda *a: self.update_resources())

    def _update_bg(self, *args):
        self._bg_rect.pos = self.pos
        self._bg_rect.size = self.size

    def update_resources(self, delta=None):
        if delta is None:
            delta = {}
        # --- Отменить предыдущую анимацию бонуса, если она была ---
        if self.scheduled_animate_event:
            Clock.unschedule(self.scheduled_animate_event)
            self.scheduled_animate_event = None

        self.clear_widgets()
        self._label_values.clear()

        resources = self.resource_manager.get_resources()

        parsed = {}
        for name, val in resources.items():
            try:
                parsed[name] = parse_formatted_number(val)
            except Exception:
                parsed[name] = None

        row_h = dp(32)
        icon_size = dp(24)
        colon_w = dp(6)
        gap = dp(8)
        val_w = self.width - (self.padding[0] + self.padding[2] + icon_size + gap + colon_w + dp(4))

        widgets = []

        def show_tooltip(res_name):
            info_text = {
                "Кроны": (
                    "Кроны нужны для найма армии и героев, создания и покупки артефактов.\n"
                    "Ведения дипломатии(заключения союзов, договоров культ. обмена и мира)\n"
                    "Так же кроны пригодятся для тайной службы(Ваша разведка)\n"
                    "Основной источник: налоги.\n"
                    "Можно получить: продав Кристаллы на рынке или от дружественных стран при торговле."
                ),
                "Рабочие": (
                    "Работоспособное население,\nспособное работать на фабриках или служить в армии.\n"
                    "Чем больше больниц — тем больше рабочих. Их число растет если растет население\n"
                    "Без них нельзя нанять армию\n"
                ),
                "Кристаллы": (
                    "Потребляемый ресурс,\n"
                    "Его добычу надо налаживать с первого хода. Вкладка Развитие и выбор соотношения стройки\n"
                    "Кристаллы нужны для поддержания армии и населения.\n"
                    "Добыча зависит от количества фабрик. Уровень добычи влияет на то растет население или голодает"
                ),
                "Население": (
                    "Платят налоги\n"
                    "Перерабатывают Кристаллы в Кристаллическое сырье 1к1 для питания себя и армии.\n"
                    "Растёт при наличии Кристаллов.\n"
                    "Умирают если нет кристаллов. Когда население иссякнет - конец игры"
                ),
                "Потребление": (
                    "Уровень потребления Кристаллического сырья армией(Кристаллы).\n"
                    "Если превышает лимит армии — армия умирает от голода."
                ),
                "Лимит Армии": (
                    "Текущий максимальный лимит,\nпотребления армией Кристаллического сырья.\n"
                    "Зависит от текущего количества городов расы."
                )
            }.get(res_name, "Информация о ресурсе недоступна.")

            # Label с текстом информации
            label = Label(
                text=info_text,
                font_size=sp(16),
                color=(0.9, 0.9, 0.9, 1),
                halign='left',
                valign='top',
                size_hint_y=None,
                padding=[dp(15), dp(10)]
            )

            # Привязка высоты к размеру текста
            label.bind(
                width=lambda *x: label.setter('text_size')(label, (label.width, None)),
                texture_size=lambda *x: label.setter('height')(label, label.texture_size[1])
            )

            # ScrollView для длинного текста
            scroll_view = ScrollView(size_hint=(1, 1))
            scroll_view.add_widget(label)

            # Кнопка закрытия
            close_btn = Button(
                text="Закрыть",
                size_hint=(1, None),
                height=dp(50),
                font_size=sp(18),
                background_color=(0.2, 0.6, 0.8, 1),
                background_normal='',
                on_press=lambda btn: popup.dismiss()
            )

            # Общий контент попапа
            content = BoxLayout(orientation='vertical', spacing=dp(10), padding=dp(10))
            content.add_widget(scroll_view)
            content.add_widget(close_btn)

            # Само окно Popup
            popup = Popup(
                title=res_name,
                content=content,
                size_hint=(0.8, 0.6),
                title_size=sp(20),
                title_align='center',
                background_color=(0.1, 0.1, 0.1, 0.98),
                separator_color=(0.3, 0.3, 0.3, 1),
                auto_dismiss=False  # чтобы случайно не закрыть вне кнопки
            )

            # Привязываем закрытие к кнопке
            close_btn.bind(on_release=popup.dismiss)

            # Открываем попап
            popup.open()

        # --- Рендеринг строк ---
        items = list(resources.items())
        for idx, (res_name, formatted) in enumerate(items):
            # Разделитель сверху
            line = Widget(size_hint=(1, None), height=dp(1))
            with line.canvas:
                Color(0.5, 0.5, 0.5, 1)
                rect = Rectangle(pos=(self.x + self.padding[0], 0),
                                 size=(self.width - (self.padding[0] + self.padding[2]), dp(1)))
                line.bind(pos=lambda inst, val: setattr(rect, 'pos', (self.x + self.padding[0], val[1])),
                          size=lambda inst, sz: setattr(rect, 'size',
                                                        (self.width - (self.padding[0] + self.padding[2]), dp(1))))

            widgets.append(line)

            # Строка с ресурсом
            row = BoxLayout(orientation='horizontal', size_hint=(1, None), height=row_h, spacing=dp(4))

            icon_path = self.ICON_MAP.get(res_name)
            if icon_path:
                img = Image(source=icon_path, size_hint=(None, None), size=(icon_size, icon_size), allow_stretch=True)
            else:
                img = Widget(size_hint=(None, None), size=(icon_size, icon_size))

            lbl_colon = Label(
                text=":",
                font_size=sp(16),
                color=(1, 1, 1, 1),
                size_hint=(None, None),
                size=(colon_w, row_h),
                halign='center',
                valign='middle'
            )
            lbl_colon.text_size = (colon_w, row_h)

            num = parsed.get(res_name)
            val_color = (1, 0, 0, 1) if (num is not None and num < 0) or (
                    res_name == "Потребление" and num > parsed.get("Лимит Армии", 0)) else (1, 1, 1, 1)

            lbl_val = Label(
                text=str(formatted),
                font_size=sp(16),
                color=val_color,
                size_hint=(None, None),
                size=(val_w, row_h),
                halign='left',
                valign='middle'
            )
            lbl_val.text_size = (val_w, row_h)
            self._label_values[res_name] = lbl_val

            row.add_widget(img)
            row.add_widget(Widget(size_hint=(None, None), size=(gap, row_h)))
            row.add_widget(lbl_colon)
            row.add_widget(Widget(size_hint=(None, None), size=(gap, row_h)))
            row.add_widget(lbl_val)

            # Если есть дельта — запускаем анимацию
            if res_name in delta:
                self.animate_resource(res_name, delta[res_name])

            # Добавляем обработчик тапа по строке для показа подсказки
            row.bind(
                on_touch_down=lambda instance, touch, name=res_name: show_tooltip(name) if instance.collide_point(
                    touch.x, touch.y) else False
            )

            widgets.append(row)

        # Нижний разделитель
        last_line = Widget(size_hint=(1, None), height=dp(1))
        with last_line.canvas:
            Color(0.5, 0.5, 0.5, 1)
            rect = Rectangle(pos=(self.x + self.padding[0], 0),
                             size=(self.width - (self.padding[0] + self.padding[2]), dp(1)))
            last_line.bind(pos=lambda inst, val: setattr(rect, 'pos', (self.x + self.padding[0], val[1])),
                           size=lambda inst, sz: setattr(rect, 'size',
                                                         (self.width - (self.padding[0] + self.padding[2]), dp(1))))

        widgets.append(last_line)

        # Добавляем все виджеты
        for w in widgets:
            self.add_widget(w)

        # Расчёт высоты
        num_rows = len(items)
        sep_h = dp(1)
        rows_h = num_rows * row_h
        lines_h = (num_rows + 1) * sep_h
        total_h_raw = self.padding[1] + self.padding[3] + rows_h + lines_h
        max_bottom_y = Window.height * 0.35
        max_allowed_h = Window.height - max_bottom_y
        final_h = min(total_h_raw, max_allowed_h)
        self.height = final_h

    def animate_resource(self, res_name, delta_data):
        label = self._label_values.get(res_name)
        if not label:
            return

        bonus = delta_data.get("bonus", 0)
        if bonus == 0:
            return

        # Отложенный вызов — подождём один кадр
        def do_animate(dt):
            show_floating_bonus(label, bonus, self.overlay)

        self.scheduled_animate_event = Clock.schedule_once(do_animate, 0)


class CircularProgressButton(Button):
    progress = NumericProperty(0)

    def __init__(self, duration=1.5, **kwargs):
        super().__init__(**kwargs)
        self.duration = duration
        self.anim = None
        self.bind(size=self.draw_circle, pos=self.draw_circle)

    def draw_circle(self, *args):
        self.canvas.after.clear()
        with self.canvas.after:
            Color(1, 1, 1, 0.3)  # Цвет индикатора
            self.circle = Line(
                circle=(self.center_x, self.center_y, min(self.width, self.height) / 2 - dp(8), 0, 0),
                width=dp(4),
                cap='round'
            )

    def start_progress(self):
        if self.anim:
            return
        self.progress = 0
        self.disabled = True
        self.canvas.after.clear()

        with self.canvas.after:
            Color(1, 1, 1, 0.3)
            self.circle = Line(
                circle=(self.center_x, self.center_y, min(self.width, self.height)/2 - dp(8), 0, 0),
                width=dp(4),
                cap='round'
            )

        anim = Animation(progress=360, duration=self.duration, t='linear')
        anim.bind(on_progress=self.update_arc)
        anim.bind(on_complete=self.reset_button)
        self.anim = anim
        anim.start(self)

    def update_arc(self, animation, instance, value):
        self.canvas.after.clear()
        with self.canvas.after:
            Color(1, 1, 1, 0.3)
            self.circle = Line(
                circle=(
                    self.center_x,
                    self.center_y,
                    min(self.width, self.height)/2 - dp(8),
                    0,
                    self.progress
                ),
                width=dp(4),
                cap='round'
            )

    def reset_button(self, *args):
        self.disabled = False
        self.anim = None
        self.canvas.after.clear()

class TabImageButton(ImageButton):
    """Кнопка вкладки с поддержкой активного/неактивного состояния"""
    def __init__(self, normal_source, active_source=None, **kwargs):
        super().__init__(**kwargs)
        self.normal_source = normal_source
        self.active_source = active_source or self._generate_active_path(normal_source)
        self.source = self.normal_source
        self.is_active = False

    def _generate_active_path(self, path):
        """Автоматически генерирует путь к активной иконке (добавляет _tab перед расширением)"""
        if path.endswith('.png'):
            return path.replace('.png', '_tab.png')
        elif path.endswith('.jpg'):
            return path.replace('.jpg', '_tab.jpg')
        return path + '_tab'

    def set_active(self, active):
        self.is_active = active
        self.source = self.active_source if active else self.normal_source


class GameScreen(Screen):
    SEASON_NAMES = ['Зима', 'Весна', 'Лето', 'Осень']
    SEASON_ICONS = ['snowflake', 'green_leaf', 'sun', 'yellow_leaf']
    IDEOLOGY_ICONS = {
        'player_submission': { # Идеология игрока - Смирение
            'same': 'files/status/ideology/un_green.png',       # Та же (Смирение)
            'different': 'files/status/ideology/fist_red.png'   # Другая (Борьба)
        },
        'player_struggle': {  # Идеология игрока - Борьба
            'same': 'files/status/ideology/fist_green.png',     # Та же (Борьба)
            'different': 'files/status/ideology/un_red.png'     # Другая (Смирение)
        }
    }

    def __init__(self, selected_faction, cities, conn=None, player_ideology=None,
                 player_allies=None, tutorial_enabled=False, **kwargs):
        super(GameScreen, self).__init__(**kwargs)
        global _active_game_screen
        _active_game_screen = self
        self.selected_faction = selected_faction
        self.cities = cities
        self.conn = conn
        self.player_ideology = player_ideology
        self.player_allies = player_allies
        self.city_star_levels = {}
        self.tutorial_enabled = tutorial_enabled
        self.current_tutorial_step = 0
        self.current_hint = None

        # --- Словарь для хранения таймеров ---
        self.scheduled_events = {}

        # Инициализация GameStateManager
        self.game_state_manager = GameStateManager(self.conn)
        self.game_state_manager.initialize(selected_faction)

        # Доступ к объектам через менеджер состояния
        self.faction = self.game_state_manager.faction
        self.conn = self.game_state_manager.conn
        self.cursor = self.game_state_manager.cursor
        self.turn_counter = self.game_state_manager.turn_counter

        # Сохраняем текущую фракцию игрока
        self.save_selected_faction_to_db()

        # Инициализация политических данных
        self.initialize_political_data()
        self.prev_diplomacy_state = {}

        # Инициализируем таблицу season
        self.season_manager = SeasonManager()

        # 1. СНАЧАЛА инициализируем таблицу (создаёт случайный сезон если нет)
        self.initialize_season_table(self.conn)

        # 2. ПОТОМ получаем сезон из БД
        current_season_data = self.get_current_season_from_db(self.conn)
        if current_season_data:
            self.current_idx = current_season_data['index']
            print(f"[SEASON] Загружен сезон из БД: {current_season_data['name']} (индекс: {self.current_idx})")
        else:
            # Если вдруг всё ещё нет (ошибка) — генерируем случайный
            self.current_idx = random.randint(0, 3)
            self.update_season_in_db(
                self.conn,
                self.SEASON_NAMES[self.current_idx],
                self.current_idx
            )
            print(f"[SEASON] Создан новый случайный сезон: {self.SEASON_NAMES[self.current_idx]}")

        # 3. Инициализируем ИИ
        self.ai_controllers = {}
        self.init_ai_controllers()

        # 3.5. Инициализация системы нашествия нежити
        initialize_undead_invasion(self.conn)

        # 4. Инициализация EventManager
        self.event_manager = EventManager(self.selected_faction, self, self.game_state_manager.faction, self.conn)

        # 5. Формируем данные для UI на основе сезона из БД
        current_season = {
            'name': self.SEASON_NAMES[self.current_idx],
            'icon': self.SEASON_ICONS[self.current_idx]
        }

        # 6. Инициализация UI
        self.is_android = platform == 'android'
        self.init_ui()
        self._update_season_display(current_season)
        self.season_manager.update(self.current_idx, self.conn)

        # Инициализация дворян
        self.initialize_nobles()

        # --- Сохраняем объекты таймеров ---
        self._prev_star_levels = None  # Кэш для отслеживания изменений карты
        # Немедленный первый вызов (после layout) + периодическое обновление
        Clock.schedule_once(lambda dt: self.update_cash(dt), 0)
        Clock.schedule_once(lambda dt: self.update_army_rating(dt), 0)
        self.scheduled_events['update_cash'] = Clock.schedule_interval(self.update_cash, 5)
        self.scheduled_events['update_army_rating'] = Clock.schedule_interval(self.update_army_rating, 3)
        self.diplomacy_ai_factory = None

        # === Отслеживание дипломатии ===
        self.prev_diplomacy_state = {}
        self.war_notification_shown = False

    def init_ai_controllers(self):
        """Создание контроллеров ИИ для каждой фракции кроме выбранной"""
        for faction in FACTIONS:
            if faction != self.selected_faction:
                self.ai_controllers[faction] = AIController(
                    faction, self.conn, self.season_manager,
                    player_faction=self.selected_faction
                )

    def check_diplomacy_changes(self):
        """
        Проверяет изменения в дипломатических отношениях.
        Если обнаружено новое объявление войны - показывает уведомление.
        """
        try:
            cursor = self.conn.cursor()
            # Загружаем все дипломатические отношения с игроком
            cursor.execute("""
                SELECT faction1, faction2, relationship
                FROM diplomacies
                WHERE faction1 = ? OR faction2 = ?
            """, (self.selected_faction, self.selected_faction))

            current_state = {}
            new_wars = []

            for row in cursor.fetchall():
                faction1, faction2, relationship = row
                other_faction = faction2 if faction1 == self.selected_faction else faction1
                key = f"{self.selected_faction}_{other_faction}"

                current_state[key] = relationship

                # Война засчитывается только если ВРАГ объявил войну игроку
                # (faction1 = враг, faction2 = игрок), а не наоборот
                if relationship == 'война' and faction2 == self.selected_faction:
                    prev_state = self.prev_diplomacy_state.get(key)
                    if prev_state != 'война':
                        new_wars.append(other_faction)

            # Нежить и Мятежники не показывают уведомления, уничтоженные тоже
            cursor.execute("SELECT DISTINCT faction FROM cities WHERE faction != 'Нейтрал'")
            alive = {r[0] for r in cursor.fetchall()}
            new_wars = [f for f in new_wars if f not in ('Нежить', 'Мятежники') and f in alive]

            # Если есть новые войны - показываем уведомление
            if new_wars and not self.war_notification_shown:
                self.show_war_declaration_popup(new_wars)
                self.war_notification_shown = True

            # Сохраняем текущее состояние для следующего сравнения
            self.prev_diplomacy_state = current_state

        except sqlite3.Error as e:
            print(f"[ERROR] Ошибка при проверке дипломатии: {e}")

    def reset_war_notification_flag(self):
        """Сбрасывает флаг уведомления (вызывать при начале нового хода)"""
        self.war_notification_shown = False

    def check_new_diplomatic_messages(self):
        """
        Проверяет новые дипломатические сообщения от AI фракций.
        Добавляет иконки фракций в DiplomacyMailbox.
        """
        try:
            cursor = self.conn.cursor()
            if not hasattr(self, '_last_checked_msg_id'):
                self._last_checked_msg_id = 0
                cursor.execute("SELECT MAX(id) FROM negotiation_history")
                result = cursor.fetchone()
                if result and result[0]:
                    self._last_checked_msg_id = result[0]
                return

            # Только сообщения от живых фракций (имеющих хотя бы 1 город)
            cursor.execute("""
                SELECT id, faction1, message FROM negotiation_history
                WHERE id > ? AND faction2 = ? AND is_player = 0
                  AND faction1 IN (SELECT DISTINCT faction FROM cities WHERE faction != 'Нейтрал')
                  AND faction1 NOT IN ('Мятежники', 'Нежить')
                ORDER BY id ASC
            """, (self._last_checked_msg_id, self.selected_faction))

            new_messages = cursor.fetchall()
            if not new_messages:
                return

            self._last_checked_msg_id = new_messages[-1][0]

            # Создаём mailbox если ещё нет
            if not hasattr(self, '_diplomacy_mailbox') or not self._diplomacy_mailbox.parent:
                self._diplomacy_mailbox = DiplomacyMailbox()
                app = App.get_running_app()
                if app and app.root:
                    app.root.add_widget(self._diplomacy_mailbox)

            for msg_id, faction, message in new_messages:
                msg_type = 'info'
                if '[СОЮЗ]' in message:
                    msg_type = 'alliance'
                elif '[ТОРГОВЛЯ]' in message:
                    msg_type = 'trade'
                elif '[УГРОЗА]' in message or '[ПРЕДУПРЕЖДЕНИЕ]' in message:
                    msg_type = 'warning'
                elif '[ПОЩАДА]' in message or '[УМОЛЯЮ]' in message:
                    msg_type = 'mercy'
                elif '[ПОМОЩЬ]' in message or '[ПРОСЬБА]' in message:
                    msg_type = 'help'

                self._diplomacy_mailbox.add_message(
                    faction_name=faction,
                    message=message,
                    message_type=msg_type,
                    on_respond=self._handle_diplomacy_response,
                )

        except Exception as e:
            import traceback
            print(f"[ERROR] Ошибка при проверке дипломатических сообщений: {e}")
            traceback.print_exc()

    def _handle_diplomacy_response(self, faction_name, answer, original_message):
        """Обработка ответа игрока на дипломатическое сообщение с реальными игровыми эффектами."""
        try:
            if answer == '__open_chat__':
                self.show_advisor(None, preselect_faction=faction_name)
                return

            cursor = self.conn.cursor()
            player_text = "Согласен" if answer == 'да' else "Отказываюсь"

            # Определяем тип предложения
            is_trade = '[ТОРГОВЛЯ]' in original_message
            is_alliance = '[СОЮЗ]' in original_message
            is_mercy = '[ПОЩАДА]' in original_message or '[УМОЛЯЮ]' in original_message
            is_help = '[ПОМОЩЬ]' in original_message or '[ПРОСЬБА]' in original_message

            result_msg = ""

            if answer == 'да':
                # === ТОРГОВЛЯ: реальный обмен ресурсов ===
                if is_trade:
                    result_msg = self._execute_trade_deal(faction_name, original_message, cursor)

                # === СОЮЗ: меняем статус + улучшаем отношения ===
                elif is_alliance:
                    cursor.execute("""
                        UPDATE diplomacies SET relationship = 'союз'
                        WHERE (faction1=? AND faction2=?) OR (faction1=? AND faction2=?)
                    """, (faction_name, self.selected_faction, self.selected_faction, faction_name))
                    cursor.execute("""
                        UPDATE relations SET relationship = MIN(100, relationship + 15)
                        WHERE (faction1=? AND faction2=?) OR (faction1=? AND faction2=?)
                    """, (faction_name, self.selected_faction, self.selected_faction, faction_name))
                    result_msg = f"Союз с {faction_name} заключён! Статус: союз. Отношения +15%."

                # === ПОЩАДА: заключаем мир + передаём ресурсы победителю ===
                elif is_mercy:
                    cursor.execute("""
                        UPDATE diplomacies SET relationship = 'нейтралитет'
                        WHERE (faction1=? AND faction2=?) OR (faction1=? AND faction2=?)
                    """, (faction_name, self.selected_faction, self.selected_faction, faction_name))
                    cursor.execute("""
                        UPDATE relations SET relationship = MAX(relationship, 25)
                        WHERE (faction1=? AND faction2=?) OR (faction1=? AND faction2=?)
                    """, (faction_name, self.selected_faction, self.selected_faction, faction_name))

                    # Передача ресурсов проигравшего → победителю
                    resource_msg = self._transfer_peace_resources(faction_name, original_message, cursor)

                    # Записываем перемирие на 3 хода
                    self._set_truce(faction_name, cursor)

                    result_msg = f"Мир с {faction_name} заключён! Статус: нейтралитет. {resource_msg}"

                # === ПРОСЬБА: улучшаем отношения ===
                elif is_help:
                    cursor.execute("""
                        UPDATE relations SET relationship = MIN(100, relationship + 8)
                        WHERE (faction1=? AND faction2=?) OR (faction1=? AND faction2=?)
                    """, (faction_name, self.selected_faction, self.selected_faction, faction_name))
                    result_msg = f"Вы помогли {faction_name}. Отношения +8%."

                # === Прочее (дружба, приветствие): маленький бонус ===
                else:
                    cursor.execute("""
                        UPDATE relations SET relationship = MIN(100, relationship + 3)
                        WHERE (faction1=? AND faction2=?) OR (faction1=? AND faction2=?)
                    """, (faction_name, self.selected_faction, self.selected_faction, faction_name))
                    result_msg = f"Отношения с {faction_name} улучшились +3%."

            else:  # Отказ
                if is_alliance or is_trade:
                    cursor.execute("""
                        UPDATE relations SET relationship = MAX(0, relationship - 3)
                        WHERE (faction1=? AND faction2=?) OR (faction1=? AND faction2=?)
                    """, (faction_name, self.selected_faction, self.selected_faction, faction_name))
                    result_msg = f"Вы отклонили предложение {faction_name}. Отношения -3%."
                elif is_mercy:
                    result_msg = f"Вы отклонили мольбу {faction_name} о пощаде. Война продолжается."
                else:
                    result_msg = f"Вы отклонили предложение {faction_name}."

            self.conn.commit()

            # Сохраняем ответ + результат в историю
            full_player_text = f"{player_text}. {result_msg}"
            cursor.execute("""
                INSERT INTO negotiation_history (faction1, faction2, message, is_player, is_incoming, timestamp)
                VALUES (?, ?, ?, 1, 0, datetime('now'))
            """, (self.selected_faction, faction_name, full_player_text))
            self.conn.commit()

            # Обновляем UI ресурсов
            self.faction.load_resources()
            self.resource_box.update_resources()

        except Exception as e:
            import traceback
            print(f"[ERROR] Ошибка при обработке ответа дипломатии: {e}")
            traceback.print_exc()

    def _execute_trade_deal(self, faction_name, original_message, cursor):
        """Выполняет реальный обмен ресурсов при принятии торговой сделки."""
        import re

        # Парсим из сообщения: "Мы отдаём X Кристаллов, вы — Y Крон."
        # или "Мы отдаём X Крон, вы — Y Кристаллов."
        give_match = re.search(r'[Мм]ы отда[её]м\s+([\d.,]+\s*(?:тыс\.|млн\.|млрд\.)?)\s*(Крон|Кристаллов|Кроны|Кристаллы)', original_message)
        want_match = re.search(r'вы\s*[—–-]\s*([\d.,]+\s*(?:тыс\.|млн\.|млрд\.)?)\s*(Крон|Кристаллов|Кроны|Кристаллы)', original_message)

        if not give_match or not want_match:
            # Fallback: просто улучшаем отношения
            cursor.execute("""
                UPDATE relations SET relationship = MIN(100, relationship + 5)
                WHERE (faction1=? AND faction2=?) OR (faction1=? AND faction2=?)
            """, (faction_name, self.selected_faction, self.selected_faction, faction_name))
            return f"Торговое соглашение с {faction_name} заключено. Отношения +5%."

        from utils.helpers import parse_formatted_number

        ai_gives_amount = int(parse_formatted_number(give_match.group(1).strip()))
        ai_gives_type = give_match.group(2).strip()
        player_gives_amount = int(parse_formatted_number(want_match.group(1).strip()))
        player_gives_type = want_match.group(2).strip()

        # Нормализуем названия ресурсов
        type_map = {'Крон': 'Кроны', 'Кроны': 'Кроны', 'Кристаллов': 'Кристаллы', 'Кристаллы': 'Кристаллы'}
        ai_gives_type = type_map.get(ai_gives_type, ai_gives_type)
        player_gives_type = type_map.get(player_gives_type, player_gives_type)

        # Проверяем хватает ли у игрока ресурсов
        player_has = self.faction.resources.get(player_gives_type, 0)
        if player_has < player_gives_amount:
            return f"Недостаточно {player_gives_type}! Нужно {player_gives_amount}, у вас {int(player_has)}."

        # Выполняем обмен: игрок отдаёт → AI получает, AI отдаёт → игрок получает
        # Игрок
        self.faction.resources[player_gives_type] -= player_gives_amount
        self.faction.resources[ai_gives_type] = self.faction.resources.get(ai_gives_type, 0) + ai_gives_amount

        # Обновляем внутренние поля Faction
        if player_gives_type == 'Кроны':
            self.faction.money -= player_gives_amount
        elif player_gives_type == 'Кристаллы':
            self.faction.raw_material -= player_gives_amount
        if ai_gives_type == 'Кроны':
            self.faction.money += ai_gives_amount
        elif ai_gives_type == 'Кристаллы':
            self.faction.raw_material += ai_gives_amount

        self.faction.save_resources_to_db()

        # AI фракция: обратный обмен
        cursor.execute("UPDATE resources SET amount = amount - ? WHERE faction=? AND resource_type=?",
                        (ai_gives_amount, faction_name, ai_gives_type))
        cursor.execute("UPDATE resources SET amount = amount + ? WHERE faction=? AND resource_type=?",
                        (player_gives_amount, faction_name, player_gives_type))

        # Улучшаем отношения
        cursor.execute("""
            UPDATE relations SET relationship = MIN(100, relationship + 5)
            WHERE (faction1=? AND faction2=?) OR (faction1=? AND faction2=?)
        """, (faction_name, self.selected_faction, self.selected_faction, faction_name))

        return (f"Сделка заключена! Вы получили {ai_gives_amount} {ai_gives_type}, "
                f"отдали {player_gives_amount} {player_gives_type}. Отношения +5%.")

    def _transfer_peace_resources(self, faction_name, original_message, cursor):
        """Извлекает из сообщения о пощаде предложенные ресурсы и передаёт их победителю."""
        import re
        from utils.helpers import parse_formatted_number

        # Ищем "Предлагаем: X Кроны, Y Кристаллы." в сообщении
        offers = re.findall(
            r'([\d.,]+\s*(?:тыс\.|млн\.|млрд\.)?)\s*(Крон[ыа]?|Кристалл[ыов]*)',
            original_message
        )

        if not offers:
            return ""

        total_msg_parts = []
        for amount_str, res_type in offers:
            amount = int(parse_formatted_number(amount_str.strip()))
            if amount <= 0:
                continue
            # Нормализуем тип ресурса
            if 'Крон' in res_type:
                res_key = 'Кроны'
            elif 'Кристалл' in res_type:
                res_key = 'Кристаллы'
            else:
                continue

            # Списываем у проигравшего (AI фракция)
            cursor.execute(
                "UPDATE resources SET amount = MAX(0, amount - ?) WHERE faction=? AND resource_type=?",
                (amount, faction_name, res_key)
            )
            # Начисляем победителю (игрок)
            self.faction.resources[res_key] = self.faction.resources.get(res_key, 0) + amount
            if res_key == 'Кроны':
                self.faction.money += amount
            elif res_key == 'Кристаллы':
                self.faction.raw_material += amount

            total_msg_parts.append(f"{amount} {res_key}")

        if total_msg_parts:
            self.faction.save_resources_to_db()
            return f"Получено контрибуцией: {', '.join(total_msg_parts)}."
        return ""

    def _set_truce(self, faction_name, cursor):
        """Устанавливает перемирие на 3 хода между фракциями."""
        # Создаём таблицу перемирий если её нет
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS truces (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                faction1 TEXT NOT NULL,
                faction2 TEXT NOT NULL,
                truce_until_turn INTEGER NOT NULL,
                UNIQUE(faction1, faction2)
            )
        """)
        truce_end = self.turn_counter + 3
        cursor.execute("""
            INSERT INTO truces (faction1, faction2, truce_until_turn)
            VALUES (?, ?, ?)
            ON CONFLICT(faction1, faction2) DO UPDATE SET truce_until_turn = excluded.truce_until_turn
        """, (faction_name, self.selected_faction, truce_end))
        cursor.execute("""
            INSERT INTO truces (faction1, faction2, truce_until_turn)
            VALUES (?, ?, ?)
            ON CONFLICT(faction1, faction2) DO UPDATE SET truce_until_turn = excluded.truce_until_turn
        """, (self.selected_faction, faction_name, truce_end))
        print(f"[TRUCE] Перемирие между {faction_name} и {self.selected_faction} до хода {truce_end}")

    def save_selected_faction_to_db(self):
        conn = self.conn
        cursor = conn.cursor()

        cursor.execute("INSERT INTO user_faction (faction_name) VALUES (?)", (self.selected_faction,))

        conn.commit()

    def init_ui(self):
        # === Главный контейнер поверх всех элементов ===
        self.root_overlay = FloatLayout()
        self.add_widget(self.root_overlay)
        self.season_container = FloatLayout(
            size_hint=(None, None),
            size=(dp(120), dp(50)),
            pos_hint={'right': 0.86, 'top': 1}
        )

        def _upd_bg(instance, value):
            self.season_container.canvas.before.clear()
            with self.season_container.canvas.before:
                Color(0.15, 0.2, 0.3, 0.9)
                self._season_bg = RoundedRectangle(pos=instance.pos, size=instance.size, radius=[10])

        self.season_container.bind(pos=_upd_bg, size=_upd_bg)

        # Image: иконка сезона
        self.season_icon = Image(
            source='',  # сюда позже запишем путь к нужной иконке
            size_hint=(None, None),
            size=(dp(40), dp(30)),
            pos_hint={'x': 0.02, 'center_y': 0.5}
        )
        # Label: название сезона
        self.season_label = Label(
            text='',  # сюда позже запишем текст («Зима», «Лето» и т.п.)
            font_size=sp(16),
            color=(1, 1, 1, 1),
            size_hint=(None, None),
            size=(dp(80), dp(30)),
            pos_hint={'x': 0.35, 'center_y': 0.5},
            halign='left',
            valign='middle'
        )
        self.season_label.bind(size=self.season_label.setter('text_size'))

        self.season_container.add_widget(self.season_icon)
        self.season_container.add_widget(self.season_label)
        self.root_overlay.add_widget(self.season_container)

        self.season_container.bind(on_touch_down=self.on_season_pressed)

        # === Контейнер для кнопки "Завершить ход" ===
        end_turn_container = BoxLayout(
            orientation='vertical',
            size_hint=(None, None),
            size=(dp(160), dp(75)),
            pos_hint={'x': 0, 'y': 0.31},
            padding=dp(5)
        )

        with end_turn_container.canvas.before:
            Color(1, 0.2, 0.2, 0.9)  # Цвет фона кнопки
            RoundedRectangle(pos=end_turn_container.pos, size=end_turn_container.size, radius=[15])

        def update_end_turn_rect(instance, value):
            instance.canvas.before.clear()
            with instance.canvas.before:
                Color(1, 0.2, 0.2, 0.9)
                RoundedRectangle(pos=instance.pos, size=instance.size, radius=[15])

        end_turn_container.bind(pos=update_end_turn_rect, size=update_end_turn_rect)

        # === Кнопка с анимацией заполнения ===
        self.end_turn_button = CircularProgressButton(
            text="Завершить ход",
            font_size=sp(20),
            bold=True,
            color=(1, 1, 1, 1),
            background_color=(0, 0, 0, 0),
            size_hint=(1, 1),
            duration=1.4  # Время анимации в секундах
        )

        # === Контейнер для названия фракции ===
        fraction_container = BoxLayout(
            orientation='vertical',
            size_hint=(None, None),
            size=(dp(130) if self.is_android else 150, dp(40) if self.is_android else 40),
            pos_hint={'x': 0.25, 'top': 1},  # Левее кнопки выхода и ближе к потолку
            padding=dp(10)
        )
        with fraction_container.canvas.before:
            Color(0.15, 0.2, 0.3, 0.95)
            self.fraction_rect = RoundedRectangle(radius=[15])

        def update_fraction_rect(instance, value):
            instance.canvas.before.clear()
            with instance.canvas.before:
                Color(0.15, 0.2, 0.3, 0.95)
                self.fraction_rect = RoundedRectangle(pos=instance.pos, size=instance.size, radius=[15])

        fraction_container.bind(pos=update_fraction_rect, size=update_fraction_rect)
        self.faction_label = Label(
            text=f"{self.selected_faction}",
            font_size=sp(20) if self.is_android else '24sp',
            bold=True,
            color=(1, 1, 1, 1),
            halign='center',
            valign='middle'
        )
        self.faction_label.bind(size=self.faction_label.setter('text_size'))
        fraction_container.add_widget(self.faction_label)
        self.root_overlay.add_widget(fraction_container)

        # === Боковая панель с кнопками режимов ===
        mode_panel_width = dp(90)
        mode_panel_container = BoxLayout(
            orientation='vertical',
            size_hint=(None, 0.82),
            width=mode_panel_width,
            pos_hint={'right': 1, 'top': 0.96},
            padding=dp(10),
            spacing=dp(16)
        )
        with mode_panel_container.canvas.before:
            Color(0.15, 0.2, 0.3, 0.9)
            RoundedRectangle(pos=mode_panel_container.pos, size=mode_panel_container.size, radius=[15])

        def update_mode_rect(instance, value):
            instance.canvas.before.clear()
            with instance.canvas.before:
                Color(0.15, 0.2, 0.3, 0.9)
                self._mode_bg = RoundedRectangle(pos=instance.pos, size=instance.size, radius=[15])

        mode_panel_container.bind(pos=update_mode_rect, size=update_mode_rect)
        # Создаем кнопки с поддержкой состояний
        advisor_normal = transform_filename(f'files/sov/{self.selected_faction}.jpg')
        advisor_active = transform_filename(f'files/sov/{self.selected_faction}.jpg')

        self.btn_advisor = TabImageButton(
            normal_source=advisor_normal,
            active_source=advisor_active if os.path.exists(advisor_active) else advisor_normal,
            size_hint=(1, None),
            height=dp(60),
            on_release=self.show_advisor
        )

        self.btn_economy = TabImageButton(
            normal_source='files/status/economy.png',
            size_hint=(1, None),
            height=dp(60),
            on_release=self.switch_to_economy
        )

        self.btn_army = TabImageButton(
            normal_source='files/status/army.png',
            size_hint=(1, None),
            height=dp(60),
            on_release=self.switch_to_army
        )

        self.btn_politics = TabImageButton(
            normal_source='files/status/politic.png',
            size_hint=(1, None),
            height=dp(60),
            on_release=self.switch_to_politics
        )

        # Сохраняем ссылки для управления состояниями
        self.tab_buttons = {
            'advisor': self.btn_advisor,
            'economy': self.btn_economy,
            'army': self.btn_army,
            'politics': self.btn_politics
        }

        # Добавляем кнопки в панель
        for btn in self.tab_buttons.values():
            mode_panel_container.add_widget(btn)

        self.root_overlay.add_widget(mode_panel_container)
        self.save_interface_element("ModePanel", "bottom", mode_panel_container)

        # === Центральная область ===
        self.game_area = FloatLayout(size_hint=(0.7, 1), pos_hint={'x': 0.25, 'y': 0})
        self.root_overlay.add_widget(self.game_area)
        self.save_interface_element("GameArea", "center", self.game_area)

        # === Счётчик ходов ===
        turn_counter_size = (dp(200), dp(50))
        turn_counter_container = BoxLayout(
            orientation='vertical',
            size_hint=(None, None),
            size=turn_counter_size,
            pos_hint={'right': 0.7, 'top': 1},
            padding=dp(10),
            spacing=dp(5)
        )
        with turn_counter_container.canvas.before:
            Color(0.15, 0.2, 0.3, 0.9)
            RoundedRectangle(pos=turn_counter_container.pos, size=turn_counter_container.size, radius=[15])

        def update_turn_rect(instance, value):
            instance.canvas.before.clear()
            with instance.canvas.before:
                Color(0.15, 0.2, 0.3, 0.9)
                RoundedRectangle(pos=instance.pos, size=instance.size, radius=[15])

        turn_counter_container.bind(pos=update_turn_rect, size=update_turn_rect)
        self.turn_label = Label(text=f"Текущий ход: {self.turn_counter}", font_size='18sp', color=(1, 1, 1, 1),
                                bold=True, halign='center')
        turn_counter_container.add_widget(self.turn_label)
        self.root_overlay.add_widget(turn_counter_container)

        # === Контейнер для кнопки выхода ===
        exit_container = BoxLayout(
            orientation='vertical',
            size_hint=(None, None),
            size=(dp(100) if self.is_android else 100, dp(50) if self.is_android else 50),
            pos_hint={'x': 0.89, 'y': 0},
            padding=dp(10),
            spacing=dp(4)
        )
        with exit_container.canvas.before:
            Color(0.1, 0.5, 0.1, 1)
            RoundedRectangle(pos=exit_container.pos, size=exit_container.size, radius=[15])

        def update_exit_rect(instance, value):
            instance.canvas.before.clear()
            with instance.canvas.before:
                Color(0.15, 0.2, 0.3, 0.9)
                RoundedRectangle(pos=instance.pos, size=instance.size, radius=[15])

        exit_container.bind(pos=update_exit_rect, size=update_exit_rect)
        self.exit_button = Button(
            text="Выход",
            size_hint=(1, 1),
            background_color=(0, 0, 0, 0),
            font_size='15sp',
            bold=True,
            color=(1, 1, 1, 1)
        )
        self.exit_button.bind(on_release=lambda x: self.confirm_exit())
        exit_container.add_widget(self.exit_button)
        self.root_overlay.add_widget(exit_container)

        # === ResourceBox ===
        # Инициализируем ResourceBox с фиксированным размером
        self.resource_box = ResourceBox(resource_manager=self.faction, overlay=self.root_overlay)
        self.root_overlay.add_widget(self.resource_box)

        # Моментальное обновление UI при любом изменении ресурсов
        self.faction._on_resources_changed = lambda: self.resource_box.update_resources()

        # Сохраняем координаты ResourceBox
        self.save_interface_element("ResourceBox", "top_left", self.resource_box)

        # === Инициализация ИИ ===


        def on_end_turn(instance):
            instance.start_progress()
            self.scheduled_events['process_turn'] = Clock.schedule_once(lambda dt: self.process_turn(None), 1.5)

        self.end_turn_button.bind(on_press=on_end_turn)
        end_turn_container.add_widget(self.end_turn_button)
        self.root_overlay.add_widget(end_turn_container)
        self.save_interface_element("EndTurnButton", "bottom_right", self.end_turn_button)

        # --- Привязка к изменению размера окна ---
        Window.bind(on_resize=self.update_resource_box_position)
        # Активируем стартовую вкладку
        self.activate_tab('advisor')

        # Запускаем обучение с небольшой задержкой (после полной отрисовки интерфейса)
        if self.tutorial_enabled:
            Clock.schedule_once(lambda dt: self.start_tutorial(), 1.2)

    def deactivate_all_tabs(self):
        """Деактивирует все кнопки вкладок"""
        for btn in self.tab_buttons.values():
            if hasattr(btn, 'set_active'):
                btn.set_active(False)
        # Останавливаем мигание советника при деактивации
        if hasattr(self.btn_advisor, 'stop_blinking'):
            self.btn_advisor.stop_blinking()

    def activate_tab(self, tab_name):
        """Активирует указанную вкладку и деактивирует остальные"""
        self.deactivate_all_tabs()
        if tab_name in self.tab_buttons:
            self.tab_buttons[tab_name].set_active(True)
            # Для советника останавливаем мигание при активации
            if tab_name == 'advisor' and hasattr(self.btn_advisor, 'stop_blinking'):
                self.btn_advisor.stop_blinking()

    def process_turn(self, instance=None):
        """
        Обработка хода игрока и ИИ.
        """
        # Увеличиваем счетчик ходов
        self.turn_counter += 1
        # Обновляем метку с текущим ходом
        self.turn_label.text = f"Текущий ход: {self.turn_counter}"
        # Сохраняем текущее значение хода в таблицу turn
        self.save_turn(self.selected_faction, self.turn_counter)
        # Сохраняем историю ходов в таблицу turn_save
        self.save_turn_history(self.selected_faction, self.turn_counter)

        # Проверяем переворот перед обработкой хода
        if self.check_coup_and_trigger_defeat(self.conn):
            return  # Игра закончена из-за переворота

        # Обновляем сезонные бонусы артефактов
        self.season_manager.apply_artifact_bonuses(self.conn)

        # Обновляем ресурсы игрока и получаем прирост
        profit_details = self.faction.update_resources()  # Теперь возвращает словарь
        bonus_details = self.faction.apply_player_bonuses()  # Получаем бонусы

        # Объединяем прирост и бонусы
        delta_resources = {}
        for res in profit_details:
            base_gain = profit_details[res]
            bonus_gain = bonus_details.get(res, 0)
            delta_resources[res] = {"base": base_gain, "bonus": bonus_gain}

        # Обновляем интерфейс и передаем дельту для подсветки
        self.resource_box.update_resources(delta=delta_resources)
        self.faction.save_resources_to_db()

        # Проверяем, есть ли Мятежники в городах, и создаём ИИ для них
        self.ensure_rebellion_ai_controller()

        # === Проверка и запуск инвазии нежити ===
        invasion_triggered, invasion_msg = check_and_trigger_invasion(
            self.conn, self.turn_counter, self.selected_faction
        )
        if invasion_triggered:
            # Показываем оповещение о начале мора
            self._show_invasion_notification(invasion_msg)
            # Создаём AI контроллер для нежити
            if UNDEAD_FACTION_NAME not in self.ai_controllers:
                self.ai_controllers[UNDEAD_FACTION_NAME] = AIController(
                    UNDEAD_FACTION_NAME, self.conn, self.season_manager,
                    player_faction=self.selected_faction
                )

        # Обработка хода нежити (подкрепления, артефакты)
        if is_invasion_active(self.conn):
            process_undead_turn(self.conn, self.turn_counter)

        # Ход ИИ
        for faction_name, ai_controller in self.ai_controllers.items():
            ai_controller.make_turn()

        # Удаляем лишних героев 2, 3, 4 классов которых мог наплодить ИИ
        self.enforce_garrison_hero_limits()

        # Обновляем статус уничтоженных фракций
        self.update_destroyed_factions()

        # Обновляем статус ходов
        self.reset_check_attack_flags()

        # Обработка дворян
        process_nobles_turn(self.conn, self.turn_counter)

        # Инициализация перемещений
        self.initialize_turn_check_move()

        # Обновляем текущий сезон
        new_season = self.update_season(self.turn_counter)
        self._update_season_display(new_season)
        self.season_manager.update(self.current_idx, self.conn)

        # Сбрасываем характеристики отсутствующих юнитов 3 класса
        self.season_manager.reset_absent_third_class_units(self.conn)

        # Обновляем рейтинг армии и отрисовываем звёздочки (сброс кэша — данные изменились)
        self._prev_star_levels = None
        self.update_army_rating()

        # Генерация случайных событий
        self.event_now = random.randint(1, 100)
        if self.turn_counter % self.event_now == 0:
            print("Генерация события...")
            self.event_manager.generate_event(self.turn_counter)
        # === ПРОВЕРКА НОВЫХ ОБЪЯВЛЕНИЙ ВОЙНЫ ===
        self.check_diplomacy_changes()
        # Сбрасываем флаг уведомления для следующего хода
        self.reset_war_notification_flag()
        # === ПРОВЕРКА НОВЫХ ДИПЛОМАТИЧЕСКИХ СООБЩЕНИЙ ОТ AI ===
        self.check_new_diplomatic_messages()
        # Проверяем условие завершения игры
        game_continues, reason = self.faction.end_game()  # Получаем статус и причину завершения
        if not game_continues:
            print("Условия завершения игры выполнены.")

            # Определяем статус завершения (win или lose)
            if "Мир во всем мире" in reason or "Все фракции были уничтожены" in reason:
                status = "win"  # Условия победы
            else:
                status = "lose"  # Условия поражения

            # Запускаем модуль results_game для обработки результатов
            results_game_instance = ResultsGame(status, reason, self.conn)
            results_game_instance.show_results(self.selected_faction, status, reason)
            App.get_running_app().restart_app()
            return  # Прерываем выполнение дальнейших действий
        print(f"Ход {self.turn_counter} завершён")

    def ensure_rebellion_ai_controller(self):
        """Проверяет, есть ли в городах Мятежники, и добавляет ИИ, если его ещё нет."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT 1 FROM cities WHERE faction = 'Мятежники' LIMIT 1")
        rebellion_exists = cursor.fetchone()

        if rebellion_exists and 'Мятежники' not in self.ai_controllers:
            print("Фракция 'Мятежники' обнаружена в городах. Создаём AIController.")
            self.ai_controllers['Мятежники'] = AIController('Мятежники', self.conn)


    def get_city_data(self):
        """Получает стратегически важные данные о городах для ИИ"""
        try:
            cursor = self.db_connection.cursor()

            # 1. Ключевая информация о городах:
            # - Кто владеет городом
            # - Его производство кристаллов
            # - Защита (гарнизон)
            cursor.execute("""
                SELECT 
                    c.name, 
                    c.faction,
                    c.kf_crystal,
                    COALESCE(g.garrison_strength, 0) as defense
                FROM cities c
                LEFT JOIN (
                    SELECT city_name, SUM(unit_count) as garrison_strength
                    FROM garrisons
                    GROUP BY city_name
                ) g ON c.name = g.city_name
            """)

            cities = []
            for row in cursor.fetchall():
                name, faction, kf_crystal, defense = row

                cities.append({
                    'name': name,
                    'faction': faction,
                    'production': kf_crystal,  # Производство кристаллов
                    'defense': defense,  # Общая численность гарнизона
                    'is_valuable': kf_crystal > 5  # Ценный ли город (высокое производство)
                })

            return cities

        except Exception as e:
            print(f"Ошибка при получении данных о городах: {e}")
            return []


    def get_diplomacy_state(self):
        """Получает текущее дипломатическое состояние"""
        try:
            cursor = self.db_connection.cursor()

            # Получаем все дипломатические отношения
            cursor.execute("SELECT faction1, faction2, relationship FROM diplomacies")

            diplomacy = {
                'wars': [],  # Кто с кем воюет
                'alliances': [],  # Кто с кем в союзе
                'neutral': []  # Кто нейтрален
            }

            for faction1, faction2, relationship in cursor.fetchall():
                if relationship == 'война':
                    diplomacy['wars'].append((faction1, faction2))
                elif relationship == 'союз':
                    diplomacy['alliances'].append((faction1, faction2))
                elif relationship == 'нейтралитет':
                    diplomacy['neutral'].append((faction1, faction2))

            return diplomacy

        except Exception as e:
            print(f"Ошибка при получении дипломатии: {e}")
            return {'wars': [], 'alliances': [], 'neutral': []}

    def get_army_strength(self):
        """Получает общую силу армий каждой фракции"""
        try:
            cursor = self.db_connection.cursor()

            # Считаем общую численность армии по фракциям
            cursor.execute("""
                SELECT u.faction, SUM(g.unit_count) as total_army
                FROM garrisons g
                JOIN units u ON g.unit_name = u.unit_name
                GROUP BY u.faction
            """)

            armies = {}
            for faction, total_army in cursor.fetchall():
                armies[faction] = {
                    'total_units': total_army or 0,
                    'city_count': self.get_city_count_for_faction(faction)
                }

            return armies

        except Exception as e:
            print(f"Ошибка при получении силы армий: {e}")
            return {}

    def get_resources_data(self):
        """Получает ресурсы фракций"""
        try:
            cursor = self.db_connection.cursor()

            cursor.execute("SELECT faction, resource_type, amount FROM resources")

            resources = {}
            for faction, resource_type, amount in cursor.fetchall():
                if faction not in resources:
                    resources[faction] = {}
                resources[faction][resource_type] = amount

            # Структурируем важные ресурсы
            structured_resources = {}
            for faction, res in resources.items():
                structured_resources[faction] = {
                    'gold': res.get('Кроны', 0),
                    'crystals': res.get('Кристаллы', 0),
                    'workers': res.get('Рабочие', 0),
                    'army_limit': res.get('Лимит Армии', 0),
                    'consumption': res.get('Потребление', 0)
                }

            return structured_resources

        except Exception as e:
            print(f"Ошибка при получении ресурсов: {e}")
            return {}

    def get_relations_data(self):
        """Получает уровень отношений между фракциями"""
        try:
            cursor = self.db_connection.cursor()

            cursor.execute("SELECT faction1, faction2, relationship FROM relations")

            relations = {}
            for faction1, faction2, relationship in cursor.fetchall():
                key = f"{faction1}_{faction2}"
                relations[key] = int(relationship)

            return relations

        except Exception as e:
            print(f"Ошибка при получении отношений: {e}")
            return {}

    def get_garrison_data(self):
        """Получает детальную информацию о гарнизонах"""
        try:
            cursor = self.db_connection.cursor()

            cursor.execute("""
                SELECT 
                    g.city_name,
                    g.unit_name,
                    g.unit_count,
                    u.attack,
                    u.defense,
                    u.durability,
                    u.unit_class
                FROM garrisons g
                JOIN units u ON g.unit_name = u.unit_name
            """)

            garrisons = {}
            for row in cursor.fetchall():
                city_name, unit_name, unit_count, attack, defense, durability, unit_class = row

                if city_name not in garrisons:
                    garrisons[city_name] = []

                garrisons[city_name].append({
                    'unit': unit_name,
                    'count': unit_count,
                    'attack': attack,
                    'defense': defense,
                    'durability': durability,
                    'class': unit_class
                })

            return garrisons

        except Exception as e:
            print(f"Ошибка при получении гарнизонов: {e}")
            return {}

    def get_unit_stats(self):
        """Получает статистику юнитов"""
        try:
            cursor = self.db_connection.cursor()

            cursor.execute("""
                SELECT 
                    faction,
                    unit_name,
                    attack,
                    defense,
                    durability,
                    unit_class,
                    cost_money
                FROM units
            """)

            units = {}
            for row in cursor.fetchall():
                faction, unit_name, attack, defense, durability, unit_class, cost_money = row

                if faction not in units:
                    units[faction] = []

                units[faction].append({
                    'name': unit_name,
                    'attack': attack,
                    'defense': defense,
                    'durability': durability,
                    'class': unit_class,
                    'cost': cost_money
                })

            return units

        except Exception as e:
            print(f"Ошибка при получении статистики юнитов: {e}")
            return {}

    def get_city_count_for_faction(self, faction):
        """Получает количество городов у фракции"""
        try:
            cursor = self.db_connection.cursor()
            cursor.execute("SELECT COUNT(*) FROM cities WHERE faction = ?", (faction,))
            return cursor.fetchone()[0] or 0
        except:
            return 0

    def train_ai_with_data(self, game_state):
        """Тренирует ИИ на основе данных игры"""
        try:
            # Анализируем состояние каждой фракции
            for faction in ['Север', 'Эльфы', 'Адепты', 'Вампиры', 'Элины']:
                if faction == self.current_faction:
                    continue  # ИИ не управляет игроком

                # 1. Оцениваем текущее положение фракции
                faction_state = self.analyze_faction_state(faction, game_state)

                # 2. Принимаем решения на основе анализа
                decisions = self.make_ai_decisions(faction, faction_state, game_state)

                # 3. Применяем решения
                self.apply_ai_decisions(faction, decisions)

        except Exception as e:
            print(f"Ошибка при тренировке ИИ: {e}")

    def analyze_faction_state(self, faction, game_state):
        """Анализирует состояние конкретной фракции"""
        state = {
            'strength': 0,
            'weakness': 0,
            'cities': 0,
            'production': 0,
            'enemies': [],
            'allies': [],
            'is_losing': False,
            'can_attack': False
        }

        # 1. Количество городов
        state['cities'] = sum(1 for city in game_state['cities'] if city['faction'] == faction)

        # 2. Производство кристаллов
        state['production'] = sum(city['production'] for city in game_state['cities'] if city['faction'] == faction)

        # 3. Сила армии
        army_data = game_state['armies'].get(faction, {})
        state['army_strength'] = army_data.get('total_units', 0)

        # 4. Враги
        for war in game_state['diplomacy']['wars']:
            if faction in war:
                enemy = war[0] if war[1] == faction else war[1]
                state['enemies'].append(enemy)

        # 5. Союзники
        for alliance in game_state['diplomacy']['alliances']:
            if faction in alliance:
                ally = alliance[0] if alliance[1] == faction else alliance[1]
                state['allies'].append(ally)

        # 6. Оцениваем, проигрывает ли фракция
        if state['cities'] < 3 or len(state['enemies']) > 2:
            state['is_losing'] = True

        # 7. Может ли атаковать
        if state['army_strength'] > 50 and state['production'] > 10:
            state['can_attack'] = True

        return state

    def make_ai_decisions(self, faction, faction_state, game_state):
        """Принимает решения для ИИ на основе анализа"""
        decisions = {
            'diplomacy': [],  # Дипломатические действия
            'military': [],  # Военные действия
            'economic': []  # Экономические действия
        }

        # ЛОГИКА ПРЕДЛОЖЕНИЯ МИРА (как вы описали)
        if faction_state['is_losing']:
            # Если проигрывает, предлагаем мир по этапам
            strongest_enemy = self.find_strongest_enemy(faction, game_state)

            if strongest_enemy:
                # Этап 1: Простое предложение мира
                decisions['diplomacy'].append({
                    'action': 'peace_proposal',
                    'target': strongest_enemy,
                    'stage': 1,
                    'offer': 'мир'
                })

        # ЛОГИКА ПРОСЬБЫ О ПОМОЩИ
        if faction_state['cities'] < 4:
            # Ищем союзников с хорошими отношениями
            good_allies = self.find_allies_with_good_relations(faction, game_state, min_relation=60)

            for ally in good_allies:
                decisions['diplomacy'].append({
                    'action': 'request_help',
                    'target': ally,
                    'reason': 'мало городов',
                    'offer': 'взаимопомощь'
                })

        # ЛОГИКА ПРИГЛАШЕНИЯ НА ВОЙНУ
        if len(faction_state['enemies']) > 1:
            # Ищем возможных союзников для совместной войны
            potential_allies = self.find_potential_allies(faction, game_state)

            for potential_ally in potential_allies:
                weakest_enemy = self.find_weakest_enemy(faction, game_state)

                if weakest_enemy:
                    decisions['diplomacy'].append({
                        'action': 'invite_to_war',
                        'target': potential_ally,
                        'enemy': weakest_enemy,
                        'offer': 'совместная атака'
                    })

        # ЛОГИКА ЗАПРОСА РАЗВЕДКИ
        if faction_state['is_losing'] or len(faction_state['enemies']) > 0:
            # Просим разведданные у союзников
            for ally in faction_state['allies']:
                decisions['diplomacy'].append({
                    'action': 'request_intel',
                    'target': ally,
                    'reason': 'стратегическая необходимость'
                })

        return decisions

    def apply_ai_decisions(self, faction, decisions):
        """Применяет решения ИИ в игре"""
        for decision_type, actions in decisions.items():
            for action in actions:
                if action['action'] == 'peace_proposal':
                    self.ai_send_peace_proposal(
                        faction,
                        action['target'],
                        action['stage'],
                        action.get('offer', '')
                    )
                elif action['action'] == 'request_help':
                    self.ai_request_help(faction, action['target'], action['reason'])
                elif action['action'] == 'invite_to_war':
                    self.ai_invite_to_war(faction, action['target'], action['enemy'])
                elif action['action'] == 'request_intel':
                    self.ai_request_intelligence(faction, action['target'])


    def get_diplomacy_data(self):
        """Получение дипломатических данных для нейронной сети"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT faction1, faction2, relationship FROM diplomacies")
        diplomacies = cursor.fetchall()

        diplomacy_data = {}
        for faction1, faction2, relationship in diplomacies:
            key = f"{faction1}_{faction2}"
            diplomacy_data[key] = relationship

        return diplomacy_data


    def cleanup(self):
        """Очистка ресурсов: таймеры, привязки, анимации."""
        print("Очистка GameScreen...")
        # 1. Отменить мигание кнопки советника
        if hasattr(self, 'btn_advisor'):
            self.btn_advisor.cleanup()

        # 2. Отменить все запланированные события
        for event_name, event_obj in self.scheduled_events.items():
            if event_obj: # Проверяем, что объект не None
                Clock.unschedule(event_obj)
                print(f"  Отменен таймер: {event_name}")
        self.scheduled_events.clear() # Очищаем словарь

        # 3. Отвязать привязки
        # Примеры, могут потребоваться другие в зависимости от реализации виджетов
        if self.resource_box:
            self.resource_box.unbind(size=lambda *a: self.resource_box.update_resources()) # Убираем привязку из init_ui
            # Добавьте другие привязки ResourceBox, если есть
        # Привязка к season_container
        if hasattr(self, 'season_container'):
            self.season_container.unbind(on_touch_down=self.on_season_pressed)
        # Привязка к Window
        Window.unbind(on_resize=self.update_resource_box_position)

        # 4. Очистить виджеты (если они содержат свои таймеры/анимации)
        if self.resource_box:
            self.resource_box.cleanup() # Вызываем cleanup у ResourceBox, если он реализован там

        print("Очистка GameScreen завершена.")


    def initialize_nobles(self):
        """Генерация начальных дворян при старте игры."""
        try:
            generate_initial_nobles(self.conn)
            print("Начальные дворяне инициализированы.")
        except Exception as e:
            print(f"Ошибка при инициализации советников: {e}")

    def update_resource_box_position(self, *args):
        """Обновляет позицию ResourceBox так, чтобы он всегда был в левом верхнем углу."""
        if self.resource_box:
            self.resource_box.pos = (dp(0), Window.height - self.resource_box.height)

    def _update_season_display(self, season_info: dict):
        """
        Получив словарь вида {'name': 'Зима', 'icon': 'snowflake'},
        обновляем иконку и подпись в интерфейсе.
        Предполагается, что у вас есть набор png (или других) иконок:
        например 'icons/snowflake.png', 'icons/green_leaf.png', 'icons/sun.png', 'icons/yellow_leaf.png'.
        """
        # Делайте путь к иконке так, как вам удобно:
        icon_map = {
            'snowflake': 'files/status/icons/snowflake.png',
            'green_leaf': 'files/status/icons/green_leaf.png',
            'sun': 'files/status/icons/sun.png',
            'yellow_leaf': 'files/status/icons/yellow_leaf.png'
        }
        icon_key = season_info.get('icon', '')
        if icon_key in icon_map:
            self.season_icon.source = icon_map[icon_key]
        else:
            self.season_icon.source = ''

        self.season_label.text = season_info.get('name', '')

    def check_coup_and_trigger_defeat(self, conn):
        """
        Проверяет таблицу coup_attempts на наличие успешных переворотов.
        Если найден успешный переворот, инициирует поражение игрока.

        Args:
            conn: Соединение с базой данных

        Returns:
            bool: True если был успешный переворот и игра должна закончиться, False otherwise
        """
        try:
            cursor = conn.cursor()
            # Проверяем наличие успешных переворотов
            cursor.execute("SELECT COUNT(*) FROM coup_attempts WHERE status = 'successful'")
            result = cursor.fetchone()

            if result and result[0] > 0:
                # Найден успешный переворот - инициируем поражение
                reason = "Вас свергли нелояльные члены совета"
                status = "lose"

                # Создаем и показываем результаты игры
                results_game_instance = ResultsGame(status, reason, conn)
                results_game_instance.show_results(self.selected_faction, status, reason)
                App.get_running_app().restart_app()
                return True

            return False
        except Exception as e:
            print(f"Ошибка при проверке переворота: {e}")
            return False


    def update_season(self, turn_count: int) -> dict:
        """
        Вызываем каждый ход, передавая turn_count.
        Если turn_count кратно 4, переключаем current_idx на следующий сезон.
        Возвращаем {'name': <название>, 'icon': <иконка>}.
        """
        if turn_count > 1 and (turn_count - 1) % 4 == 0:
            # Переходим к следующему сезону
            self.current_idx = (self.current_idx + 1) % 4
            # Обновляем сезон в базе данных
            self.update_season_in_db(
                self.conn,
                self.SEASON_NAMES[self.current_idx],
                self.current_idx
            )

        return {
            'name': self.SEASON_NAMES[self.current_idx],
            'icon': self.SEASON_ICONS[self.current_idx]
        }

    def initialize_season_table(self, conn):
        """
        Создает таблицу season для хранения текущего сезона.
        Если таблица пуста — инициализирует СЛУЧАЙНЫМ сезоном.
        """
        try:
            cursor = conn.cursor()

            # Проверяем, есть ли запись о сезоне
            cursor.execute("SELECT COUNT(*) FROM season WHERE id = 1")
            count = cursor.fetchone()[0]

            if count == 0:
                # ← СЛУЧАЙНЫЙ СЕЗОН (не по реальному времени!)
                import random
                season_index = random.randint(0, 3)  # 0=Зима, 1=Весна, 2=Лето, 3=Осень
                season_name = self.SEASON_NAMES[season_index]

                cursor.execute("""
                INSERT INTO season (id, current_season, season_index)
                VALUES (1, ?, ?)
                """, (season_name, season_index))
                conn.commit()
                print(f"[SEASON] Таблица season инициализирована. Случайный сезон: {season_name}")
            else:
                # Сезон уже есть в БД — получаем его
                cursor.execute("SELECT current_season, season_index FROM season WHERE id = 1")
                result = cursor.fetchone()
                print(f"[SEASON] Сезон загружен из БД: {result[0]} (индекс: {result[1]})")

        except sqlite3.Error as e:
            print(f"[ERROR] Ошибка при инициализации таблицы season: {e}")

    def get_current_season_from_db(self, conn):
        """
        Получает текущий сезон из базы данных.
        """
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

    def update_season_in_db(self, conn, season_name, season_index):
        """
        Обновляет информацию о текущем сезоне в базе данных.
        """
        try:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE season 
                SET current_season = ?, season_index = ? 
                WHERE id = 1
            """, (season_name, season_index))
            conn.commit()
            print(f"[SEASON] Сезон обновлен в БД: {season_name} (индекс: {season_index})")
        except sqlite3.Error as e:
            print(f"[ERROR] Ошибка при обновлении сезона в БД: {e}")

    def on_season_pressed(self, instance, touch):
        """
        Показывает информационное окно с эффектом текущего сезона
        для выбранной фракции при клике (касании) внутри season_container.
        """
        if instance.collide_point(touch.x, touch.y):
            current_idx = self.current_idx
            current_season_name = self.SEASON_NAMES[current_idx]

            # === Расчёт оставшихся дней до конца сезона ===
            turns_since_season_start = (self.turn_counter - 1) % 4
            days_left = 3 - turns_since_season_start  # Всего 4 хода на сезон
            if days_left == 0:
                days_text = "(Сезон сменится на следующем ходу)"
            else:
                def decline_day(n):
                    if n == 1:
                        return "ход"
                    elif n == 2 or n == 3:
                        return "хода"

                days_text = f"(осталось {days_left} {decline_day(days_left)})"

            # Извлекаем коэффициенты именно для этой фракции
            faction = self.selected_faction
            try:
                coeffs = SeasonManager.FACTION_EFFECTS[current_idx][faction]
            except KeyError:
                effect_text = "Информация о бонусах для вашей фракции недоступна."
            else:
                stat_f = coeffs['stat']
                cost_f = coeffs['cost']
                parts = []
                if stat_f != 1.0:
                    stat_pct = (stat_f - 1.0) * 100
                    stat_pct_int = int(abs(round(stat_pct)))
                    sign = '+' if stat_pct > 0 else '-'
                    parts.append(f"{sign}{stat_pct_int}% к Урону, Защите и Здоровью")
                if cost_f != 1.0:
                    cost_pct = (cost_f - 1.0) * 100
                    cost_pct_int = int(abs(round(cost_pct)))
                    sign = '+' if cost_pct > 0 else '-'
                    parts.append(f"{sign}{cost_pct_int}% к стоимости юнитов")
                if not parts:
                    effect_text = "Нет изменений для вашей фракции в этом сезоне."
                else:
                    effect_text = ", ".join(parts)

            # ========== Определяем адаптивные размеры ==========
            popup_width = Window.width * 0.9
            popup_height = Window.height * 0.6
            if platform == 'android':
                label_font = sp(18)
                button_font = sp(16)
                button_height_dp = dp(46)
                padding_dp = dp(18)
                spacing_dp = dp(13)
            else:
                label_font = sp(18)
                button_font = sp(16)
                button_height_dp = dp(46)
                padding_dp = dp(18)
                spacing_dp = dp(13)

            # ========== Собираем контент Popup ==========
            content = BoxLayout(
                orientation='vertical',
                padding=padding_dp,
                spacing=spacing_dp
            )

            # Маркированный текст: жирным показываем название сезона, дальше — effect_text
            label = Label(
                text=f"{effect_text}\n\n[b]{days_text}[/b]",
                font_size=label_font,
                halign='center',
                valign='middle',
                markup=True,
                color=(1, 1, 1, 1),
                size_hint_y=None
            )
            label.text_size = (popup_width - 2 * padding_dp, None)
            label.texture_update()
            label.height = label.texture_size[1] + dp(10)

            btn_close = Button(
                text="Закрыть",
                size_hint=(1, None),
                height=button_height_dp,
                background_normal='',
                background_color=(0.2, 0.6, 0.8, 1),
                font_size=button_font,
                bold=True,
                color=(1, 1, 1, 1)
            )

            content.add_widget(label)
            content.add_widget(btn_close)

            popup = Popup(
                title=f"Эффект сезона. {self.selected_faction}",
                title_align='center',
                title_size=sp(20) if platform != 'android' else sp(22),
                title_color=(1, 1, 1, 1),
                content=content,
                size_hint=(None, None),
                size=(popup_width, popup_height),
                background_color=(0.1, 0.1, 0.1, 0.95),
                separator_color=(0.3, 0.3, 0.3, 1),
                auto_dismiss=False
            )

            btn_close.bind(on_release=popup.dismiss)
            popup.open()

            return True
        return False

    def confirm_exit(self):
        # === Создаём основное содержимое Popup с отступами ===
        content = BoxLayout(
            orientation='vertical',
            spacing=dp(15),
            padding=[dp(20), dp(20), dp(20), dp(20)]
        )

        # --- Сообщение с увеличенным шрифтом и адаптивной шириной ---
        message = Label(
            text="Устали, Ваше Величество?",
            font_size=sp(18),
            color=(1, 1, 1, 1),
            halign='center',
            valign='middle',
            size_hint=(1, None)
        )

        # Привязываем ширину сообщения к ширине Popup (учитываем паддинг)
        def update_message_size(instance, width):
            # width здесь — ширина content, без padding по горизонтали
            message.text_size = (width, None)
            message.texture_update()
            message.height = message.texture_size[1] + dp(10)

        content.bind(width=update_message_size)
        # Инициализируем высоту сразу
        update_message_size(message, Window.width * 0.95 - dp(10))

        # --- Горизонтальный контейнер для кнопок ---
        btn_container = BoxLayout(
            orientation='horizontal',
            size_hint=(1, None),
            height=dp(48),
            spacing=dp(10)
        )

        # --- Кнопка «Да» (красная) ---
        btn_yes = Button(
            text="Да",
            size_hint=(1, 1),
            background_normal='',
            background_color=get_color_from_hex('#E53E3E'),
            font_size=sp(16),
            bold=True,
            color=(1, 1, 1, 1)
        )

        # --- Кнопка «Нет» (зелёная) ---
        btn_no = Button(
            text="Нет",
            size_hint=(1, 1),
            background_normal='',
            background_color=get_color_from_hex('#38A169'),
            font_size=sp(16),
            bold=True,
            color=(1, 1, 1, 1)
        )

        btn_container.add_widget(btn_yes)
        btn_container.add_widget(btn_no)

        # Добавляем метку и контейнер с кнопками в основной контент
        content.add_widget(message)
        content.add_widget(btn_container)

        # --- Создаём сам Popup, делаем его адаптивным по размеру экрана ---
        popup = Popup(
            title="Подтверждение выхода из матча",
            title_size=sp(20),
            title_align='center',
            title_color=(1, 1, 1, 1),
            content=content,
            size_hint=(0.9, None),
            height=Window.height * 0.51,
            background_color=(0.1, 0.1, 0.1, 0.95),
            separator_color=(0.3, 0.3, 0.3, 1),
            auto_dismiss=False
        )

        # --- Привязываем действия к кнопкам ---
        btn_yes.bind(on_release=lambda x: (popup.dismiss(), App.get_running_app().restart_app()))
        btn_no.bind(on_release=popup.dismiss)

        popup.open()

    def show_war_declaration_popup(self, enemy_factions):
        """
        Показывает красивое уведомление об объявлении войны.
        :param enemy_factions: Список фракций, объявивших войну
        """
        from kivy.uix.popup import Popup
        from kivy.uix.boxlayout import BoxLayout
        from kivy.uix.label import Label
        from kivy.uix.button import Button
        from kivy.graphics import Color, RoundedRectangle
        from kivy.metrics import dp, sp

        print(f"[WAR] Объявлена война от: {', '.join(enemy_factions)}")
        title_text = f"[color=#FF4444]ВОЙНА![/color]"
        message_text = f"[b]{enemy_factions[0]}[/b] объявили вам войну!\nГотовьтесь к битве, Ваше Величество!"

        # === Создаём основной контейнер ===
        content = BoxLayout(
            orientation='vertical',
            padding=[dp(20), dp(20), dp(20), dp(20)],
            spacing=dp(15),
            size_hint=(1, 1)
        )

        # === Заголовок с анимацией ===
        title_label = Label(
            text=title_text,
            font_size=sp(32),
            markup=True,
            halign='center',
            valign='middle',
            size_hint_y=None,
            height=dp(60)
        )
        title_label.bind(size=title_label.setter('text_size'))
        content.add_widget(title_label)

        # === Текст сообщения ===
        message_label = Label(
            text=message_text,
            font_size=sp(20),
            markup=True,
            halign='center',
            valign='middle',
            size_hint_y=None,
            height=dp(80)
        )
        message_label.bind(size=message_label.setter('text_size'))
        content.add_widget(message_label)

        # === Кнопка подтверждения ===
        ok_button = Button(
            text="[b]Сейчас они получат...[/b]",
            font_size=sp(18),
            markup=True,
            size_hint=(1, None),
            height=dp(50),
            background_normal='',
            background_color=(0.6, 0.1, 0.1, 1),
            color=(1, 1, 1, 1)
        )

        # === Создаём Popup ===
        popup = Popup(
            title='',
            content=content,
            size_hint=(0.7, 0.6),
            auto_dismiss=False,
            background_color=(0.2, 0.05, 0.05, 0.95),
            separator_height=0
        )
        # === Закрытие popup ===
        def on_ok_pressed(instance):
            popup.dismiss()
            print("[WAR] Уведомление о войне закрыто")

        ok_button.bind(on_press=on_ok_pressed)
        content.add_widget(ok_button)

        # === Отрисовка рамки с эффектом свечения ===
        def draw_glow_border(instance, value):
            instance.canvas.before.clear()
            with instance.canvas.before:
                # Внешнее свечение
                Color(1, 0.2, 0.2, 0.3)
                RoundedRectangle(
                    pos=(instance.x - 3, instance.y - 3),
                    size=(instance.width + 6, instance.height + 6),
                    radius=[15]
                )
                # Основная рамка
                Color(0.8, 0.1, 0.1, 0.9)
                RoundedRectangle(
                    pos=instance.pos,
                    size=instance.size,
                    radius=[12]
                )

        popup.bind(pos=draw_glow_border, size=draw_glow_border)

        # === Показываем popup ===
        popup.open()



    def _show_invasion_notification(self, message):
        """Показывает уведомление о начале нашествия нежити (Приход Мора)."""
        from kivy.uix.popup import Popup
        from kivy.uix.boxlayout import BoxLayout
        from kivy.uix.label import Label
        from kivy.uix.button import Button
        from kivy.graphics import Color, RoundedRectangle
        from kivy.metrics import dp, sp

        print(f"[UNDEAD] Показываем уведомление о начале мора")

        content = BoxLayout(
            orientation='vertical',
            padding=[dp(20), dp(20), dp(20), dp(20)],
            spacing=dp(15),
            size_hint=(1, 1)
        )

        # Заголовок
        title_label = Label(
            text="[color=#33BF99]ПРИХОД МОРА![/color]",
            font_size=sp(32),
            markup=True,
            halign='center',
            valign='middle',
            size_hint_y=None,
            height=dp(60)
        )
        title_label.bind(size=title_label.setter('text_size'))
        content.add_widget(title_label)

        # Текст сообщения
        message_label = Label(
            text=message,
            font_size=sp(16),
            markup=True,
            halign='center',
            valign='middle',
            size_hint_y=None,
            height=dp(150)
        )
        message_label.bind(size=message_label.setter('text_size'))
        content.add_widget(message_label)

        # Кнопка
        ok_button = Button(
            text="[b]Мы выстоим![/b]",
            font_size=sp(18),
            markup=True,
            size_hint=(1, None),
            height=dp(50),
            background_normal='',
            background_color=(0.1, 0.5, 0.4, 1),
            color=(1, 1, 1, 1)
        )

        popup = Popup(
            title='',
            content=content,
            size_hint=(0.75, 0.65),
            auto_dismiss=False,
            background_color=(0.05, 0.15, 0.12, 0.95),
            separator_height=0
        )

        def on_ok_pressed(instance):
            popup.dismiss()

        ok_button.bind(on_press=on_ok_pressed)
        content.add_widget(ok_button)

        # Рамка с зеленоватым свечением
        def draw_glow_border(instance, value):
            instance.canvas.before.clear()
            with instance.canvas.before:
                Color(0.2, 0.8, 0.6, 0.3)
                RoundedRectangle(
                    pos=(instance.x - 3, instance.y - 3),
                    size=(instance.width + 6, instance.height + 6),
                    radius=[15]
                )
                Color(0.1, 0.5, 0.4, 0.9)
                RoundedRectangle(
                    pos=instance.pos,
                    size=instance.size,
                    radius=[12]
                )

        popup.bind(pos=draw_glow_border, size=draw_glow_border)
        popup.open()

    def initialize_political_data(self):
        """
        Инициализирует таблицу political_systems с учетом выбора игрока.
        Использует self.player_ideology и self.player_allies для определения распределения идеологий.
        Если self.player_ideology не установлен, используется случайное распределение.
        """
        cursor = self.conn.cursor()
        try:
            # Проверяем, есть ли записи в таблице
            cursor.execute("SELECT COUNT(*) FROM political_systems")
            count = cursor.fetchone()[0]

            if count == 0:
                # Список всех фракций
                factions = ["Север", "Эльфы", "Вампиры", "Адепты", "Элины"]

                # Определяем выбор игрока
                self._determine_player_ideology_and_allies()

                # Если игрок не выбрал идеологию - используем случайное распределение
                if not hasattr(self, 'player_ideology') or self.player_ideology is None:
                    print("Идеология игрока не выбрана, используем случайное распределение")
                    self._initialize_random_political_systems(cursor, factions)
                else:
                    print(
                        f"Инициализация с идеологией игрока: {self.player_ideology}, союзников: {getattr(self, 'player_allies', 1)}")
                    self._initialize_player_based_political_systems(cursor, factions)

                self.conn.commit()
                print("Таблица political_systems успешно инициализирована.")

                # Обновляем атрибут player_ideology после инициализации
                self._update_player_ideology_attribute()

        except sqlite3.Error as e:
            print(f"Ошибка при инициализации таблицы political_systems: {e}")
            self.conn.rollback()

    def _determine_player_ideology_and_allies(self):
        """
        Определяет выбор игрока из атрибутов или использует значения по умолчанию.
        Может быть расширена для получения значений из внешнего источника (например, экрана выбора).
        """
        # Проверяем, были ли установлены значения извне
        if not hasattr(self, 'player_ideology'):
            # Можно получить из сохраненных данных или использовать случайную
            self.player_ideology = None

        if not hasattr(self, 'player_allies'):
            self.player_allies = 1  # Значение по умолчанию

        # Если идеология не выбрана, можно предложить случайную
        if self.player_ideology is None:
            pass

    def _initialize_random_political_systems(self, cursor, factions):
        """
        Случайное распределение идеологий (старая логика).
        Условие: не может быть меньше 2 и больше 3 стран с одним политическим строем.
        """
        systems = ["Смирение", "Борьба"]

        def is_valid_distribution(distribution):
            counts = {system: distribution.count(system) for system in systems}
            return all(2 <= count <= 3 for count in counts.values())

        # Генерация случайного распределения
        import random
        while True:
            default_systems = [(faction, random.choice(systems)) for faction in factions]
            distribution = [system for _, system in default_systems]

            if is_valid_distribution(distribution):
                break

        # Вставляем данные в таблицу
        cursor.executemany(
            "INSERT INTO political_systems (faction, system) VALUES (?, ?)",
            default_systems
        )
        print("Таблица political_systems инициализирована случайными значениями.")

    def _initialize_player_based_political_systems(self, cursor, factions):
        """
        Распределение идеологий на основе выбора игрока.
        Игрок получает выбранную идеологию, указанное количество союзников - тоже.
        Остальные фракции получают противоположную идеологию.
        """
        # Получаем параметры игрока
        player_ideology = self.player_ideology
        allies_count = getattr(self, 'player_allies', 1)  # По умолчанию 1 союзник

        # Проверяем корректность значений
        if player_ideology not in ["Смирение", "Борьба"]:
            print(f"Некорректная идеология: {player_ideology}, используем 'Смирение'")
            player_ideology = "Смирение"

        if allies_count not in [1, 2]:
            print(f"Некорректное количество союзников: {allies_count}, используем 1")
            allies_count = 1

        # Определяем противоположную идеологию
        opposite_ideology = "Борьба" if player_ideology == "Смирение" else "Смирение"

        # Получаем список всех фракций кроме игрока
        player_faction = self.selected_faction
        other_factions = [f for f in factions if f != player_faction]

        # Случайным образом выбираем союзников
        import random
        random.shuffle(other_factions)

        # Выбираем союзников (максимально доступное количество)
        max_allies = min(allies_count, len(other_factions))
        allies = other_factions[:max_allies]
        enemies = other_factions[max_allies:]

        # Создаем список для вставки в БД
        political_systems = []

        # 1. Идеология игрока
        political_systems.append((player_faction, player_ideology))

        # 2. Идеологии союзников
        for ally in allies:
            political_systems.append((ally, player_ideology))

        # 3. Идеологии врагов
        for enemy in enemies:
            political_systems.append((enemy, opposite_ideology))

        # Вставляем данные в таблицу
        cursor.executemany(
            "INSERT INTO political_systems (faction, system) VALUES (?, ?)",
            political_systems
        )

        # Сохраняем информацию о союзниках в отдельной таблице для быстрого доступа
        self._save_allies_info(cursor, player_faction, allies)

        # Логируем результат
        print(f"Распределение идеологий:")
        print(f"  Игрок ({player_faction}): {player_ideology}")
        print(f"  Союзники ({len(allies)} из {allies_count}): {', '.join(allies) if allies else 'нет'}")
        print(f"  Враги: {', '.join(enemies) if enemies else 'нет'}")

    def _save_allies_info(self, cursor, player_faction, allies):
        """
        Сохраняет информацию о союзниках в отдельной таблице.
        """
        try:
            # Создаем таблицу для союзников, если её нет
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS player_allies (
                    player_faction TEXT,
                    ally_faction TEXT,
                    PRIMARY KEY (player_faction, ally_faction)
                )
            """)

            # Очищаем старые записи для текущего игрока
            cursor.execute("DELETE FROM player_allies WHERE player_faction = ?", (player_faction,))

            # Добавляем новых союзников
            for ally in allies:
                cursor.execute(
                    "INSERT INTO player_allies (player_faction, ally_faction) VALUES (?, ?)",
                    (player_faction, ally)
                )

            print(f"Информация о {len(allies)} союзниках сохранена в таблицу player_allies")

        except sqlite3.Error as e:
            print(f"Ошибка при сохранении информации о союзниках: {e}")

    def _update_player_ideology_attribute(self):
        """
        Обновляет атрибут player_ideology после инициализации таблицы.
        """
        try:
            self.player_ideology = self.get_player_ideology(self.conn)
            if self.player_ideology:
                print(f"Идеология игрока установлена: {self.player_ideology}")
            else:
                print("Не удалось установить идеологию игрока")
        except Exception as e:
            print(f"Ошибка при обновлении атрибута player_ideology: {e}")

    def get_player_ideology(self, conn):
        """
        Получает идеологию выбранной фракции игрока из таблицы political_systems.
        Возвращает 'player_submission' для Смирение, 'player_struggle' для Борьба.
        """
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT system FROM political_systems WHERE faction = ?", (self.selected_faction,))
            result = cursor.fetchone()
            if result:
                ideology = result[0]
                # Приводим к внутреннему формату, используемому в IDEOLOGY_ICONS
                if ideology == "Смирение":
                    return "player_submission"
                elif ideology == "Борьба":
                    return "player_struggle"
                else:
                    print(f"Неизвестная идеология в БД: {ideology}")
                    return None
            else:
                print(f"Не найдена идеология для фракции {self.selected_faction}")
                return None
        except sqlite3.Error as e:
            print(f"Ошибка при получении идеологии игрока из БД: {e}")
            return None

    def update_cash(self, dt):
        """Обновление текущего капитала фракции через каждые 1 секунду."""
        self.faction.update_cash()
        self.resource_box.update_resources()

    def switch_to_economy(self, instance):
        # Блокируем переключение вкладок во время обучения (кроме текущего шага)
        if self.tutorial_enabled and self.current_tutorial_step != 1:
            return

        self.activate_tab('economy')
        self.clear_game_area()
        economic.start_economy_mode(
            self.game_state_manager.faction,
            self.game_area,
            self.conn,
            self.season_manager
        )

    def switch_to_army(self, instance):
        # Блокируем переключение вкладок во время обучения (кроме текущего шага)
        if self.tutorial_enabled and self.current_tutorial_step != 2:
            return

        self.activate_tab('army')
        self.clear_game_area()
        army.start_army_mode(
            self.selected_faction,
            self.game_area,
            self.game_state_manager.faction,
            self.conn
        )

    def switch_to_politics(self, instance):
        # Блокируем переключение вкладок во время обучения (кроме текущего шага)
        if self.tutorial_enabled and self.current_tutorial_step != 3:
            return

        self.activate_tab('politics')
        self.clear_game_area()
        politic.start_politic_mode(
            self.selected_faction,
            self.game_area,
            self.game_state_manager.faction,
            self.conn
        )

    def show_advisor(self, instance, preselect_faction=None):
        # Блокируем переключение вкладок во время обучения (кроме текущего шага)
        if self.tutorial_enabled and self.current_tutorial_step != 4:
            return

        self.activate_tab('advisor')
        self.clear_game_area()
        advisor_view = AdvisorView(self.selected_faction, self.conn, game_screen_instance=self,
                                   preselect_faction=preselect_faction)
        self.game_area.add_widget(advisor_view)
        self.mark_messages_as_read()

    def clear_game_area(self):
        """Очистка центральной области."""
        self.game_area.clear_widgets()

    def on_stop(self):
        Window.unbind(on_resize=self.update_resource_box_position)
        self.game_state_manager.close_connection()

    def mark_messages_as_read(self, conn=None):
        """Помечает входящие сообщения как прочитанные."""
        if conn is None:
            conn = self.conn

        try:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE negotiation_history 
                SET is_incoming = FALSE 
                WHERE faction2 = ? AND is_incoming = TRUE
            """, (self.selected_faction,))
            conn.commit()
            print(f"Сообщения для {self.selected_faction} помечены как прочитанные")
        except sqlite3.Error as e:
            print(f"Ошибка при пометке сообщений как прочитанных: {e}")

    def update_destroyed_factions(self):
        """
        Обновляет статус фракций в таблице diplomacies.
        Если у фракции нет ни одного города в таблице cities,
        все записи для этой фракции в таблице diplomacies помечаются как "уничтожена".
        Исключает фракцию "Мятежники".
        """
        cursor = self.conn.cursor()
        try:
            # Шаг 1: Получаем список всех фракций, у которых есть города
            cursor.execute("""
                SELECT DISTINCT faction
                FROM cities
            """)
            factions_with_cities = {row[0] for row in cursor.fetchall()}

            # Шаг 1.1: Учитываем фракции, у которых есть хотя бы одна армия в гарнизонах
            cursor.execute("""
                SELECT DISTINCT u.faction
                FROM garrisons g
                JOIN units u ON g.unit_name = u.unit_name
            """)
            factions_with_units = {row[0] for row in cursor.fetchall()}
            factions_with_cities |= factions_with_units

            # Шаг 2: Получаем все уникальные фракции из таблицы diplomacies
            cursor.execute("""
                SELECT DISTINCT faction1
                FROM diplomacies
            """)
            all_factions = {row[0] for row in cursor.fetchall()}

            # Исключаем "Мятежников" и "Нежить" из проверки на уничтожение
            for skip in ("Мятежники", "Нежить"):
                all_factions.discard(skip)
                factions_with_cities.discard(skip)
                factions_with_units.discard(skip)

            # Шаг 3: Определяем фракции, у которых нет ни одного города
            destroyed_factions = all_factions - factions_with_cities

            if destroyed_factions:
                print(f"Фракции без городов (уничтожены): {', '.join(destroyed_factions)}")

                # Шаг 4: Обновляем записи в таблице diplomacies для уничтоженных фракций
                for faction in destroyed_factions:
                    cursor.execute("""
                        UPDATE diplomacies
                        SET relationship = ?
                        WHERE faction1 = ? OR faction2 = ?
                    """, ("уничтожена", faction, faction))
                    print(f"Статус фракции '{faction}' обновлен на 'уничтожена'.")

                # Фиксируем изменения в базе данных
                self.conn.commit()
            else:
                print("Все фракции имеют хотя бы один город. Нет уничтоженных фракций.")

        except sqlite3.Error as e:
            print(f"Ошибка при обновлении статуса уничтоженных фракций: {e}")

    def reset_check_attack_flags(self):
        """
        Обновляет значения check_attack на False для всех записей в таблице turn_check_attack_faction.
        """
        cursor = self.conn.cursor()
        try:
            cursor.execute("""
                UPDATE turn_check_attack_faction
                SET check_attack = ?
            """, (False,))
            self.conn.commit()
            print("Флаги check_attack успешно сброшены на False.")
        except sqlite3.Error as e:
            print(f"Ошибка при сбросе флагов check_attack: {e}")

    def update_army_rating(self, dt=None):
        """Обновляет рейтинг армии и отрисовывает звёзды над городами."""
        self.update_city_military_status()
        self.draw_army_stars_on_map()

    # Кэш проверок существования файлов (проверяем один раз за сессию)
    _file_exists_cache = {}

    @classmethod
    def _check_file(cls, path):
        """Проверяет существование файла с кэшированием."""
        if path not in cls._file_exists_cache:
            cls._file_exists_cache[path] = os.path.exists(path)
        return cls._file_exists_cache[path]

    def draw_army_stars_on_map(self):
        """
        Рисует звёздочки над иконками городов и иконки идеологии/кристаллов.
        Использует кэширование: не перерисовывает если данные не изменились.
        """
        # Пропускаем перерисовку если данные не изменились
        if not hasattr(self, 'city_star_levels') or not self.city_star_levels:
            return
        if self._prev_star_levels == self.city_star_levels:
            return
        self._prev_star_levels = dict(self.city_star_levels)

        star_img_path = 'files/status/army_in_city/star.png'
        red_star_img_path = 'files/status/army_in_city/red_star.png'
        crystal_icon_path = 'files/status/city_bonus/crystal.png'
        player_choise_icon_path = 'files/status/choise.png'

        # Параметры отрисовки
        STAR_SIZE = 25
        SPACING = 5
        CITY_ICON_SIZE = 77
        # Размер иконки идеологии (предположим квадратная)
        IDEOLOGY_ICON_SIZE = 55
        # Отступ от правого края иконки города
        IDEOLOGY_ICON_OFFSET_X = 5

        # --- НОВЫЕ ПАРАМЕТРЫ ДЛЯ ИКОНОК КРИСТАЛЛОВ ---
        CRYSTAL_ICON_SIZE = 20  # Установим размер иконки кристалла поменьше
        # Отступ от правого края иконки города для ПЕРВОЙ иконки кристалла
        CRYSTAL_ICON_START_OFFSET_X = 5  # Например, начинаем сразу справа от иконки города
        CRYSTAL_ICON_SPACING = 5  # Расстояние между иконками кристаллов
        CRYSTAL_ICON_Y_OFFSET = -5  # Сдвиг вниз относительно центра иконки города (чуть ниже)
        # --- КОНЕЦ НОВЫХ ПАРАМЕТРОВ ---

        # --- НОВЫЕ ПАРАМЕТРЫ ДЛЯ ИКОНКИ ВЫБОРА ИГРОКА ---
        # Размер иконки выбора - в 1.5 раза больше иконки города
        PLAYER_CHOISE_ICON_SIZE = int(CITY_ICON_SIZE * 1.2)
        # Центрируем иконку выбора по центру иконки города
        # PLAYER_CHOISE_ICON_OFFSET_X и PLAYER_CHOISE_ICON_Y_OFFSET не нужны, так как она центрирована
        # --- КОНЕЦ НОВЫХ ПАРАМЕТРОВ ---

        # Очищаем прошлые элементы (звезды и иконки)
        self.game_area.canvas.before.clear()
        with self.game_area.canvas.before:
            for city_name, data in self.city_star_levels.items():
                try:
                    # Ожидаем, что в data теперь 8 элементов: ... , is_player_city
                    star_level, icon_x, icon_y, city_name, has_hero, ideology_icon_path, crystal_icon_count, is_player_city = data
                except ValueError:
                    # Совместимость со старым форматом данных (если вдруг)
                    # Пытаемся распаковать 7 элементов
                    try:
                        star_level, icon_x, icon_y, city_name, has_hero, ideology_icon_path, crystal_icon_count = data
                        is_player_city = False # Устанавливаем False, если данные не содержат принадлежности
                        print(f"Предупреждение: данные для {city_name} не содержат is_player_city, установлено в False.")
                    except ValueError:
                        # Пытаемся распаковать 6 элементов (ещё старее)
                        try:
                            star_level, icon_x, icon_y, city_name, has_hero, ideology_icon_path = data
                            crystal_icon_count = 0 # Устанавливаем 0, если данные не содержат бонуса
                            is_player_city = False # Устанавливаем False, если данные не содержат принадлежности
                            print(f"Предупреждение: данные для {city_name} не содержат crystal_icon_count и is_player_city, установлены в 0 и False.")
                        except ValueError:
                            # Если и это не удалось, что-то серьёзно не так
                            print(f"Ошибка: неожиданный формат данных для {city_name}: {data}")
                            continue

                # Центр иконки
                icon_center_x = icon_x + CITY_ICON_SIZE / 2
                icon_center_y = icon_y + CITY_ICON_SIZE / 2

                # --- ВЫДЕЛЕНИЕ ГОРОДОВ ИГРОКА (glow-эффект) ---
                if is_player_city:
                    from design_system import FACTION_COLORS as _FC
                    fc = _FC.get(self.selected_faction, {})
                    glow_color = fc.get('glow', (0.4, 0.7, 1.0, 0.5))
                    primary = fc.get('primary', (0.3, 0.6, 0.9, 1))

                    # Внешнее мягкое свечение
                    glow_size = CITY_ICON_SIZE * 1.6
                    Color(glow_color[0], glow_color[1], glow_color[2], 0.2)
                    Ellipse(
                        pos=(icon_center_x - glow_size / 2, icon_center_y - glow_size / 2),
                        size=(glow_size, glow_size)
                    )
                    # Среднее свечение
                    mid_size = CITY_ICON_SIZE * 1.25
                    Color(primary[0], primary[1], primary[2], 0.25)
                    Ellipse(
                        pos=(icon_center_x - mid_size / 2, icon_center_y - mid_size / 2),
                        size=(mid_size, mid_size)
                    )
                    # Тонкая рамка
                    Color(primary[0], primary[1], primary[2], 0.6)
                    Line(
                        ellipse=(icon_center_x - mid_size / 2, icon_center_y - mid_size / 2,
                                 mid_size, mid_size),
                        width=1.2
                    )


                # --- Отрисовка иконки идеологии ---
                if ideology_icon_path and self._check_file(ideology_icon_path):
                    ideology_x = icon_x + CITY_ICON_SIZE + IDEOLOGY_ICON_OFFSET_X
                    ideology_y = icon_center_y - IDEOLOGY_ICON_SIZE / 2
                    Color(1, 1, 1, 1)
                    Rectangle(
                        source=ideology_icon_path,
                        pos=(ideology_x, ideology_y),
                        size=(IDEOLOGY_ICON_SIZE, IDEOLOGY_ICON_SIZE)
                    )

                # --- Отрисовка иконок бонуса кристаллов ---
                if crystal_icon_count > 0 and self._check_file(crystal_icon_path):
                    crystal_y = icon_y + CRYSTAL_ICON_Y_OFFSET
                    for i in range(crystal_icon_count):
                        crystal_x = icon_x + CITY_ICON_SIZE + CRYSTAL_ICON_START_OFFSET_X + i * (CRYSTAL_ICON_SIZE + CRYSTAL_ICON_SPACING)
                        Color(1, 1, 1, 1)
                        Rectangle(
                            source=crystal_icon_path,
                            pos=(crystal_x, crystal_y),
                            size=(CRYSTAL_ICON_SIZE, CRYSTAL_ICON_SIZE)
                        )


                # --- Отрисовка красной звезды (если есть герой) ---
                if has_hero:
                    red_star_y = icon_center_y + 20 + STAR_SIZE + SPACING  # чуть выше обычных звезд
                    Rectangle(
                        source=red_star_img_path,
                        pos=(icon_center_x - STAR_SIZE / 2, red_star_y),  # Центрируем по иконке города
                        size=(STAR_SIZE, STAR_SIZE)
                    )

                # --- Отрисовка обычных звезд силы ---
                if star_level <= 0:
                    continue
                # Общая ширина всех звёздочек
                total_width = STAR_SIZE * star_level + SPACING * (star_level - 1)
                # Смещаем так, чтобы центр звёзд совпадал с центром иконки
                start_x = icon_center_x - total_width / 2
                start_y = icon_center_y + 20  # чуть выше центра иконки

                # Рисуем каждую звезду
                for i in range(star_level):
                    x_i = start_x + i * (STAR_SIZE + SPACING)
                    y_i = start_y
                    Rectangle(
                        source=star_img_path,
                        pos=(x_i, y_i),
                        size=(STAR_SIZE, STAR_SIZE)
                    )

    def update_city_military_status(self):
        """
        Для всех фракций:
          1) Находим все города, где есть гарнизоны
          2) Для каждой фракции считаем общую мощь армии
          3) Для каждого города этой фракции считаем его мощь
          4) Вычисляем star_level = 0–3
          5) Проверяем наличие юнитов 2-4 класса в гарнизоне
          6) Получаем идеологию фракции города и определяем иконку
          7) Загружаем коэффициент kf_crystal и определяем количество иконок бонуса кристаллов
          8) Проверяем принадлежность города фракции игрока
          9) Сохраняем в self.city_star_levels:
             { city_name: (star_level, icon_x, icon_y, city_name, has_hero, ideology_icon_path, crystal_icon_count, is_player_city) }
        """
        cursor = self.conn.cursor()
        try:
            cursor.execute("""
                SELECT name, faction, icon_coordinates, kf_crystal
                FROM cities 
                WHERE icon_coordinates IS NOT NULL
            """)
            raw_cities = cursor.fetchall()
        except sqlite3.Error as e:
            print(f"Ошибка при получении городов с координатами и kf_crystal: {e}")
            self.city_star_levels = {}
            return

        if not raw_cities:
            print("Нет городов с координатами.")
            self.city_star_levels = {}
            return

        # --- Получаем идеологии всех фракций ---
        faction_ideologies = {}
        try:
            cursor.execute("SELECT faction, system FROM political_systems")
            for faction_name, system in cursor.fetchall():
                # Приводим к внутреннему формату
                if system == "Смирение":
                    faction_ideologies[faction_name] = "submission"
                elif system == "Борьба":
                    faction_ideologies[faction_name] = "struggle"
        except sqlite3.Error as e:
            print(f"Ошибка при получении идеологий фракций из БД: {e}")
            # В случае ошибки, не отрисовываем иконки
            faction_ideologies = {}

        from collections import defaultdict
        factions_cities = defaultdict(list)
        # --- ИЗМЕНЕНО: Теперь сохраняем faction ---
        for city_name, faction, coords_str, kf_crystal_val in raw_cities:
            factions_cities[faction].append((city_name, coords_str, kf_crystal_val, faction))

        # Batch-загрузка героев для всех городов (вместо N запросов)
        cities_with_heroes = set()
        try:
            cursor.execute("""
                SELECT DISTINCT g.city_name
                FROM garrisons g
                JOIN units u ON g.unit_name = u.unit_name
                WHERE u.unit_class IN (2, 3, 4)
            """)
            cities_with_heroes = {row[0] for row in cursor.fetchall()}
        except sqlite3.Error:
            pass

        new_dict = {}
        for faction, cities_list in factions_cities.items():
            total_strength = self.get_total_army_strength_by_faction(faction)
            for city_name, coords_str, kf_crystal_val, city_faction in cities_list:
                try:
                    coords = eval(coords_str)
                    icon_x, icon_y = coords
                except Exception as ex:
                    print(f"Ошибка парсинга icon_coordinates для {city_name}: {ex}")
                    continue

                has_hero = city_name in cities_with_heroes

                # --- Расчет силы армии в городе ---
                city_strength = self.get_city_army_strength_by_faction(city_name, faction)
                star_level = 0  # По умолчанию 0 звезд
                if total_strength > 0 and city_strength > 0:  # Избегаем деления на 0
                    percent = (city_strength / total_strength) * 100
                    if percent < 35:
                        star_level = 1
                    elif percent < 65:
                        star_level = 2
                    else:
                        star_level = 3

                # --- Определение иконки идеологии ---
                ideology_icon_path = None
                if self.player_ideology and faction in faction_ideologies:
                    city_faction_ideology = faction_ideologies[faction]
                    player_ideology_type = self.player_ideology.split('_')[1] # "submission" или "struggle"

                    if city_faction_ideology == player_ideology_type:
                        # Та же идеология
                        ideology_icon_path = self.IDEOLOGY_ICONS[self.player_ideology]['same']
                    else:
                        # Другая идеология
                        ideology_icon_path = self.IDEOLOGY_ICONS[self.player_ideology]['different']

                    # Проверяем существование файла иконки
                    if not self._check_file(ideology_icon_path):
                        ideology_icon_path = None

                # --- Логика для определения количества иконок бонуса кристаллов ---
                crystal_icon_count = 0  # По умолчанию - 0 иконок
                if kf_crystal_val is not None:
                    kf_val = float(kf_crystal_val)
                    if 1.0 <= kf_val < 1.2:
                        crystal_icon_count = 1
                    elif 1.8 <= kf_val < 3.0:
                        crystal_icon_count = 2
                    elif kf_val >= 3.0:
                        crystal_icon_count = 3
                else:
                    print(f"Предупреждение: kf_crystal для города {city_name} равен NULL.")
                # --- Конец логики бонуса кристаллов ---

                # --- Логика для определения, принадлежит ли город игроку ---
                is_player_city = (city_faction == self.selected_faction)
                # --- Конец логики принадлежности ---
                new_dict[city_name] = (star_level, icon_x, icon_y, city_name, has_hero, ideology_icon_path, crystal_icon_count, is_player_city)

        self.city_star_levels = new_dict

    def get_total_army_strength_by_faction(self, faction):
        """Возвращает общую мощь армии фракции (все юниты в городах фракции, включая перешедших)."""
        cursor = self.conn.cursor()
        class_coefficients = {
            "1": 1.3,
            "2": 1.7,
            "3": 2.0,
            "4": 3.0,
            "5": 4.0
        }
        try:
            # Считаем ВСЕ юниты в городах фракции, не только юниты с u.faction = faction.
            # Перешедшие войска (юниты другой фракции в гарнизоне) тоже учитываются.
            cursor.execute("""
                SELECT g.unit_name, g.unit_count, u.attack, u.defense, u.durability, u.unit_class
                FROM garrisons g
                JOIN units u ON g.unit_name = u.unit_name
                WHERE g.city_name IN (SELECT name FROM cities WHERE faction = ?)
            """, (faction,))
            rows = cursor.fetchall()
            total_strength = 0
            for row in rows:
                unit_name, count, attack, defense, durability, unit_class = row
                coefficient = class_coefficients.get(unit_class, 1.0)
                unit_strength = (attack * coefficient) + defense + durability
                total_strength += unit_strength * count
            return total_strength
        except sqlite3.Error as e:
            print(f"Ошибка при подсчёте общей мощи армии: {e}")
            return 0

    def get_city_army_strength_by_faction(self, city_name, faction):
        """Возвращает мощь армии в конкретном городе (ВСЕ юниты гарнизона, не только своей фракции)."""
        cursor = self.conn.cursor()
        class_coefficients = {
            "1": 1.3,
            "2": 1.7,
            "3": 2.0,
            "4": 3.0,
            "5": 4.0
        }
        try:
            # Считаем ВСЕ юниты в гарнизоне города, а не только юниты фракции-владельца.
            # Перешедшие на сторону игрока войска (из другой фракции) тоже должны учитываться.
            cursor.execute("""
                SELECT g.unit_name, g.unit_count, u.attack, u.defense, u.durability, u.unit_class
                FROM garrisons g
                JOIN units u ON g.unit_name = u.unit_name
                WHERE g.city_name = ?
            """, (city_name,))
            rows = cursor.fetchall()
            city_strength = 0
            for row in rows:
                unit_name, count, attack, defense, durability, unit_class = row
                coefficient = class_coefficients.get(unit_class, 1.0)
                unit_strength = (attack * coefficient) + defense + durability
                city_strength += unit_strength * count
            return city_strength
        except sqlite3.Error as e:
            print(f"Ошибка при подсчёте мощи города {city_name}: {e}")
            return 0

    def calculate_star_level(self, total_strength, city_strength):
        """Возвращает уровень (количество звездочек) на основе процентного соотношения мощи."""
        if total_strength == 0 or city_strength == 0:
            return 0  # Нет войск — нет звёздочек

        percent = (city_strength / total_strength) * 100

        if percent < 45:
            return 1
        elif 45 <= percent < 85:
            return 2
        elif 85 <= percent <= 100:
            return 3
        else:
            return 3  # На случай, если процент > 100 из-за ошибок округления

    def initialize_turn_check_move(self):
        """
        Инициализирует запись о возможности перемещения для текущей фракции.
        Устанавливает значение 'can_move' = True по умолчанию.
        """
        cursor = self.conn.cursor()
        try:
            cursor.execute("""
                UPDATE turn_check_move
                SET can_move = ?
            """, (True,))
            self.conn.commit()
            print("Флаги can_move успешно сброшены на True.")
        except sqlite3.Error as e:
            print(f"Ошибка при сбросе флагов can_move: {e}")

    def refresh_player_ideology(self):
        """
        Обновляет атрибут player_ideology, получая значение из БД,
        и пересчитывает данные, зависящие от идеологии (например, иконки на карте).
        """
        print("Обновление идеологии игрока...")
        old_ideology = getattr(self, 'player_ideology', None) # Получаем старое значение, если есть

        # Получаем новую идеологию из БД
        new_ideology = self.get_player_ideology(self.conn)
        if new_ideology is not None:
            self.player_ideology = new_ideology
            print(f"Идеология игрока обновлена: {old_ideology} -> {new_ideology}")
            if old_ideology != new_ideology:
                print("Обнаружено изменение идеологии, обновляем данные на карте...")
                # Пересчитываем данные для отрисовки с новой идеологией
                self.update_city_military_status() # Это обновит self.city_star_levels
            else:
                print("Идеология не изменилась.")
        else:
            print("Не удалось получить новую идеологию игрока из БД.")

    def load_turn(self, faction):
        """Загрузка текущего значения хода для фракции."""
        cursor = self.conn.cursor()
        cursor.execute('SELECT turn_count FROM turn WHERE faction = ?', (faction,))
        result = cursor.fetchone()
        return result[0] if result else 0

    def save_turn(self, faction, turn_count):
        """Сохранение текущего значения хода для фракции."""
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO turn (faction, turn_count)
            VALUES (?, ?)
        ''', (faction, turn_count))
        self.conn.commit()

    def save_turn_history(self, faction, turn_count):
        """Сохранение истории ходов в таблицу turn_save."""
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO turn_save (faction, turn_count)
            VALUES (?, ?)
        ''', (faction, turn_count))
        self.conn.commit()

    def save_interface_element(self, element_name, screen_section, widget):
        """Сохраняет координаты и размер элемента интерфейса в базу данных."""
        if not self.conn:
            return
        cursor = self.conn.cursor()
        try:
            pos = widget.pos
            size = widget.size
            pos_hint = str(widget.pos_hint) if widget.pos_hint else None

            cursor.execute('''
                INSERT INTO interface_coord (
                    element_name, screen_section, x, y, width, height, size_hint_x, size_hint_y, pos_hint
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                element_name,
                screen_section,
                pos[0], pos[1],
                size[0], size[1],
                widget.size_hint[0] if widget.size_hint[0] is not None else None,
                widget.size_hint[1] if widget.size_hint[1] is not None else None,
                pos_hint
            ))
            self.conn.commit()
        except sqlite3.Error as e:
            print(f"Ошибка при сохранении координат {element_name}: {e}")

    def enforce_garrison_hero_limits(self):
        """
        Для каждого юнита 2–4 класса (unit_class > 1) проверяет в таблице garrisons,
        сколько записей этого юнита у каждой фракции. Оставляет только одну запись
        и устанавливает unit_count = 1. Все лишние строки удаляет.
        """
        cur = None
        try:
            # Убедимся, что предыдущая временная таблица удалена
            cleanup_cur = self.conn.cursor()
            try:
                cleanup_cur.execute("DROP TABLE IF EXISTS city_factions")
                self.conn.commit()
            except sqlite3.Error:
                self.conn.rollback()
            finally:
                cleanup_cur.close()

            cur = self.conn.cursor()

            # 1) Построим временную таблицу с городами и их фракциями
            cur.execute("""
                CREATE TEMP TABLE city_factions AS
                SELECT name AS city_name, faction
                  FROM cities
            """)

            # 2) Находим всех «героев» unit_class > 1 вместе с их фракцией
            cur.execute("""
                SELECT g.id, cf.faction, g.unit_name, u.unit_class
                  FROM garrisons AS g
                  JOIN units      AS u  ON g.unit_name = u.unit_name
                  JOIN city_factions AS cf ON g.city_name = cf.city_name
                 WHERE u.unit_class > 1
            """)
            rows = cur.fetchall()

            # Группируем по (faction, unit_name)
            from collections import defaultdict
            heroes = defaultdict(list)
            for row in rows:
                row_id, faction, unit_name, unit_class = row
                heroes[(faction, unit_name)].append(row_id)

            # 3) Обрабатываем каждую группу
            for (faction, unit_name), ids in heroes.items():
                keep_id = ids[0]
                delete_ids = ids[1:]

                if delete_ids:
                    cur.execute(
                        "DELETE FROM garrisons WHERE id IN ({})"
                        .format(",".join("?" * len(delete_ids))),
                        delete_ids
                    )

                # 4) Обновляем count в оставшейся записи
                cur.execute(
                    "UPDATE garrisons SET unit_count = 1 WHERE id = ?",
                    (keep_id,)
                )

            # Коммитим все изменения
            self.conn.commit()

        except sqlite3.OperationalError as e:
            print(f"Операционная ошибка при работе с БД в enforce_garrison_hero_limits: {e}")
            if self.conn:
                self.conn.rollback()
        except sqlite3.Error as e:
            print(f"Ошибка SQLite в enforce_garrison_hero_limits: {e}")
            if self.conn:
                self.conn.rollback()
        except Exception as e:
            print(f"Неожиданная ошибка в enforce_garrison_hero_limits: {e}")
            if self.conn:
                self.conn.rollback()
        finally:
            # Удаляем временную таблицу и закрываем курсор
            if cur:
                try:
                    cur.execute("DROP TABLE IF EXISTS city_factions")
                    self.conn.commit()
                except sqlite3.Error as e:
                    print(f"Ошибка при удалении временной таблицы: {e}")
                    if self.conn:
                        self.conn.rollback()
                finally:
                    cur.close()

    def start_tutorial(self):
        """Запуск системы обучения (вызывается после полной инициализации UI)"""
        if not self.tutorial_enabled:
            return

        print("Запуск системы обучения...")
        self.current_tutorial_step = 1
        self.show_tutorial_step_1()

    def show_tutorial_step_1(self):
        """Шаг 1: Подсказка для кнопки 'Экономика'"""
        hint = TutorialHint(
            target_widget=self.btn_economy,
            arrow_source='files/pict/right_learn.png',
            message=(
                "[b]Экономика[/b]\n\n"
                "Здесь вы управляете:\n"
                "• Уровнем налогов(Налоги)\n"
                "• Выбираете режим строительства(Развитие)\n"
                "• Покупкой/продажей кристаллов(Рынок)\n"
                "• Созданием и покупкой артефактов для героев(Мастерская и Артефакты)"
            ),
            arrow_direction='right',
            on_next=lambda: self.on_step1_next(),
            on_skip=self.skip_tutorial
        )
        self.root_overlay.add_widget(hint)
        self.current_hint = hint
        print("Шаг 1 обучения: вкладка 'Экономика'")

    def on_step1_next(self):
        """Переход к шагу 2 после нажатия 'Далее' на шаге 1"""
        # Убираем подсказку
        if self.current_hint and self.current_hint.parent:
            self.current_hint.parent.remove_widget(self.current_hint)
        self.current_hint = None

        # НЕ переключаем вкладку автоматически!
        # Просто показываем следующую подсказку
        Clock.schedule_once(lambda dt: self.show_tutorial_step_2(), 0.5)

    def show_tutorial_step_2(self):
        """Шаг 2: Подсказка для кнопки 'Армия'"""
        hint = TutorialHint(
            target_widget=self.btn_army,
            arrow_source='files/pict/right_learn.png',
            message=(
                "[b]Армия[/b]\n\n"
                "Здесь вы можете "
                "нанимать солдат и героев.\n"
                "Всего в игре 4 класса юнитов.\n"
                "1 - обычные юниты\n"
                "2 - слабые герои, усиливают обычных юнитов, но не носят артефакты\n"
                "3 - основные герои, усиливают обычных юнитов могут и должны носить артефакты\n"
                "4 - сильные герои, сильны сами по себе, никого не усиливают и не носят артефакты"
            ),
            arrow_direction='right',
            on_next=lambda: self.on_step2_next(),
            on_skip=self.skip_tutorial
        )
        self.root_overlay.add_widget(hint)
        self.current_hint = hint
        print("Шаг 2 обучения: вкладка 'Армия'")

    def on_step2_next(self):
        """Переход к шагу 3 после нажатия 'Далее' на шаге 2"""
        # Убираем подсказку
        if self.current_hint and self.current_hint.parent:
            self.current_hint.parent.remove_widget(self.current_hint)
        self.current_hint = None

        # НЕ переключаем вкладку автоматически!
        Clock.schedule_once(lambda dt: self.show_tutorial_step_3(), 0.5)

    def show_tutorial_step_3(self):
        """Шаг 3: Подсказка для кнопки 'Политика'"""
        hint = TutorialHint(
            target_widget=self.btn_politics,
            arrow_source='files/pict/right_learn.png',
            message=(
                "[b]Политика[/b]\n\n"
                "Важно следить за тем что происходит в Совете, если Совет будет не лоялен к Вашей персоне, "
                "то тогда Вас могут свергнуть.\n"
                "Проводите мероприятия и отслеживайте лояльность дворян во вкладке тайная служба"
            ),
            arrow_direction='right',
            on_next=lambda: self.on_step3_next(),
            on_skip=self.skip_tutorial
        )
        self.root_overlay.add_widget(hint)
        self.current_hint = hint
        print("Шаг 3 обучения: вкладка 'Политика'")

    def on_step3_next(self):
        """Переход к шагу 4 после нажатия 'Далее' на шаге 3"""
        # Убираем подсказку
        if self.current_hint and self.current_hint.parent:
            self.current_hint.parent.remove_widget(self.current_hint)
        self.current_hint = None

        # НЕ переключаем вкладку автоматически!
        Clock.schedule_once(lambda dt: self.show_tutorial_step_4(), 0.5)

    def show_tutorial_step_4(self):
        """Шаг 4: Подсказка для кнопки 'Советник'"""
        hint = TutorialHint(
            target_widget=self.btn_advisor,
            arrow_source='files/pict/right_learn.png',
            message=(
                "[b]Дипломатия[/b]\n\n"
                "Здесь ведутся переговоры в формате переписки:\n"
                "• Обмен ресурсами с другими фракциями\n"
                "• Улучшение отношений с теми с кем это еще можно сделать\n"
                "• Заключение союзов\n"
                "• Планирование совместных атак на врага \n"
                "• Объявление войны или заключение мира\n"
                "\n"
                "Главное не хамите, если не хотите войны..."
            ),
            arrow_direction='right',
            on_next=lambda: self.complete_tutorial(),
            on_skip=self.skip_tutorial
        )
        self.root_overlay.add_widget(hint)
        self.current_hint = hint
        print("Шаг 4 обучения: вкладка 'Советник'")

    def complete_tutorial(self):
        """Завершение обучения"""
        # Убираем подсказку
        if self.current_hint and self.current_hint.parent:
            self.current_hint.parent.remove_widget(self.current_hint)
        self.current_hint = None

        # Отключаем режим обучения
        self.tutorial_enabled = False
        self.current_tutorial_step = 0

        print("Обучение завершено успешно!")
        show_message("Обучение завершено!", "Вы познали управление государством! Удачи, Ваше Величество!")

    def skip_tutorial(self):
        """Пропустить обучение полностью"""
        print("Обучение пропущено пользователем")

        # Убираем подсказку
        if hasattr(self, 'current_hint') and self.current_hint:
            if self.current_hint.parent:
                self.current_hint.parent.remove_widget(self.current_hint)
            self.current_hint = None

        # Отключаем режим обучения
        self.tutorial_enabled = False
        self.current_tutorial_step = 0

        print("Обучение пропущено")

    def _on_step1_complete(self):
        """Обработчик завершения шага 1 — передаём управление обучением в экономический модуль"""
        # Убираем текущую подсказку
        if self.current_hint and self.current_hint.parent:
            self.current_hint.parent.remove_widget(self.current_hint)
        self.current_hint = None

        # Восстанавливаем оригинальный обработчик кнопки экономики
        self.btn_economy.unbind(on_release=self._tutorial_economy_handler)
        self.btn_economy.bind(on_release=self._original_economy_handler)

        # Активируем вкладку и запускаем экономический режим с флагом обучения
        self.activate_tab('economy')
        self.clear_game_area()
        economic.start_economy_mode(
            self.game_state_manager.faction,
            self.game_area,
            self.conn,
            self.season_manager
        )

        # Отключаем обучение в основном экране (управление передано)
        self.tutorial_enabled = False
        self.current_tutorial_step = 0

    def check_recent_incoming_messages(self, conn):
        """
        Проверяет, есть ли в последних 5 записях negotiation_history
        входящие сообщения (is_incoming = TRUE).

        Возвращает:
            bool: True если есть входящие сообщения в последних 5 записях
        """
        try:
            cursor = conn.cursor()

            # Получаем последние 5 записей для текущей фракции игрока
            cursor.execute("""
                SELECT is_incoming 
                FROM negotiation_history 
                WHERE faction2 = ? OR faction1 = ?
                ORDER BY timestamp DESC 
                LIMIT 5
            """, (self.selected_faction, self.selected_faction))

            recent_records = cursor.fetchall()

            # Проверяем, есть ли среди них входящие сообщения
            for record in recent_records:
                if record[0]:  # is_incoming = TRUE
                    return True

            return False

        except sqlite3.Error as e:
            print(f"Ошибка при проверке входящих сообщений: {e}")
            return False

    def on_leave(self, *args):
        """Вызывается при уходе с экрана."""
        self.cleanup()
        return super().on_leave(*args)

    def on_pre_enter(self, *args):
        """Вызывается перед входом на экран."""
        # Проверяем входящие сообщения при входе
        Clock.schedule_once(lambda dt: self.check_and_update_diplomacy_notifications(), 0.5)

        return super().on_pre_enter(*args)

    def reset_game(self):
        """Сброс игры (например, при новой игре)."""
        self.save_turn(self.selected_faction, 0)  # Сбрасываем счетчик ходов до 0
        self.turn_counter = 0
        print("Счетчик ходов сброшен.")
