from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.popup import Popup
from kivy.metrics import dp, sp
from kivy.core.window import Window
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.graphics import Color, RoundedRectangle
from kivy.clock import Clock
import json

# --- КОНФИГУРАЦИЯ СТИЛЕЙ (THEME) ---
class UIStyles:
    # Цветовая палитра "Королевство"
    COLOR_BG = (0.05, 0.05, 0.1, 1)       # Темно-синий фон
    COLOR_CARD = (0.15, 0.15, 0.25, 1)    # Фон карточки
    COLOR_GOLD = (0.8, 0.65, 0.2, 1)      # Золото
    COLOR_TEXT = (0.9, 0.9, 0.9, 1)       # Белый текст
    COLOR_TEXT_DIM = (0.6, 0.6, 0.6, 1)   # Тусклый текст
    COLOR_SUCCESS = (0.2, 0.8, 0.4, 1)    # Зеленый
    COLOR_DANGER = (0.8, 0.2, 0.2, 1)     # Красный
    COLOR_ACTION = (0.3, 0.5, 0.8, 1)     # Синяя кнопка

    # Размеры (Базовые)
    BTN_HEIGHT_PC = dp(40)
    BTN_HEIGHT_ANDROID = dp(32)
    CARD_HEIGHT_PC = dp(60)
    CARD_HEIGHT_ANDROID = dp(50)
    PADDING = dp(10)
    RADIUS = dp(10)

    @staticmethod
    def is_android():
        return hasattr(Window, 'keyboard')

    @staticmethod
    def get_btn_height():
        return UIStyles.BTN_HEIGHT_ANDROID if UIStyles.is_android() else UIStyles.BTN_HEIGHT_PC

    @staticmethod
    def get_card_height():
        return UIStyles.CARD_HEIGHT_ANDROID if UIStyles.is_android() else UIStyles.CARD_HEIGHT_PC

    @staticmethod
    def get_font_size(base_size, is_label=False):
        """Адаптивный шрифт. Для лейблов делаем чуть крупнее для читаемости."""
        if UIStyles.is_android():
            if is_label:
                return base_size * 0.95  # Текст читаемый
            return base_size * 0.85      # Кнопки и второстепенное мельче
        return base_size

# --- КАСТОМНЫЕ ВИДЖЕТЫ ---
class StyledButton(Button):
    """Кнопка со скругленными углами и эффектом нажатия"""
    def __init__(self, color=UIStyles.COLOR_ACTION, **kwargs):
        # Принудительно устанавливаем высоту для адаптивности
        if 'size_hint_y' not in kwargs:
            kwargs['size_hint_y'] = None
        if 'height' not in kwargs:
            kwargs['height'] = UIStyles.get_btn_height()

        super().__init__(**kwargs)
        self.background_color = (0, 0, 0, 0)
        self.background_normal = ''
        self.color = UIStyles.COLOR_TEXT
        self._color = color
        self._original_color = color

        # Адаптивный шрифт для кнопки
        self.font_size = sp(UIStyles.get_font_size(14, is_label=False))

        with self.canvas.before:
            self._bg_color = Color(*self._color)
            self._bg_rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[UIStyles.RADIUS])
            self.bind(pos=self._update_rect, size=self._update_rect)
            self.bind(on_press=self._on_press, on_release=self._on_release)

    def _update_rect(self, instance, value):
        self._bg_rect.pos = instance.pos
        self._bg_rect.size = instance.size

    def _on_press(self, instance):
        self._bg_color.rgba = (self._color[0]*0.7, self._color[1]*0.7, self._color[2]*0.7, 1)

    def _on_release(self, instance):
        self._bg_color.rgba = self._original_color

def get_noble_bonus_text(noble_data):
    """Возвращает текст бонуса от советника если лояльность > 50%."""
    loyalty = noble_data.get('loyalty', 0)
    if loyalty < 50:
        return None

    try:
        ideology_raw = noble_data.get('ideology', '{}')
        if isinstance(ideology_raw, str) and ideology_raw.startswith('{'):
            traits = json.loads(ideology_raw)
        elif isinstance(ideology_raw, dict):
            traits = ideology_raw
        elif isinstance(ideology_raw, str) and ideology_raw.startswith("Любит "):
            traits = {'type': 'race_love', 'value': ideology_raw.split(" ", 1)[1]}
        else:
            traits = {'type': 'ideology', 'value': ideology_raw}
    except Exception:
        return None

    bonus_pct = min(int((loyalty - 50) / 5), 10)  # 0-10% бонус от лояльности 50-100

    if traits.get('type') == 'ideology':
        if traits.get('value') == 'Борьба':
            return f"[color=88ccff]+{bonus_pct}% к добыче Кристаллов[/color]"
        else:
            return f"[color=ffdd66]+{bonus_pct}% к доходу Крон[/color]"
    elif traits.get('type') == 'race_love':
        return f"[color=88ff88]+{bonus_pct}% к отношениям с {traits['value']}[/color]"
    elif traits.get('type') == 'greed':
        return f"[color=ffaa55]+{bonus_pct}% к торговым сделкам[/color]"
    return None


def get_noble_trait_text(noble_data):
    """Возвращает краткое описание типа советника."""
    try:
        ideology_raw = noble_data.get('ideology', '{}')
        if isinstance(ideology_raw, str) and ideology_raw.startswith('{'):
            traits = json.loads(ideology_raw)
        elif isinstance(ideology_raw, dict):
            traits = ideology_raw
        elif isinstance(ideology_raw, str) and ideology_raw.startswith("Любит "):
            return f"[color=88ff88]Симпатизирует: {ideology_raw.split(' ', 1)[1]}[/color]"
        else:
            color = "88ccff" if ideology_raw == "Борьба" else "ffdd66"
            return f"[color={color}]Идеология: {ideology_raw}[/color]"
    except Exception:
        return "[color=aaaaaa]Неизвестно[/color]"

    if traits.get('type') == 'greed':
        demand = traits.get('demand', 0)
        return f"[color=ffaa55]Корыстный (хочет {demand:,} крон)[/color]"
    return "[color=aaaaaa]Неизвестно[/color]"


