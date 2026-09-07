from db_lerdon_connect import *
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.graphics import Color, RoundedRectangle
from kivy.metrics import dp, sp
from kivy.uix.popup import Popup
from kivy.uix.behaviors import ButtonBehavior
from kivy.core.window import Window
import sqlite3
import threading

from utils.helpers import format_number
# Глобальная блокировка для работы с БД
db_lock = threading.Lock()
from nobles import show_nobles_window
from diversion import show_diversion_window

translation_dict = {
    "Север": "arkadia",
    "Эльфы": "celestia",
    "Адепты": "eteria",
    "Вампиры": "giperion",
    "Элины": "halidon",
}

# Словарь для перевода названий файлов в русскоязычные названия фракций
faction_names = {
    "arkadia_in_city": "Север",
    "celestia_in_city": "Эльфы",
    "eteria_in_city": "Адепты",
    "giperion_in_city": "Вампиры",
    "halidon_in_city": "Элины"
}

faction_names_build = {
    "arkadia_buildings_city": "Север",
    "celestia_buildings_city": "Эльфы",
    "eteria_buildings_city": "Адепты",
    "giperion_buildings_city": "Вампиры",
    "halidon_buildings_city": "Элины"
}

def transform_filename(file_path):
    path_parts = file_path.split('/')
    for i, part in enumerate(path_parts):
        for ru_name, en_name in translation_dict.items():
            if ru_name in part:
                path_parts[i] = part.replace(ru_name, en_name)
    return '/'.join(path_parts)


reverse_translation_dict = {v: k for k, v in translation_dict.items()}

def all_factions(cursor):
    """
    Выгружает список активных фракций из таблицы diplomacies.
    Возвращает уникальный список фракций, у которых статус в relationship не равен "уничтожена".
    :param cursor: Курсор для работы с базой данных
    :return: Список активных фракций
    """
    try:
        # Запрос для получения всех уникальных фракций, кроме тех, что имеют статус "уничтожена"
        query = """
            SELECT DISTINCT faction 
            FROM (
                SELECT faction1 AS faction, relationship FROM diplomacies
                UNION
                SELECT faction2 AS faction, relationship FROM diplomacies
            ) AS all_factions
            WHERE relationship != 'уничтожена' AND faction != 'Мятежники'
        """
        cursor.execute(query)
        factions = [row[0] for row in cursor.fetchall()]
        return factions
    except sqlite3.Error as e:
        print(f"Ошибка при получении списка активных фракций: {e}")
        return []

# Функция для расчета базового размера шрифта
def calculate_font_size():
    """Рассчитывает базовый размер шрифта на основе высоты окна."""
    base_height = 720  # Базовая высота окна для нормального размера шрифта
    default_font_size = 16  # Базовый размер шрифта
    scale_factor = Window.height / base_height  # Коэффициент масштабирования
    return max(8, int(default_font_size * scale_factor))  # Минимальный размер шрифта — 8

def get_relation_level(conn, f1, f2):
    cursor = conn.cursor()
    cursor.execute("""
        SELECT relationship FROM relations 
        WHERE (faction1=? AND faction2=?) OR (faction1=? AND faction2=?)
    """, (f1, f2, f2, f1))
    row = cursor.fetchone()
    return int(row[0]) if row else 0


def calculate_coefficient(rel):
    rel = int(rel)
    if rel < 15:
        return 0
    if 15 <= rel < 25:
        return 0.1
    if 25 <= rel < 35:
        return 0.4
    if 35 <= rel < 54:
        return 0.95
    if 54 <= rel < 65:
        return 1.5
    if 65 <= rel < 75:
        return 2
    if 75 <= rel < 90:
        return 3.1
    if 90 <= rel <= 100:
        return 4
    return 0


