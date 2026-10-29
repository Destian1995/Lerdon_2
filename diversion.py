from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.popup import Popup
from kivy.metrics import dp, sp
from kivy.core.window import Window
from kivy.uix.scrollview import ScrollView
from kivy.uix.widget import Widget
from kivy.uix.gridlayout import GridLayout
from kivy.uix.slider import Slider
from kivy.graphics import Color, RoundedRectangle
from kivy.utils import get_color_from_hex, platform
import random
import sqlite3

_is_mobile = platform in ('android', 'ios')

# --- Цветовая палитра ---
BACKGROUND_COLOR = get_color_from_hex("#121212")
CARD_COLOR = get_color_from_hex("#1e1e1e")
TEXT_COLOR = get_color_from_hex("#ffffff")
ACCENT_COLOR = get_color_from_hex("#bb86fc")
SECONDARY_COLOR = get_color_from_hex("#03dac6")
WARNING_COLOR = get_color_from_hex("#cf6679")
DISABLED_COLOR = get_color_from_hex("#444444")
SELECTED_OUTLINE = get_color_from_hex("#bb86fc")

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
            print(f"[DEBUG] Загружены ресурсы для фракции '{self.faction}': {resources}")
            return resources
        except Exception as e:
            print(f"Ошибка при загрузке ресурсов: {e}")
            return {"Кроны": 0, "Рабочие": 0}

    def deduct_resources(self, crowns, workers=0):
        try:
            current_crowns = self.class_faction.get_resource_now("Кроны")
            current_workers = self.class_faction.get_resource_now("Рабочие")
            print(f"[DEBUG] Текущие ресурсы: Кроны={current_crowns}, Рабочие={current_workers}")

            if current_crowns < crowns or current_workers < workers:
                print("[DEBUG] Недостаточно ресурсов для списания.")
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

class ThemedButton(Button):
    def __init__(self, **kwargs):
        btn_color = kwargs.pop('background_color', CARD_COLOR)
        super().__init__(**kwargs)
        self.background_color = (0, 0, 0, 0)
        with self.canvas.before:
            self._btn_color_instr = Color(*btn_color)
            self.rect = RoundedRectangle(size=self.size, pos=self.pos, radius=[dp(12)])
        self.bind(pos=self.update_graphics, size=self.update_graphics)

    def update_graphics(self, *args):
        self.rect.pos = self.pos
        self.rect.size = self.size

class ThemedPopup(Popup):
    def __init__(self, **kwargs):
        kwargs.setdefault('background_color', (0.07, 0.08, 0.13, 1))
        kwargs.setdefault('separator_color', (0.55, 0.22, 0.80, 0.75))
        kwargs.setdefault('title_color', (0.82, 0.60, 1.0, 1))
        kwargs.setdefault('title_size', sp(16))
        kwargs.setdefault('title_align', 'center')
        super().__init__(**kwargs)

