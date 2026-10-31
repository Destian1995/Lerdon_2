
from db_lerdon_connect import *
from utils.helpers import format_number


PRIMARY_COLOR = get_color_from_hex('#2E7D32')
SECONDARY_COLOR = get_color_from_hex('#388E3C')
BACKGROUND_COLOR = get_color_from_hex('#212121')
TEXT_COLOR = get_color_from_hex('#FFFFFF')
INPUT_BACKGROUND = get_color_from_hex('#FFFFFF')

class ArmyButton(Button):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.background_normal = ''
        self.background_color = (0,0,0,0)
        self.color = TEXT_COLOR
        self.font_size = dp(18)
        self.bold = True
        self.size_hint = (1, None)
        self.height = dp(60)
        self.padding = (dp(20), dp(10))

        with self.canvas.before:
            Color(*PRIMARY_COLOR)
            self.rect = RoundedRectangle(
                radius=[dp(15)],
                pos=self.pos,
                size=self.size
            )

        self.bind(pos=self.update_rect, size=self.update_rect)

    def update_rect(self, *args):
        self.rect.pos = self.pos
        self.rect.size = self.size

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            Animation(background_color=(*SECONDARY_COLOR, 1), d=0.1).start(self)
        return super().on_touch_down(touch)

    def on_touch_up(self, touch):
        Animation(background_color=(*PRIMARY_COLOR, 1), d=0.2).start(self)
        return super().on_touch_up(touch)