class NobleCard(BoxLayout):
    """Карточка дворянина — расширенная с лояльностью и бонусами"""
    def __init__(self, noble_data, conn, cash_player, refresh_callback, **kwargs):
        super().__init__(
            orientation='vertical',
            size_hint_y=None,
            height=dp(105),
            padding=dp(8),
            spacing=dp(4),
            **kwargs
        )
        loyalty = noble_data.get('loyalty', 0)

        # Цвет рамки по лояльности
        if loyalty >= 70:
            border_color = (0.2, 0.7, 0.3, 0.8)
        elif loyalty >= 50:
            border_color = (0.7, 0.65, 0.15, 0.8)
        elif loyalty >= 30:
            border_color = (0.7, 0.4, 0.1, 0.8)
        else:
            border_color = (0.7, 0.15, 0.15, 0.8)

        with self.canvas.before:
            Color(*border_color)
            self._border = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(12)])
            Color(*UIStyles.COLOR_CARD)
            self._bg = RoundedRectangle(
                pos=(self.x + dp(2), self.y + dp(2)),
                size=(self.width - dp(4), self.height - dp(4)),
                radius=[dp(10)]
            )
        self.bind(pos=self._update_bg, size=self._update_bg)

        # --- Верхняя строка: имя + лояльность + кнопка ---
        top_row = BoxLayout(size_hint_y=None, height=dp(30), spacing=dp(6))

        name_lbl = Label(
            text=f"[b]{noble_data['name']}[/b]", markup=True,
            font_size=sp(15), color=UIStyles.COLOR_TEXT,
            halign='left', valign='middle', size_hint_x=0.45
        )
        name_lbl.bind(size=name_lbl.setter('text_size'))

        loyalty_color = "00ff00" if loyalty >= 70 else "ffff00" if loyalty >= 50 else "ff8800" if loyalty >= 30 else "ff0000"
        loyalty_lbl = Label(
            text=f"[color={loyalty_color}]Лояльность: {int(loyalty)}%[/color]", markup=True,
            font_size=sp(12), halign='center', valign='middle', size_hint_x=0.3
        )
        loyalty_lbl.bind(size=loyalty_lbl.setter('text_size'))

        # Кнопка действия
        action_widget = self._create_action_button(noble_data, conn, cash_player, refresh_callback)
        action_widget.size_hint_x = 0.25

        top_row.add_widget(name_lbl)
        top_row.add_widget(loyalty_lbl)
        top_row.add_widget(action_widget)

        # --- Средняя строка: тип советника + посещаемость ---
        mid_row = BoxLayout(size_hint_y=None, height=dp(22), spacing=dp(6))

        trait_text = get_noble_trait_text(noble_data)
        trait_lbl = Label(
            text=trait_text, markup=True,
            font_size=sp(11), halign='left', valign='middle', size_hint_x=0.6
        )
        trait_lbl.bind(size=trait_lbl.setter('text_size'))

        status_text = self._get_status_text(noble_data)
        status_lbl = Label(
            text=status_text, markup=True,
            font_size=sp(11), halign='right', valign='middle', size_hint_x=0.4
        )
        status_lbl.bind(size=status_lbl.setter('text_size'))

        mid_row.add_widget(trait_lbl)
        mid_row.add_widget(status_lbl)

        # --- Нижняя строка: бонус ---
        bonus_text = get_noble_bonus_text(noble_data)
        if bonus_text:
            bonus_lbl = Label(
                text=f"Бонус: {bonus_text}", markup=True,
                font_size=sp(12), halign='left', valign='middle',
                size_hint_y=None, height=dp(20)
            )
            bonus_lbl.bind(size=bonus_lbl.setter('text_size'))
        else:
            bonus_lbl = Label(
                text="[color=666666]Бонус: лояльность ниже 50%[/color]", markup=True,
                font_size=sp(11), halign='left', valign='middle',
                size_hint_y=None, height=dp(20)
            )
            bonus_lbl.bind(size=bonus_lbl.setter('text_size'))

        self.add_widget(top_row)
        self.add_widget(mid_row)
        self.add_widget(bonus_lbl)

    def _update_bg(self, instance, value):
        self._border.pos = instance.pos
        self._border.size = instance.size
        self._bg.pos = (instance.x + dp(2), instance.y + dp(2))
        self._bg.size = (instance.width - dp(4), instance.height - dp(4))

    def _get_status_text(self, noble_data):
        attendance = noble_data.get('attendance_history', '')
        if attendance:
            try:
                history = [int(x) for x in str(attendance).split(',') if x.isdigit()]
                if history:
                    percent = int((sum(history) / len(history)) * 100)
                    color = "[color=ff0000]" if percent < 30 else "[color=ffff00]" if percent < 60 else "[color=00ff00]"
                    return f"{color}Посещаемость: {percent}%[/color]"
            except:
                pass
        return "[color=aaaaaa]Статус неизвестен[/color]"

    def _create_action_button(self, noble_data, conn, cash_player, refresh_callback):
        """Создаёт кнопку действия для дворянина"""
        try:
            ideology_raw = noble_data.get('ideology', '{}')
            if isinstance(ideology_raw, str):
                ideology = json.loads(ideology_raw)
            else:
                ideology = ideology_raw

            if isinstance(ideology, dict) and ideology.get('type') == 'greed':
                btn = StyledButton(text="Договориться", color=UIStyles.COLOR_GOLD)
                btn.bind(on_release=lambda inst: self._handle_deal(conn, noble_data, cash_player, refresh_callback))
                return btn
        except Exception:
            pass

        placeholder = Label(text="", size_hint_x=0.25)
        return placeholder

    def _handle_deal(self, conn, noble_data, cash_player, refresh_callback):
        """Обработка кнопки договориться"""
        show_deal_popup(conn, noble_data, cash_player)
        Clock.schedule_once(lambda dt: refresh_callback(), 0.5)

# --- ОБНОВЛЕННЫЕ ФУНКЦИИ ИНТЕРФЕЙСА ---
def _build_bonus_summary(nobles_data):
    """Собирает суммарные бонусы от всех лояльных советников."""
    bonuses = {'crowns': 0, 'crystals': 0, 'relations': [], 'trade': 0}
    for noble in nobles_data:
        loyalty = noble.get('loyalty', 0)
        if loyalty < 50:
            continue
        bonus_pct = min(int((loyalty - 50) / 5), 10)
        try:
            ideology_raw = noble.get('ideology', '{}')
            if isinstance(ideology_raw, str) and ideology_raw.startswith('{'):
                traits = json.loads(ideology_raw)
            elif isinstance(ideology_raw, dict):
                traits = ideology_raw
            elif isinstance(ideology_raw, str) and ideology_raw.startswith("Любит "):
                traits = {'type': 'race_love', 'value': ideology_raw.split(" ", 1)[1]}
            else:
                traits = {'type': 'ideology', 'value': ideology_raw}
        except Exception:
            continue

        if traits.get('type') == 'ideology':
            if traits.get('value') == 'Борьба':
                bonuses['crystals'] += bonus_pct
            else:
                bonuses['crowns'] += bonus_pct
        elif traits.get('type') == 'race_love':
            bonuses['relations'].append((traits['value'], bonus_pct))
        elif traits.get('type') == 'greed':
            bonuses['trade'] += bonus_pct

    parts = []
    if bonuses['crowns']:
        parts.append(f"[color=ffdd66]+{bonuses['crowns']}% Кроны[/color]")
    if bonuses['crystals']:
        parts.append(f"[color=88ccff]+{bonuses['crystals']}% Кристаллы[/color]")
    for race, pct in bonuses['relations']:
        parts.append(f"[color=88ff88]+{pct}% с {race}[/color]")
    if bonuses['trade']:
        parts.append(f"[color=ffaa55]+{bonuses['trade']}% торговля[/color]")

    return "  ".join(parts) if parts else "[color=888888]Нет активных бонусов[/color]"