def show_diversion_window(conn, faction, class_faction):
    cash_player = CalculateCash(faction, class_faction)
    player_faction = faction

    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT faction FROM cities WHERE faction != ? AND faction NOT IN ('Мятежники', 'Нежить', 'Нейтрал')", (player_faction,))
    target_factions = [row[0] for row in cursor.fetchall() if row[0]]

    if not target_factions:
        no_targets_popup = ThemedPopup(
            title="Нет целей",
            content=Label(text="Нет других фракций для операций.", halign='center', valign='middle',
                          color=TEXT_COLOR, text_size=(dp(250), None)),
            size_hint=(0.8, 0.35) if not _is_mobile else (0.9, 0.3)
        )
        no_targets_popup.open()
        return

    targets_info = {}
    for tf in target_factions:
        cursor.execute("""
            SELECT DISTINCT c.name FROM cities c
            JOIN garrisons g ON c.name = g.city_name
            JOIN units u ON g.unit_name = u.unit_name
            WHERE c.faction = ? AND u.faction = ?
        """, (tf, tf))
        cities_with = [r[0] for r in cursor.fetchall()]
        cursor.execute("""
            SELECT name FROM cities WHERE faction = ? AND name NOT IN (
                SELECT DISTINCT city_name FROM garrisons
                JOIN units u ON garrisons.unit_name = u.unit_name WHERE u.faction = ?
            )
        """, (tf, tf))
        cities_without = [r[0] for r in cursor.fetchall()]
        cursor.execute("""
            SELECT u.unit_name FROM units u
            JOIN garrisons g ON u.unit_name = g.unit_name
            WHERE u.faction = ? AND (u.attack > 0 OR u.defense > 0)
        """, (tf,))
        heroes = [r[0] for r in cursor.fetchall()]
        targets_info[tf] = {
            'cities_with_garrison': cities_with,
            'cities_without_garrison': cities_without,
            'heroes': heroes
        }

    # Основной контейнер
    content = BoxLayout(orientation='vertical', padding=[dp(12), dp(10)], spacing=dp(8))
    with content.canvas.before:
        Color(0.06, 0.07, 0.11, 1)
        content._bg = RoundedRectangle(pos=content.pos, size=content.size, radius=[dp(12)])
    content.bind(pos=lambda i, v: setattr(i._bg, 'pos', v),
                 size=lambda i, v: setattr(i._bg, 'size', v))

    # Заголовок
    header = Label(
        text="[b]Тайная Служба[/b]", markup=True,
        font_size=sp(18) if not _is_mobile else sp(16),
        color=(0.85, 0.25, 0.25, 1),
        size_hint_y=None, height=dp(34), halign='center'
    )
    header.bind(size=lambda i, s: setattr(i, 'text_size', (s[0], None)))
    content.add_widget(header)

    sub = Label(
        text="[color=#AAAAAA]Выберите цель для операции[/color]", markup=True,
        font_size=sp(12) if not _is_mobile else sp(10),
        size_hint_y=None, height=dp(20), halign='center',
        color=(0.7, 0.7, 0.7, 1)
    )
    sub.bind(size=lambda i, s: setattr(i, 'text_size', (s[0], None)))
    content.add_widget(sub)

    # Список фракций — каждая как карточка
    scroll = ScrollView(do_scroll_x=False, size_hint_y=1)
    factions_list = BoxLayout(orientation='vertical', size_hint_y=None, spacing=dp(6))
    factions_list.bind(minimum_height=factions_list.setter('height'))

    _FACTION_COLORS = {
        'Адепты': (0.45, 0.40, 0.10, 1), 'Вампиры': (0.30, 0.12, 0.35, 1),
        'Эльфы': (0.12, 0.35, 0.15, 1), 'Север': (0.15, 0.28, 0.50, 1),
        'Элины': (0.50, 0.30, 0.08, 1),
    }

    for tf in target_factions:
        card = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(52),
                         padding=[dp(10), dp(6)], spacing=dp(8))
        _clr = _FACTION_COLORS.get(tf, (0.18, 0.18, 0.25, 1))
        with card.canvas.before:
            Color(*_clr)
            card._bg = RoundedRectangle(pos=card.pos, size=card.size, radius=[dp(8)])
        card.bind(pos=lambda i, v: setattr(i._bg, 'pos', v),
                  size=lambda i, v: setattr(i._bg, 'size', v))

        # Инфо
        info = BoxLayout(orientation='vertical', size_hint_x=0.6, spacing=dp(2))
        name_lbl = Label(
            text=f"[b]{tf}[/b]", markup=True,
            font_size=sp(14) if not _is_mobile else sp(12),
            color=(0.95, 0.92, 0.85, 1), halign='left', valign='middle'
        )
        name_lbl.bind(size=name_lbl.setter('text_size'))
        ti = targets_info[tf]
        detail = f"[color=#AAAAAA]Городов: {len(ti['cities_with_garrison']) + len(ti['cities_without_garrison'])}  |  Героев: {len(ti['heroes'])}[/color]"
        detail_lbl = Label(
            text=detail, markup=True,
            font_size=sp(10) if not _is_mobile else sp(9),
            color=(0.6, 0.6, 0.6, 1), halign='left', valign='middle'
        )
        detail_lbl.bind(size=detail_lbl.setter('text_size'))
        info.add_widget(name_lbl)
        info.add_widget(detail_lbl)

        # Кнопка
        btn = Button(
            text="Операции", size_hint_x=0.4,
            font_size=sp(12) if not _is_mobile else sp(10),
            bold=True, background_normal='', background_color=(0, 0, 0, 0),
            color=(1, 1, 1, 1)
        )
        with btn.canvas.before:
            Color(0.55, 0.15, 0.15, 0.9)
            btn._rr = RoundedRectangle(pos=btn.pos, size=btn.size, radius=[dp(6)])
        btn.bind(pos=lambda i, v: setattr(i._rr, 'pos', v),
                 size=lambda i, v: setattr(i._rr, 'size', v))

        def _make_handler(_tf):
            def _h(inst):
                popup.dismiss()
                show_operations_window(conn, player_faction, cash_player, _tf, targets_info)
            return _h
        btn.bind(on_release=_make_handler(tf))

        card.add_widget(info)
        card.add_widget(btn)
        factions_list.add_widget(card)

    scroll.add_widget(factions_list)
    content.add_widget(scroll)

    # Кнопка закрыть
    close_btn = Button(
        text="Закрыть", size_hint_y=None, height=dp(38),
        font_size=sp(13) if not _is_mobile else sp(11),
        bold=True, background_normal='', background_color=(0, 0, 0, 0),
        color=(0.9, 0.9, 0.9, 1)
    )
    with close_btn.canvas.before:
        Color(0.15, 0.15, 0.22, 0.95)
        close_btn._rr = RoundedRectangle(pos=close_btn.pos, size=close_btn.size, radius=[dp(8)])
    close_btn.bind(pos=lambda i, v: setattr(i._rr, 'pos', v),
                   size=lambda i, v: setattr(i._rr, 'size', v))
    content.add_widget(close_btn)

    popup = Popup(
        title="", content=content,
        size_hint=(0.8 if not _is_mobile else 0.95, 0.75 if not _is_mobile else 0.85),
        pos_hint={'center_x': 0.5, 'center_y': 0.5},
        background_color=(0.04, 0.05, 0.09, 0.98),
        separator_height=0
    )
    close_btn.bind(on_release=lambda *a: popup.dismiss())
    popup.open()

