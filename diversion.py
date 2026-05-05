from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.popup import Popup
from kivy.metrics import dp, sp
from kivy.core.window import Window
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.uix.slider import Slider
from kivy.graphics import Color, RoundedRectangle
from kivy.utils import get_color_from_hex
import random
import sqlite3

# --- Цветовая палитра ---
BACKGROUND_COLOR = get_color_from_hex("#121212")
CARD_COLOR = get_color_from_hex("#1e1e1e")
TEXT_COLOR = get_color_from_hex("#ffffff")
ACCENT_COLOR = get_color_from_hex("#bb86fc")
SECONDARY_COLOR = get_color_from_hex("#03dac6")
WARNING_COLOR = get_color_from_hex("#cf6679")
DISABLED_COLOR = get_color_from_hex("#444444")
SELECTED_OUTLINE = get_color_from_hex("#bb86fc")

def format_number(number):
    if not isinstance(number, (int, float)):
        return str(number)
    if number == 0:
        return "0"
    absolute = abs(number)
    sign = -1 if number < 0 else 1

    if absolute >= 1_000_000_000:
        return f"{sign * absolute / 1e9:.1f} млрд."
    elif absolute >= 1_000_000:
        return f"{sign * absolute / 1e6:.1f} млн."
    elif absolute >= 1_000:
        return f"{sign * absolute / 1e3:.1f} тыс."
    else:
        return f"{number}"

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

    is_android = hasattr(Window, 'keyboard')
    padding_main = dp(15)
    spacing_main = dp(5)  # Уменьшен отступ между элементами
    font_title = sp(18)   # Уменьшен размер заголовка окна
    font_header = sp(12)  # Уменьшен размер заголовка таблицы
    font_info = sp(11)    # Уменьшен размер текста информации
    font_btn = sp(11)     # Уменьшен размер текста кнопки
    btn_height = dp(25)   # Уменьшена высота кнопки вдвое
    item_height = dp(27)  # Уменьшена высота строки вдвое (примерно)

    content = BoxLayout(orientation='vertical', padding=padding_main, spacing=spacing_main)

    cursor = conn.cursor()
    # Исключаем Мятежников из списка целей
    cursor.execute("SELECT DISTINCT faction FROM cities WHERE faction != ? AND faction != 'Мятежники'", (player_faction,))
    target_factions_result = cursor.fetchall()
    target_factions = [row[0] for row in target_factions_result if row[0]]

    if not target_factions:
        no_targets_popup = ThemedPopup(
            title="Нет целей",
            content=Label(
                text="Нет других фракций для диверсии.",
                halign='center',
                valign='middle',
                color=TEXT_COLOR,
                text_size=(dp(250), None)
            ),
            size_hint=(0.8, 0.4)
        )
        no_targets_popup.open()
        return

    targets_info = {}
    for target_faction in target_factions:
        cursor.execute("""
            SELECT DISTINCT c.name FROM cities c
            JOIN garrisons g ON c.name = g.city_name
            JOIN units u ON g.unit_name = u.unit_name
            WHERE c.faction = ? AND u.faction = ?
        """, (target_faction, target_faction))
        cities_with_garrison = [row[0] for row in cursor.fetchall()]

        cursor.execute("""
            SELECT name FROM cities
            WHERE faction = ? AND name NOT IN (
                SELECT DISTINCT city_name FROM garrisons
                JOIN units u ON garrisons.unit_name = u.unit_name
                WHERE u.faction = ?
            )
        """, (target_faction, target_faction))
        cities_without_garrison = [row[0] for row in cursor.fetchall()]

        cursor.execute("""
            SELECT u.unit_name FROM units u
            JOIN garrisons g ON u.unit_name = g.unit_name
            WHERE u.faction = ? AND (u.attack > 0 OR u.defense > 0)
        """, (target_faction,))
        target_heroes = [row[0] for row in cursor.fetchall()]

        targets_info[target_faction] = {
            'cities_with_garrison': cities_with_garrison,
            'cities_without_garrison': cities_without_garrison,
            'heroes': target_heroes
        }

    # --- Обновленный интерфейс для Android ---
    scroll_view_factions = ScrollView(do_scroll_x=False, size_hint=(1, 0.6))
    table_factions = GridLayout(cols=2, spacing=dp(5), size_hint_y=None)
    table_factions.bind(minimum_height=table_factions.setter('height'))

    _BTN_DEFAULT = (0.18, 0.28, 0.45, 1)
    _BTN_SELECTED = (0.72, 0.18, 0.22, 1)

    selected_faction = [None]
    selected_btn = [None]

    def select_target_faction(instance):
        popup.dismiss()
        if selected_faction[0]:
            show_operations_window(conn, player_faction, cash_player, selected_faction[0], targets_info)

    for target_faction in target_factions:
        # Создаем Label для названия фракции
        faction_label = Label(
            text=target_faction,
            halign='left',
            valign='middle',
            font_size=font_info,
            color=TEXT_COLOR,
            size_hint_y=None,
            height=item_height,
            text_size=(dp(150), None)
        )
        faction_label.bind(size=faction_label.setter('text_size'))

        # Создаем кнопку "Выбрать"
        select_btn = ThemedButton(
            text="Выбрать",
            size_hint_y=None,
            height=btn_height,
            font_size=font_btn,
            background_color=_BTN_DEFAULT
        )

        # Функция для выбора фракции
        def make_select_handler(faction_name, btn):
            def handler(instance):
                if selected_btn[0] and selected_btn[0] is not btn:
                    selected_btn[0]._btn_color_instr.rgba = _BTN_DEFAULT
                btn._btn_color_instr.rgba = _BTN_SELECTED
                selected_btn[0] = btn
                selected_faction[0] = faction_name
                select_all_btn.disabled = False
            return handler

        select_btn.bind(on_release=make_select_handler(target_faction, select_btn))

        # Добавляем элементы в таблицу
        table_factions.add_widget(faction_label)
        table_factions.add_widget(select_btn)

    scroll_view_factions.add_widget(table_factions)

    # Кнопка "Перейти к операциям" (изначально отключена)
    select_all_btn = ThemedButton(
        text="Перейти к операциям",
        size_hint_y=None,
        height=btn_height, # Используем уменьшенную высоту
        font_size=font_btn, # Используем уменьшенный шрифт
        background_color=ACCENT_COLOR,
        disabled=True
    )
    select_all_btn.bind(on_release=select_target_faction)

    close_btn = ThemedButton(
        text="Закрыть",
        size_hint_y=None,
        height=btn_height, # Используем уменьшенную высоту
        font_size=font_btn, # Используем уменьшенный шрифт
        background_color=WARNING_COLOR
    )

    content.add_widget(Label(text="Выберите цель:", font_size=font_header, bold=True, halign='center', color=TEXT_COLOR, size_hint_y=None, height=dp(25))) # Уменьшена высота заголовка
    content.add_widget(scroll_view_factions)
    content.add_widget(select_all_btn)
    content.add_widget(close_btn)

    popup = ThemedPopup(
        title="Главное управление Тайной Службы",
        content=content,
        size_hint=(0.95, 0.9),
        auto_dismiss=False
    )
    close_btn.bind(on_release=popup.dismiss)
    popup.open()