# Класс для управления дипломатическими отношениями
class DiplomacyManager:
    def __init__(self, faction, db_connection, cursor):
        self.faction = faction
        self.db_connection = db_connection
        self.cursor = cursor

    def get_diplomatic_relations(self):
        """Получает дипломатические отношения текущей фракции с другими"""
        try:
            # Получаем только живые фракции (имеющие хотя бы 1 город)
            self.cursor.execute("""
                SELECT DISTINCT faction FROM cities
                WHERE faction != ? AND faction != 'Нейтрал'
                  AND faction != 'Мятежники' AND faction != 'Нежить'
            """, (self.faction,))
            all_factions = [row[0] for row in self.cursor.fetchall()]

            relations = {}

            for other_faction in all_factions:
                # Получаем дипломатический статус из таблицы diplomacies
                self.cursor.execute("""
                    SELECT relationship FROM diplomacies 
                    WHERE (faction1 = ? AND faction2 = ?) OR (faction1 = ? AND faction2 = ?)
                """, (self.faction, other_faction, other_faction, self.faction))

                status_row = self.cursor.fetchone()
                diplomatic_status = status_row[0] if status_row else "нейтралитет"

                # Получаем уровень отношений из таблицы relations
                self.cursor.execute("""
                    SELECT relationship FROM relations 
                    WHERE (faction1 = ? AND faction2 = ?) OR (faction1 = ? AND faction2 = ?)
                """, (self.faction, other_faction, other_faction, self.faction))

                relation_row = self.cursor.fetchone()
                relation_level = int(relation_row[0]) if relation_row else 0

                relations[other_faction] = {
                    "status": diplomatic_status,
                    "level": relation_level,
                    "description": self.get_relation_description(relation_level),
                    "color": self.get_status_color(diplomatic_status)
                }

            return relations

        except sqlite3.Error as e:
            print(f"Ошибка при получении дипломатических отношений: {e}")
            return {}

    def get_relation_description(self, level):
        """Возвращает текстовое описание уровня отношений"""
        if level <= 10:
            return "Ненависть"
        elif level <= 25:
            return "Вражда"
        elif level <= 40:
            return "Неприязнь"
        elif level <= 55:
            return "Нейтралитет"
        elif level <= 70:
            return "Дружелюбие"
        elif level <= 85:
            return "Уважение"
        else:
            return "Союзничество"

    def get_status_color(self, status):
        """Возвращает цвет для статуса отношений"""
        colors = {
            "война": (1.0, 0.2, 0.2, 1),      # Красный
            "нейтралитет": (1.0, 1.0, 0.5, 1), # Желтый
            "союз": (0.2, 0.8, 0.2, 1),        # Зеленый
            "уничтожена": (0.5, 0.5, 0.5, 1)   # Серый
        }
        return colors.get(status, (1.0, 1.0, 1.0, 1))  # Белый по умолчанию

    def show_diplomatic_relations(self):
        """Показывает окно с дипломатическими отношениями"""
        relations = self.get_diplomatic_relations()

        if not relations:
            print(f"Нет данных о дипломатических отношениях для фракции {self.faction}.")
            return

        # Создаем контент для popup
        content = BoxLayout(orientation='vertical', spacing=dp(8), padding=dp(10))
        with content.canvas.before:
            Color(0.07, 0.08, 0.13, 1)
            content._bg = Rectangle(pos=content.pos, size=content.size)
        content.bind(pos=lambda i, v: setattr(i._bg, 'pos', v),
                     size=lambda i, v: setattr(i._bg, 'size', v))

        # Создаем таблицу
        table = GridLayout(
            cols=5,
            size_hint_y=None,
            spacing=dp(4),
            row_default_height=dp(45)
        )
        table.bind(minimum_height=table.setter('height'))

        # Заголовки таблицы
        headers = ["Фракция", "Статус", "Уровень", "Отношения", "Действие"]
        for title in headers:
            table.add_widget(self.create_header(title))

        # Заполняем таблицу данными
        for other_faction, data in sorted(relations.items()):
            status = data["status"]
            level = data["level"]
            description = data["description"]
            status_color = data["color"]

            faction_label = self._create_cell(other_faction)

            status_label = Label(
                text=status,
                font_size='14sp',
                bold=True,
                color=status_color,
                halign='center',
                valign='middle',
                size_hint_y=None,
                height=dp(45),
                outline_color=(0, 0, 0, 1),
                outline_width=2
            )

            level_label = self._create_cell(str(level))

            desc_label = Label(
                text=description,
                font_size='14sp',
                bold=False,
                color=(1, 1, 1, 1),
                halign='center',
                valign='middle',
                size_hint_y=None,
                height=dp(45)
            )

            # Кнопка действия
            action_btn = self._create_action_button(other_faction, status, table, relations)

            table.add_widget(faction_label)
            table.add_widget(status_label)
            table.add_widget(level_label)
            table.add_widget(desc_label)
            table.add_widget(action_btn)

        # Добавляем таблицу в ScrollView
        scroll = ScrollView(
            size_hint=(1, 0.8),
            bar_width=dp(6),
            bar_color=(0.5, 0.5, 0.5, 0.6),
            scroll_type=['bars', 'content']
        )
        scroll.add_widget(table)
        content.add_widget(scroll)

        # Легенда статусов
        legend_layout = BoxLayout(
            orientation='horizontal',
            size_hint=(1, None),
            height=dp(40),
            spacing=dp(10)
        )

        # Кнопка закрытия
        close_button = Button(
            text="Закрыть",
            size_hint=(1, None),
            height=dp(46),
            font_size=sp(15),
            bold=True,
            background_color=(0, 0, 0, 0),
            color=(1, 1, 1, 1)
        )
        with close_button.canvas.before:
            close_button._bc = Color(0.65, 0.18, 0.18, 1)
            close_button._br = RoundedRectangle(pos=close_button.pos, size=close_button.size, radius=[dp(10)])
        close_button.bind(
            pos=lambda i, v: setattr(i._br, 'pos', v),
            size=lambda i, v: setattr(i._br, 'size', v)
        )

        def close_popup(instance):
            if hasattr(self, 'popup'):
                self.popup.dismiss()

        close_button.bind(on_release=close_popup)
        content.add_widget(close_button)

        self.popup = Popup(
            title=f"Отношения: {self.faction}",
            content=content,
            size_hint=(0.85, 0.9),
            auto_dismiss=False,
            background_color=(0.07, 0.08, 0.13, 1),
            separator_color=(0.20, 0.55, 0.88, 0.7),
            title_color=(0.65, 0.88, 1, 1),
            title_size=sp(16),
            title_align='center'
        )
        self.popup.open()

    def create_header(self, text):
        """Создает заголовок таблицы с фоном через canvas"""
        label = Label(
            text=f"[b]{text}[/b]",
            markup=True,
            font_size='16sp',
            bold=True,
            color=(1, 1, 1, 1),
            halign='center',
            valign='middle',
            size_hint_y=None,
            height=dp(50),
            text_size=(None, None),
            outline_color=(0, 0, 0, 1),
            outline_width=2
        )

        # Добавляем фон через canvas
        with label.canvas.before:
            Color(0.2, 0.4, 0.6, 1)  # Темно-синий цвет фона
            label.bg = RoundedRectangle(
                pos=label.pos,
                size=label.size,
                radius=[dp(4)]
            )

        # Обновляем фон при изменении размера
        def update_bg(instance, value):
            instance.bg.pos = instance.pos
            instance.bg.size = instance.size

        label.bind(pos=update_bg, size=update_bg)
        label.bind(size=label.setter('text_size'))
        return label

    def _create_cell(self, text, highlight=False):
        """Создает ячейку таблицы"""
        if highlight:
            bg_color = (0.3, 0.5, 0.7, 0.3)  # Светло-синий фон для подсветки
            text_color = (1, 1, 0.5, 1)  # Желтый текст для подсветки
        else:
            bg_color = (0.1, 0.1, 0.1, 0.2)  # Темный фон для остальных
            text_color = (1, 1, 1, 1)  # Белый текст

        label = Label(
            text=text,
            font_size='14sp',
            bold=True if highlight else False,
            color=text_color,
            halign='center',
            valign='middle',
            size_hint_y=None,
            height=dp(45),
            text_size=(None, None)
        )

        # Добавляем фон
        with label.canvas.before:
            Color(*bg_color)
            label.background = RoundedRectangle(
                pos=label.pos,
                size=label.size,
                radius=[dp(4)]
            )

        # Обновляем фон при изменении размера
        def update_background(instance, value):
            instance.background.pos = instance.pos
            instance.background.size = instance.size

        label.bind(pos=update_background, size=update_background)
        label.bind(size=label.setter('text_size'))

        return label

    def _create_action_button(self, target_faction, status, table, relations):
        """Создаёт кнопку действия: Объявить войну / Предложить мир."""
        if status == 'война':
            btn_text = "Предложить мир"
            btn_color = (0.2, 0.6, 0.3, 1)
        elif status == 'союз':
            btn_text = "—"
            # Нельзя объявить войну союзнику — пустая ячейка
            return self._create_cell("—")
        else:
            btn_text = "Объявить войну"
            btn_color = (0.7, 0.18, 0.18, 1)

        btn = Button(
            text=btn_text,
            font_size=sp(12),
            bold=True,
            size_hint_y=None,
            height=dp(45),
            background_color=(0, 0, 0, 0),
            background_normal='',
            color=(1, 1, 1, 1)
        )
        with btn.canvas.before:
            btn._bg_c = Color(*btn_color)
            btn._bg_r = RoundedRectangle(pos=btn.pos, size=btn.size, radius=[dp(6)])
        btn.bind(
            pos=lambda i, v: setattr(i._bg_r, 'pos', v),
            size=lambda i, v: setattr(i._bg_r, 'size', v)
        )

        def on_action(instance, faction=target_faction, cur_status=status):
            if cur_status == 'война':
                self._propose_peace(faction)
            else:
                self._declare_war(faction)
            # Обновляем попап
            if hasattr(self, 'popup'):
                self.popup.dismiss()
                self.show_diplomatic_relations()

        btn.bind(on_release=on_action)
        return btn

    def _declare_war(self, target_faction):
        """Игрок объявляет войну фракции."""
        try:
            # Обновляем обе записи в diplomacies
            self.cursor.execute(
                "UPDATE diplomacies SET relationship = 'война' WHERE faction1 = ? AND faction2 = ?",
                (self.faction, target_faction)
            )
            self.cursor.execute(
                "UPDATE diplomacies SET relationship = 'война' WHERE faction1 = ? AND faction2 = ?",
                (target_faction, self.faction)
            )
            # Снижаем отношения
            self.cursor.execute(
                "UPDATE relations SET relationship = MAX(0, relationship - 30) WHERE faction1 = ? AND faction2 = ?",
                (self.faction, target_faction)
            )
            self.cursor.execute(
                "UPDATE relations SET relationship = MAX(0, relationship - 30) WHERE faction1 = ? AND faction2 = ?",
                (target_faction, self.faction)
            )
            self.db_connection.commit()
            print(f"[ДИПЛОМАТИЯ] {self.faction} объявил войну {target_faction}!")

            from nobles import show_toast
            show_toast(f"Война с {target_faction} объявлена!")
        except Exception as e:
            print(f"Ошибка объявления войны: {e}")

    def _propose_peace(self, target_faction):
        """Игрок предлагает мир фракции."""
        try:
            # Мир стоит денег — 500к крон
            peace_cost = 500000
            self.cursor.execute(
                "SELECT amount FROM resources WHERE faction = ? AND resource_type = 'Кроны'",
                (self.faction,)
            )
            row = self.cursor.fetchone()
            current_money = row[0] if row else 0

            if current_money < peace_cost:
                from nobles import show_toast
                show_toast(f"Недостаточно крон для мира (нужно {peace_cost:,})")
                return

            # Списываем деньги
            self.cursor.execute(
                "UPDATE resources SET amount = amount - ? WHERE faction = ? AND resource_type = 'Кроны'",
                (peace_cost, self.faction)
            )

            # Устанавливаем нейтралитет
            self.cursor.execute(
                "UPDATE diplomacies SET relationship = 'нейтралитет' WHERE faction1 = ? AND faction2 = ?",
                (self.faction, target_faction)
            )
            self.cursor.execute(
                "UPDATE diplomacies SET relationship = 'нейтралитет' WHERE faction1 = ? AND faction2 = ?",
                (target_faction, self.faction)
            )
            # Немного улучшаем отношения
            self.cursor.execute(
                "UPDATE relations SET relationship = MIN(100, relationship + 10) WHERE faction1 = ? AND faction2 = ?",
                (self.faction, target_faction)
            )
            self.cursor.execute(
                "UPDATE relations SET relationship = MIN(100, relationship + 10) WHERE faction1 = ? AND faction2 = ?",
                (target_faction, self.faction)
            )
            self.db_connection.commit()
            print(f"[ДИПЛОМАТИЯ] {self.faction} заключил мир с {target_faction} за {peace_cost} крон")

            from nobles import show_toast
            show_toast(f"Мир с {target_faction} заключён за {peace_cost:,} крон")
        except Exception as e:
            print(f"Ошибка предложения мира: {e}")