def show_operations_window(conn, player_faction, cash_player, target_faction, targets_info):
    content = BoxLayout(orientation='vertical', padding=[dp(12), dp(10)], spacing=dp(8))
    with content.canvas.before:
        Color(0.06, 0.07, 0.11, 1)
        content._bg = RoundedRectangle(pos=content.pos, size=content.size, radius=[dp(12)])
    content.bind(pos=lambda i, v: setattr(i._bg, 'pos', v),
                 size=lambda i, v: setattr(i._bg, 'size', v))

    # Заголовок
    header = Label(
        text=f"[b]Операции против {target_faction}[/b]", markup=True,
        font_size=sp(17) if not _is_mobile else sp(15),
        color=(0.85, 0.25, 0.25, 1),
        size_hint_y=None, height=dp(34), halign='center'
    )
    header.bind(size=lambda i, s: setattr(i, 'text_size', (s[0], None)))
    content.add_widget(header)

    ops_descriptions = {
        'Саботаж': {
            'desc': 'Снижение войск в городе на 30-75%',
            'detail': '50% шанс успеха',
            'cost': 1_000_000
        },
        'Мятеж': {
            'desc': 'Захват города без гарнизона',
            'detail': 'От 700K до 6.5M крон',
            'cost': 700_000
        },
        'Заказ': {
            'desc': 'Убийство вражеского героя',
            'detail': '50% шанс успеха',
            'cost': 1_000_000
        }
    }

    # Карточки операций
    scroll = ScrollView(do_scroll_x=False, size_hint_y=1)
    ops_list = BoxLayout(orientation='vertical', size_hint_y=None, spacing=dp(6))
    ops_list.bind(minimum_height=ops_list.setter('height'))

    _OP_COLORS = {
        'Саботаж': (0.25, 0.18, 0.10, 1),
        'Мятеж': (0.30, 0.12, 0.12, 1),
        'Заказ': (0.18, 0.12, 0.30, 1),
    }

    for op_name, op_info in ops_descriptions.items():
        card = BoxLayout(orientation='vertical', size_hint_y=None, height=dp(75),
                         padding=[dp(10), dp(6)], spacing=dp(3))
        _clr = _OP_COLORS.get(op_name, (0.18, 0.18, 0.25, 1))
        with card.canvas.before:
            Color(*_clr)
            card._bg = RoundedRectangle(pos=card.pos, size=card.size, radius=[dp(8)])
        card.bind(pos=lambda i, v: setattr(i._bg, 'pos', v),
                  size=lambda i, v: setattr(i._bg, 'size', v))

        # Верх: название + стоимость
        top_row = BoxLayout(size_hint_y=None, height=dp(22))
        op_title = Label(
            text=f"[b]{op_name}[/b]", markup=True,
            font_size=sp(14) if not _is_mobile else sp(12),
            color=(0.95, 0.90, 0.80, 1), halign='left', valign='middle'
        )
        op_title.bind(size=op_title.setter('text_size'))
        op_cost = Label(
            text=f"[color=#FFD700]{format_number(op_info['cost'])} крон[/color]", markup=True,
            font_size=sp(12) if not _is_mobile else sp(10),
            halign='right', valign='middle',
            color=(0.9, 0.8, 0.4, 1)
        )
        op_cost.bind(size=op_cost.setter('text_size'))
        top_row.add_widget(op_title)
        top_row.add_widget(op_cost)

        # Описание
        desc_lbl = Label(
            text=f"[color=#AAAAAA]{op_info['desc']}[/color]  |  [color=#88AACC]{op_info['detail']}[/color]",
            markup=True, font_size=sp(10) if not _is_mobile else sp(9),
            halign='left', valign='middle', size_hint_y=None, height=dp(18),
            color=(0.7, 0.7, 0.7, 1)
        )
        desc_lbl.bind(size=desc_lbl.setter('text_size'))

        card.add_widget(top_row)
        card.add_widget(desc_lbl)

        # Делаем карточку кликабельной
        def _make_op_handler(_op_name, _op_info):
            def _h(instance, touch):
                if not instance.collide_point(*touch.pos):
                    return False
                if _op_name == 'Мятеж':
                    # Проверяем — мятежники уже на карте?
                    try:
                        _mc = conn.cursor()
                        _mc.execute("SELECT COUNT(*) FROM cities WHERE faction = 'Мятежники'")
                        if _mc.fetchone()[0] > 0:
                            from kivy.uix.popup import Popup as _MPopup
                            _me = BoxLayout(orientation='vertical', padding=[dp(14), dp(10)])
                            with _me.canvas.before:
                                Color(0.06, 0.07, 0.11, 1)
                                _me._bg = RoundedRectangle(pos=_me.pos, size=_me.size, radius=[dp(12)])
                            _me.bind(pos=lambda i, v: setattr(i._bg, 'pos', v),
                                     size=lambda i, v: setattr(i._bg, 'size', v))
                            _me.add_widget(Label(
                                text="[b]Мятеж невозможен[/b]\n\n[color=#AAAAAA]Мятежники уже присутствуют на карте.\n"
                                     "Используйте чат с ними для управления.[/color]",
                                markup=True, font_size=sp(13), halign='center', valign='middle',
                                color=(0.9, 0.5, 0.2, 1)))
                            _mp = _MPopup(title="", content=_me,
                                          size_hint=(0.65 if not _is_mobile else 0.85, 0.3),
                                          background_color=(0.04, 0.05, 0.09, 0.98), separator_height=0)
                            _mp.open()
                            from kivy.clock import Clock as _MC
                            _MC.schedule_once(lambda dt: _mp.dismiss() if _mp._is_open else None, 2.5)
                            return True
                    except Exception:
                        pass
                    show_rebellion_cost_selection(conn, player_faction, cash_player, _op_name, _op_info, target_faction, targets_info)
                else:
                    show_confirmation_popup(conn, player_faction, cash_player, _op_name, _op_info, target_faction, targets_info)
                return True
            return _h
        card.bind(on_touch_down=_make_op_handler(op_name, op_info))
        ops_list.add_widget(card)

    scroll.add_widget(ops_list)
    content.add_widget(scroll)

    # Кнопка назад
    back_btn = Button(
        text="Назад", size_hint_y=None, height=dp(38),
        font_size=sp(13) if not _is_mobile else sp(11),
        bold=True, background_normal='', background_color=(0, 0, 0, 0),
        color=(0.9, 0.9, 0.9, 1)
    )
    with back_btn.canvas.before:
        Color(0.15, 0.15, 0.22, 0.95)
        back_btn._rr = RoundedRectangle(pos=back_btn.pos, size=back_btn.size, radius=[dp(8)])
    back_btn.bind(pos=lambda i, v: setattr(i._rr, 'pos', v),
                  size=lambda i, v: setattr(i._rr, 'size', v))
    content.add_widget(back_btn)

    popup = Popup(
        title="", content=content,
        size_hint=(0.8 if not _is_mobile else 0.95, 0.65 if not _is_mobile else 0.75),
        pos_hint={'center_x': 0.5, 'center_y': 0.5},
        background_color=(0.04, 0.05, 0.09, 0.98),
        separator_height=0
    )
    back_btn.bind(on_release=lambda *a: popup.dismiss())
    popup.open()

# --- Остальные функции остаются без изменений ---
# (show_rebellion_cost_selection, show_confirmation_popup, execute_diversion_operation, show_result_popup)
# Просто убедитесь, что в них используются те же уменьшенные значения для высот и шрифтов, где это возможно и логично.