def show_operations_window(conn, player_faction, cash_player, target_faction, targets_info):
    is_android = hasattr(Window, 'keyboard')
    padding_main = dp(15)
    spacing_main = dp(5)  # Уменьшен отступ
    font_title = sp(16)   # Уменьшен размер заголовка
    font_info = sp(11)    # Уменьшен размер текста информации
    font_btn = sp(11)     # Уменьшен размер текста кнопки
    btn_height = dp(25)   # Уменьшена высота кнопки вдвое

    content = BoxLayout(orientation='vertical', padding=padding_main, spacing=spacing_main)

    title_label = Label(
        text=f"Цель: {target_faction}",
        font_size=font_title,
        bold=True,
        color=TEXT_COLOR,
        size_hint_y=None,
        height=dp(30) # Уменьшена высота заголовка
    )

    ops_descriptions = {
        'Саботаж': {
            'desc': 'Снижение численности войск в городе на 5-40% (50% шанс успеха). Стоимость: 150 тыс.',
            'cost': 150_000
        },
        'Мятеж': {
            'desc': 'Захват города без гарнизона.',
            'cost': 700_000
        },
        'Заказ': {
            'desc': 'Убийство вражеского героя (30% шанс успеха). Стоимость: 250 тыс.',
            'cost': 250_000
        }
    }

    # Создаем ScrollView для операций
    operations_scroll = ScrollView(size_hint_y=0.6)
    operations_layout = BoxLayout(orientation='vertical', size_hint_y=None, spacing=spacing_main) # Используем уменьшенный отступ
    operations_layout.bind(minimum_height=operations_layout.setter('height'))

    _OP_DEFAULT = (0.50, 0.14, 0.18, 1)
    _OP_PRESSED = (0.72, 0.18, 0.22, 1)
    _selected_op = [None]

    for op_name, op_info in ops_descriptions.items():
        op_btn = ThemedButton(
            text=f"{op_name}\n{op_info['desc']}",
            size_hint_y=None,
            height=dp(50),
            font_size=font_info,
            background_color=_OP_DEFAULT
        )
        def make_op_handler(op_name, op_info):
            def on_op_select(instance):
                if _selected_op[0] and _selected_op[0] is not instance:
                    _selected_op[0]._btn_color_instr.rgba = _OP_DEFAULT
                instance._btn_color_instr.rgba = _OP_PRESSED
                _selected_op[0] = instance
                if op_name == 'Мятеж':
                    show_rebellion_cost_selection(conn, player_faction, cash_player, op_name, op_info, target_faction, targets_info)
                else:
                    show_confirmation_popup(conn, player_faction, cash_player, op_name, op_info, target_faction, targets_info)
            return on_op_select

        op_btn.bind(on_release=make_op_handler(op_name, op_info))
        operations_layout.add_widget(op_btn)

    operations_scroll.add_widget(operations_layout)

    close_btn = ThemedButton(
        text="Назад",
        size_hint_y=None,
        height=btn_height, # Используем уменьшенную высоту
        font_size=font_btn, # Используем уменьшенный шрифт
        background_color=WARNING_COLOR
    )

    content.add_widget(title_label)
    content.add_widget(operations_scroll)
    content.add_widget(close_btn)

    popup = ThemedPopup(
        title="Выберите операцию",
        content=content,
        size_hint=(0.9, 0.8),
        auto_dismiss=False
    )
    close_btn.bind(on_release=popup.dismiss)
    popup.open()