# Кастомная кнопка с анимациями и эффектами
class StyledButton(ButtonBehavior, BoxLayout):
    def __init__(self, text, font_size, button_color, text_color, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'vertical'
        self.size_hint = (1, None)
        self.height = font_size * 3  # Высота кнопки зависит от размера шрифта
        self.padding = [font_size // 2, font_size // 4]  # Отступы внутри кнопки
        self.normal_color = button_color
        self.hover_color = [c * 0.9 for c in button_color]  # Темнее при наведении
        self.pressed_color = [c * 0.8 for c in button_color]  # Еще темнее при нажатии
        self.current_color = self.normal_color

        with self.canvas.before:
            Color(*self.current_color)
            self.rect = RoundedRectangle(size=self.size, pos=self.pos, radius=[font_size // 2])

        self.bind(pos=self.update_rect, size=self.update_rect)

        self.label = Label(
            text=text,
            font_size=font_size * 1.2,
            color=text_color,
            bold=True,
            halign='center',
            valign='middle'
        )
        self.label.bind(size=self.label.setter('text_size'))
        self.add_widget(self.label)

        self.bind(on_press=self.on_press_effect, on_release=self.on_release_effect)
        self.bind(on_touch_move=self.on_hover, on_touch_up=self.on_leave)

    def update_rect(self, *args):
        self.rect.pos = self.pos
        self.rect.size = self.size

    def on_press_effect(self, instance):
        """Эффект затемнения при нажатии"""
        anim = Animation(current_color=self.pressed_color, duration=0.1)
        anim.start(self)
        self.update_color()

    def on_release_effect(self, instance):
        """Возвращаем цвет после нажатия"""
        anim = Animation(current_color=self.normal_color, duration=0.1)
        anim.start(self)
        self.update_color()

    def on_hover(self, instance, touch):
        """Эффект при наведении"""
        if self.collide_point(*touch.pos):
            anim = Animation(current_color=self.hover_color, duration=0.1)
            anim.start(self)
            self.update_color()

    def on_leave(self, instance, touch):
        """Возвращаем цвет, если курсор ушел с кнопки"""
        if not self.collide_point(*touch.pos):
            anim = Animation(current_color=self.normal_color, duration=0.1)
            anim.start(self)
        self.update_color()

    def update_color(self):
        """Обновляет цвет фона"""
        self.canvas.before.clear()
        with self.canvas.before:
            Color(*self.current_color)
            self.rect = RoundedRectangle(size=self.size, pos=self.pos, radius=[self.height // 4])



def calculate_peace_army_points(conn, faction):
    """
    Вычисляет общую силу армии фракции с локальными бонусами:
    - Герои 2 и 3 класса усиливают ТОЛЬКО юнитов 1 класса из своего гарнизона
    - Бонусы не распространяются между городами
    """
    cursor = conn.cursor()

    try:
        # Получаем данные с привязкой к городу
        cursor.execute("""
            SELECT g.city_name, g.unit_name, g.unit_count, u.attack, u.defense, u.durability, u.unit_class 
            FROM garrisons g
            JOIN units u ON g.unit_name = u.unit_name
            WHERE u.faction = ?
        """, (faction,))
        units_data = cursor.fetchall()

        # Группируем юниты по городам
        cities_data = {}

        for row in units_data:
            city_name, unit_name, unit_count, attack, defense, durability, unit_class = row

            if city_name not in cities_data:
                cities_data[city_name] = {
                    "class_1": {"count": 0, "total_stats": 0},
                    "heroes": {"total_stats": 0},   # классы 2 и 3
                    "others": {"total_stats": 0}    # классы 4 и выше
                }

            stats_sum = attack + defense + durability

            if unit_class == "1":
                cities_data[city_name]["class_1"]["count"] += unit_count
                cities_data[city_name]["class_1"]["total_stats"] += stats_sum * unit_count
            elif unit_class in ("2", "3"):
                cities_data[city_name]["heroes"]["total_stats"] += stats_sum * unit_count
            else:
                cities_data[city_name]["others"]["total_stats"] += stats_sum * unit_count

        # Рассчитываем силу для каждого города отдельно
        total_strength = 0

        for city, data in cities_data.items():
            class_1_count = data["class_1"]["count"]
            base_stats = data["class_1"]["total_stats"]
            hero_bonus = data["heroes"]["total_stats"]
            others_stats = data["others"]["total_stats"]

            city_strength = 0

            # Бонусы героев применяются ТОЛЬКО к юнитам 1 класса в этом городе
            if class_1_count > 0:
                city_strength += base_stats + hero_bonus * class_1_count

            # Юниты 4+ класса добавляются без бонусов
            city_strength += others_stats

            total_strength += city_strength

        return total_strength

    except Exception as e:
        print(f"Ошибка при вычислении очков армии: {e}")
        return 0


def calculate_army_strength(conn):
    """Рассчитывает силу армий для каждой фракции с локальными бонусами по гарнизонам."""

    army_strength = {}

    try:
        cursor = conn.cursor()

        # Получаем все юниты с привязкой к городу
        cursor.execute("""
            SELECT g.city_name, g.unit_name, g.unit_count, u.faction, u.attack, u.defense, u.durability, u.unit_class 
            FROM garrisons g
            JOIN units u ON g.unit_name = u.unit_name
        """)
        garrison_data = cursor.fetchall()

        # Собираем данные по фракциям и городам
        factions_data = {}

        for row in garrison_data:
            city_name, unit_name, unit_count, faction, attack, defense, durability, unit_class = row

            if not faction:
                continue

            if faction not in factions_data:
                factions_data[faction] = {}

            if city_name not in factions_data[faction]:
                factions_data[faction][city_name] = {
                    "class_1": {"count": 0, "total_stats": 0},
                    "heroes": {"total_stats": 0},  # герои класса 2 и 3
                    "others": {"total_stats": 0}   # юниты класса 4 и выше
                }

            stats_sum = attack + defense + durability
            city_data = factions_data[faction][city_name]

            if unit_class == "1":
                city_data["class_1"]["count"] += unit_count
                city_data["class_1"]["total_stats"] += stats_sum * unit_count
            elif unit_class in ("2", "3"):
                city_data["heroes"]["total_stats"] += stats_sum * unit_count
            else:  # класс 4 и выше
                city_data["others"]["total_stats"] += stats_sum * unit_count

        # Рассчитываем силу для каждой фракции
        for faction, cities in factions_data.items():
            faction_strength = 0

            for city, data in cities.items():
                class_1_count = data["class_1"]["count"]
                base_stats = data["class_1"]["total_stats"]
                hero_bonus = data["heroes"]["total_stats"]
                others_stats = data["others"]["total_stats"]

                city_strength = 0

                # Локальное применение бонусов: только внутри города
                if class_1_count > 0:
                    city_strength += base_stats + hero_bonus * class_1_count

                city_strength += others_stats
                faction_strength += city_strength

            army_strength[faction] = faction_strength

    except Exception as e:
        print(f"Ошибка при работе с базой данных: {e}")
        return {}

    # Возвращаем два словаря: один с числовыми значениями, другой с отформатированными строками
    formatted_army_strength = {faction: format_number(strength) for faction, strength in army_strength.items()}
    return army_strength, formatted_army_strength

def create_army_rating_table(conn):
    """Создает таблицу рейтинга армий в стиле таблицы отношений (тёмная тема)."""

    cursor = conn.cursor()
    cursor.execute("""
        SELECT DISTINCT faction FROM cities
        WHERE faction != 'Нейтрал' AND faction != 'Мятежники' AND faction != 'Нежить'
    """)
    all_factions = [row[0] for row in cursor.fetchall()]

    if not all_factions:
        return GridLayout()

    faction_ratings = []
    for faction in all_factions:
        local_power = calculate_peace_army_points(conn, faction)
        global_power = calculate_total_faction_power(conn, faction)
        faction_ratings.append({
            "faction": faction,
            "local_power": local_power,
            "global_power": global_power
        })

    faction_ratings.sort(key=lambda x: x["global_power"], reverse=True)

    layout = GridLayout(
        cols=3,
        size_hint_y=None,
        spacing=dp(4),
        row_default_height=dp(45)
    )
    layout.bind(minimum_height=layout.setter('height'))

    # Заголовки — стиль как в таблице отношений
    header_bg = (0.15, 0.35, 0.65, 1)
    for title in ["Фракция", "Мощь героя", "Общая мощь"]:
        lbl = Label(
            text=f"[b]{title}[/b]", markup=True,
            font_size=sp(14), color=(1, 1, 1, 1),
            halign='center', valign='middle',
            size_hint_y=None, height=dp(45)
        )
        lbl.bind(size=lbl.setter('text_size'))
        with lbl.canvas.before:
            Color(*header_bg)
            lbl._bg = RoundedRectangle(pos=lbl.pos, size=lbl.size, radius=[dp(4)])
        lbl.bind(
            pos=lambda i, v: setattr(i._bg, 'pos', v),
            size=lambda i, v: setattr(i._bg, 'size', v)
        )
        layout.add_widget(lbl)

    # Данные — тёмный фон, белый текст
    def _cell(text, bold=False):
        lbl = Label(
            text=text, font_size=sp(14), bold=bold,
            color=(1, 1, 1, 1), halign='center', valign='middle',
            size_hint_y=None, height=dp(45)
        )
        lbl.bind(size=lbl.setter('text_size'))
        with lbl.canvas.before:
            Color(0.1, 0.1, 0.1, 0.2)
            lbl._bg = RoundedRectangle(pos=lbl.pos, size=lbl.size, radius=[dp(4)])
        lbl.bind(
            pos=lambda i, v: setattr(i._bg, 'pos', v),
            size=lambda i, v: setattr(i._bg, 'size', v)
        )
        return lbl

    for data in faction_ratings:
        faction_name = faction_names.get(data["faction"], data["faction"])
        layout.add_widget(_cell(faction_name))
        layout.add_widget(_cell(format_number(int(data["local_power"]))))
        layout.add_widget(_cell(format_number(int(data["global_power"])), bold=True))

    return layout

def calculate_total_faction_power(conn, faction):
    """
    Вычисляет ОБЩУЮ мощь фракции с ГЛОБАЛЬНЫМИ бонусами:
    - ВСЕ герои фракции классов 2 и 3 усиливают ВСЕХ юнитов 1-го класса
      во ВСЕХ гарнизонах фракции (бонусы суммируются)
    """
    cursor = conn.cursor()

    try:
        # === ШАГ 1: Находим ВСЕХ героев фракции классов 2 и 3 ===
        # Убрали LIMIT 1 — теперь получаем всех героев для суммирования бонусов
        cursor.execute("""
            SELECT u.attack, u.defense, u.durability, u.unit_class
            FROM garrisons g
            JOIN units u ON g.unit_name = u.unit_name
            WHERE u.faction = ? AND u.unit_class IN ('2', '3')
        """, (faction,))

        hero_rows = cursor.fetchall()

        # Суммируем характеристики ВСЕХ героев классов 2 и 3
        total_hero_stats = 0
        for hero_row in hero_rows:
            hero_attack, hero_defense, hero_durability, hero_class = hero_row
            total_hero_stats += hero_attack + hero_defense + hero_durability

        # === ШАГ 2: Считаем ВСЕ юниты фракции ===
        cursor.execute("""
            SELECT g.unit_name, g.unit_count, u.attack, u.defense, u.durability, u.unit_class 
            FROM garrisons g
            JOIN units u ON g.unit_name = u.unit_name
            WHERE u.faction = ?
        """, (faction,))

        units_data = cursor.fetchall()

        total_class_1_count = 0      # Общее количество юнитов 1-го класса по всей фракции
        total_class_1_stats = 0      # Сумма характеристик всех юнитов 1-го класса
        total_others_stats = 0       # Сумма характеристик юнитов 4+ класса

        for row in units_data:
            unit_name, unit_count, attack, defense, durability, unit_class = row
            stats_sum = attack + defense + durability

            if unit_class == "1":
                total_class_1_count += unit_count
                total_class_1_stats += stats_sum * unit_count
            elif unit_class in ("2", "3"):
                # Герои не учитываются в базе мощности, только как источник бонуса
                pass
            else:  # класс 4 и выше
                total_others_stats += stats_sum * unit_count

        # === ШАГ 3: Применяем ГЛОБАЛЬНЫЙ бонус ВСЕХ героев ===
        # Суммарный бонус всех героев умножается на ОБЩЕЕ количество юнитов 1-го класса фракции
        global_bonus = total_hero_stats * total_class_1_count

        # Итоговая формула:
        # Общая мощь = (база юнитов 1-го класса) + (глобальный бонус всех героев) + (юниты 4+ класса)
        total_power = total_class_1_stats + global_bonus + total_others_stats

        return total_power

    except Exception as e:
        print(f"Ошибка при вычислении общей мощи фракции {faction}: {e}")
        return 0

def show_ratings_popup(conn):
    """Открывает всплывающее окно с рейтингом армий."""
    from kivy.core.window import Window
    from kivy.utils import platform

    is_android = platform == 'android'

    content = BoxLayout(orientation='vertical', spacing=dp(8), padding=dp(10))
    with content.canvas.before:
        Color(0.07, 0.08, 0.13, 1)
        content._bg = Rectangle(pos=content.pos, size=content.size)
    content.bind(pos=lambda i, v: setattr(i._bg, 'pos', v),
                 size=lambda i, v: setattr(i._bg, 'size', v))

    # === Таблица ===
    table = create_army_rating_table(conn)

    scroll = ScrollView(
        size_hint=(1, 1),
        bar_width=dp(6),
        bar_color=(0.20, 0.55, 0.88, 0.5),
        scroll_type=['bars', 'content']
    )
    scroll.add_widget(table)
    content.add_widget(scroll)

    # === Кнопка закрытия ===
    close_button = Button(
        text="Закрыть",
        size_hint=(1, None),
        height=dp(46),
        font_size=sp(15),
        bold=True,
        background_color=(0, 0, 0, 0),
        color=(1, 1, 1, 1)
    )
    with close_button.canvas.before:
        close_button._bc = Color(0.65, 0.18, 0.18, 1)
        close_button._br = RoundedRectangle(pos=close_button.pos, size=close_button.size, radius=[dp(10)])
    close_button.bind(
        pos=lambda i, v: setattr(i._br, 'pos', v),
        size=lambda i, v: setattr(i._br, 'size', v)
    )

    def close_popup(instance):
        if hasattr(show_ratings_popup, 'popup'):
            show_ratings_popup.popup.dismiss()

    close_button.bind(on_release=close_popup)
    content.add_widget(close_button)

    show_ratings_popup.popup = Popup(
        title="Силы армий",
        content=content,
        size_hint=(0.95, 0.85),
        auto_dismiss=False,
        background_color=(0.07, 0.08, 0.13, 1),
        separator_color=(0.20, 0.55, 0.88, 0.7),
        title_color=(0.65, 0.88, 1, 1),
        title_size=sp(17),
        title_align='center'
    )
    show_ratings_popup.popup.open()

# Функция для показа окна дипломатических отношений
def show_diplomacy_window(faction, conn):
    """Показывает окно с дипломатическими отношениями"""
    cursor = conn.cursor()
    manager = DiplomacyManager(faction, conn, cursor)
    manager.show_diplomatic_relations()


#------------------------------------------------------------------
def show_faction_bonuses_popup(conn, faction):
    """Показывает попап с подробной информацией о бонусах фракции в цифрах."""
    from kivy.uix.popup import Popup
    from kivy.metrics import dp, sp
    from kivy.graphics import Color, RoundedRectangle, Rectangle

    cursor = conn.cursor()

    # === Собираем данные ===
    # Здания
    cursor.execute("SELECT building_type, SUM(count) FROM buildings WHERE faction = ? GROUP BY building_type", (faction,))
    buildings = {row[0]: row[1] for row in cursor.fetchall()}
    walls = buildings.get('Стена', 0)
    markets = buildings.get('Рынок', 0)
    smithies = buildings.get('Кузница', 0)
    towers = buildings.get('Вышка', 0)

    # Базовый урон юнитов 1 класса
    cursor.execute("SELECT unit_name, attack FROM units WHERE faction = ? AND unit_class = '1' LIMIT 1", (faction,))
    unit_row = cursor.fetchone()
    base_unit_atk = unit_row[1] if unit_row else 0
    unit_name = unit_row[0] if unit_row else "—"

    # Герои — суммарный бонус от героев 2-3 класса
    cursor.execute("""
        SELECT SUM(u.attack) FROM garrisons g
        JOIN units u ON g.unit_name = u.unit_name
        WHERE u.faction = ? AND u.unit_class IN ('2', '3')
    """, (faction,))
    hero_atk_bonus = cursor.fetchone()[0] or 0

    # Итоговый урон юнита с героем
    total_unit_atk = base_unit_atk + hero_atk_bonus

    # Сезон
    cursor.execute("SELECT season_index FROM season LIMIT 1")
    season_row = cursor.fetchone()
    season_idx = season_row[0] if season_row else 0
    season_names = {0: "Зима", 1: "Весна", 2: "Лето", 3: "Осень"}

    # Количество советников с бонусом
    try:
        cursor.execute("SELECT COUNT(*) FROM nobles WHERE status = 'active' AND loyalty > 50")
        loyal_nobles = cursor.fetchone()[0]
    except Exception:
        loyal_nobles = 0

    # === Формируем строки бонусов ===
    FACTION_DATA = {
        'Север': {
            'name': 'Шквал',
            'desc': 'Если бонусы увеличили урон в 20+ раз, x1.7 к урону',
            'color': (0.25, 0.52, 0.92, 1),
            'calc': lambda: _calc_shkval(base_unit_atk, total_unit_atk),
        },
        'Эльфы': {
            'name': 'Лесная хитрость',
            'desc': '+10% инициатива всех юнитов в бою',
            'color': (0.22, 0.76, 0.32, 1),
            'calc': lambda: [("Бонус инициативы", "+10%", "Всегда активен")],
        },
        'Вампиры': {
            'name': 'Вампиризм',
            'desc': '5% убитых врагов воскресают как ваши юниты',
            'color': (0.78, 0.10, 0.16, 1),
            'calc': lambda: [("Воскрешение врагов", "5%", "После каждого боя")],
        },
        'Адепты': {
            'name': 'Святое благословение',
            'desc': '+20% защита при обороне своих городов',
            'color': (0.62, 0.22, 0.88, 1),
            'calc': lambda: [("Бонус защиты (оборона)", "+20%", "При защите городов")],
        },
        'Элины': {
            'name': 'Торговая империя',
            'desc': '+15% доход крон (стакается с Рынком)',
            'color': (0.92, 0.70, 0.10, 1),
            'calc': lambda: [("Бонус торговли", f"+{15 + markets * 10}%", f"15% фракция + {markets * 10}% от {markets} рынков")],
        },
    }

    def _calc_shkval(base, total):
        ratio = total / base if base > 0 else 0
        active = ratio >= 20.0
        final_dmg = int(total * 1.70) if active else total
        bonus_dmg = final_dmg - total if active else 0
        status = f"[color=00ff00]АКТИВЕН (итого {final_dmg})[/color]" if active else f"[color=ff8800]Не активен (x{ratio:.1f}, нужно x20)[/color]"
        return [
            ("Базовый урон", str(base_unit_atk), unit_name),
            ("Бонус от героев", f"+{hero_atk_bonus}", f"Итого: {total}"),
            ("Множитель", f"x{ratio:.1f}", f"Нужно x20"),
            ("Шквал (x1.7)", f"+{bonus_dmg}" if active else "---", status),
        ]

    faction_info = FACTION_DATA.get(faction)
    if not faction_info:
        return

    bonus_rows = faction_info['calc']()

    # === UI ===
    content = BoxLayout(orientation='vertical', spacing=dp(8), padding=dp(12))
    with content.canvas.before:
        Color(0.07, 0.08, 0.13, 1)
        content._bg = Rectangle(pos=content.pos, size=content.size)
    content.bind(pos=lambda i, v: setattr(i._bg, 'pos', v),
                 size=lambda i, v: setattr(i._bg, 'size', v))

    # Заголовок способности
    accent = faction_info['color']
    title = Label(
        text=f"[b]{faction_info['name']}[/b]", markup=True,
        font_size=sp(18), color=accent,
        size_hint_y=None, height=dp(30), halign='center', valign='middle'
    )
    title.bind(size=title.setter('text_size'))
    content.add_widget(title)

    desc = Label(
        text=faction_info['desc'], font_size=sp(13),
        color=(0.7, 0.7, 0.7, 1), size_hint_y=None, height=dp(22),
        halign='center', valign='middle'
    )
    desc.bind(size=desc.setter('text_size'))
    content.add_widget(desc)

    # Разделитель
    sep = Widget(size_hint_y=None, height=dp(1))
    with sep.canvas:
        Color(*accent[:3], 0.4)
        sep._r = Rectangle(pos=sep.pos, size=sep.size)
    sep.bind(pos=lambda i, v: setattr(i._r, 'pos', v), size=lambda i, v: setattr(i._r, 'size', v))
    content.add_widget(sep)

    # Строки бонусов
    for label_text, value_text, detail_text in bonus_rows:
        row = BoxLayout(size_hint_y=None, height=dp(28), spacing=dp(4))
        lbl = Label(text=label_text, font_size=sp(13), color=(0.85, 0.85, 0.85, 1),
                    halign='left', valign='middle', size_hint_x=0.35)
        lbl.bind(size=lbl.setter('text_size'))
        val = Label(text=f"[b]{value_text}[/b]", markup=True, font_size=sp(14),
                    color=accent, halign='center', valign='middle', size_hint_x=0.2)
        val.bind(size=val.setter('text_size'))
        det = Label(text=detail_text, markup=True, font_size=sp(11),
                    color=(0.6, 0.6, 0.6, 1), halign='left', valign='middle', size_hint_x=0.45)
        det.bind(size=det.setter('text_size'))
        row.add_widget(lbl)
        row.add_widget(val)
        row.add_widget(det)
        content.add_widget(row)

    # Разделитель
    sep2 = Widget(size_hint_y=None, height=dp(1))
    with sep2.canvas:
        Color(0.3, 0.3, 0.3, 0.3)
        sep2._r = Rectangle(pos=sep2.pos, size=sep2.size)
    sep2.bind(pos=lambda i, v: setattr(i._r, 'pos', v), size=lambda i, v: setattr(i._r, 'size', v))
    content.add_widget(sep2)

    # Общие бонусы от зданий
    building_bonuses = [
        ("Стены", walls, f"+{walls * 15}% защита гарнизона"),
        ("Рынки", markets, f"+{markets * 10}% доход крон"),
        ("Кузницы", smithies, f"+{smithies * 5}% атака обороны"),
        ("Вышки", towers, f"+{towers * 500} лимит армии"),
        ("Советники", loyal_nobles, f"Лояльные (>50%) дают бонусы"),
    ]

    bld_title = Label(
        text="[b]Бонусы от зданий и советников[/b]", markup=True,
        font_size=sp(14), color=(0.85, 0.75, 0.4, 1),
        size_hint_y=None, height=dp(24), halign='left', valign='middle'
    )
    bld_title.bind(size=bld_title.setter('text_size'))
    content.add_widget(bld_title)

    for name, count, effect in building_bonuses:
        if count == 0:
            continue
        row = BoxLayout(size_hint_y=None, height=dp(24), spacing=dp(4))
        n_lbl = Label(text=f"{name}: {count}", font_size=sp(12),
                      color=(0.8, 0.8, 0.8, 1), halign='left', size_hint_x=0.4)
        n_lbl.bind(size=n_lbl.setter('text_size'))
        e_lbl = Label(text=effect, font_size=sp(12),
                      color=(0.6, 0.85, 0.5, 1), halign='left', size_hint_x=0.6)
        e_lbl.bind(size=e_lbl.setter('text_size'))
        row.add_widget(n_lbl)
        row.add_widget(e_lbl)
        content.add_widget(row)

    # Сезон
    season_lbl = Label(
        text=f"Сезон: {season_names.get(season_idx, '?')}", font_size=sp(12),
        color=(0.5, 0.7, 0.9, 1), size_hint_y=None, height=dp(20),
        halign='center', valign='middle'
    )
    season_lbl.bind(size=season_lbl.setter('text_size'))
    content.add_widget(season_lbl)

    # Кнопка закрыть
    close_btn = Button(
        text="Закрыть", size_hint_y=None, height=dp(44), font_size=sp(14), bold=True,
        background_color=(0, 0, 0, 0), background_normal='', color=(1, 1, 1, 1)
    )
    with close_btn.canvas.before:
        Color(0.5, 0.2, 0.2, 1)
        close_btn._r = RoundedRectangle(pos=close_btn.pos, size=close_btn.size, radius=[dp(10)])
    close_btn.bind(pos=lambda i, v: setattr(i._r, 'pos', v),
                   size=lambda i, v: setattr(i._r, 'size', v))

    popup = Popup(
        title=f"Бонусы — {faction}",
        content=content,
        size_hint=(0.7, 0.75),
        auto_dismiss=False,
        background_color=(0.07, 0.08, 0.13, 1),
        separator_color=accent[:3] + (0.7,),
        title_color=accent,
        title_size=sp(16),
        title_align='center'
    )
    close_btn.bind(on_release=lambda x: popup.dismiss())
    content.add_widget(close_btn)
    popup.open()


def start_politic_mode(faction, game_area, class_faction, conn):
    """Инициализация политического режима для выбранной фракции"""

    from kivy.metrics import dp, sp
    from kivy.uix.widget import Widget

    is_android = platform == 'android'

    politics_layout = BoxLayout(
        orientation='horizontal',
        size_hint=(1, None),
        height=dp(70) if is_android else 60,
        pos_hint={'x': -0.34, 'y': 0},
        spacing=dp(10) if is_android else 10,
        padding=[dp(10), dp(5), dp(10), dp(5)] if is_android else [10, 5, 10, 5]
    )

    # Добавляем пустое пространство слева
    politics_layout.add_widget(Widget(size_hint_x=None, width=dp(20)))

    def styled_btn(text, callback):
        btn = Button(
            text=text,
            size_hint_x=None,
            width=dp(120) if is_android else 100,
            size_hint_y=None,
            height=dp(60) if is_android else 50,
            background_color=(0, 0, 0, 0),
            color=(1, 1, 1, 1),
            font_size=sp(18) if is_android else 16,
            bold=True
        )

        with btn.canvas.before:
            Color(0.2, 0.6, 1, 1)
            btn.rect = RoundedRectangle(pos=btn.pos, size=btn.size, radius=[15])

        def update_rect(instance, value):
            instance.rect.pos = instance.pos
            instance.rect.size = instance.size

        btn.bind(pos=update_rect, size=update_rect)
        btn.bind(on_release=callback)
        return btn

    # Добавляем кнопки в нужном порядке
    btn_army = styled_btn("Сила армий", lambda btn: show_ratings_popup(conn))
    btn_diplomacy = styled_btn("Отношения", lambda btn: show_diplomacy_window(faction, conn))
    btn_nobles = styled_btn("Совет", lambda btn: show_nobles_window(conn, faction, class_faction))
    btn_diversion = styled_btn("Диверсия", lambda btn: show_diversion_window(conn, faction, class_faction))
    btn_bonuses = styled_btn("Бонусы", lambda btn: show_faction_bonuses_popup(conn, faction))

    politics_layout.add_widget(btn_army)
    politics_layout.add_widget(btn_diplomacy)
    politics_layout.add_widget(btn_nobles)
    politics_layout.add_widget(btn_diversion)
    politics_layout.add_widget(btn_bonuses)

    game_area.add_widget(politics_layout)