def show_nobles_window(conn, faction, class_faction):
    """Главное окно совета с бонусами и улучшенным управлением"""
    cash_player = CalculateCash(faction, class_faction)
    player_faction = get_player_faction(conn)
    season_index = get_current_season_index(conn)

    # Основной контейнер
    main_layout = BoxLayout(orientation='vertical', padding=UIStyles.PADDING, spacing=dp(6))
    main_layout.canvas.before.add(Color(*UIStyles.COLOR_BG))
    main_layout.canvas.before.add(RoundedRectangle(pos=main_layout.pos, size=main_layout.size, radius=[dp(15)]))

    # --- Блок суммарных бонусов ---
    bonus_header = BoxLayout(orientation='vertical', size_hint_y=None, height=dp(50), padding=[dp(8), dp(4)])
    with bonus_header.canvas.before:
        Color(0.1, 0.12, 0.2, 1)
        bonus_header._bg = RoundedRectangle(pos=bonus_header.pos, size=bonus_header.size, radius=[dp(8)])
    bonus_header.bind(
        pos=lambda i, v: setattr(i._bg, 'pos', v),
        size=lambda i, v: setattr(i._bg, 'size', v)
    )

    bonus_title = Label(
        text="[b]Бонусы совета[/b]", markup=True,
        font_size=sp(13), color=(0.85, 0.75, 0.4, 1),
        halign='left', valign='middle', size_hint_y=None, height=dp(20)
    )
    bonus_title.bind(size=bonus_title.setter('text_size'))

    bonus_summary_label = Label(
        text="", markup=True,
        font_size=sp(12), halign='left', valign='middle',
        size_hint_y=None, height=dp(22)
    )
    bonus_summary_label.bind(size=bonus_summary_label.setter('text_size'))

    bonus_header.add_widget(bonus_title)
    bonus_header.add_widget(bonus_summary_label)
    main_layout.add_widget(bonus_header)

    # --- Список дворян (ScrollView) ---
    scroll_view = ScrollView(do_scroll_x=False, size_hint_y=1)
    nobles_list = BoxLayout(orientation='vertical', size_hint_y=None, spacing=dp(6))
    nobles_list.bind(minimum_height=nobles_list.setter('height'))
    scroll_view.add_widget(nobles_list)
    main_layout.add_widget(scroll_view)

    # --- Панель действий ---
    actions_layout = BoxLayout(size_hint_y=None, height=UIStyles.get_btn_height() + dp(10), spacing=dp(8))
    btn_secret = StyledButton(text="Тайная служба", color=UIStyles.COLOR_DANGER)
    btn_secret.bind(on_release=lambda inst: show_secret_service_popup(conn, lambda res: None, cash_player, lambda: refresh_list()))
    btn_event = StyledButton(text="Мероприятие", color=UIStyles.COLOR_ACTION)
    btn_event.bind(on_release=lambda inst: show_event_popup(conn, player_faction, season_index, lambda: refresh_list(), cash_player))

    actions_layout.add_widget(btn_secret)
    actions_layout.add_widget(btn_event)
    main_layout.add_widget(actions_layout)

    # Кнопка закрытия
    btn_close = StyledButton(text="Закрыть", color=(0.5, 0.5, 0.5, 1), size_hint_y=None, height=UIStyles.get_btn_height())
    btn_close.bind(on_release=lambda inst: popup.dismiss())
    main_layout.add_widget(btn_close)

    def refresh_list():
        nobles_list.clear_widgets()
        all_nobles = get_all_nobles(conn)
        for noble in all_nobles:
            nobles_list.add_widget(NobleCard(noble, conn, cash_player, refresh_list))
        # Обновляем суммарные бонусы
        bonus_summary_label.text = _build_bonus_summary(all_nobles)

    refresh_list()

    popup = Popup(
        title="Королевский совет",
        content=main_layout,
        size_hint=(0.95, 0.9) if not UIStyles.is_android() else (1, 1),
        pos_hint={'center_x': 0.5, 'center_y': 0.5},
        background_color=(0.07, 0.08, 0.13, 1),
        separator_color=(0.72, 0.55, 0.18, 0.75),
        title_color=(1.0, 0.88, 0.50, 1),
        title_size=sp(17),
        title_align='center'
    )
    popup.open()

def show_deal_popup(conn, noble_data, cash_player):
    """Красивое окно сделки с улучшенной проверкой баланса"""
    noble_traits = get_noble_traits(noble_data['ideology'])
    if noble_traits['type'] != 'greed':
        return
    demand = noble_traits['demand']
    cash_player.load_resources()
    current_money = cash_player.resources.get("Кроны", 0)

    # --- ПРОВЕРКА БАЛАНСА ПЕРЕД ОТКРЫТИЕМ ---
    if current_money < demand:
        shortage = demand - current_money
        show_insufficient_funds_popup(demand, current_money, shortage)
        return
    # -----------------------------------

    content = BoxLayout(orientation='vertical', padding=dp(15), spacing=dp(10))

    # Заголовок сделки
    title = Label(
        text=f"[color={UIStyles.COLOR_GOLD[0]}, {UIStyles.COLOR_GOLD[1]}, {UIStyles.COLOR_GOLD[2]}, 1]{noble_data['name']}[/color]",
        font_size=sp(UIStyles.get_font_size(18, is_label=True)),
        markup=True,
        halign='center',
        size_hint_y=None,
        height=dp(35)
    )

    # Сумма
    cost_label = Label(
        text=f"Требуется: [b]{format_number(demand)} крон[/b]",
        font_size=sp(UIStyles.get_font_size(16, is_label=True)),
        markup=True,
        halign='center',
        color=UIStyles.COLOR_TEXT
    )

    # Кнопки
    btn_layout = BoxLayout(size_hint_y=None, height=UIStyles.get_btn_height(), spacing=dp(10))
    btn_pay = StyledButton(text="Заплатить", color=UIStyles.COLOR_SUCCESS)
    btn_cancel = StyledButton(text="Отмена", color=(0.5, 0.5, 0.5, 1))

    def do_pay(*args):
        if cash_player.deduct_resources(demand):
            if pay_greedy_noble(conn, noble_data['id'], demand):
                # ИЗМЕНЕНО: Используем тост вместо попапа с заголовком
                show_toast_notification("Ближайшие 3 мероприятия моя лояльность к Вам будет расти!", is_success=True, duration=1.0)
                popup.dismiss()
            else:
                # ИЗМЕНЕНО: Тост об ошибке
                show_toast_notification("Опять они мне банк операцию отклонил...", is_success=False, duration=1.5)
        else:
            # ИЗМЕНЕНО: Тост о недостатке средств (вторичная проверка)
            show_toast_notification("Кажется мой счет заблокировали, попробуйте позже...", is_success=False, duration=1.5)

    btn_pay.bind(on_release=do_pay)
    btn_cancel.bind(on_release=lambda *args: popup.dismiss())

    btn_layout.add_widget(btn_pay)
    btn_layout.add_widget(btn_cancel)

    content.add_widget(title)
    content.add_widget(cost_label)
    content.add_widget(Label()) # Распорка
    content.add_widget(btn_layout)

    popup = Popup(
        title="Предложение",
        content=content,
        size_hint=(0.85, 0.5) if not UIStyles.is_android() else (0.95, 0.55),
        pos_hint={'center_x': 0.5, 'center_y': 0.5},
        background_color=(0, 0, 0, 0.7)
    )
    popup.open()