def show_rebellion_cost_selection(conn, player_faction, cash_player, op_name, op_info, target_faction, targets_info):
    """Окно мятежа — выбор типа цели, суммы, количества мятежников."""

    # Определяем доступные города
    cities_empty = targets_info[target_faction].get('cities_without_garrison', [])
    # Города с гарнизоном но без героев 2-4 класса
    cities_with_garrison_no_heroes = []
    try:
        cursor = conn.cursor()
        for city in targets_info[target_faction].get('cities_with_garrison', []):
            cursor.execute("""
                SELECT COUNT(*) FROM garrisons g
                JOIN units u ON g.unit_name = u.unit_name
                WHERE g.city_name = ? AND u.unit_class >= 2 AND g.unit_count > 0
            """, (city,))
            hero_count = cursor.fetchone()[0]
            if hero_count == 0:
                cities_with_garrison_no_heroes.append(city)
    except Exception:
        pass

    has_empty = len(cities_empty) > 0
    has_garrison = len(cities_with_garrison_no_heroes) > 0

    if not has_empty and not has_garrison:
        _ne = BoxLayout(orientation='vertical', padding=[dp(14), dp(10)])
        with _ne.canvas.before:
            Color(0.06, 0.07, 0.11, 1)
            _ne._bg = RoundedRectangle(pos=_ne.pos, size=_ne.size, radius=[dp(12)])
        _ne.bind(pos=lambda i, v: setattr(i._bg, 'pos', v), size=lambda i, v: setattr(i._bg, 'size', v))
        _ne.add_widget(Label(text="[b]Восстание невозможно[/b]\n\n[color=#AAAAAA]Все города защищены героями[/color]",
                             markup=True, font_size=sp(14), halign='center', valign='middle',
                             color=(0.9, 0.3, 0.3, 1)))
        _np = Popup(title="", content=_ne,
                    size_hint=(0.65 if not _is_mobile else 0.85, 0.3),
                    background_color=(0.04, 0.05, 0.09, 0.98), separator_height=0)
        _np.open()
        from kivy.clock import Clock as _C
        _C.schedule_once(lambda dt: _np.dismiss() if _np._is_open else None, 2.0)
        return

    # Состояние
    _state = {'target_type': 'empty', 'cost_mult': 1.0}  # empty или garrison

    content = BoxLayout(orientation='vertical', padding=[dp(14), dp(10)], spacing=dp(8))
    with content.canvas.before:
        Color(0.06, 0.07, 0.11, 1)
        content._bg = RoundedRectangle(pos=content.pos, size=content.size, radius=[dp(12)])
    content.bind(pos=lambda i, v: setattr(i._bg, 'pos', v),
                 size=lambda i, v: setattr(i._bg, 'size', v))

    # Заголовок
    title_lbl = Label(
        text="[b]Мятеж[/b]", markup=True,
        font_size=sp(18) if not _is_mobile else sp(16),
        color=(0.85, 0.25, 0.25, 1),
        size_hint_y=None, height=dp(32), halign='center'
    )
    title_lbl.bind(size=lambda i, s: setattr(i, 'text_size', (s[0], None)))
    content.add_widget(title_lbl)

    # Выбор типа цели
    type_row = BoxLayout(size_hint_y=None, height=dp(36), spacing=dp(8))

    btn_empty = Button(
        text=f"Без гарнизона ({len(cities_empty)})", bold=True,
        font_size=sp(11) if not _is_mobile else sp(10),
        background_normal='', background_color=(0, 0, 0, 0), color=(1, 1, 1, 1),
        disabled=not has_empty
    )
    with btn_empty.canvas.before:
        Color(0.15, 0.45, 0.2, 0.95)
        btn_empty._rr = RoundedRectangle(pos=btn_empty.pos, size=btn_empty.size, radius=[dp(6)])
    btn_empty.bind(pos=lambda i, v: setattr(i._rr, 'pos', v),
                   size=lambda i, v: setattr(i._rr, 'size', v))

    btn_garrison = Button(
        text=f"С гарнизоном ({len(cities_with_garrison_no_heroes)})", bold=True,
        font_size=sp(11) if not _is_mobile else sp(10),
        background_normal='', background_color=(0, 0, 0, 0), color=(1, 1, 1, 1),
        disabled=not has_garrison
    )
    with btn_garrison.canvas.before:
        Color(0.45, 0.2, 0.15, 0.95)
        btn_garrison._rr = RoundedRectangle(pos=btn_garrison.pos, size=btn_garrison.size, radius=[dp(6)])
    btn_garrison.bind(pos=lambda i, v: setattr(i._rr, 'pos', v),
                      size=lambda i, v: setattr(i._rr, 'size', v))

    def _select_empty(*a):
        _state['target_type'] = 'empty'
        _state['cost_mult'] = 1.0
        btn_empty._rr.size = btn_empty.size  # refresh
        cost_hint.text = "[color=#AAAAAA]Цель: город без гарнизона[/color]"
        _update_display()

    def _select_garrison(*a):
        _state['target_type'] = 'garrison'
        _state['cost_mult'] = 1.25
        cost_hint.text = "[color=#FF8844]Цель: город с гарнизоном (+25% стоимость)[/color]"
        _update_display()

    btn_empty.bind(on_release=_select_empty)
    btn_garrison.bind(on_release=_select_garrison)
    type_row.add_widget(btn_empty)
    type_row.add_widget(btn_garrison)
    content.add_widget(type_row)

    # Подсказка
    cost_hint = Label(
        text="[color=#AAAAAA]Цель: город без гарнизона[/color]", markup=True,
        font_size=sp(10) if not _is_mobile else sp(9),
        size_hint_y=None, height=dp(18), halign='center',
        color=(0.7, 0.7, 0.7, 1)
    )
    cost_hint.bind(size=lambda i, s: setattr(i, 'text_size', (s[0], None)))
    content.add_widget(cost_hint)

    # Слайдер
    cash_player.load_resources()
    current_money = cash_player.resources.get("Кроны", 0)
    max_affordable = min(6_500_000, current_money)

    slider = Slider(min=700_000, max=max(700_000, max_affordable), value=700_000, step=10000,
                    size_hint_y=None, height=dp(35))
    content.add_widget(slider)

    def calculate_rebels(cost):
        base_cost = 700_000
        extra_money = max(0, cost - base_cost)
        extra_percentage = (extra_money // 100_000) * 0.37
        return int(2750 * (1.0 + extra_percentage))

    info_lbl = Label(
        text="", markup=True,
        font_size=sp(12) if not _is_mobile else sp(10),
        size_hint_y=None, height=dp(40), halign='center',
        color=(0.9, 0.9, 0.9, 1)
    )
    info_lbl.bind(size=lambda i, s: setattr(i, 'text_size', (s[0], None)))
    content.add_widget(info_lbl)

    def _update_display(*a):
        base = int(slider.value)
        final_cost = int(base * _state['cost_mult'])
        rebels = calculate_rebels(base)
        info_lbl.text = (
            f"[color=#FFD700]Стоимость: {format_number(final_cost)} крон[/color]\n"
            f"[color=#AAAAAA]Мятежников: [b]{format_number(rebels)}[/b][/color]"
        )

    slider.bind(value=lambda *a: _update_display())
    _update_display()

    content.add_widget(Widget(size_hint_y=1))

    # Кнопки
    btn_layout = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(10))

    confirm_btn = Button(
        text="Поднять мятеж", bold=True,
        font_size=sp(13) if not _is_mobile else sp(11),
        background_normal='', background_color=(0, 0, 0, 0), color=(1, 1, 1, 1)
    )
    with confirm_btn.canvas.before:
        Color(0.55, 0.15, 0.15, 0.95)
        confirm_btn._rr = RoundedRectangle(pos=confirm_btn.pos, size=confirm_btn.size, radius=[dp(8)])
    confirm_btn.bind(pos=lambda i, v: setattr(i._rr, 'pos', v),
                     size=lambda i, v: setattr(i._rr, 'size', v))

    cancel_btn = Button(
        text="Отмена", bold=True,
        font_size=sp(13) if not _is_mobile else sp(11),
        background_normal='', background_color=(0, 0, 0, 0), color=(0.9, 0.9, 0.9, 1)
    )
    with cancel_btn.canvas.before:
        Color(0.15, 0.15, 0.22, 0.95)
        cancel_btn._rr = RoundedRectangle(pos=cancel_btn.pos, size=cancel_btn.size, radius=[dp(8)])
    cancel_btn.bind(pos=lambda i, v: setattr(i._rr, 'pos', v),
                    size=lambda i, v: setattr(i._rr, 'size', v))

    popup = Popup(
        title="", content=content,
        size_hint=(0.75 if not _is_mobile else 0.95, 0.6 if not _is_mobile else 0.55),
        pos_hint={'center_x': 0.5, 'center_y': 0.5},
        auto_dismiss=False,
        background_color=(0.04, 0.05, 0.09, 0.98), separator_height=0
    )

    def on_confirm(instance):
        selected_cost = int(slider.value * _state['cost_mult'])
        rebels_count = calculate_rebels(int(slider.value))
        popup.dismiss()
        # Передаём тип цели через op_info
        _op_info = dict(op_info)
        _op_info['_target_type'] = _state['target_type']
        _op_info['_garrison_cities'] = cities_with_garrison_no_heroes
        show_confirmation_popup(conn, player_faction, cash_player, op_name, _op_info, target_faction,
                                targets_info, custom_cost=selected_cost, rebels_count=rebels_count)

    confirm_btn.bind(on_release=on_confirm)
    cancel_btn.bind(on_release=lambda *a: popup.dismiss())

    btn_layout.add_widget(confirm_btn)
    btn_layout.add_widget(cancel_btn)
    content.add_widget(btn_layout)

    popup.open()