# --- Остальные функции остаются без изменений ---
# (show_rebellion_cost_selection, show_confirmation_popup, execute_diversion_operation, show_result_popup)
# Просто убедитесь, что в них используются те же уменьшенные значения для высот и шрифтов, где это возможно и логично.

def show_rebellion_cost_selection(conn, player_faction, cash_player, op_name, op_info, target_faction, targets_info):
    is_android = hasattr(Window, 'keyboard')
    padding_main = dp(15)
    spacing_main = dp(5) # Уменьшен
    font_title = sp(16) # Уменьшен
    font_info = sp(11) # Уменьшен
    font_btn = sp(11) # Уменьшен
    btn_height = dp(25) # Уменьшен

    content = BoxLayout(orientation='vertical', padding=padding_main, spacing=spacing_main)

    title_label = Label(
        text="Стоимость мятежа",
        font_size=font_title,
        bold=True,
        color=TEXT_COLOR,
        size_hint_y=None,
        height=dp(30) # Уменьшена
    )

    desc_label = Label(
        text="Выберите сумму (от 700 тыс до 6.5 млн):",
        font_size=font_info,
        color=TEXT_COLOR,
        halign='center',
        valign='middle',
        text_size=(dp(280), None)
    )
    desc_label.bind(size=desc_label.setter('text_size'))

    cash_player.load_resources()
    current_money = cash_player.resources.get("Кроны", 0)
    max_affordable = min(6_500_000, current_money)

    slider = Slider(
        min=700_000,
        max=max_affordable,
        value=700_000,
        step=10000
    )
    slider_label = Label(
        text=f"Выбрано: {format_number(slider.value)}",
        font_size=font_info,
        color=TEXT_COLOR,
        halign='center',
        valign='middle',
        text_size=(dp(280), None)
    )
    slider.bind(value=lambda instance, value: slider_label.setter('text')(slider_label, f"Выбрано: {format_number(value)}"))

    def calculate_rebels(cost):
        base_cost = 700_000
        extra_money = max(0, cost - base_cost)
        extra_percentage = (extra_money // 100_000) * 0.37
        total_percentage = 1.0 + extra_percentage
        return int(2750 * total_percentage)

    rebels_label = Label(
        text=f"Количество мятежников: {calculate_rebels(slider.value)}",
        font_size=font_info,
        color=TEXT_COLOR,
        halign='center',
        valign='middle',
        text_size=(dp(280), None)
    )
    slider.bind(value=lambda instance, value: rebels_label.setter('text')(rebels_label, f"Количество мятежников: {calculate_rebels(value)}"))

    btn_layout = BoxLayout(size_hint_y=None, height=btn_height, spacing=dp(10))

    confirm_btn = ThemedButton(
        text="Подтвердить",
        font_size=font_btn,
        background_color=SECONDARY_COLOR
    )
    cancel_btn = ThemedButton(
        text="Отмена",
        font_size=font_btn,
        background_color=WARNING_COLOR
    )

    def on_confirm(instance):
        selected_cost = int(slider.value)
        rebels_count = calculate_rebels(selected_cost)
        popup.dismiss()
        show_confirmation_popup(conn, player_faction, cash_player, op_name, op_info, target_faction, targets_info, custom_cost=selected_cost, rebels_count=rebels_count)

    def on_cancel(instance):
        popup.dismiss()

    confirm_btn.bind(on_release=on_confirm)
    cancel_btn.bind(on_release=on_cancel)

    btn_layout.add_widget(confirm_btn)
    btn_layout.add_widget(cancel_btn)

    content.add_widget(title_label)
    content.add_widget(desc_label)
    content.add_widget(slider)
    content.add_widget(slider_label)
    content.add_widget(rebels_label)
    content.add_widget(btn_layout)

    popup = ThemedPopup(
        title="Мятеж",
        content=content,
        size_hint=(0.85, 0.7),
        auto_dismiss=False
    )
    popup.open()

def show_confirmation_popup(conn, player_faction, cash_player, op_name, op_info, target_faction, targets_info, custom_cost=None, rebels_count=None):
    is_android = hasattr(Window, 'keyboard')
    padding_main = dp(15)
    spacing_main = dp(5) # Уменьшен
    font_title = sp(16) # Уменьшен
    font_info = sp(11) # Уменьшен
    font_btn = sp(11) # Уменьшен
    btn_height = dp(25) # Уменьшен

    content = BoxLayout(orientation='vertical', padding=padding_main, spacing=spacing_main)

    title_label = Label(
        text=f"Операция: {op_name}",
        font_size=font_title,
        bold=True,
        color=TEXT_COLOR,
        size_hint_y=None,
        height=dp(30) # Уменьшена
    )

    cost = custom_cost if custom_cost else op_info['cost']
    desc = f"Цель: {target_faction}\nСтоимость: {format_number(cost)}"
    if rebels_count:
        desc += f"\nКоличество мятежников: {rebels_count}"

    desc_label = Label(
        text=desc,
        font_size=font_info,
        color=TEXT_COLOR,
        halign='center',
        valign='middle',
        text_size=(dp(280), None)
    )
    desc_label.bind(size=desc_label.setter('text_size'))

    cash_player.load_resources()
    current_money = cash_player.resources.get("Кроны", 0)
    if current_money < cost:
        insufficient_funds_popup = ThemedPopup(
            title="Недостаточно средств",
            content=Label(
                text=f"Недостаточно Крон для операции.\nСтоимость: {format_number(cost)}\nУ вас: {format_number(current_money)}",
                halign='center',
                valign='middle',
                color=WARNING_COLOR,
                text_size=(dp(250), None)
            ),
            size_hint=(0.8, 0.4)
        )
        insufficient_funds_popup.open()
        return

    # --- Проверка наличия целей до списания ---
    if op_name == 'Мятеж':
        cities_without_garrison = targets_info[target_faction]['cities_without_garrison']
        if not cities_without_garrison:
            no_targets_popup = ThemedPopup(
                title="Нет целей",
                content=Label(
                    text="Нет городов без гарнизона для мятежа.",
                    halign='center',
                    valign='middle',
                    color=WARNING_COLOR,
                    text_size=(dp(250), None)
                ),
                size_hint=(0.8, 0.4)
            )
            no_targets_popup.open()
            return

    btn_layout = BoxLayout(size_hint_y=None, height=btn_height, spacing=dp(10))

    confirm_btn = ThemedButton(
        text="Выполнить",
        font_size=font_btn,
        background_color=SECONDARY_COLOR
    )
    cancel_btn = ThemedButton(
        text="Отмена",
        font_size=font_btn,
        background_color=WARNING_COLOR
    )

    popup = ThemedPopup(
        title="Подтверждение операции",
        content=content,
        size_hint=(0.85, 0.6),
        auto_dismiss=False
    )

    def on_confirm(instance):
        # Списание ресурсов происходит только после проверки
        popup.dismiss()
        deduction_success = cash_player.deduct_resources(cost)
        if not deduction_success:
            show_result_popup("Ошибка", "Ошибка списания средств.", False)
            return
        execute_diversion_operation(conn, player_faction, op_name, op_info, target_faction, targets_info, custom_cost=custom_cost, rebels_count=rebels_count)

    def on_cancel(instance):
        popup.dismiss()

    confirm_btn.bind(on_release=on_confirm)
    cancel_btn.bind(on_release=on_cancel)

    btn_layout.add_widget(confirm_btn)
    btn_layout.add_widget(cancel_btn)

    content.add_widget(title_label)
    content.add_widget(desc_label)
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
            reduction_percentage = random.uniform(0.05, 0.40)
            for unit_name, unit_count in all_units:
                reduction_amount = int(unit_count * reduction_percentage)
                new_count = max(0, unit_count - reduction_amount)
                if new_count > 0:
                    cursor.execute("UPDATE garrisons SET unit_count = ? WHERE city_name = ? AND unit_name = ?", (new_count, target_city, unit_name))
                else:
                    cursor.execute("DELETE FROM garrisons WHERE city_name = ? AND unit_name = ?", (target_city, unit_name))
            message = f"Саботаж в городе {target_city} фракции {target_faction} успешен! Юниты повреждены."
        else:
            message = f"Саботаж в городе {target_city} фракции {target_faction} провален."

    elif op_name == 'Мятеж':
        cities_without_garrison = targets_info[target_faction]['cities_without_garrison']
        if not cities_without_garrison:
            show_result_popup("Ошибка", "Нет подходящих целей для мятежа.", False)
            return
        target_city = random.choice(cities_without_garrison)

        # Получаем фракцию, которой принадлежал город до мятежа
        cursor.execute("SELECT faction FROM cities WHERE name = ?", (target_city,))
        original_faction = cursor.fetchone()
        if not original_faction:
            show_result_popup("Ошибка", f"Не удалось получить фракцию города {target_city}.", False)
            return
        original_faction = original_faction[0]

        rebel_hero_name = "Кейдж"
        rebel_peasant_name = "Мятежники"

        cursor.execute("SELECT unit_name, image_path FROM units WHERE unit_name IN (?, ?)", (rebel_hero_name, rebel_peasant_name))
        existing_units = {row[0]: row[1] for row in cursor.fetchall()}

        if rebel_hero_name not in existing_units or rebel_peasant_name not in existing_units:
            show_result_popup("Ошибка", f"Необходимые юниты для мятежа ('{rebel_hero_name}', '{rebels_count}') отсутствуют в таблице 'units'.", False)
            return

        rebel_units_to_add = [
            {"name": rebel_hero_name, "count": 1},
            {"name": rebel_peasant_name, "count": rebels_count}
        ]

        cursor.execute("UPDATE cities SET faction = 'Мятежники' WHERE name = ?", (target_city,))
        cursor.execute("DELETE FROM garrisons WHERE city_name = ?", (target_city,))
        for unit in rebel_units_to_add:
            unit_name = unit["name"]
            unit_image_path = existing_units[unit_name]
            cursor.execute("""
                INSERT INTO garrisons (city_name, unit_name, unit_count, unit_image)
                VALUES (?, ?, ?, ?)
            """, (target_city, unit_name, unit["count"], unit_image_path))

        success = True
        message = f"Мятеж в городе {target_city} фракции {target_faction} успешен! Город перешел под контроль Мятежников. Количество мятежников: {rebels_count}."

        # --- Объявляем войну между Мятежниками и фракцией, которой принадлежал город ---
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
        message += f"\nФракция '{original_faction}' начала борьбу с Мятежниками."

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

        if random.random() < 0.3:
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
    is_android = hasattr(Window, 'keyboard')
    font_title = sp(16) # Уменьшен
    font_message = sp(12) # Уменьшен
    padding_main = dp(20)
    spacing_main = dp(5) # Уменьшен

    content = BoxLayout(orientation='vertical', padding=padding_main, spacing=spacing_main)

    title_label = Label(
        text=f"[b]{title}[/b]",
        font_size=font_title,
        markup=True,
        halign='center',
        valign='middle',
        color=SECONDARY_COLOR if is_success else WARNING_COLOR,
        size_hint_y=None,
        height=dp(30) # Уменьшена
    )
    title_label.bind(size=title_label.setter('text_size'))

    message_label = Label(
        text=message,
        font_size=font_message,
        halign='center',
        valign='middle',
        markup=True,
        color=TEXT_COLOR,
        text_size=(dp(280), None)
    )
    message_label.bind(size=message_label.setter('text_size'))

    content.add_widget(title_label)
    content.add_widget(message_label)

    popup = ThemedPopup(
        title="",
        content=content,
        size_hint=(0.85, 0.5),
        auto_dismiss=True
    )
    popup.open()