def show_insufficient_funds_popup(required, current, shortage):
    """
    Красивое окно с информацией о недостатке средств.
    Показывает сколько есть, сколько нужно и сколько не хватает (красным).
    Авто-закрытие через 1.5 секунды.
    """
    is_android = UIStyles.is_android()
    padding_main = dp(15) if not is_android else dp(10)
    spacing_main = dp(8) if not is_android else dp(5)
    font_title = sp(UIStyles.get_font_size(16, is_label=True))
    font_info = sp(UIStyles.get_font_size(13, is_label=True))

    content = BoxLayout(orientation='vertical', padding=padding_main, spacing=spacing_main)

    # Фон карточки
    with content.canvas.before:
        Color(*UIStyles.COLOR_CARD)
        content.rect = RoundedRectangle(pos=content.pos, size=content.size, radius=[UIStyles.RADIUS])

    def update_rect(instance, value):
        content.rect.pos = instance.pos
        content.rect.size = instance.size
    content.bind(pos=update_rect, size=update_rect)

    # Заголовок
    title_label = Label(
        text="[b]Недостаточно средств[/b]",
        font_size=font_title,
        markup=True,
        halign='center',
        valign='middle',
        size_hint_y=None,
        height=dp(35) if is_android else dp(40),
        color=UIStyles.COLOR_DANGER
    )

    # Информация о финансах
    info_text = (
        f"[color=aaaaaa]У вас:[/color] [b]{format_number(current)} крон[/b]\n"
        f"[color=aaaaaa]Нужно:[/color] [b]{format_number(required)} крон[/b]\n"
        f"[color=ff0000]Не хватает:[/color] [b][color=ff0000]{format_number(shortage)} крон[/color][/b]"
    )

    info_label = Label(
        text=info_text,
        font_size=font_info,
        markup=True,
        halign='center',
        valign='middle',
        color=UIStyles.COLOR_TEXT
    )
    info_label.bind(size=info_label.setter('text_size'))

    content.add_widget(title_label)
    content.add_widget(info_label)

    popup = Popup(
        title="",
        content=content,
        size_hint=(0.85, 0.35) if not is_android else (0.9, 0.3),
        pos_hint={'center_x': 0.5, 'center_y': 0.5},
        auto_dismiss=False,
        background_color=(0, 0, 0, 0.7),
        separator_height=0
    )

    popup.open()
    # Авто-закрытие через 1.0 секунды (без кнопки)
    Clock.schedule_once(lambda dt: popup.dismiss() if popup._is_open else None, 1.0)

def show_result_popup(title, message, is_success=True):
    """Универсальное окно результата (БЕЗ КНОПОК, авто-скрытие)"""
    content = BoxLayout(orientation='vertical', padding=dp(20), spacing=dp(10))
    color = UIStyles.COLOR_SUCCESS if is_success else UIStyles.COLOR_DANGER

    lbl_title = Label(
        text=f"[b]{title}[/b]",
        font_size=sp(UIStyles.get_font_size(20, is_label=True)),
        markup=True,
        color=color,
        size_hint_y=None,
        height=dp(40)
    )

    lbl_msg = Label(
        text=message,
        font_size=sp(UIStyles.get_font_size(16, is_label=True)),
        halign='center',
        valign='middle',
        color=UIStyles.COLOR_TEXT
    )
    lbl_msg.bind(size=lbl_msg.setter('text_size'))

    # Кнопка убрана по запросу
    # btn = StyledButton(text="Принять", color=UIStyles.COLOR_ACTION)
    # btn.bind(on_release=lambda *args: popup.dismiss())

    content.add_widget(lbl_title)
    content.add_widget(lbl_msg)
    # content.add_widget(btn)

    popup = Popup(
        title="",
        content=content,
        size_hint=(0.7, 0.35),
        pos_hint={'center_x': 0.5, 'center_y': 0.5},
        background_color=(0, 0, 0, 0.8),
        separator_height=0,
        auto_dismiss=False
    )

    popup.open()
    # Авто-закрытие через 2 секунды
    Clock.schedule_once(lambda dt: popup.dismiss() if popup._is_open else None, 2.0)

def show_event_result_popup(message):
    """Показывает всплывающее окно с результатом мероприятия (БЕЗ КНОПОК)"""
    is_android = UIStyles.is_android()
    padding_main = dp(15) if not is_android else dp(10)
    spacing_main = dp(10) if not is_android else dp(7)
    font_title = sp(18) if not is_android else sp(16)
    font_message = sp(15) if not is_android else sp(13)

    content = BoxLayout(orientation='vertical', padding=padding_main, spacing=spacing_main)

    if "проведено" in message.lower():
        title = "Успех!"
        title_color = (0.2, 0.8, 0.2, 1)
    else:
        title = "Ошибка"
        title_color = (0.9, 0.2, 0.2, 1)

    title_label = Label(
        text=f"[b]{title}[/b]",
        font_size=font_title,
        markup=True,
        halign='center',
        valign='middle',
        size_hint_y=None,
        height=dp(40) if not is_android else dp(35),
        color=title_color
    )
    title_label.bind(size=title_label.setter('text_size'))

    message_label = Label(
        text=message,
        font_size=font_message,
        halign='center',
        valign='middle',
        text_size=(dp(280) if not is_android else dp(250), None)
    )
    message_label.bind(size=message_label.setter('text_size'))

    # Кнопка закрытия убрана
    # close_btn = Button(...)

    content.add_widget(title_label)
    content.add_widget(message_label)
    # content.add_widget(close_btn)

    popup_size_hint = (0.8, 0.4) if not is_android else (0.9, 0.35)
    popup = Popup(
        title="",
        content=content,
        size_hint=popup_size_hint,
        pos_hint={'center_x': 0.5, 'center_y': 0.5},
        auto_dismiss=False,
        background_color=(0, 0, 0, 0.8),
        separator_height=0
    )

    popup.open()
    # Авто-закрытие
    Clock.schedule_once(lambda dt: popup.dismiss() if popup._is_open else None, 2.0)


