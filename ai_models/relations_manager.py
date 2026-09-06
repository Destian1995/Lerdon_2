# ai_models/relations_manager.py
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.graphics import Color, Line
from kivy.metrics import dp
import sqlite3

from .translation import translation_dict


class RelationsManager:
    def __init__(self, advisor_view):
        self.advisor = advisor_view
        self.faction = advisor_view.faction
        self.db_connection = advisor_view.db_connection
        self.cursor = advisor_view.cursor

    def load_relations(self):
        """
        Загружает текущие отношения из таблицы relations.
        Возвращает словарь, где ключи — названия фракций, а значения — уровни отношений.
        """
        try:
            self.cursor.execute('''
                SELECT faction2, relationship
                FROM relations
                WHERE faction1 = ? AND faction2 != 'Мятежники'
            ''', (self.faction,))
            rows = self.cursor.fetchall()

            relations = {faction2: relationship for faction2, relationship in rows}
            return relations

        except sqlite3.Error as e:
            print(f"Ошибка при загрузке отношений из таблицы relations: {e}")
            return {}

    def load_diplomacies(self):
        """
        Загружает дипломатические соглашения из базы данных для текущей фракции.
        Возвращает словарь, где ключи — названия фракций, а значения — статусы отношений.
        """
        diplomacies_data = {}
        try:
            cursor = self.db_connection.cursor()
            query = "SELECT faction2, relationship FROM diplomacies WHERE faction1 = ? AND faction2 != 'Мятежники'"
            cursor.execute(query, (self.faction,))
            rows = cursor.fetchall()

            print("Загруженные данные из таблицы diplomacies:", rows)

            # Преобразуем результат в словарь
            for faction2, relationship in rows:
                diplomacies_data[faction2] = relationship

        except sqlite3.Error as e:
            print(f"Ошибка при работе с базой данных: {e}")
        finally:
            print("Результат загрузки diplomacies_data:", diplomacies_data)
            return diplomacies_data

    def load_relations_for_target(self, target_faction):
        """
        Загружает отношения для указанной целевой фракции.
        Возвращает словарь, где ключи — названия фракций, а значения — уровни отношений.
        """
        try:
            self.cursor.execute('''
                SELECT faction2, relationship
                FROM relations
                WHERE faction1 = ? AND faction2 != 'Мятежники'
            ''', (target_faction,))
            rows = self.cursor.fetchall()
            return {faction2: relationship for faction2, relationship in rows}
        except sqlite3.Error as e:
            print(f"Ошибка при загрузке отношений для фракции {target_faction}: {e}")
            return {}

    def load_combined_relations(self):
        """
        Загружает и комбинирует отношения из таблицы relations и файла diplomaties
        Возвращает словарь, где ключи — названия фракций, а значения — словари с уровнем отношений и статусом.
        """
        # Загрузка данных из таблицы relations
        relations_data = self.load_relations()
        print("Загруженные данные из таблицы relations:", relations_data)

        # Загрузка данных из таблицы diplomaties
        diplomacies_data = self.load_diplomacies()
        print("Загруженные данные из таблицы diplomaties:", diplomacies_data)

        # Получаем список живых фракций (у которых есть хотя бы 1 город)
        try:
            self.cursor.execute("SELECT DISTINCT faction FROM cities WHERE faction != 'Нейтрал'")
            alive_factions = {row[0] for row in self.cursor.fetchall()}
        except Exception:
            alive_factions = set()

        # Фракции которые всегда скрываем
        hidden = {'Мятежники', 'Нежить', self.faction}

        # Создаем комбинированный словарь отношений
        combined_relations = {}

        # Обрабатываем данные из таблицы relations
        for target_faction, relation_level in relations_data.items():
            if target_faction in hidden or target_faction not in alive_factions:
                continue
            combined_relations[target_faction] = {
                "relation_level": relation_level,
                "status": "неизвестно"
            }

        # Добавляем/обновляем статусы из таблицы diplomaties
        for target_faction, status in diplomacies_data.items():
            if target_faction in hidden or target_faction not in alive_factions:
                continue
            if target_faction in combined_relations:
                combined_relations[target_faction]["status"] = status
            else:
                combined_relations[target_faction] = {
                    "relation_level": 0,
                    "status": status
                }

        print("Комбинированные отношения:", combined_relations)
        return combined_relations

    def manage_relations(self):
        """
        Управление отношениями только для фракций, заключивших дипломатическое соглашение.
        Использует данные из таблиц БД `relations` и `diplomacies`.
        """
        # Загружаем текущие отношения из базы данных
        relations_data = self.load_relations()

        if not relations_data:
            print(f"Отношения для фракции {self.faction} не найдены.")
            return

        # Загружаем дипломатические соглашения из базы данных
        diplomacies_data = self.load_diplomacies()

        # Проверяем, есть ли дипломатические соглашения для текущей фракции
        if self.faction not in diplomacies_data:
            print(f"Дипломатические соглашения для фракции {self.faction} не найдены.")
            return

        # Получаем список фракций, с которыми заключены соглашения
        agreements = diplomacies_data[self.faction].get("отношения", {})

        for target_faction, status in agreements.items():
            if status == "союз":
                # Проверяем, есть ли отношения с этой фракцией
                if target_faction in relations_data:
                    current_value_self = relations_data[target_faction]
                    current_value_other = self.load_relations_for_target(target_faction).get(self.faction, 0)

                    # Увеличиваем уровень отношений (не более 100)
                    relations_data[target_faction] = min(current_value_self + 7, 100)
                    self.update_relations_in_db(target_faction, min(current_value_other + 7, 100))

        # Сохраняем обновленные данные в базу данных
        self.save_relations_to_db(relations_data)

    def update_relations_in_db(self, target_faction, new_value):
        """
        Обновляет уровень отношений в базе данных для указанной целевой фракции.
        """
        try:
            self.cursor.execute('''
                UPDATE relations
                SET relationship = ?
                WHERE faction1 = ? AND faction2 = ?
            ''', (new_value, target_faction, self.faction))
            self.db_connection.commit()
        except sqlite3.Error as e:
            print(f"Ошибка при обновлении отношений для фракции {target_faction}: {e}")

    def save_relations_to_db(self, relations_data):
        """
        Сохраняет обновленные отношения в базе данных.
        """
        try:
            for target_faction, relationship in relations_data.items():
                self.cursor.execute('''
                    UPDATE relations
                    SET relationship = ?
                    WHERE faction1 = ? AND faction2 = ?
                ''', (relationship, self.faction, target_faction))
            self.db_connection.commit()
            print("Отношения успешно сохранены в базе данных.")
        except sqlite3.Error as e:
            print(f"Ошибка при сохранении отношений в базе данных: {e}")

    def update_relation_in_db(self, target_faction, new_value):
        """Обновляет уровень отношений в базе данных"""
        try:
            cursor = self.db_connection.cursor()
            cursor.execute('''
                UPDATE relations
                SET relationship = ?
                WHERE faction1 = ? AND faction2 = ?
            ''', (new_value, self.faction, target_faction))
            self.db_connection.commit()
        except Exception as e:
            print(f"Ошибка при обновлении отношений в БД: {e}")

    def calculate_coefficient(self, relation_level):
        """Рассчитывает коэффициент на основе уровня отношений"""
        try:
            rel = int(relation_level)
        except (ValueError, TypeError):
            rel = 50

        if rel < 15:
            return 0
        if 15 <= rel < 25:
            return 0.1
        if 25 <= rel < 35:
            return 0.4
        if 35 <= rel < 54:
            return 0.9
        if 54 <= rel < 65:
            return 1.5
        if 65 <= rel < 75:
            return 2
        if 75 <= rel < 90:
            return 3.1
        if 90 <= rel <= 100:
            return 4
        return 0

    def show_relations(self, instance=None):
        """Отображает окно с таблицей отношений."""
        self.manage_relations()
        combined_relations = self.load_combined_relations()

        if not combined_relations:
            print(f"Нет данных об отношениях для фракции {self.faction}.")
            return

        # === Основное содержимое ===
        content = BoxLayout(orientation='vertical', spacing=dp(8), padding=dp(10))

        # Таблица
        table = GridLayout(
            cols=4,
            size_hint_y=None,
            spacing=dp(4),
            row_default_height=dp(40)
        )
        table.bind(minimum_height=table.setter('height'))

        for title in ["Фракция", "Отношения", "Торговля", "Статус"]:
            table.add_widget(self.create_header(title))

        for country, data in combined_relations.items():
            relation_level = data["relation_level"]
            status = data["status"]

            table.add_widget(self.create_cell(country))
            table.add_widget(self.create_value_cell(relation_level))
            table.add_widget(self.create_value_trade_cell(self.calculate_coefficient(relation_level)))
            table.add_widget(self.create_status_cell(status))

        scroll = ScrollView(
            size_hint=(1, 0.7),
            bar_width=dp(6),
            bar_color=(0.5, 0.5, 0.5, 0.6),
            scroll_type=['bars', 'content']
        )
        scroll.add_widget(table)
        content.add_widget(scroll)

        # === Кнопка Назад ===
        from .advisor_view import calculate_font_size

        back_button = Button(
            text="Назад",
            background_color=(0.227, 0.525, 0.835, 1),
            font_size='16sp',
            size_hint=(1, None),
            height=calculate_font_size() * 0.9,
            color=(1, 1, 1, 1),
            background_normal='',
            background_down='',
            bold=True
        )

        # Добавляем рамку вокруг кнопки Назад
        with back_button.canvas.after:
            Color(0.1, 0.1, 0.1, 1)
            back_button.border_line = Line(
                rectangle=(back_button.x, back_button.y, back_button.width, back_button.height), width=1.5)
        back_button.bind(
            size=lambda inst, val: setattr(inst.border_line, "rectangle", (inst.x, inst.y, inst.width, inst.height))
        )
        back_button.bind(
            pos=lambda inst, val: setattr(inst.border_line, "rectangle", (inst.x, inst.y, inst.width, inst.height))
        )

        # При нажатии — возвращаем исходный интерфейс
        back_button.bind(on_release=lambda x: self.advisor.return_to_main_tab())

        content.add_widget(back_button)
        self.advisor.popup.content = content

    def create_value_cell(self, value):
        """Создает ячейку с значением отношений"""
        color = self.get_relation_color(value)
        return Label(
            text=str(value),
            font_size='14sp',
            bold=True,
            color=color,
            halign='center',
            valign='middle',
            size_hint_y=None,
            height=dp(40),
            outline_color=(0, 0, 0, 1),
            outline_width=2
        )

    def create_value_trade_cell(self, coefficient):
        """Создает ячейку с коэффициентом торговли"""
        color = self.get_relation_trade_color(coefficient)
        return Label(
            text=f"{coefficient:.1f}x",
            font_size='14sp',
            bold=True,
            color=color,
            halign='center',
            valign='middle',
            size_hint_y=None,
            height=dp(40),
            outline_color=(0, 0, 0, 1),
            outline_width=2
        )

    def create_status_cell(self, status):
        """Создает ячейку со статусом"""
        color = self.get_status_color(status)
        return Label(
            text=status,
            font_size='14sp',
            bold=True,
            color=color,
            halign='center',
            valign='middle',
            size_hint_y=None,
            height=dp(40),
            outline_color=(0, 0, 0, 1),
            outline_width=2
        )

    def create_cell(self, text, status="нейтралитет"):
        """Создает обычную ячейку"""
        color = self.get_status_color(status)
        label = Label(
            text=str(text),
            size_hint_y=None,
            height=dp(40),
            color=color,
            halign='center',
            valign='middle',
            outline_color=(0, 0, 0, 1),
            outline_width=2
        )
        label.bind(size=label.setter('text_size'))
        return label

    def create_header(self, text):
        """Создает заголовок таблицы"""
        label = Label(
            text=f"[b]{text}[/b]",
            markup=True,
            font_size='14sp',
            bold=True,
            color=(1, 1, 1, 1),
            halign='center',
            valign='middle',
            size_hint_y=None,
            height=dp(40),
            text_size=(None, None),
            outline_color=(0, 0, 0, 1),
            outline_width=2
        )
        label.bind(size=label.setter('text_size'))
        return label

    def get_status_color(self, status):
        """Определяет цвет на основе статуса отношений."""
        if status == "война":
            return (1, 0, 0, 1)  # Красный
        elif status == "нейтралитет":
            return (1, 1, 1, 1)  # Белый
        elif status == "союз":
            return (0, 0.75, 0.8, 1)  # Синий
        else:
            return (0.5, 0.5, 0.5, 1)  # Серый

    def get_relation_trade_color(self, value):
        """Возвращает цвет в зависимости от значения коэффициента"""
        if value <= 0.1:
            return (0.8, 0.1, 0.1, 1)  # Красный
        elif 0.1 < value <= 0.4:
            return (1.0, 0.5, 0.0, 1)  # Оранжевый
        elif 0.4 < value <= 0.9:
            return (1.0, 0.8, 0.0, 1)  # Желтый
        elif 0.9 < value <= 1.5:
            return (0.2, 0.7, 0.3, 1)  # Зеленый
        elif 1.5 < value <= 2:
            return (0.0, 0.8, 0.8, 1)  # Голубой
        elif 2 < value <= 3.1:
            return (0.0, 0.6, 1.0, 1)  # Синий
        elif 3.1 < value <= 4:
            return (0.1, 0.3, 0.9, 1)  # Темно-синий
        else:
            return (1, 1, 1, 1)  # Белый

    def get_relation_color(self, value):
        """Возвращает цвет в зависимости от значения"""
        try:
            value = int(value)
        except (ValueError, TypeError):
            value = 50

        if value <= 15:
            return (0.8, 0.1, 0.1, 1)
        elif 15 < value <= 25:
            return (1.0, 0.5, 0.0, 1)
        elif 25 < value <= 35:
            return (1.0, 0.8, 0.0, 1)
        elif 35 < value <= 54:
            return (0.2, 0.7, 0.3, 1)
        elif 54 < value <= 65:
            return (0.0, 0.8, 0.8, 1)
        elif 65 < value <= 75:
            return (0.0, 0.6, 1.0, 1)
        elif 75 < value <= 90:
            return (0.1, 0.3, 0.9, 1)
        else:
            return (1, 1, 1, 1)