def show_confirmation_popup(conn, player_faction, cash_player, op_name, op_info, target_faction, targets_info, custom_cost=None, rebels_count=None):
    cost = custom_cost if custom_cost else op_info['cost']

    cash_player.load_resources()
    current_money = cash_player.resources.get("Кроны", 0)
    if current_money < cost:
        _err = BoxLayout(orientation='vertical', padding=[dp(14), dp(10)], spacing=dp(8))
        with _err.canvas.before:
            Color(0.06, 0.07, 0.11, 1)
            _err._bg = RoundedRectangle(pos=_err.pos, size=_err.size, radius=[dp(12)])
        _err.bind(pos=lambda i, v: setattr(i._bg, 'pos', v), size=lambda i, v: setattr(i._bg, 'size', v))
        _err.add_widget(Label(
            text=f"[b]Недостаточно средств[/b]\n\n"
                 f"[color=#AAAAAA]Нужно:[/color] [b]{format_number(cost)}[/b] крон\n"
                 f"[color=#AAAAAA]Есть:[/color] [b]{format_number(int(current_money))}[/b] крон\n"
                 f"[color=#FF6644]Не хватает: {format_number(cost - int(current_money))}[/color]",
            markup=True, font_size=sp(13) if not _is_mobile else sp(11),
            halign='center', valign='middle', color=(0.9, 0.9, 0.9, 1)
        ))
        _ep = Popup(title="", content=_err,
                    size_hint=(0.65 if not _is_mobile else 0.85, 0.35),
                    background_color=(0.04, 0.05, 0.09, 0.98), separator_height=0)
        _ep.open()
        from kivy.clock import Clock
        Clock.schedule_once(lambda dt: _ep.dismiss() if _ep._is_open else None, 2.0)
        return

    if op_name == 'Мятеж':
        cities_without = targets_info[target_faction].get('cities_without_garrison', [])
        cities_with = targets_info[target_faction].get('cities_with_garrison', [])
        if not cities_without and not cities_with:
            _ne = BoxLayout(orientation='vertical', padding=[dp(14), dp(10)])
            with _ne.canvas.before:
                Color(0.06, 0.07, 0.11, 1)
                _ne._bg = RoundedRectangle(pos=_ne.pos, size=_ne.size, radius=[dp(12)])
            _ne.bind(pos=lambda i, v: setattr(i._bg, 'pos', v), size=lambda i, v: setattr(i._bg, 'size', v))
            _ne.add_widget(Label(text="[b]Нет доступных городов для мятежа[/b]", markup=True,
                                 font_size=sp(14), halign='center', valign='middle',
                                 color=(0.9, 0.3, 0.3, 1)))
            _np = Popup(title="", content=_ne,
                        size_hint=(0.6 if not _is_mobile else 0.8, 0.25),
                        background_color=(0.04, 0.05, 0.09, 0.98), separator_height=0)
            _np.open()
            from kivy.clock import Clock
            Clock.schedule_once(lambda dt: _np.dismiss() if _np._is_open else None, 1.5)
            return

    # Основной контейнер подтверждения
    content = BoxLayout(orientation='vertical', padding=[dp(16), dp(12)], spacing=dp(10))
    with content.canvas.before:
        Color(0.06, 0.07, 0.11, 1)
        content._bg = RoundedRectangle(pos=content.pos, size=content.size, radius=[dp(12)])
    content.bind(pos=lambda i, v: setattr(i._bg, 'pos', v),
                 size=lambda i, v: setattr(i._bg, 'size', v))

    # Название операции
    title_lbl = Label(
        text=f"[b]{op_name}[/b]", markup=True,
        font_size=sp(20) if not _is_mobile else sp(17),
        color=(0.85, 0.25, 0.25, 1),
        size_hint_y=None, height=dp(36), halign='center'
    )
    title_lbl.bind(size=lambda i, s: setattr(i, 'text_size', (s[0], None)))
    content.add_widget(title_lbl)

    # Детали
    detail_text = f"[color=#AAAAAA]Цель:[/color]  [b]{target_faction}[/b]\n"
    detail_text += f"[color=#AAAAAA]Стоимость:[/color]  [color=#FFD700][b]{format_number(cost)} крон[/b][/color]"
    if rebels_count:
        detail_text += f"\n[color=#AAAAAA]Мятежников:[/color]  [b]{rebels_count}[/b]"

    detail_lbl = Label(
        text=detail_text, markup=True,
        font_size=sp(14) if not _is_mobile else sp(12),
        halign='center', valign='middle',
        size_hint_y=None, height=dp(55) if not rebels_count else dp(72),
        color=(0.9, 0.9, 0.9, 1)
    )
    detail_lbl.bind(size=lambda i, s: setattr(i, 'text_size', (s[0], None)))
    content.add_widget(detail_lbl)

    content.add_widget(Widget(size_hint_y=1))

    # Кнопки
    btn_layout = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(10))

    confirm_btn = Button(
        text="Выполнить", bold=True,
        font_size=sp(14) if not _is_mobile else sp(12),
        background_normal='', background_color=(0, 0, 0, 0), color=(1, 1, 1, 1)
    )
    with confirm_btn.canvas.before:
        Color(0.15, 0.45, 0.2, 0.95)
        confirm_btn._rr = RoundedRectangle(pos=confirm_btn.pos, size=confirm_btn.size, radius=[dp(8)])
    confirm_btn.bind(pos=lambda i, v: setattr(i._rr, 'pos', v),
                     size=lambda i, v: setattr(i._rr, 'size', v))

    cancel_btn = Button(
        text="Отмена", bold=True,
        font_size=sp(14) if not _is_mobile else sp(12),
        background_normal='', background_color=(0, 0, 0, 0), color=(0.9, 0.9, 0.9, 1)
    )
    with cancel_btn.canvas.before:
        Color(0.35, 0.15, 0.15, 0.95)
        cancel_btn._rr = RoundedRectangle(pos=cancel_btn.pos, size=cancel_btn.size, radius=[dp(8)])
    cancel_btn.bind(pos=lambda i, v: setattr(i._rr, 'pos', v),
                    size=lambda i, v: setattr(i._rr, 'size', v))

    popup = Popup(
        title="", content=content,
        size_hint=(0.65 if not _is_mobile else 0.85, 0.45 if not _is_mobile else 0.42),
        pos_hint={'center_x': 0.5, 'center_y': 0.5},
        auto_dismiss=False,
        background_color=(0.04, 0.05, 0.09, 0.98),
        separator_height=0
    )

    def on_confirm(instance):
        popup.dismiss()
        deduction_success = cash_player.deduct_resources(cost)
        if not deduction_success:
            show_result_popup("Ошибка", "Ошибка списания средств.", False)
            return
        execute_diversion_operation(conn, player_faction, op_name, op_info, target_faction, targets_info, custom_cost=custom_cost, rebels_count=rebels_count)

    confirm_btn.bind(on_release=on_confirm)
    cancel_btn.bind(on_release=lambda *a: popup.dismiss())

    btn_layout.add_widget(confirm_btn)
    btn_layout.add_widget(cancel_btn)
    content.add_widget(btn_layout)

    popup.open()