from nobles_generator import (
    get_all_nobles,
    update_noble_loyalty_for_event,
    attempt_secret_service_action,
    get_player_faction,
    get_noble_traits,
    pay_greedy_noble,
    show_secret_service_result_popup,
    get_noble_display_name_with_sympathies
)

from utils.helpers import format_number

class CalculateCash:
    def __init__(self, faction, class_faction):
        self.faction = faction
        self.class_faction = class_faction
        self.resources = self.load_resources()

    def load_resources(self):
        try:
            resources = {
                "Кроны": self.class_faction.get_resource_now("Кроны"),
                "Рабочие": self.class_faction.get_resource_now("Рабочие")
            }
            return resources
        except Exception as e:
            print(f"Ошибка при загрузке ресурсов: {e}")
            return {"Кроны": 0, "Рабочие": 0}

    def deduct_resources(self, crowns, workers=0):
        try:
            current_crowns = self.class_faction.get_resource_now("Кроны")
            current_workers = self.class_faction.get_resource_now("Рабочие")
            if current_crowns < crowns or current_workers < workers:
                return False
            self.class_faction.update_resource_now("Кроны", current_crowns - crowns)
            if workers > 0:
                self.class_faction.update_resource_now("Рабочие", current_workers - workers)
            self.resources["Кроны"] = current_crowns - crowns
            if workers > 0:
                self.resources["Рабочие"] = current_workers - workers
            return True
        except Exception as e:
            print(f"Ошибка при списании ресурсов: {e}")
            return False

def get_current_season_index(conn):
    cursor = conn.cursor()
    cursor.execute("SELECT season_index FROM season WHERE id = 1")
    result = cursor.fetchone()
    return result[0] if result else 0

def get_season_name_by_index(index):
    season_names = ['Зима', 'Весна', 'Лето', 'Осень']
    return season_names[index] if 0 <= index < len(season_names) else 'Зима'

def get_event_type_by_season(season_index):
    events = {0: 'Бал', 1: 'Королевский совет', 2: 'Королевская охота', 3: 'Рыцарский турнир'}
    return events.get(season_index, 'Неизвестное мероприятие')

def calculate_event_cost(season_index):
    base_cost = 2_000
    seasonal_multiplier = {0: 1.9, 1: 0.4, 2: 4.5, 3: 9.1}
    multiplier = seasonal_multiplier.get(season_index, 1.0)
    return int(base_cost * multiplier)

def get_events_count_from_history(conn):
    cursor = conn.cursor()
    cursor.execute("SELECT attendance_history FROM nobles WHERE status = 'active'")
    all_histories = cursor.fetchall()
    all_lengths = []
    for history_row in all_histories:
        history_str = history_row[0] if history_row[0] else ""
        if history_str:
            try:
                history_list = [x for x in history_str.split(',') if x.isdigit()]
                all_lengths.append(len(history_list))
            except Exception:
                continue
        else:
            all_lengths.append(0)
    return max(all_lengths) if all_lengths else 0

def show_secret_service_popup(conn, on_result_callback, cash_player, refresh_main_list_callback):
    """Показывает всплывающее окно для Тайной службы (Адаптивное)"""
    COST_SECRET_SERVICE = 100_000

    cash_player.load_resources()
    current_money = cash_player.resources.get("Кроны", 0)

    # --- УЛУЧШЕННАЯ ПРОВЕРКА БАЛАНСА ---
    if current_money < COST_SECRET_SERVICE:
        shortage = COST_SECRET_SERVICE - current_money
        show_insufficient_funds_popup(COST_SECRET_SERVICE, current_money, shortage)
        return
    # -----------------------------------

    events_count = get_events_count_from_history(conn)

    try:
        cursor = conn.cursor()
        cursor.execute("""
        SELECT id, name, loyalty, status, ideology, attendance_history
        FROM nobles
        WHERE status = 'active'
        ORDER BY name ASC
        """)
        all_active_nobles = cursor.fetchall()
        nobles_data = []
        for row in all_active_nobles:
            noble_dict = {
                'id': row[0], 'name': row[1], 'loyalty': row[2],
                'status': row[3], 'ideology': row[4], 'attendance_history': row[5]
            }
            if events_count >= 3:
                noble_dict['show_loyalty'] = True
                noble_dict['show_views'] = True
                noble_dict['calculated_loyalty'] = int(noble_dict['loyalty']) if noble_dict['loyalty'] is not None else None
            else:
                noble_dict['show_loyalty'] = False
                noble_dict['show_views'] = False
                noble_dict['calculated_loyalty'] = None
            nobles_data.append(noble_dict)
    except Exception as e:
        print(f"[ERROR] Ошибка при получении списка активных дворян: {e}")
        show_result_popup("Ошибка", "Ошибка получения списка целей.", False)
        return

    if not nobles_data:
        show_result_popup("Ошибка", "Нет доступных целей.", False)
        return

    # Основной контейнер
    main_layout = BoxLayout(orientation='vertical', padding=UIStyles.PADDING, spacing=dp(8))
    main_layout.canvas.before.add(Color(*UIStyles.COLOR_BG))
    main_layout.canvas.before.add(RoundedRectangle(pos=main_layout.pos, size=main_layout.size, radius=[dp(15)]))

    # Заголовок
    header = Label(
        text="[b]Тайная служба[/b]",
        font_size=sp(UIStyles.get_font_size(20, is_label=True)),
        color=UIStyles.COLOR_DANGER,
        markup=True,
        size_hint_y=None,
        height=dp(40),
        halign='center'
    )
    main_layout.add_widget(header)

    # Информация о стоимости
    cost_info = Label(
        text=f"Цена санкции: [b]{format_number(COST_SECRET_SERVICE)} крон[/b]",
        font_size=sp(UIStyles.get_font_size(13, is_label=True)),
        color=UIStyles.COLOR_TEXT_DIM,
        markup=True,
        size_hint_y=None,
        height=dp(25),
        halign='center'
    )
    main_layout.add_widget(cost_info)

    # Список целей
    scroll_view = ScrollView(do_scroll_x=False, size_hint_y=1)
    nobles_list = BoxLayout(orientation='vertical', size_hint_y=None, spacing=dp(4))
    nobles_list.bind(minimum_height=nobles_list.setter('height'))
    scroll_view.add_widget(nobles_list)
    main_layout.add_widget(scroll_view)

    # Кнопки внизу
    btn_layout = BoxLayout(size_hint_y=None, height=UIStyles.get_btn_height() + dp(10), spacing=dp(10))
    btn_cancel = StyledButton(text="Отмена", color=(0.5, 0.5, 0.5, 1))
    btn_layout.add_widget(btn_cancel)
    main_layout.add_widget(btn_layout)

    popup = Popup(
        title="",
        content=main_layout,
        size_hint=(0.95, 0.9) if not UIStyles.is_android() else (1, 1),
        pos_hint={'center_x': 0.5, 'center_y': 0.5},
        background_color=(0, 0, 0, 0.7),
        separator_height=0
    )

    btn_cancel.bind(on_release=lambda *args: popup.dismiss())

    def refresh_list():
        nobles_list.clear_widgets()
        for noble_data in nobles_data:
            card = SecretServiceCard(noble_data, conn, cash_player, popup, refresh_main_list_callback, events_count)
            nobles_list.add_widget(card)

    refresh_list()
    popup.open()