class ArmyCash:
    def __init__(self, faction, class_faction, conn):
        """
        Инициализация класса ArmyCash.
        :param faction: Название фракции.
        :param class_faction: Экземпляр класса Faction (экономический модуль).
        """
        self.faction = faction
        self.class_faction = class_faction  # Экономический модуль
        self.conn = conn  # Подключение к
        self.cursor = self.conn.cursor()
        self.resources = self.load_resources()  # Загрузка начальных ресурсов

    def load_resources(self):
        """
        Загружает текущие ресурсы фракции из базы данных.
        """
        try:
            rows = self.load_data("resources", ["resource_type", "amount"], "faction = ?", (self.faction,))
            resources = {"Кроны": 0, "Рабочие": 0}
            for resource_type, amount in rows:
                if resource_type in resources:
                    resources[resource_type] = amount

            # Отладочный вывод: загруженные ресурсы
            print(f"[DEBUG] Загружены ресурсы для фракции '{self.faction}': {resources}")
            return resources
        except sqlite3.Error as e:
            print(f"Ошибка при загрузке ресурсов: {e}")
            return {"Кроны": 0, "Рабочие": 0}

    def load_data(self, table, columns, condition=None, params=None):
        """
        Универсальный метод для загрузки данных из таблицы базы данных.
        """
        try:
            query = f"SELECT {', '.join(columns)} FROM {table}"
            if condition:
                query += f" WHERE {condition}"
            self.cursor.execute(query, params or ())
            result = self.cursor.fetchall()

            # Отладочный вывод: SQL-запрос и результат
            print(f"[DEBUG] SQL-запрос: {query}, параметры: {params}")
            print(f"[DEBUG] Результат запроса: {result}")

            return result
        except sqlite3.Error as e:
            print(f"Ошибка при загрузке данных из таблицы {table}: {e}")
            return []

    def deduct_resources(self, crowns, workers):
        """
        Списывает ресурсы через экономический модуль.

        :param crowns: Количество крон для списания.
        :param workers: Количество рабочих для списания.
        :return: True, если ресурсы успешно списаны; False, если недостаточно ресурсов.
        """
        try:
            # Проверяем доступность ресурсов через экономический модуль
            current_crowns = self.class_faction.get_resource_now("Кроны")
            current_workers = self.class_faction.get_resource_now("Рабочие")

            print(f"[DEBUG] Текущие ресурсы: Кроны={current_crowns}, Рабочие={current_workers}")

            if current_crowns < crowns or current_workers < workers:
                print("[DEBUG] Недостаточно ресурсов для списания.")
                return False

            # Списываем ресурсы через экономический модуль
            self.class_faction.update_resource_now("Кроны", current_crowns - crowns)
            self.class_faction.update_resource_now("Рабочие", current_workers - workers)

            return True

        except Exception as e:
            print(f"Ошибка при списании ресурсов: {e}")
            return False

    def hire_unit(self, unit_name, unit_cost, quantity, unit_stats, unit_image):
        """
        Нанимает юнит (оружие), если ресурсов достаточно и соблюдены правила найма по классам.

        :param unit_name: Название юнита.
        :param unit_cost: Стоимость юнита в виде кортежа (кроны, рабочие).
        :param quantity: Количество нанимаемых юнитов.
        :param unit_stats: Характеристики юнита (должен быть словарём).
        :param unit_image: Путь к изображению юнита.
        :return: True, если найм успешен; False в противном случае.
        """
        crowns, workers = unit_cost
        required_crowns = int(crowns) * int(quantity)
        required_workers = int(workers) * int(quantity)

        # Проверка типа unit_stats
        if not isinstance(unit_stats, dict):
            print("[ERROR] unit_stats должен быть словарём!")
            return False

        # Получаем класс юнита
        try:
            unit_class_str = unit_stats.get("Класс юнита", "")
            unit_class = int(unit_class_str.split()[0])  # Например, "1 класс" -> 1
        except (ValueError, KeyError, IndexError):
            print(f"[ERROR] Не удалось определить класс юнита. Получено значение: '{unit_class_str}'")
            return False

        # --- Проверка ограничений по классу ДО списания ресурсов ---
        if unit_class == 1:
            # Класс 1 — можно нанимать всегда, без дополнительных проверок
            pass

        elif unit_class in [2, 3, 4]:
            # Герои: только один
            if quantity > 1:
                self.show_message(
                    title="Ошибка найма",
                    message=f"Можно нанять только одного героя {unit_class} класса."
                )
                return False

            # Проверяем, есть ли уже живой герой этого класса в armies или garrisons
            try:
                self.cursor.execute("""
                    SELECT 1
                    FROM armies
                    WHERE faction = ? AND (unit_class = ? OR unit_class LIKE ?)
                    LIMIT 1
                """, (self.faction, str(unit_class), f"{unit_class} %"))

                exists_in_armies = self.cursor.fetchone()

                # Проверка в garrisons через units
                self.cursor.execute("""
                    SELECT 1
                    FROM garrisons g
                    JOIN units u ON g.unit_name = u.unit_name
                    WHERE u.faction = ? AND CAST(u.unit_class AS INTEGER) = ?
                    LIMIT 1
                """, (self.faction, unit_class))

                exists_in_garrisons = self.cursor.fetchone()

                if exists_in_armies or exists_in_garrisons:
                    self.show_message(
                        title="Ошибка найма",
                        message=f"Герой {unit_class} класса уже существует у вашей фракции.\n"
                                f"Одновременно можно иметь только одного героя такого класса."
                    )
                    return False

            except sqlite3.Error as e:
                print(f"[ERROR] Ошибка при проверке существующего героя: {e}")
                return False

        else:
            self.show_message(
                title="Ошибка найма",
                message="Неизвестный класс юнита."
            )
            return False

        # Проверка наличия ресурсов (после всех проверок, чтобы не списывать при ошибке)
        if not self.deduct_resources(required_crowns, required_workers):
            self.show_message(
                title="Ошибка найма",
                message=f"Нанять юнитов невозможно: недостаточно ресурсов.\n"
                        f"Необходимые: {format_number(required_crowns)} крон и {format_number(required_workers)} рабочих."
            )
            return False

        # Добавление юнитов в базу данных
        self.add_or_update_army_unit(unit_name, quantity, unit_stats, unit_image)

        # Отображение сообщения об успехе
        self.show_message(
            title="Успех",
            message=f"{unit_name} нанят!\n"
                    f"Потрачено: {format_number(required_crowns)} крон и {format_number(required_workers)} рабочих."
        )

        return True

    def add_or_update_army_unit(self, unit_name, quantity, unit_stats, unit_image):
        """
        Добавляет или обновляет данные о юните в базе данных.
        """
        self.cursor.execute("""
            SELECT quantity, total_attack, total_defense, total_durability, unit_image
            FROM armies
            WHERE faction = ? AND unit_type = ?
        """, (self.faction, unit_name))
        result = self.cursor.fetchone()

        if result:
            # Если юнит уже существует, обновляем его данные
            current_quantity, total_attack, total_defense, total_durability, _ = result
            new_quantity = current_quantity + quantity
            self.cursor.execute("""
                UPDATE armies
                SET quantity = ?, total_attack = ?, total_defense = ?, total_durability = ?, unit_image = ?
                WHERE faction = ? AND unit_type = ?
            """, (
                new_quantity,
                total_attack + unit_stats["Урон"] * quantity,
                total_defense + unit_stats["Защита"] * quantity,
                total_durability + unit_stats["Живучесть"] * quantity,
                unit_image,  # Обновляем изображение
                self.faction,
                unit_name
            ))
        else:
            # Если юнит новый, добавляем его в базу
            self.cursor.execute("""
                INSERT INTO armies (faction, unit_type, quantity, total_attack, total_defense, total_durability, unit_class, unit_image)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                self.faction,
                unit_name,
                quantity,
                unit_stats["Урон"] * quantity,
                unit_stats["Защита"] * quantity,
                unit_stats["Живучесть"] * quantity,
                unit_stats["Класс юнита"],
                unit_image  # Добавляем изображение
            ))

        self.conn.commit()

    def hire_weapons(self, weapon_name, unit_cost, quantity):
        """
        Обновляет или создает запись в таблице weapons.
        :param unit_cost: кортеж, содержащий стоимость оружия в кронах и рабочих.
        """
        crowns, workers = unit_cost
        required_crowns = int(crowns) * int(quantity)
        required_workers = int(workers) * int(quantity)


        # Проверка наличия ресурсов
        if not self.deduct_resources(required_crowns, required_workers):
            self.show_message(
                title="Ошибка найма",
                message=f"Нанять юнитов невозможно: недостаточно ресурсов.\n"
                        f"Необходимые: {format_number(required_crowns)} крон и {format_number(required_workers)} рабочих."
            )
            return False
        return True

    def update_weapon_in_db(self, faction, weapon_name, quantity, damage, koef):
        """
        Обновляет или создает запись в таблице weapons.
        :param faction: Название фракции.
        :param weapon_name: Название оружия.
        :param quantity: Количество единиц оружия.
        :param damage: Урон оружия.
        :param koef: Коэффициент преодоления ПВО.
        """
        try:
            # Проверяем, существует ли запись для данного оружия
            self.cursor.execute('''
                SELECT quantity
                FROM weapons
                WHERE faction = ? AND weapon_name = ?
            ''', (faction, weapon_name))
            result = self.cursor.fetchone()

            if result:
                # Если запись существует, обновляем количество
                current_quantity = result[0]
                new_quantity = current_quantity + quantity
                self.cursor.execute('''
                    UPDATE weapons
                    SET quantity = ?, damage = ?, koef = ?
                    WHERE faction = ? AND weapon_name = ?
                ''', (new_quantity, damage, koef, faction, weapon_name))
            else:
                # Если запись отсутствует, создаем новую
                self.cursor.execute('''
                    INSERT INTO weapons (faction, weapon_name, quantity, damage, koef)
                    VALUES (?, ?, ?, ?, ?)
                ''', (faction, weapon_name, quantity, damage, koef))

            self.conn.commit()
            print(f"[DEBUG] Данные оружия '{weapon_name}' успешно обновлены в таблице weapons.")

        except sqlite3.Error as e:
            print(f"Ошибка при обновлении таблицы weapons: {e}")

    def show_message(self, title, message):
        # Определяем акцент по заголовку
        is_error = 'ошибк' in title.lower()
        acc = (0.72, 0.18, 0.18, 1) if is_error else (0.20, 0.55, 0.88, 1)
        sep = (0.78, 0.18, 0.18, 0.85) if is_error else (0.20, 0.55, 0.88, 0.7)
        title_clr = (1, 0.55, 0.55, 1) if is_error else (0.65, 0.88, 1, 1)

        content_layout = BoxLayout(
            orientation='vertical',
            padding=[dp(14), dp(10), dp(14), dp(12)],
            spacing=dp(10)
        )

        message_label = Label(
            text=message,
            color=(0.94, 0.94, 0.94, 1),
            font_size=sp(14),
            halign='center',
            valign='middle',
            markup=True
        )
        message_label.bind(size=message_label.setter('text_size'))
        content_layout.add_widget(message_label)

        close_button = Button(
            text="Закрыть",
            font_size=sp(14),
            size_hint_y=None,
            height=dp(40),
            background_color=(0, 0, 0, 0),
            color=(1, 1, 1, 1),
            bold=True
        )
        with close_button.canvas.before:
            close_button._bc = Color(*acc)
            close_button._br = RoundedRectangle(
                pos=close_button.pos, size=close_button.size, radius=[dp(10)]
            )
        close_button.bind(
            pos=lambda i, v: setattr(i._br, 'pos', v),
            size=lambda i, v: setattr(i._br, 'size', v)
        )
        content_layout.add_widget(close_button)

        _is_mobile = platform in ('android', 'ios')
        popup = Popup(
            title='',
            separator_height=0,
            content=content_layout,
            size_hint=(0.90 if _is_mobile else 0.78, 0.32 if _is_mobile else 0.28),
            auto_dismiss=False,
            background_color=(0.07, 0.08, 0.13, 0.95),
            background='',
        )
        close_button.bind(on_release=popup.dismiss)
        popup.open()


def load_unit_data(faction, conn):
    """Загружает данные о юнитах для выбранной фракции из базы данных."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT unit_name, consumption, cost_money, cost_time, image_path, attack, defense, durability, unit_class
        FROM units WHERE faction = ?
    """, (faction,))
    rows = cursor.fetchall()

    unit_data = {}
    for row in rows:
        unit_name, consumption, cost_money, cost_time, image_path, attack, defense, durability, unit_class = row
        unit_data[unit_name] = {
            "cost": [cost_money, cost_time],
            "image": image_path,
            "stats": {
                "Урон": attack,
                "Защита": defense,
                "Живучесть": durability,
                "Класс юнита": unit_class,
                "Потребление Кристаллов": consumption
            }
        }
    return unit_data


def start_army_mode(faction, game_area, class_faction, conn):
    """Open the shared strategy recruitment window with lazy unit cards."""
    from recruitment_ui import RecruitmentSession
    session = RecruitmentSession(faction, ArmyCash(faction, class_faction, conn),
                                 load_unit_data(faction, conn), broadcast_units)
    game_area.add_widget(session)
    session.open()
    return session


def broadcast_units(unit_name, unit_cost, quantity_input, army_hire, image, unit_stats):
    try:
        # Если input передан — берём оттуда, иначе — один юнит
        if quantity_input is not None:
            qty_text = quantity_input.text.strip()
            quantity = int(qty_text) if qty_text else 0
        else:
            quantity = 1

        if quantity <= 0:
            raise ValueError("Количество должно быть положительным числом")

        army_hire.hire_unit(
            unit_name=unit_name,
            unit_cost=unit_cost,
            quantity=quantity,
            unit_stats=unit_stats,
            unit_image=image
        )

    except ValueError as e:
        show_army_message(
            title="Ошибка",
            message=f"[color=#FF0000]{str(e) or 'Введите корректное число!'}[/color]"
        )

def show_army_message(title, message):
    is_error = 'ошибк' in title.lower()
    acc = (0.72, 0.18, 0.18, 1) if is_error else (0.20, 0.55, 0.88, 1)
    sep = (0.78, 0.18, 0.18, 0.85) if is_error else (0.20, 0.55, 0.88, 0.7)
    title_clr = (1, 0.55, 0.55, 1) if is_error else (0.65, 0.88, 1, 1)

    content = BoxLayout(orientation='vertical', padding=[dp(14), dp(10), dp(14), dp(12)], spacing=dp(10))

    lbl = Label(
        text=message, markup=True,
        font_size=sp(14), color=(0.94, 0.94, 0.94, 1),
        halign='center', valign='middle'
    )
    lbl.bind(size=lbl.setter('text_size'))
    content.add_widget(lbl)

    btn = Button(
        text="Закрыть", size_hint_y=None, height=dp(40),
        background_color=(0, 0, 0, 0), color=(1, 1, 1, 1),
        font_size=sp(14), bold=True
    )
    with btn.canvas.before:
        btn._bc = Color(*acc)
        btn._br = RoundedRectangle(pos=btn.pos, size=btn.size, radius=[dp(10)])
    btn.bind(pos=lambda i, v: setattr(i._br, 'pos', v),
             size=lambda i, v: setattr(i._br, 'size', v))
    content.add_widget(btn)

    is_mobile = platform in ('android', 'ios')
    popup = Popup(
        title=title, content=content,
        size_hint=(0.90 if is_mobile else 0.78, 0.42 if is_mobile else 0.34),
        background_color=(0.07, 0.08, 0.13, 1),
        separator_color=sep,
        title_color=title_clr,
        title_size=sp(17) if is_mobile else sp(15), title_align='center',
        auto_dismiss=False
    )
    btn.bind(on_release=popup.dismiss)
    popup.open()

def set_font_size(relative_size):
    """Вычисляет размер шрифта относительно размера окна"""
    from kivy.core.window import Window
    return Window.width * relative_size

#---------------------------------------------------------------
class StyledButton(Button):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        with self.canvas.before:
            Color(0.2, 0.6, 0.8, 1)  # Основной цвет кнопки
            self.rect = RoundedRectangle(radius=[20], size=self.size, pos=self.pos)
        self.bind(pos=self.update_rect, size=self.update_rect)

    def update_rect(self, *args):
        self.rect.pos = self.pos
        self.rect.size = self.size
        # Фиксируем радиус закругления
        self.rect.radius = [20]

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            # Сохраняем радиус при анимации
            self.rect.size = (self.size[0] - 5, self.size[1] - 5)
            self.rect.radius = [20]  # Форсируем обновление радиуса
        return super().on_touch_down(touch)

    def on_touch_up(self, touch):
        if self.collide_point(*touch.pos):
            self.rect.size = self.size
            self.rect.radius = [20]  # Форсируем обновление радиуса
        return super().on_touch_up(touch)