def execute_diversion_operation(conn, player_faction, op_name, op_info, target_faction, targets_info, custom_cost=None, rebels_count=None):
    cursor = conn.cursor()
    success = False
    message = ""
    target_city = None

    if op_name == 'Саботаж':
        # Найти любой город, в котором есть юниты фракции цели (включая героев)
        cursor.execute("""
            SELECT DISTINCT g.city_name
            FROM garrisons g
            JOIN units u ON g.unit_name = u.unit_name
            WHERE u.faction = ?
        """, (target_faction,))
        cities_with_units = [row[0] for row in cursor.fetchall()]

        if not cities_with_units:
            show_result_popup("Ошибка", "Нет городов с войсками для саботажа.", False)
            return

        target_city = random.choice(cities_with_units)

        # Получаем все юниты в этом городе
        cursor.execute("""
            SELECT g.unit_name, g.unit_count FROM garrisons g
            JOIN units u ON g.unit_name = u.unit_name
            WHERE g.city_name = ? AND u.faction = ?
        """, (target_city, target_faction))

        all_units = cursor.fetchall()
        if not all_units:
            show_result_popup("Ошибка", f"В городе {target_city} нет юнитов для саботажа.", False)
            return

        if random.random() < 0.5:
            success = True
            reduction_percentage = random.uniform(0.30, 0.75)
            # Урон по войскам
            for unit_name, unit_count in all_units:
                reduction_amount = int(unit_count * reduction_percentage)
                new_count = max(0, unit_count - reduction_amount)
                if new_count > 0:
                    cursor.execute("UPDATE garrisons SET unit_count = ? WHERE city_name = ? AND unit_name = ?", (new_count, target_city, unit_name))
                else:
                    cursor.execute("DELETE FROM garrisons WHERE city_name = ? AND unit_name = ?", (target_city, unit_name))
            # Урон по зданиям в том же проценте
            buildings_destroyed = 0
            try:
                cursor.execute("SELECT building_type, count FROM buildings WHERE city_name = ? AND count > 0", (target_city,))
                city_buildings = cursor.fetchall()
                for b_type, b_count in city_buildings:
                    b_reduction = max(1, int(b_count * reduction_percentage))
                    new_b_count = max(0, b_count - b_reduction)
                    if new_b_count > 0:
                        cursor.execute("UPDATE buildings SET count = ? WHERE city_name = ? AND building_type = ?",
                                       (new_b_count, target_city, b_type))
                    else:
                        cursor.execute("DELETE FROM buildings WHERE city_name = ? AND building_type = ?",
                                       (target_city, b_type))
                    buildings_destroyed += b_reduction
            except Exception as e:
                print(f"[SABOTAGE] Ошибка разрушения зданий: {e}")
            bld_msg = f" Зданий разрушено: {buildings_destroyed}." if buildings_destroyed > 0 else ""
            pct_display = int(reduction_percentage * 100)
            message = f"Саботаж в {target_city} ({target_faction}) успешен! Войска -{pct_display}%.{bld_msg}"
        else:
            message = f"Саботаж в городе {target_city} фракции {target_faction} провален."

    elif op_name == 'Мятеж':
        _target_type = op_info.get('_target_type', 'empty')
        _garrison_cities = op_info.get('_garrison_cities', [])

        if _target_type == 'garrison' and _garrison_cities:
            target_city = random.choice(_garrison_cities)
        else:
            cities_without_garrison = targets_info[target_faction]['cities_without_garrison']
            if not cities_without_garrison:
                show_result_popup("Ошибка", "Нет подходящих целей для мятежа.", False)
                return
            target_city = random.choice(cities_without_garrison)

        rebel_hero_name = "Кейдж"
        rebel_peasant_name = "Мятежники"

        cursor.execute("SELECT unit_name, image_path FROM units WHERE unit_name IN (?, ?)", (rebel_hero_name, rebel_peasant_name))
        existing_units = {row[0]: row[1] for row in cursor.fetchall()}

        if rebel_hero_name not in existing_units or rebel_peasant_name not in existing_units:
            show_result_popup("Ошибка", "Юниты для мятежа отсутствуют в БД.", False)
            return

        if _target_type == 'garrison':
            # Загружаем статы юнитов из БД
            def _load_unit_stats(unit_name):
                cursor.execute(
                    "SELECT attack, defense, durability, unit_class FROM units WHERE unit_name = ?",
                    (unit_name,))
                _s = cursor.fetchone()
                if _s:
                    return {"Урон": _s[0], "Защита": _s[1], "Живучесть": _s[2], "Класс юнита": _s[3]}
                return {"Урон": 0, "Защита": 0, "Живучесть": 0, "Класс юнита": 1}

            # Мятежники вступают в бой с гарнизоном
            rebel_army = [
                {"unit_name": rebel_hero_name, "unit_count": 1,
                 "unit_image": existing_units[rebel_hero_name],
                 "units_stats": _load_unit_stats(rebel_hero_name)},
                {"unit_name": rebel_peasant_name, "unit_count": rebels_count,
                 "unit_image": existing_units[rebel_peasant_name],
                 "units_stats": _load_unit_stats(rebel_peasant_name)}
            ]
            # Собираем гарнизон защитника
            cursor.execute("""
                SELECT g.unit_name, g.unit_count, g.unit_image FROM garrisons g
                WHERE g.city_name = ?
            """, (target_city,))
            def_garrison = cursor.fetchall()
            defending_army = []
            for row in def_garrison:
                defending_army.append({
                    "unit_name": row[0], "unit_count": row[1],
                    "unit_image": row[2],
                    "units_stats": _load_unit_stats(row[0])
                })

            from fight import fight
            result = fight(
                attacking_city=target_city,
                defending_city=target_city,
                defending_army=defending_army,
                attacking_army=rebel_army,
                attacking_fraction='Мятежники',
                defending_fraction=target_faction,
                conn=conn
            )
            if result['winner'] == 'attacker':
                success = True
                cursor.execute("UPDATE cities SET faction = 'Мятежники', color_faction = '#888888' WHERE name = ?", (target_city,))
                message = f"Мятеж в {target_city} успешен! Гарнизон разбит."
            else:
                message = f"Мятеж в {target_city} подавлен гарнизоном."
        else:
            # Город без гарнизона — захват напрямую
            cursor.execute("UPDATE cities SET faction = 'Мятежники', color_faction = '#888888' WHERE name = ?", (target_city,))
            cursor.execute("DELETE FROM garrisons WHERE city_name = ?", (target_city,))
            for unit_info in [{"name": rebel_hero_name, "count": 1},
                              {"name": rebel_peasant_name, "count": rebels_count}]:
                cursor.execute("""
                    INSERT INTO garrisons (city_name, unit_name, unit_count, unit_image)
                    VALUES (?, ?, ?, ?)
                """, (target_city, unit_info["name"], unit_info["count"], existing_units[unit_info["name"]]))
            success = True
            message = f"Мятеж в городе {target_city} успешен!"

        # Перерисовка карты
        try:
            from game_process import refresh_map
            refresh_map()
        except Exception:
            pass

        # --- Объявляем войну между Мятежниками и фракцией, которой принадлежал город ---
        original_faction = target_faction
        cursor.execute("""
            SELECT relationship FROM diplomacies
            WHERE (faction1 = 'Мятежники' AND faction2 = ?) OR (faction1 = ? AND faction2 = 'Мятежники')
        """, (original_faction, original_faction))
        existing_rel = cursor.fetchone()

        if existing_rel:
            cursor.execute("""
                UPDATE diplomacies SET relationship = 'война'
                WHERE (faction1 = 'Мятежники' AND faction2 = ?) OR (faction1 = ? AND faction2 = 'Мятежники')
            """, (original_faction, original_faction))
        else:
            cursor.execute("""
                INSERT INTO diplomacies (faction1, faction2, relationship)
                VALUES ('Мятежники', ?, 'война')
            """, (original_faction,))

        conn.commit()

    elif op_name == 'Заказ':
        # Найти всех героев 3 класса фракции цели, которые находятся в гарнизонах
        cursor.execute("""
            SELECT g.city_name, u.unit_name
            FROM garrisons g
            JOIN units u ON g.unit_name = u.unit_name
            WHERE u.faction = ? AND u.unit_class LIKE '3%'
        """, (target_faction,))
        heroes_3_class = cursor.fetchall()

        if not heroes_3_class:
            show_result_popup("Ошибка", "Нет героев 3 класса для ликвидации.", False)
            return

        hero_city, target_hero = random.choice(heroes_3_class)

        if random.random() < 0.5:
            success = True
            cursor.execute("DELETE FROM garrisons WHERE unit_name = ?", (target_hero,))
            message = f"Заказ на героя {target_hero} фракции {target_faction} в городе {hero_city} успешен! Цель ликвидирована."
        else:
            message = f"Заказ на героя {target_hero} фракции {target_faction} в городе {hero_city} провален."

    else:
        message = f"Неизвестная операция: {op_name}"
        show_result_popup("Ошибка", message, False)
        return

    conn.commit()

    # --- Проверка на раскрытие ---
    if random.random() < 0.5:
        cursor.execute("""
            SELECT relationship FROM diplomacies
            WHERE (faction1 = ? AND faction2 = ?) OR (faction1 = ? AND faction2 = ?)
        """, (player_faction, target_faction, target_faction, player_faction))
        existing_rel = cursor.fetchone()

        if existing_rel:
            cursor.execute("""
                UPDATE diplomacies SET relationship = 'война'
                WHERE (faction1 = ? AND faction2 = ?) OR (faction1 = ? AND faction2 = ?)
            """, (player_faction, target_faction, target_faction, player_faction))
        else:
            cursor.execute("""
                INSERT INTO diplomacies (faction1, faction2, relationship)
                VALUES (?, ?, 'война')
            """, (player_faction, target_faction))

        conn.commit()
        message += f"\nОперация раскрыта! Фракция {target_faction} объявила войну фракции {player_faction}."
    else:
        message += "\nОперация осталась незамеченной."

    show_result_popup("Результат операции", message, success)