def show_insufficient_funds_popup(required, current, shortage):
    """
    Красивое окно с информацией о недостатке средств.
    Показывает сколько есть, сколько нужно и сколько не хватает (красным).
    """
    is_android = UIStyles.is_android()
    padding_main = dp(15) if not is_android else dp(10)
    spacing_main = dp(8) if not is_android else dp(5)
    font_title = sp(UIStyles.get_font_size(16, is_label=True))
    font_info = sp(UIStyles.get_font_size(13, is_label=True))

    content = BoxLayout(orientation='vertical', padding=padding_main, spacing=spacing_main)

    # Фон карточки
    with content.canvas.before:
        Color(*UIStyles.COLOR_CARD)
        content.rect = RoundedRectangle(pos=content.pos, size=content.size, radius=[UIStyles.RADIUS])

    def update_rect(instance, value):
        content.rect.pos = instance.pos
        content.rect.size = instance.size
    content.bind(pos=update_rect, size=update_rect)

    # Заголовок
    title_label = Label(
        text="[b]Недостаточно средств[/b]",
        font_size=font_title,
        markup=True,
        halign='center',
        valign='middle',
        size_hint_y=None,
        height=dp(35) if is_android else dp(40),
        color=UIStyles.COLOR_DANGER
    )

    # Информация о финансах
    info_text = (
        f"[color=aaaaaa]У вас:[/color] [b]{format_number(current)} крон[/b]\n"
        f"[color=aaaaaa]Нужно:[/color] [b]{format_number(required)} крон[/b]\n"
        f"[color=ff0000]Не хватает:[/color] [b][color=ff0000]{format_number(shortage)} крон[/color][/b]"
    )

    info_label = Label(
        text=info_text,
        font_size=font_info,
        markup=True,
        halign='center',
        valign='middle',
        color=UIStyles.COLOR_TEXT
    )
    info_label.bind(size=info_label.setter('text_size'))

    content.add_widget(title_label)
    content.add_widget(info_label)

    popup = Popup(
        title="",
        content=content,
        size_hint=(0.85, 0.35) if not is_android else (0.9, 0.3),
        pos_hint={'center_x': 0.5, 'center_y': 0.5},
        auto_dismiss=False,
        background_color=(0, 0, 0, 0.7),
        separator_height=0
    )

    popup.open()
    # Авто-закрытие через 1.5 секунды
    Clock.schedule_once(lambda dt: popup.dismiss() if popup._is_open else None, 1.5)

class SecretServiceCard(BoxLayout):
    """Карточка цели для Тайной службы (Адаптивная)"""
    def __init__(self, noble_data, conn, cash_player, popup_ref, refresh_callback, events_count, **kwargs):
        super().__init__(
            orientation='horizontal',
            size_hint_y=None,
            height=UIStyles.get_card_height(), # Адаптивная высота
            padding=dp(5),
            spacing=dp(5),
            **kwargs
        )
        self.noble_data = noble_data
        self.conn = conn
        self.cash_player = cash_player
        self.popup_ref = popup_ref
        self.refresh_callback = refresh_callback
        self.events_count = events_count
        self.COST_SECRET_SERVICE = 100_000

        # Фон карточки
        with self.canvas.before:
            Color(*UIStyles.COLOR_CARD)
            self.rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[UIStyles.RADIUS])
            self.bind(pos=self._update_rect, size=self._update_rect)

        # 1. Информация
        info_layout = BoxLayout(orientation='vertical', size_hint_x=0.65, spacing=dp(2))
        name_label = Label(
            text=noble_data['name'],
            font_size=sp(UIStyles.get_font_size(14, is_label=True)),
            halign='left',
            valign='middle',
            color=UIStyles.COLOR_TEXT,
            markup=True,
            shorten=True,
            shorten_from='right'
        )
        name_label.bind(size=name_label.setter('text_size'))

        status_text = self._get_status_text()
        status_label = Label(
            text=status_text,
            font_size=sp(UIStyles.get_font_size(10, is_label=True)),
            halign='left',
            valign='middle',
            color=UIStyles.COLOR_TEXT_DIM,
            markup=True
        )
        status_label.bind(size=status_label.setter('text_size'))

        info_layout.add_widget(name_label)
        info_layout.add_widget(status_label)

        # 2. Кнопка устранения
        btn_layout = BoxLayout(size_hint_x=0.35)
        action_btn = StyledButton(text="Устранить", color=UIStyles.COLOR_DANGER)
        action_btn.bind(on_release=lambda inst: self._handle_elimination())
        btn_layout.add_widget(action_btn)

        self.add_widget(info_layout)
        self.add_widget(btn_layout)

    def _update_rect(self, instance, value):
        self.rect.pos = instance.pos
        self.rect.size = instance.size

    def _get_status_text(self):
        parts = []
        if self.noble_data['show_loyalty'] and self.noble_data['calculated_loyalty'] is not None:
            loyalty = self.noble_data['calculated_loyalty']
            if loyalty < 30: color = "ff0000"
            elif loyalty < 60: color = "ffff00"
            else: color = "00ff00"
            parts.append(f"[color={color}]Лояльность: {loyalty}%[/color]")
        else:
            parts.append("[color=aaaaaa]Лояльность: ?[/color]")

        if self.noble_data['show_views']:
            try:
                noble_traits = get_noble_traits(self.noble_data['ideology'])
                ideology_to_text = {
                    'Борьба': "Борьба", 'Смирение': "Смирение",
                    'Любит Эльфы': "Эльфы", 'Любит Элины': "Элины",
                    'Любит Север': "Люди", 'Любит Вампиры': "Вампиры",
                    'Любит Адепты': "Адепты",
                }
                if noble_traits['type'] == 'greed':
                    views = "Продажный"
                else:
                    views = ideology_to_text.get(noble_traits['value'], noble_traits['value'])
                parts.append(f"[color=cccccc]{views}[/color]")
            except:
                parts.append("[color=aaaaaa]Взгляды: ?[/color]")
        else:
            parts.append("[color=aaaaaa]Взгляды: скрыто[/color]")

        return "  |  ".join(parts)

    def _handle_elimination(self):
        self.cash_player.load_resources()
        current_money = self.cash_player.resources.get("Кроны", 0)
        if current_money < self.COST_SECRET_SERVICE:
            show_result_popup("Ошибка", "Недостаточно средств.", False)
            return

        # Подтверждение (Здесь кнопки оставляем, так как это опасное действие)
        confirm_content = BoxLayout(orientation='vertical', padding=dp(15), spacing=dp(10))
        confirm_popup = Popup(
            title="Подтверждение",
            content=confirm_content,
            size_hint=(0.85, 0.4) if not UIStyles.is_android() else (0.95, 0.45),
            pos_hint={'center_x': 0.5, 'center_y': 0.5},
            background_color=(0, 0, 0, 0.7),
            separator_height=0
        )

        title = Label(
            text=f"[b]Устранить {self.noble_data['name']}?[/b]",
            font_size=sp(UIStyles.get_font_size(15, is_label=True)),
            markup=True,
            color=UIStyles.COLOR_DANGER,
            size_hint_y=None,
            height=dp(35),
            halign='center'
        )
        cost = Label(
            text=f"Цена: {format_number(self.COST_SECRET_SERVICE)} крон",
            font_size=sp(UIStyles.get_font_size(13, is_label=True)),
            color=UIStyles.COLOR_TEXT,
            halign='center'
        )

        btn_layout = BoxLayout(size_hint_y=None, height=UIStyles.get_btn_height(), spacing=dp(10))

        def do_eliminate(*args):
            confirm_popup.dismiss()
            deduction_success = self.cash_player.deduct_resources(self.COST_SECRET_SERVICE)
            if deduction_success:
                result = attempt_secret_service_action(
                    self.conn,
                    get_player_faction(self.conn),
                    target_noble_id=self.noble_data['id']
                )
                show_secret_service_result_popup(result)
                if callable(self.refresh_callback):
                    Clock.schedule_once(lambda dt: self.refresh_callback(), 0.5)
                if self.popup_ref:
                    self.popup_ref.dismiss()
            else:
                show_result_popup("Ошибка", "Ошибка списания средств.", False)

        btn_confirm = StyledButton(text="Да", color=UIStyles.COLOR_DANGER)
        btn_confirm.bind(on_release=do_eliminate)
        btn_cancel = StyledButton(text="Нет", color=(0.5, 0.5, 0.5, 1))
        btn_cancel.bind(on_release=lambda *args: confirm_popup.dismiss())

        btn_layout.add_widget(btn_confirm)
        btn_layout.add_widget(btn_cancel)

        confirm_content.add_widget(title)
        confirm_content.add_widget(cost)
        confirm_content.add_widget(Label())
        confirm_content.add_widget(btn_layout)
        confirm_popup.open()

def show_toast_notification(message, is_success=True, duration=0.5):
    """Всплывающее уведомление (Уменьшен тайминг)"""
    is_android = UIStyles.is_android()
    padding_main = dp(20) if not is_android else dp(15)
    font_message = sp(16) if not is_android else sp(14)

    color = UIStyles.COLOR_SUCCESS if is_success else UIStyles.COLOR_DANGER

    content = BoxLayout(
        orientation='vertical',
        padding=padding_main,
        size_hint_y=None,
        height=dp(70) if not is_android else dp(60)
    )

    with content.canvas.before:
        Color(*UIStyles.COLOR_CARD)
        content.rect = RoundedRectangle(pos=content.pos, size=content.size, radius=[UIStyles.RADIUS])

    def update_rect(instance, value):
        content.rect.pos = instance.pos
        content.rect.size = instance.size
    content.bind(pos=update_rect, size=update_rect)

    message_label = Label(
        text=f"[b]{message}[/b]",
        font_size=font_message,
        markup=True,
        halign='center',
        valign='middle',
        color=UIStyles.COLOR_TEXT
    )
    message_label.bind(size=message_label.setter('text_size'))
    content.add_widget(message_label)

    toast_popup = Popup(
        title="",
        content=content,
        size_hint=(0.7, None),
        height=dp(70) if not is_android else dp(60),
        pos_hint={'center_x': 0.5, 'center_y': 0.5},
        background_color=(0, 0, 0, 0),
        separator_height=0,
        auto_dismiss=False
    )

    def close_toast(dt):
        try:
            if toast_popup._is_open:
                toast_popup.dismiss()
        except:
            pass

    toast_popup.open()
    Clock.schedule_once(close_toast, duration)