def show_result_popup(title, message, is_success=True):
    from kivy.graphics import Color as _RCol, RoundedRectangle as _RRR
    _is_m = platform in ('android', 'ios')
    _fs_t = sp(17) if _is_m else sp(15)
    _fs_m = sp(14) if _is_m else sp(13)

    content = BoxLayout(orientation='vertical', spacing=dp(12),
                        padding=[dp(20), dp(16), dp(20), dp(16)])

    # Заголовок
    _title = Label(
        text=f"[b]{title}[/b]", markup=True,
        font_size=_fs_t, halign='center', valign='middle',
        color=(0.2, 0.9, 0.8, 1) if is_success else (1, 0.4, 0.3, 1),
        size_hint_y=None, height=dp(36))
    _title.bind(size=lambda w, v: setattr(w, 'text_size', (w.width, None)))
    content.add_widget(_title)

    # Сообщение в карточке
    _msg_box = BoxLayout(orientation='vertical', size_hint_y=None, height=dp(70),
                         padding=[dp(12), dp(10)])
    with _msg_box.canvas.before:
        _RCol(0.12, 0.14, 0.22, 0.9)
        _msg_box._bg = _RRR(pos=_msg_box.pos, size=_msg_box.size, radius=[dp(8)])
    _msg_box.bind(pos=lambda w, v: setattr(w._bg, 'pos', v),
                  size=lambda w, v: setattr(w._bg, 'size', v))

    _msg = Label(
        text=message, font_size=_fs_m,
        halign='center', valign='middle',
        color=(0.9, 0.9, 0.95, 1),
        size_hint_y=1)
    _msg.bind(size=lambda w, v: setattr(w, 'text_size', (w.width, None)))
    _msg_box.add_widget(_msg)
    content.add_widget(_msg_box)

    # Пространство
    content.add_widget(Widget(size_hint_y=1))

    # Кнопка
    _btn = Button(text="Назад", font_size=_fs_m, bold=True,
                  size_hint_y=None, height=dp(44),
                  background_normal='', background_color=(0.5, 0.15, 0.15, 1))
    content.add_widget(_btn)

    popup = Popup(title='', content=content,
                  size_hint=(0.85 if _is_m else 0.4, 0.45 if _is_m else 0.4),
                  auto_dismiss=False, separator_height=0,
                  background='', background_color=(0.04, 0.05, 0.09, 0.98))
    _btn.bind(on_press=lambda i: popup.dismiss())
    popup.open()