def show_event_popup(conn, player_faction, season_index, refresh_callback, cash_player):
    """Показывает всплывающее окно для выбора и проведения мероприятия."""
    event_type = get_event_type_by_season(season_index)
    event_season = get_season_name_by_index(season_index)
    cost = calculate_event_cost(season_index)

    is_android = UIStyles.is_android()
    padding_main = dp(15) if not is_android else dp(10)
    spacing_main = dp(15) if not is_android else dp(10)
    font_title = sp(18) if not is_android else sp(16)
    font_info = sp(15) if not is_android else sp(13)
    btn_layout_height = UIStyles.get_btn_height()

    cash_player.load_resources()
    current_money = cash_player.resources.get("Кроны", 0)

    if current_money < cost:
        # Упрощенный popup ошибки без кнопок
        content_err = Label(
            text=f"Недостаточно Крон.\nСтоимость: {format_number(cost)}\nУ вас: {format_number(current_money)}",
            halign='center',
            valign='middle',
            text_size=(dp(250), None),
            font_size=sp(14) if not is_android else sp(12),
            color=UIStyles.COLOR_DANGER
        )
        insufficient_funds_popup = Popup(
            title="Недостаточно средств",
            content=content_err,
            size_hint=(0.85, 0.4) if not is_android else (0.95, 0.4),
            pos_hint={'center_x': 0.5, 'center_y': 0.5},
            background_color=(0, 0, 0, 0.8),
            separator_height=0,
            auto_dismiss=False
        )
        insufficient_funds_popup.open()
        Clock.schedule_once(lambda dt: insufficient_funds_popup.dismiss() if insufficient_funds_popup._is_open else None, 1.0)
        return

    content = BoxLayout(orientation='vertical', padding=padding_main, spacing=spacing_main)

    event_type_label = Label(
        text=f"[b]{event_type}[/b]",
        font_size=font_title,
        halign='center',
        valign='middle',
        size_hint_y=None,
        height=dp(30) if not is_android else dp(25),
        markup=True,
        color=(0.7, 0.9, 1, 1)
    )
    event_type_label.bind(size=event_type_label.setter('text_size'))

    info_box = BoxLayout(orientation='vertical', size_hint_y=None, height=dp(80) if not is_android else dp(70), spacing=dp(5))
    season_label = Label(
        text=f"Сезон: [b]{event_season}[/b]",
        font_size=font_info,
        halign='center',
        valign='middle',
        markup=True,
        color=(0.8, 0.8, 1, 1)
    )
    season_label.bind(size=season_label.setter('text_size'))
    guests_label = Label(
        text="Вся знать будет приглашена",
        font_size=font_info - sp(1),
        halign='center',
        valign='middle',
        color=(0.7, 0.9, 0.7, 1)
    )
    guests_label.bind(size=guests_label.setter('text_size'))
    cost_label = Label(
        text=f"Стоимость: [b]{format_number(cost)}[/b] крон",
        font_size=font_info,
        halign='center',
        valign='middle',
        markup=True,
        color=(1, 0.8, 0.6, 1)
    )
    cost_label.bind(size=cost_label.setter('text_size'))

    info_box.add_widget(season_label)
    info_box.add_widget(guests_label)
    info_box.add_widget(cost_label)

    btn_layout = BoxLayout(size_hint_y=None, height=btn_layout_height, spacing=dp(15) if not is_android else dp(10))
    confirm_btn = StyledButton(text="Провести", color=UIStyles.COLOR_SUCCESS)
    cancel_btn = StyledButton(text="Отмена", color=(0.5, 0.5, 0.5, 1))

    popup_size_hint = (0.85, 0.6) if not is_android else (0.95, 0.65)
    popup = Popup(
        title="Мероприятие",
        content=content,
        size_hint=popup_size_hint,
        pos_hint={'center_x': 0.5, 'center_y': 0.5},
        auto_dismiss=False,
        background_color=(0, 0, 0, 0.7),
        separator_height=0
    )

    def on_confirm(instance):
        popup.dismiss()
        success = cash_player.deduct_resources(cost)
        if success:
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM nobles WHERE status = 'active'")
                active_nobles = cursor.fetchall()
                for noble_row in active_nobles:
                    noble_id = noble_row[0]
                    update_noble_loyalty_for_event(conn, noble_id, player_faction, event_type, event_season)
                # Тост-уведомление (быстрое)
                show_toast_notification("Мероприятие проведено!", is_success=True, duration=0.4)
                if callable(refresh_callback):
                    Clock.schedule_once(lambda dt: refresh_callback(), 0.5)
            except Exception as e:
                print(f"Ошибка при проведении мероприятия: {e}")
                show_toast_notification("Ошибка проведения", is_success=False, duration=1.5)
        else:
            show_toast_notification("Недостаточно средств", is_success=False, duration=1.5)

    def on_cancel(instance):
        popup.dismiss()

    confirm_btn.bind(on_release=on_confirm)
    cancel_btn.bind(on_release=on_cancel)

    btn_layout.add_widget(confirm_btn)
    btn_layout.add_widget(cancel_btn)

    content.add_widget(event_type_label)
    content.add_widget(info_box)
    content.add_widget(btn_layout)
    popup.open()

def create_noble_widget_with_deal(noble_data, conn, cash_player, refresh_callback):
    """Создание виджета для отображения одного дворянина с кнопкой 'Договориться' (Табличный формат)"""
    is_android = UIStyles.is_android()
    widget_height = dp(50) if not is_android else dp(45)
    font_large = sp(16) if not is_android else sp(14)
    font_medium = sp(14) if not is_android else sp(12)
    font_small = sp(12) if not is_android else sp(10)
    padding_inner = dp(8) if not is_android else dp(5)
    spacing_inner = dp(5) if not is_android else dp(3)

    layout = GridLayout(cols=3, size_hint_y=None, height=widget_height, padding=padding_inner, spacing=spacing_inner)

    name_label = Label(
        text=noble_data['name'],
        font_size=font_large,
        halign='left',
        valign='middle',
        text_size=(None, None),
        shorten=True,
        shorten_from='right'
    )
    name_label.bind(size=name_label.setter('text_size'))

    attendance_history_raw = noble_data.get('attendance_history', '')
    attention_text = "?"
    attention_color = (1, 1, 1, 1)

    if isinstance(attendance_history_raw, str) and attendance_history_raw:
        try:
            history_list = [int(x) for x in attendance_history_raw.split(',') if x.isdigit()]
        except ValueError:
            history_list = []
    elif isinstance(attendance_history_raw, list):
        history_list = [x for x in attendance_history_raw if isinstance(x, int)]
    else:
        history_list = []

    if history_list:
        total_events = len(history_list)
        attended_events = sum(history_list)
        if total_events > 0:
            attendance_percentage = int((attended_events / total_events) * 100)
            attention_text = f"{attendance_percentage}%"
            if attendance_percentage < 30:
                attention_color = (1, 0, 0, 1)
            elif attendance_percentage < 60:
                attention_color = (1, 1, 0, 1)
            else:
                attention_color = (0, 1, 0, 1)

    attention_label = Label(
        text=attention_text,
        font_size=font_medium,
        halign='center',
        valign='middle',
        color=attention_color,
        text_size=(None, None)
    )
    attention_label.bind(size=attention_label.setter('text_size'))

    try:
        import json
        ideology_data = json.loads(noble_data['ideology']) if isinstance(noble_data['ideology'], str) else noble_data['ideology']
        if isinstance(ideology_data, dict) and ideology_data.get('type') == 'greed':
            deal_btn = Button(
                text="Договориться",
                font_size=font_small,
                size_hint_y=None,
                height=dp(30) if not is_android else dp(25),
                background_color=(0.3, 0.7, 0.3, 1)
            )
            def on_deal(instance):
                show_deal_popup(conn, noble_data, cash_player)
                Clock.schedule_once(lambda dt: refresh_callback(), 0.1)
            deal_btn.bind(on_release=on_deal)
        else:
            deal_btn = Label(
                text="-",
                font_size=font_small,
                halign='center',
                valign='middle',
                color=(0.7, 0.7, 0.7, 1)
            )
            deal_btn.bind(size=deal_btn.setter('text_size'))
    except (json.JSONDecodeError, TypeError):
        deal_btn = Label(
            text="-",
            font_size=font_small,
            halign='center',
            valign='middle',
            color=(0.7, 0.7, 0.7, 1)
        )
        deal_btn.bind(size=deal_btn.setter('text_size'))

    layout.add_widget(name_label)
    layout.add_widget(attention_label)
    layout.add_widget(deal_btn)
    return layout