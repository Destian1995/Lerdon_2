from kivy.uix.checkbox import CheckBox

from db_lerdon_connect import *
from heroes import open_artifacts_popup
from create_artifacts import workshop
from utils.helpers import format_number


def save_building_change(faction_name, city, building_type, delta, conn):
    """
    Обновляет количество зданий для указанного города в базе данных.
    delta — изменение (например, +1 или -1).
    """

    cursor = conn.cursor()

    try:
        # Проверяем, существует ли запись для данного города и типа здания
        cursor.execute('''
            SELECT count 
            FROM buildings 
            WHERE city_name = ? AND faction = ? AND building_type = ?
        ''', (city, faction_name, building_type))
        row = cursor.fetchone()

        if row:
            # Обновляем существующую запись
            new_count = row[0] + delta
            if new_count < 0:
                new_count = 0  # Предотвращаем отрицательные значения
            cursor.execute('''
                UPDATE buildings 
                SET count = ? 
                WHERE city_name = ? AND faction = ? AND building_type = ?
            ''', (new_count, city, faction_name, building_type))
        else:
            # Добавляем новую запись
            cursor.execute('''
                INSERT INTO buildings (city_name, faction, building_type, count)
                VALUES (?, ?, ?, ?)
            ''', (city, faction_name, building_type, delta))

        conn.commit()
    except sqlite3.Error as e:
        print(f"Ошибка при сохранении изменений в зданиях: {e}")


class Faction:
    def __init__(self, name, conn):
        self.faction = name
        self.conn = conn
        self.cursor = self.conn.cursor()
        self.resources = self.load_resources_from_db()  # Загрузка ресурсов
        self.buildings = self.load_buildings()  # Загрузка зданий
        self.trade_agreements = self.load_trade_agreements()
        self.city_count = 0
        self.cities = self.load_cities()  # Загрузка городов
        self.hospitals = 0
        self.factories = 0
        self.walls = 0
        self.markets = 0
        self.smithies = 0
        self.towers = 0
        self.taxes = 0
        self.food_info = 0
        self.work_peoples = 0
        self.money_info = 0
        self.born_peoples = 0
        self.money_up = 0
        self.taxes_info = 0
        self.food_peoples = 0
        self.tax_effects = 0
        self.clear_up_peoples = 0
        self.current_consumption = 0
        self.turn = 0
        self.last_turn_loaded = -1  # Последний загруженный номер хода
        self.raw_material_price_history = []  # История цен на еду
        self.current_tax_rate = 0  # Начальная ставка налога — по умолчанию 0%
        self.turns = 0  # Счетчик ходов
        self.tax_set = False  # Флаг, установлен ли налог
        self.custom_tax_rate = 0  # Новый атрибут для хранения пользовательской ставки налога
        self.auto_build_enabled = False
        self.auto_build_ratio = (1, 1)  # По умолчанию 1:1
        self.load_auto_build_settings()
        self.cities_buildings = {city['name']: {'Больница': 0, 'Фабрика': 0} for city in self.cities}

        self.resources = {
            'Кроны': self.money,
            'Рабочие': self.free_peoples,
            'Кристаллы': self.raw_material,
            'Население': self.population,
            'Потребление': self.current_consumption,
            'Лимит Армии': self.max_army_limit
        }
        self.economic_params = {
            "Север": {"tax_rate": 0.12},
            "Эльфы": {"tax_rate": 0.08},
            "Вампиры": {"tax_rate": 0.06},
            "Адепты": {"tax_rate": 0.04},
            "Элины": {"tax_rate": 0.03},
        }

        self.is_first_run = True  # Флаг для первого запуска
        self._on_resources_changed = None  # Callback для моментального обновления UI
        self.generate_raw_material_price()  # Генерация начальной цены на еду

    def load_data(self, table, columns, condition=None, params=None):
        """
        Универсальный метод для загрузки данных из таблицы базы данных.
        :param table: Имя таблицы.
        :param columns: Список колонок для выборки.
        :param condition: Условие WHERE (строка).
        :param params: Параметры для условия.
        :return: Список кортежей с данными.
        """
        try:
            query = f"SELECT {', '.join(columns)} FROM {table}"
            if condition:
                query += f" WHERE {condition}"
            self.cursor.execute(query, params or ())
            return self.cursor.fetchall()
        except sqlite3.Error as e:
            return []

    def _get_supplied_cities(self):
        """
        Возвращает множество названий городов фракции, которые связаны
        дорогами с основной территорией (наибольшая связная компонента).
        Города вне основной территории считаются отрезанными от снабжения.
        """
        try:
            self.cursor.execute("SELECT id, name, faction FROM cities")
            all_cities = self.cursor.fetchall()
            id_to_name = {cid: name for cid, name, _ in all_cities}
            id_to_faction = {cid: faction for cid, _, faction in all_cities}
            own_city_ids = {cid for cid, faction in id_to_faction.items() if faction == self.faction}

            if not own_city_ids:
                return set()

            self.cursor.execute("SELECT city1, city2 FROM roads")
            all_roads = self.cursor.fetchall()
            adjacency = {}
            for c1, c2 in all_roads:
                adjacency.setdefault(c1, []).append(c2)
                adjacency.setdefault(c2, []).append(c1)

            # Находим все связные компоненты среди городов фракции
            visited = set()
            components = []
            for start_id in own_city_ids:
                if start_id in visited:
                    continue
                component = set()
                queue = [start_id]
                visited.add(start_id)
                while queue:
                    current = queue.pop(0)
                    component.add(current)
                    for neighbor in adjacency.get(current, []):
                        if neighbor in visited or neighbor not in own_city_ids:
                            continue
                        visited.add(neighbor)
                        queue.append(neighbor)
                components.append(component)

            if not components:
                return set()

            main_component = max(components, key=len)
            return {id_to_name[cid] for cid in main_component}
        except Exception as e:
            print(f"[ERROR] _get_supplied_cities: {e}")
            # Фоллбэк: все города фракции
            try:
                self.cursor.execute("SELECT name FROM cities WHERE faction = ?", (self.faction,))
                return {r[0] for r in self.cursor.fetchall()}
            except Exception:
                return set()

    def load_resources(self):
        """Загружает ресурсы из таблицы resources."""
        rows = self.load_data("resources", ["resource_type", "amount"], "faction = ?", (self.faction,))
        resources = {"Рабочие": 0, "Кроны": 0, "Кристаллы": 0, "Население": 0}
        for resource_type, amount in rows:
            resources[resource_type] = amount
        return resources

    def load_auto_build_settings(self):
        conn = self.conn
        cursor = conn.cursor()
        cursor.execute('''
            SELECT enabled, hospitals_ratio, factories_ratio 
            FROM auto_build_settings 
            WHERE faction = ?
        ''', (self.faction,))
        result = cursor.fetchone()

        if result:
            self.auto_build_enabled = bool(result[0])
            # Сохраняем пропорцию как кортеж целых чисел
            self.auto_build_ratio = (result[1], result[2])
        else:
            self.auto_build_ratio = (1, 1)  # Значение по умолчанию

    def save_auto_build_settings(self):
        conn = self.conn
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO auto_build_settings 
            (faction, enabled, hospitals_ratio, factories_ratio)
            VALUES (?, ?, ?, ?)
        ''', (self.faction, int(self.auto_build_enabled),
              self.auto_build_ratio[0], self.auto_build_ratio[1]))
        conn.commit()

    def city_has_space(self, city_name):
        current = self.cities_buildings.get(city_name, {"Больница": 0, "Фабрика": 0})
        return current["Больница"] + current["Фабрика"] < 25

    # Основной метод автоматического строительства
    def auto_build(self):
        """
        Рассчитывает количество возможных зданий на основе текущих ресурсов
        и передает результат в методы build_factory и build_hospital.
        Учитывает лимит в 10 зданий на город и минимальное количество крон (200).
        """
        if not self.auto_build_enabled:
            return

        # Проверяем, достаточно ли денег для строительства
        if self.money < 10:
            print("Недостаточно крон для авто-строительства. Минимум требуется 200 крон.")
            return

        print("Проверка доступных городов перед загрузкой:", self.cities)
        # Загружаем актуальные данные о городах и зданиях
        self.load_cities()
        self.load_buildings()

        # Получаем соотношение из настроек авто-строительства
        hospitals_ratio, factories_ratio = self.auto_build_ratio
        total_per_cycle = hospitals_ratio + factories_ratio

        if total_per_cycle == 0:
            return

        # Определяем стоимость одного цикла строительства
        hospital_cost = 15
        factory_cost = 10
        cost_per_cycle = hospitals_ratio * hospital_cost + factories_ratio * factory_cost

        if cost_per_cycle == 0:
            return

        # Проверяем доступные ресурсы
        max_cycles_by_money = self.money // cost_per_cycle
        if max_cycles_by_money == 0:
            return

        # Проверяем доступное место в городах
        available_cities = []
        print("Проверка доступных городов после загрузки:", self.cities)
        for city in self.cities:
            city_name = city['name']
            current_buildings = self.cities_buildings.get(city_name, {"Больница": 0, "Фабрика": 0})
            total_current = current_buildings["Больница"] + current_buildings["Фабрика"]
            space_left = 25 - total_current
            available_cities.extend([city_name] * (space_left // total_per_cycle))

        # Если доступных городов нет, завершаем выполнение
        if not available_cities:
            print("Нет доступных городов для строительства.")
            return

        max_cycles_by_cities = len(available_cities) // total_per_cycle
        max_full_cycles = min(max_cycles_by_money, max_cycles_by_cities)

        if max_full_cycles == 0:
            print("Недостаточно ресурсов или места в городах для строительства.")
            return

        # Рассчитываем общее количество зданий
        total_hospitals = hospitals_ratio * max_full_cycles
        total_factories = factories_ratio * max_full_cycles
        total_cost = max_full_cycles * cost_per_cycle

        # Списываем средства
        if not self.cash_build(total_cost):
            print("Не удалось списать средства для строительства.")
            return

        # Распределяем здания по городам
        try:
            # ✅ Исправленная строка: используем int() для округления
            selected_count = int(max_full_cycles * total_per_cycle)
            # Дополнительно проверим, чтобы не превысить длину available_cities
            selected_count = min(selected_count, len(available_cities))
            selected_cities = random.sample(available_cities, selected_count)
        except ValueError:
            print("Ошибка при выборе городов. Возможно, недостаточно доступных городов.")
            return

        try:
            # Группируем здания по городам
            city_buildings = {}
            for i in range(total_hospitals):
                city = selected_cities[i]
                if self.city_has_space(city):  # Проверяем, есть ли место в городе
                    if city not in city_buildings:
                        city_buildings[city] = {"Больница": 0, "Фабрика": 0}
                    city_buildings[city]["Больница"] += 1

            for i in range(total_hospitals, total_hospitals + total_factories):
                city = selected_cities[i]
                if self.city_has_space(city):  # Проверяем, есть ли место в городе
                    if city not in city_buildings:
                        city_buildings[city] = {"Больница": 0, "Фабрика": 0}
                    city_buildings[city]["Фабрика"] += 1

            # Строим здания за один вызов для каждого города
            for city, buildings in city_buildings.items():
                if buildings["Больница"] > 0:
                    self.build_hospital(city, quantity=buildings["Больница"])
                if buildings["Фабрика"] > 0:
                    self.build_factory(city, quantity=buildings["Фабрика"])

            # Пересчитываем общие показатели один раз после всех построек
            self.load_buildings()

        except Exception as e:
            print(f"Ошибка в авто-строительстве: {e}")

    def load_buildings(self):
        """
        Загружает данные о зданиях для текущей фракции из таблицы buildings.
        """
        try:
            self.cursor.execute('''
                SELECT city_name, building_type, count
                FROM buildings
                WHERE faction = ?
            ''', (self.faction,))
            rows = self.cursor.fetchall()

            # Сброс текущих данных о зданиях
            self.cities_buildings = {}
            total_hospitals = 0
            total_factories = 0
            total_walls = 0
            total_markets = 0
            total_smithies = 0
            total_towers = 0

            for row in rows:
                city_name, building_type, count = row
                if city_name not in self.cities_buildings:
                    self.cities_buildings[city_name] = {
                        "Больница": 0, "Фабрика": 0,
                        "Стена": 0, "Рынок": 0, "Кузница": 0, "Вышка": 0
                    }

                if building_type in self.cities_buildings.get(city_name, {}):
                    self.cities_buildings[city_name][building_type] += count

                if building_type == "Больница":
                    total_hospitals += count
                elif building_type == "Фабрика":
                    total_factories += count
                elif building_type == "Стена":
                    total_walls += count
                elif building_type == "Рынок":
                    total_markets += count
                elif building_type == "Кузница":
                    total_smithies += count
                elif building_type == "Вышка":
                    total_towers += count

            # Обновление глобальных показателей
            self.hospitals = total_hospitals
            self.factories = total_factories
            self.walls = total_walls
            self.markets = total_markets
            self.smithies = total_smithies
            self.towers = total_towers

        except sqlite3.Error as e:
            print(f"Ошибка при загрузке зданий: {e}")

    def load_trade_agreements(self):
        """Загружает данные о торговых соглашениях для текущей фракции из таблицы trade_agreements."""
        rows = self.load_data(
            "trade_agreements",
            ["initiator_faction", "target_faction", "initiator_type_resource",
             "initiator_summ_resource", "target_type_resource", "target_summ_resource"],
            "initiator_faction = ? OR target_faction = ?",
            (self.faction, self.faction)
        )
        trade_agreements = []
        for row in rows:
            trade_agreements.append({
                "initiator_faction": row[0],
                "target_faction": row[1],
                "initiator_type_resource": row[2],
                "initiator_summ_resource": row[3],
                "target_type_resource": row[4],
                "target_summ_resource": row[5]
            })
        return trade_agreements

    def load_cities(self):
        """
        Загружает список городов для текущей фракции из таблицы cities.
        Не перезаписывает существующие данные о зданиях в городах.
        """

        rows = self.load_data("cities", ["name", "coordinates"], "faction = ?", (self.faction,))
        print(f"[DEBUG ROWS CITY!]:{rows}")
        cities = []
        self.city_count = 0

        for row in rows:
            name, coordinates = row
            try:
                coordinates = coordinates.strip('[]')
                x, y = map(int, coordinates.split(','))
            except ValueError:
                print(f"Ошибка при разборе координат для города {name}: {coordinates}")
                x, y = 0, 0

            cities.append({"name": name, "x": x, "y": y})

            # Не перезаписываем, если уже есть данные о зданиях
            if name not in self.cities_buildings:
                self.cities_buildings[name] = {'Больница': 0, 'Фабрика': 0}

            self.city_count += 1
        self.cities = cities
        return cities

    def build_factory(self, city, quantity=1):
        """Увеличить количество фабрик в указанном городе на заданное количество."""
        if city not in self.cities_buildings:
            self.cities_buildings[city] = {'Больница': 0, 'Фабрика': 0}
        self.cities_buildings[city]['Фабрика'] += quantity
        save_building_change(self.faction, city, "Фабрика", quantity, self.conn)

    def build_hospital(self, city, quantity=1):
        """Увеличить количество больниц в указанном городе на заданное количество."""
        if city not in self.cities_buildings:
            self.cities_buildings[city] = {'Больница': 0, 'Фабрика': 0}
        self.cities_buildings[city]['Больница'] += quantity
        save_building_change(self.faction, city, "Больница", quantity, self.conn)

    def cash_build(self, money):
        """Списывает деньги, если их хватает, и возвращает True, иначе False."""
        if self.money >= money:
            self.money -= money
            self._sync_resources()
            self.save_resources_to_db()
            return True
        else:
            return False

    def get_income_per_person(self):
        """Получение дохода с одного человека для данной фракции."""
        if self.tax_set and self.custom_tax_rate is not None:
            return self.custom_tax_rate
        params = self.economic_params[self.faction]
        return params["tax_rate"]

    def calculate_tax_income(self):
        """Расчет дохода от налогов с учетом установленной ставки."""
        if not self.tax_set:
            print("Налог не установлен. Прироста от налогов нет.")
            self.taxes = 0
        else:
            # Используем пользовательскую ставку налога или базовую, если пользовательская не задана
            tax_rate = self.custom_tax_rate if self.custom_tax_rate is not None else self.get_base_tax_rate()
            self.taxes = self.population * tax_rate  # Применяем базовую налоговую ставку
        return self.taxes

    def set_taxes(self, new_tax_rate):
        """
        Установка нового уровня налогов и обновление ресурсов.
        """
        self.custom_tax_rate = self.get_base_tax_rate() * new_tax_rate
        self.tax_set = True
        self.calculate_tax_income()

    def tax_effect(self, tax_rate):
        """
        Рассчитывает процентное изменение населения на основе ставки налога.
        :param tax_rate: Текущая ставка налога (в процентах).
        :return: Процент изменения населения (положительное или отрицательное значение).
        """
        if tax_rate >= 90:
            return -89  # Критическая убыль населения (-89%)
        elif 80 <= tax_rate < 90:
            return -51  # Значительная убыль населения (-51%)
        elif 65 <= tax_rate < 80:
            return -37  # Умеренная убыль населения (-37%)
        elif 45 <= tax_rate < 65:
            return -15  # Умеренная убыль населения (-15%)
        elif 35 <= tax_rate < 45:
            return -4  # Небольшая убыль населения (-4%)
        elif 25 <= tax_rate < 35:
            return 0  # Нейтральный эффект (0%)
        elif 16 <= tax_rate < 25:
            return 11  # Небольшой рост (5%)
        elif 10 <= tax_rate < 16:
            return 20  # Небольшой рост населения (+20%)
        elif 1 <= tax_rate < 10:
            return 32  # Небольшой рост населения (+32%)
        else:
            return 57  # Существенный рост населения (+57%)

    def apply_tax_effect(self, tax_rate):
        """
        Применяет эффект налогов на население в виде процентного изменения.
        :param tax_rate: Текущая ставка налога (в процентах).
        :return: Абсолютное изменение населения.
        """
        # Получаем процентное изменение населения
        percentage_change = self.tax_effect(tax_rate)

        # Загружаем текущее население из базы данных
        try:
            self.cursor.execute('''
                SELECT amount
                FROM resources
                WHERE faction = ? AND resource_type = "Население"
            ''', (self.faction,))
            row = self.cursor.fetchone()
            current_population = row[0] if row else 0
        except sqlite3.Error as e:
            print(f"Ошибка при загрузке данных о населении: {e}")
            current_population = 0

        # Рассчитываем абсолютное изменение населения
        population_change = int(current_population * (percentage_change / 100))

        # Применяем эффект налогов
        self.tax_effects = population_change
        return self.tax_effects

    def calculate_base_tax_rate(self, tax_rate):
        """Формула расчёта базовой налоговой ставки для текущей фракции."""
        params = self.economic_params[self.faction]
        base_tax_rate = params["tax_rate"]  # Базовая ставка налога для текущей фракции

        # Формируем корректировочный коэффициент на основе введённой ставки
        multiplier = tax_rate
        # Возвращаем корректированную налоговую ставку
        return base_tax_rate * multiplier

    def get_base_tax_rate(self):
        """Получение базовой налоговой ставки для текущей фракции."""
        return self.economic_params[self.faction]["tax_rate"]

    def show_popup(self, title, message):
        """Отображает всплывающее окно с сообщением."""
        popup = Popup(title=title, content=Label(text=message), size_hint=(0.6, 0.4))
        popup.open()

    def load_available_buildings_from_db(self):
        """
        Загружает список доступных зданий для текущей фракции из базы данных.
        """
        try:
            self.cursor.execute('''
                SELECT DISTINCT building_type
                FROM buildings
                WHERE faction = ?
            ''', (self.faction,))
            rows = self.cursor.fetchall()
            return [row[0] for row in rows]  # Возвращаем список типов зданий
        except sqlite3.Error as e:
            print(f"Ошибка при загрузке зданий: {e}")
            return []

    def update_cash(self):
        """
        Синхронизирует и сохраняет ресурсы в БД.
        НЕ перезагружает из БД — использует актуальные in-memory значения.
        """
        self.recalculate_consumption()
        self._sync_resources()
        self.save_resources_to_db()
        return self.resources

    def check_resource_availability(self, resource_type, required_amount):
        """
        Проверяет, достаточно ли у фракции ресурсов для выполнения сделки.

        :param resource_type: Тип ресурса (например, "Кристаллы", "Кроны", "Рабочие", "Население").
        :param required_amount: Требуемое количество ресурсов.
        :return: True, если ресурсов достаточно, иначе False.
        """
        # Убедимся, что required_amount является числом и не отрицательным
        if not isinstance(required_amount, (int, float)) or required_amount < 0:
            print(f"Некорректное требуемое количество ресурсов: {required_amount}")
            return False

        # Получаем текущее значение ресурса из словаря self.resources
        current_amount = self.resources.get(resource_type, 0)

        # Если значение None или некорректное, считаем его равным 0
        if current_amount is None or not isinstance(current_amount, (int, float)):
            current_amount = 0

        # Проверяем, достаточно ли ресурсов
        if current_amount >= required_amount:
            return True
        else:
            print(f"Недостаточно ресурсов типа '{resource_type}': "
                  f"требуется {required_amount}, доступно {current_amount}")
            return False

    def update_resource_deals(self, resource_type='', amount=''):
        """
        Обновляет количество ресурсов фракции на указанное значение.

        :param resource_type: Тип ресурса (например, "Кристаллы", "Кроны", "Рабочие", "Население").
        :param amount: Изменение количества ресурсов (положительное или отрицательное).
        """
        if resource_type == "Кристаллы":
            self.resources['Кристаллы'] += amount
        elif resource_type == "Кроны":
            self.resources['Кроны'] += amount
        elif resource_type == "Население":
            self.resources['Население'] += amount
        elif resource_type == "Рабочие":
            self.resources['Рабочие'] += amount
        else:
            raise ValueError(f"Неизвестный тип ресурса: {resource_type}")

    def update_trade_resources_from_db(self):
        try:
            # 1. Обработка и УДАЛЕНИЕ отклонённых сделок (agree = 2)
            self.cursor.execute('''
                SELECT id, initiator, target_faction 
                FROM trade_agreements 
                WHERE (initiator = ? OR target_faction = ?) AND agree = 2
            ''', (self.faction, self.faction))

            rejected_rows = self.cursor.fetchall()
            rejected_ids = []

            for row in rejected_rows:
                trade_id, initiator, target_faction = row
                rejected_ids.append(trade_id)

                if initiator == self.faction:
                    show_message("Отказ", f"{target_faction} свернули сделку...\n(возможно у них кончились ресурсы)")
                elif target_faction == self.faction:
                    show_message("Отказ", f"{initiator} свернули сделку...\n(возможно у них кончились ресурсы)")

            # Удаляем отклонённые сделки СРАЗУ
            for trade_id in rejected_ids:
                self.cursor.execute('DELETE FROM trade_agreements WHERE id = ?', (trade_id,))

            # 2. Обработка подтверждённых сделок (agree = 1)
            self.cursor.execute('''
                SELECT id, initiator, target_faction, initiator_type_resource, 
                       initiator_summ_resource, target_type_resource, target_summ_resource
                FROM trade_agreements 
                WHERE (initiator = ? OR target_faction = ?) AND agree = 1
            ''', (self.faction, self.faction))

            rows = self.cursor.fetchall()
            completed_trades = []
            failed_trades = []  # Для отслеживания "зависших" сделок

            for row in rows:
                trade_id, initiator, target_faction, initiator_type_resource, \
                    initiator_summ_resource, target_type_resource, target_summ_resource = row

                try:
                    # Проверка ресурсов ДО показа сообщений
                    if initiator == self.faction:
                        if initiator_summ_resource and initiator_type_resource:
                            if not self.check_resource_availability(initiator_type_resource, initiator_summ_resource):
                                print(f"Недостаточно ресурсов для сделки {trade_id}. Сделка отложена.")
                                failed_trades.append(trade_id)
                                continue

                            self.update_resource_deals(initiator_type_resource, -initiator_summ_resource)

                        if target_summ_resource and target_type_resource:
                            self.update_resource_deals(target_type_resource, target_summ_resource)
                            show_message(initiator_type_resource, f"{target_faction} прислали ресурсы!")

                    elif target_faction == self.faction:
                        if target_summ_resource and target_type_resource:
                            if not self.check_resource_availability(target_type_resource, target_summ_resource):
                                print(f"Недостаточно ресурсов для сделки {trade_id}. Сделка отложена.")
                                failed_trades.append(trade_id)
                                continue

                            self.update_resource_deals(target_type_resource, -target_summ_resource)

                        if initiator_summ_resource and initiator_type_resource:
                            self.update_resource_deals(initiator_type_resource, initiator_summ_resource)
                            show_message(target_type_resource, f"{initiator} прислали ресурсы!")

                    completed_trades.append(trade_id)
                    print(f"Сделка успешно выполнена: {trade_id}")

                except Exception as e:
                    print(f"Ошибка при обработке сделки {trade_id}: {e}")
                    failed_trades.append(trade_id)

            # Удаляем успешно выполненные сделки
            for trade_id in completed_trades:
                self.cursor.execute('DELETE FROM trade_agreements WHERE id = ?', (trade_id,))

            self.save_resources_to_db()

        except sqlite3.Error as e:
            print(f"Ошибка при обновлении ресурсов: {e}")

    def recalculate_consumption(self):
        """
        Пересчитывает текущее потребление армии на основе данных из таблицы garrisons.
        Обновляет атрибуты current_consumption и ресурс 'Потребление'.
        """
        try:
            self.current_consumption = 0
            # Выгрузка всех гарнизонов фракции
            self.cursor.execute("""
                SELECT g.unit_name, g.unit_count, u.consumption
                FROM garrisons g
                JOIN units u ON g.unit_name = u.unit_name
                WHERE u.faction = ?
            """, (self.faction,))
            rows = self.cursor.fetchall()

            for unit_name, unit_count, consumption in rows:
                self.current_consumption += consumption * unit_count

            # Обновляем ресурс в словаре
            self.resources['Потребление'] = self.current_consumption

            return self.current_consumption

        except sqlite3.Error as e:
            print(f"Ошибка при пересчёте потребления: {e}")
            return self.current_consumption

    def load_resources_from_db(self):
        """
        Загружает текущие ресурсы фракции из таблицы resources.
        """
        try:
            self.cursor.execute('''
                SELECT resource_type, amount
                FROM resources
                WHERE faction = ?
            ''', (self.faction,))
            rows = self.cursor.fetchall()

            # Инициализация ресурсов по умолчанию
            self.money = 0
            self.free_peoples = 0
            self.raw_material = 0
            self.population = 0
            self.current_consumption = 0
            # Лимит армии рассчитывается динамически, но потребление загружаем

            # Обновление ресурсов на основе данных из базы данных
            for resource_type, amount in rows:
                if resource_type == "Кроны":
                    self.money = amount
                elif resource_type == "Рабочие":
                    self.free_peoples = amount
                elif resource_type == "Кристаллы":
                    self.raw_material = amount
                elif resource_type == "Население":
                    self.population = amount
                elif resource_type == "Потребление":  # ← Добавлено
                    self.current_consumption = amount

        except sqlite3.Error as e:
            print(f"Ошибка при загрузке ресурсов: {e}")

    def save_resources_to_db(self):
        """
        Сохраняет текущие ресурсы фракции в таблицу resources.
        Использует batch UPDATE для минимизации обращений к БД.
        """
        try:
            update_data = [
                (amount, self.faction, resource_type)
                for resource_type, amount in self.resources.items()
            ]
            self.cursor.executemany('''
                UPDATE resources
                SET amount = ?
                WHERE faction = ? AND resource_type = ?
            ''', update_data)
            self.conn.commit()
        except sqlite3.Error as e:
            print(f"Ошибка при сохранении ресурсов: {e}")

    @property
    def max_army_limit(self):
        """
        Динамически рассчитывает максимальный лимит армии
        на основе базового значения, бонуса от городов и Вышек.
        """
        base_limit = 4000
        city_bonus = 1000 * self.city_count
        tower_bonus = 500 * self.towers  # +500 за каждую Вышку
        return base_limit + city_bonus + tower_bonus

    def load_relations(self):
        """
        Загружает текущие отношения из таблицы relations в базе данных.
        Возвращает словарь, где ключи — названия фракций, а значения — уровни отношений.
        """
        try:
            self.cursor.execute('''
                SELECT faction2, relationship
                FROM relations
                WHERE faction1 = ?
            ''', (self.faction,))
            rows = self.cursor.fetchall()

            # Преобразуем результат в словарь, преобразуя значения в числа
            relations = {faction2: int(relationship) for faction2, relationship in rows}
            return relations

        except sqlite3.Error as e:
            print(f"Ошибка при загрузке отношений из таблицы relations: {e}")
            return {}

    def load_political_system(self):
        """
        Загружает текущую политическую систему фракции из базы данных.
        """
        try:
            query = "SELECT system FROM political_systems WHERE faction = ?"
            self.cursor.execute(query, (self.faction,))
            result = self.cursor.fetchone()
            return result[0] if result else "Смирение"  # По умолчанию "Смирение"
        except sqlite3.Error as e:
            print(f"Ошибка при загрузке политической системы: {e}")
            return "Смирение"

    def _get_council_bonuses(self):
        """Рассчитывает бонусы от советников с лояльностью > 50%."""
        import json
        crowns_pct = 0
        crystals_pct = 0
        try:
            self.cursor.execute("SELECT loyalty, ideology FROM nobles WHERE status = 'active'")
            for loyalty, ideology_str in self.cursor.fetchall():
                if loyalty < 50:
                    continue
                bonus_pct = min(int((loyalty - 50) / 5), 10)

                try:
                    if isinstance(ideology_str, str) and ideology_str.startswith('{'):
                        traits = json.loads(ideology_str)
                    elif isinstance(ideology_str, str) and ideology_str.startswith("Любит "):
                        traits = {'type': 'race_love'}
                    else:
                        traits = {'type': 'ideology', 'value': ideology_str}
                except Exception:
                    continue

                if traits.get('type') == 'ideology':
                    if traits.get('value') == 'Борьба':
                        crystals_pct += bonus_pct
                    else:
                        crowns_pct += bonus_pct
                elif traits.get('type') == 'greed':
                    crowns_pct += bonus_pct // 2
                    crystals_pct += bonus_pct // 2
        except Exception as e:
            print(f"[Совет] Ошибка расчёта бонусов: {e}")
        return crowns_pct, crystals_pct

    def apply_player_bonuses(self):
        bonuses = {}
        try:
            system = self.load_political_system()
            if system == "Смирение":
                crowns_bonus = int(self.money_up * 7.00)
                if crowns_bonus > 0:
                    self.money += crowns_bonus
                    bonuses["Кроны"] = crowns_bonus
            elif system == "Борьба":
                raw_material_bonus = int(self.food_info * 5.50)
                if raw_material_bonus > 0:
                    self.raw_material += raw_material_bonus
                    bonuses["Кристаллы"] = raw_material_bonus

            # Бонусы от советников
            council_crowns_pct, council_crystals_pct = self._get_council_bonuses()
            if council_crowns_pct > 0 and self.money_up > 0:
                council_crowns = int(self.money_up * council_crowns_pct / 100)
                self.money += council_crowns
                bonuses["Кроны"] = bonuses.get("Кроны", 0) + council_crowns
            if council_crystals_pct > 0 and self.food_info > 0:
                council_crystals = int(self.food_info * council_crystals_pct / 100)
                self.raw_material += council_crystals
                bonuses["Кристаллы"] = bonuses.get("Кристаллы", 0) + council_crystals

            if self.turn % 3 == 0:
                self.update_relations_based_on_political_system()

            # Синхронизируем resources dict чтобы UI сразу отображал бонус
            self._sync_resources()
            return bonuses
        except Exception as e:
            print(f"Ошибка при применении бонусов игроку: {e}")
            return {}

    def load_political_system_for_faction(self, faction):
        """
        Загружает политическую систему указанной фракции.
        """
        try:
            query = "SELECT system FROM political_systems WHERE faction = ?"
            self.cursor.execute(query, (faction,))
            result = self.cursor.fetchone()
            return result[0] if result else "Смирение"  # По умолчанию "Смирение"
        except sqlite3.Error as e:
            print(f"Ошибка при загрузке политической системы для фракции {faction}: {e}")
            return "Смирение"

    def update_relations_based_on_political_system(self):
        """
        Изменяет отношения на основе политической системы каждые 4 хода.
        """
        current_system = self.load_political_system()
        all_factions = self.load_relations()

        for faction, relation_level in all_factions.items():
            if faction == self.faction:
                continue  # пропускаем собственную фракцию

            other_system = self.load_political_system_for_faction(faction)

            if current_system.strip() == other_system.strip():
                # Улучшаем отношения на +3%
                new_relation = min(relation_level + 3, 100)
                print(f"Улучшение отношений с {faction}: {relation_level} -> {new_relation}")
            else:
                # Ухудшаем отношения на -7%
                new_relation = max(relation_level - 7, 0)
                print(f"Ухудшение отношений с {faction}: {relation_level} -> {new_relation}")

            # Обновляем уровень отношений в базе данных
            self.update_relation_in_db(faction, new_relation)

    def update_relation_in_db(self, faction, new_relation):
        """
        Обновляет уровень отношений в базе данных.
        """
        try:
            print(f"Обновляем отношения для {faction}: новое значение = {new_relation}")
            query = """
                UPDATE relations
                SET relationship = ?
                WHERE faction1 = ? AND faction2 = ?
            """
            self.cursor.execute(query, (new_relation, self.faction, faction))
            self.conn.commit()
            print(f"Отношения успешно обновлены для {faction}.")
        except sqlite3.Error as e:
            print(f"Ошибка при обновлении отношений для фракции {faction}: {e}")

    def calculate_and_deduct_consumption(self):
        """
        Метод для расчета потребления Кристаллы гарнизонами текущей фракции
        и вычета суммарного потребления из self.raw_material.
        Также проверяет лимиты потребления и при необходимости сокращает армию,
        уменьшая количество юнитов на 15% от их числа.
        """
        try:
            self.current_consumption = 0
            # Шаг 1: Получаем города текущей фракции
            self.cursor.execute("SELECT name FROM cities WHERE faction = ?", (self.faction,))
            own_cities = {row[0] for row in self.cursor.fetchall()}

            # Шаг 2: Выгрузка гарнизонов только из своих городов
            self.cursor.execute("SELECT city_name, unit_name, unit_count FROM garrisons")
            garrisons = self.cursor.fetchall()

            # Шаг 3: Batch-загрузка всех юнитов за один запрос
            self.cursor.execute("SELECT unit_name, consumption, faction FROM units")
            faction_units = {
                row[0]: {'consumption': row[1], 'faction': row[2]}
                for row in self.cursor.fetchall()
            }

            # Потребление считается по принадлежности города, а не юнита:
            # все юниты в городах фракции (включая пленных) потребляют её кристаллы
            for garrison in garrisons:
                city_name, unit_name, unit_count = garrison
                if unit_name not in faction_units:
                    continue
                if city_name in own_cities:
                    self.current_consumption += faction_units[unit_name]['consumption'] * unit_count

            starving_units = []
            if self.current_consumption > self.max_army_limit:
                excess_consumption = self.current_consumption - self.max_army_limit

                for garrison in garrisons:
                    city_name, unit_name, unit_count = garrison

                    if unit_count <= 0 or city_name not in own_cities:
                        continue

                    reduction = max(1, int(unit_count * 0.15))

                    self.cursor.execute("""
                        UPDATE garrisons
                        SET unit_count = unit_count - ?
                        WHERE city_name = ? AND unit_name = ?
                    """, (reduction, city_name, unit_name))

                    new_unit_count = unit_count - reduction
                    starving_units.append((unit_name, reduction))

                    if new_unit_count <= 0:
                        self.cursor.execute("DELETE FROM garrisons WHERE city_name = ? AND unit_name = ?",
                                            (city_name, unit_name))
                    else:
                        self.current_consumption -= faction_units[unit_name]['consumption'] * reduction
                        excess_consumption -= faction_units[unit_name]['consumption'] * reduction

                    if excess_consumption <= 0:
                        break

            # Шаг 3: Обновляем досье
            total_starved = sum(reduction for _, reduction in starving_units)

            if total_starved > 0:
                try:
                    self.cursor.execute("SELECT avg_soldiers_starving FROM dossier WHERE faction = ?", (self.faction,))
                    result = self.cursor.fetchone()

                    if result and result[0] is not None:
                        new_avg = (result[0] + total_starved) / 2
                    else:
                        new_avg = total_starved

                    # Округление в меньшую сторону
                    new_avg = math.floor(new_avg)

                    self.cursor.execute("""
                        INSERT INTO dossier (faction, avg_soldiers_starving, last_data)
                        VALUES (?, ?, datetime('now'))
                        ON CONFLICT(faction) DO UPDATE SET
                            avg_soldiers_starving = ?,
                            last_data = datetime('now')
                    """, (self.faction, new_avg, new_avg))

                except Exception as e:
                    print(f"[Ошибка] Не удалось обновить досье: {e}")
                    self.conn.rollback()

            # Шаг 4: Вывод сообщения о голодании
            if starving_units:
                message = "Армия голодает и будет сокращаться:\n"
                for unit_name, reduction in starving_units:
                    message += f"- {unit_name}: умерло {reduction} юнитов\n"
                show_message("Голод в армии", message)
                print(f"Армия сокращена до допустимого лимита.")

            # Шаг 5: Обновление ресурсов
            self.raw_material -= self.current_consumption
            print(f"Общее потребление Кристаллы: {self.current_consumption}")
            print(f"Остаток Кристаллы у фракции: {self.raw_material}")

            self.resources['Потребление'] = self.current_consumption
            self.save_resources_to_db()

            self.conn.commit()

        except Exception as e:
            print(f"[Ошибка] Произошла ошибка: {e}")
            self.conn.rollback()
            self.resources['Потребление'] = self.current_consumption

    def update_average_net_profit(self, coins_profit, raw_profit):
        """
        Обновляет или создает запись в таблице results для колонок Average_Net_Profit_Coins и Average_Net_Profit_Raw.
        :param coins_profit: Текущая прибыль по кронам
        :param raw_profit: Текущая прибыль по Кристаллы
        """
        try:
            # Проверяем существование записи для фракции
            self.cursor.execute('''
                SELECT Average_Net_Profit_Coins, Average_Net_Profit_Raw 
                FROM results 
                WHERE faction = ?
            ''', (self.faction,))
            row = self.cursor.fetchone()

            if row:
                current_coins_profit, current_raw_profit = row

                # Рассчитываем новые средние значения
                new_coins_profit = round((current_coins_profit + coins_profit) / 2, 2)
                new_raw_profit = round((current_raw_profit + raw_profit) / 2, 2)

                # Обновляем существующую запись
                self.cursor.execute('''
                    UPDATE results 
                    SET Average_Net_Profit_Coins = ?, Average_Net_Profit_Raw = ?
                    WHERE faction = ?
                ''', (new_coins_profit, new_raw_profit, self.faction))
            else:
                # Создаем новую запись
                self.cursor.execute('''
                    INSERT INTO results (faction, Average_Net_Profit_Coins, Average_Net_Profit_Raw)
                    VALUES (?, ?, ?)
                ''', (self.faction, round(coins_profit, 2), round(raw_profit, 2)))

            self.conn.commit()
        except sqlite3.Error as e:
            print(f"Ошибка при обновлении средней чистой прибыли: {e}")

    def update_resources(self):
        """
        Обновление текущих ресурсов с учетом данных из базы данных.
        Все расчеты выполняются на основе таблиц в базе данных.
        """
        print('-----------------ХОДИТ ИГРОК-----------', self.faction.upper)
        # Обновляем данные о зданиях из таблицы buildings
        self.turn += 1
        # Строим
        self.auto_build()
        # Сохраняем предыдущие значения ресурсов
        previous_money = self.money
        previous_raw_material = self.raw_material  # Сохраняем *до* обновления

        # Генерируем новую цену на Кристаллы
        self.generate_raw_material_price()

        # Обновляем ресурсы на основе торговых соглашений
        self.update_trade_resources_from_db()

        # Коэффициенты для каждой фракции
        faction_coefficients = {
            'Север': {'money_loss': 5, 'food_loss': 0.3},
            'Эльфы': {'money_loss': 6, 'food_loss': 0.15},
            'Вампиры': {'money_loss': 7, 'food_loss': 0.08},
            'Адепты': {'money_loss': 8, 'food_loss': 0.02},
            'Элины': {'money_loss': 9, 'food_loss': 0.005},
        }

        # Получение коэффициентов для текущей фракции
        faction = self.faction
        if faction not in faction_coefficients:
            raise ValueError(f"Фракция '{faction}' не найдена.")
        coeffs = faction_coefficients[faction]

        # Обновление ресурсов с учетом коэффициентов
        self.born_peoples = int(self.hospitals * 50)
        self.work_peoples = int(self.factories * 20)
        self.clear_up_peoples = self.born_peoples - self.work_peoples

        # Загружаем текущие значения ресурсов из базы данных
        self.load_resources_from_db()

        # Выполняем расчеты
        # Изменение свободных рабочих только от разницы рожденных/работающих
        self.free_peoples += self.clear_up_peoples
        base_income = int(self.calculate_tax_income() - (self.hospitals * coeffs['money_loss']))
        # Бонус от Рынков: +10% дохода крон за каждый рынок
        market_bonus = 1.0 + self.markets * 0.10
        boosted_income = int(base_income * market_bonus)
        self.money += boosted_income
        self.money_info = int(self.hospitals * coeffs['money_loss'])
        self.money_up = boosted_income
        self.taxes_info = int(self.calculate_tax_income())

        # Рассчитываем базовый прирост Кристаллов (до бонусов городов)
        base_raw_material_production = (self.factories * 105) - (self.population * coeffs['food_loss'])

        # Загружаем коэффициенты kf_crystal только для городов,
        # связанных дорогами с основной территорией (снабжение)
        city_raw_material_bonus = 0.0
        try:
            supplied_cities = self._get_supplied_cities()
            self.cursor.execute('''
                SELECT name, kf_crystal
                FROM cities
                WHERE faction = ?
            ''', (self.faction,))
            rows = self.cursor.fetchall()
            for row in rows:
                city_name, kf_val = row
                if kf_val is None:
                    continue
                if city_name not in supplied_cities:
                    print(f"[Снабжение] Город {city_name} ({self.faction}) отрезан от снабжения — ресурсы не учитываются.")
                    continue
                city_raw_material_bonus += float(kf_val)
        except sqlite3.Error as e:
            print(f"Ошибка при загрузке kf_crystal из таблицы cities: {e}")

        # Рассчитываем бонус от городов (kf_crystal)
        # Базовый прирост Кристаллов * суммарный kf_crystal
        total_city_bonus_kf = int(base_raw_material_production * city_raw_material_bonus)

        # food_info — база для бонуса идеологии «Борьба»:
        # включает бонус городов, но НЕ вычитает потребление армии
        # (армия уже списывает кристаллы напрямую; двойное наказание нарушает баланс).
        # max(0, ...) гарантирует, что фракция с отрицательным базовым производством
        # просто не получает бонус, вместо отрицательного значения.
        self.food_info = max(0, int(base_raw_material_production + total_city_bonus_kf))

        # Итоговый прирост Кристаллов = базовый + бонус от kf_crystal - потребление армии
        # self.raw_material увеличивается на этот итоговый прирост
        self.raw_material += int(base_raw_material_production + total_city_bonus_kf - self.current_consumption)

        # self.food_peoples не изменяется, так как зависит от coeffs['food_loss'] и населения
        self.food_peoples = int(self.population * coeffs['food_loss'])

        # --- ПРИМЕНЕНИЕ ЭФФЕКТА НАЛОГОВ К НАСЕЛЕНИЮ ---
        # Получаем текущую ставку налога (предполагается, что она хранится как строка, например, "15%")
        # Извлекаем числовое значение
        try:
            # Убираем символ '%' и преобразуем в float
            current_tax_rate_numeric = float(self.current_tax_rate.rstrip('%'))
        except (ValueError, AttributeError):
            print(f"Предупреждение: Не удалось распознать ставку налога '{self.current_tax_rate}', используется 0%.")
            current_tax_rate_numeric = 0.0

        # Рассчитываем процентное изменение населения от налогов
        tax_percentage_change = self.tax_effect(current_tax_rate_numeric)

        # Рассчитываем абсолютное изменение населения от налогов
        # Округляем до ближайшего целого
        tax_population_change = int(self.population * (tax_percentage_change / 100))

        # --- ОБНОВЛЕНИЕ НАСЕЛЕНИЯ ---
        # Проверяем условия для роста/убыли населения
        if self.raw_material > 0:
            # При избытке Кристаллов:
            # 1. Прирост населения от больниц (рождение)
            # 2. Изменение населения от эффекта налогов (как абсолютное значение, рассчитанное от текущего населения)
            net_growth_from_hospitals_and_tax = self.born_peoples + tax_population_change
            self.population += net_growth_from_hospitals_and_tax
        else:
            # Логика убыли населения при недостатке Кристаллов (как было)
            if self.population > 5:
                loss = int(self.population * 0.45)  # 45% от населения
                self.population -= loss
            else:
                loss = min(self.population, 50)  # Обнуление по 50, но не ниже 0
                self.population -= loss
            self.free_peoples = 0  # Все рабочие обнуляются, так как Кристаллы нет

        # Принудительные лимиты на сами поля (а не только на dict)
        self.money = max(min(round(self.money, 2), 10_000_000), 0)
        self.free_peoples = max(min(round(self.free_peoples, 2), 500_000), 0)
        self.raw_material = max(min(round(self.raw_material, 2), 10_000_000), 0)
        self.population = max(min(round(self.population, 2), 100_000_000), 0)

        # Синхронизируем dict ресурсов
        self.resources.update({
            "Кроны": self.money,
            "Рабочие": self.free_peoples,
            "Кристаллы": self.raw_material,
            "Население": self.population,
            "Потребление": round(self.current_consumption, 2),
            "Лимит Армии": round(self.max_army_limit, 2)
        })

        # Рассчитываем чистую прибыль (разница после *всех* изменений)
        net_profit_coins = round(self.money - previous_money, 2)
        net_profit_raw = round(self.raw_material - previous_raw_material, 2)

        # Обновляем средние значения чистой прибыли в таблице results
        self.update_average_net_profit(net_profit_coins, net_profit_raw)
        self.calculate_and_deduct_consumption()
        # Синхронизируем и сохраняем
        self._sync_resources()
        self.save_resources_to_db()

        print(f"Ресурсы обновлены: {self.resources}, Больницы: {self.hospitals}, Фабрики: {self.factories}")

        # apply_player_bonuses вызывается из game_process.py после update_resources()

        # profit_details для UI может включать базовую прибыль и бонусы, если нужно отображать отдельно.
        # В текущем виде, profit_details отражает чистое изменение ресурса за ход до бонусов UI.
        profit_details = {
            "Кроны": net_profit_coins,
            "Кристаллы": net_profit_raw,  # Это прибыль до бонусов, но отражает чистое изменение за ход
        }
        # Оставляем только положительные значения для UI
        profit_details = {k: v for k, v in profit_details.items() if v > 0}

        # Возвращаем словарь с прибылью (базовой, до бонусов UI)
        return profit_details

    def get_resource_now(self, resource_type):
        """
        Возвращает текущее значение указанного ресурса.
        :param resource_type: Тип ресурса (например, "Кроны").
        :return: Значение ресурса.
        """
        return self.resources.get(resource_type, 0)

    def update_resource_now(self, resource_type, new_amount):
        if resource_type == 'Кроны':
            self.money = new_amount
        elif resource_type == 'Рабочие':
            self.free_peoples = new_amount
        elif resource_type == 'Кристаллы':
            self.raw_material = new_amount
        elif resource_type == 'Население':
            self.population = new_amount

    def get_resources(self):
        """Получение текущих ресурсов с форматированием чисел."""
        formatted_resources = {}

        for resource, value in self.resources.items():
            formatted_resources[resource] = format_number(value)

        return formatted_resources

    def get_city_count(self):
        """
        Возвращает текущее количество городов для фракции.
        :return: Количество городов (целое число).
        """
        try:
            # Выполняем запрос к таблице cities для подсчета городов фракции
            self.cursor.execute('''
                SELECT COUNT(*)
                FROM cities
                WHERE faction = ?
            ''', (self.faction,))

            # Получаем результат запроса
            row = self.cursor.fetchone()
            if row and isinstance(row[0], int):  # Проверяем, что результат корректен
                return row[0]  # Возвращаем количество городов
            else:
                return 0  # Если записей нет или результат некорректен, возвращаем 0
        except sqlite3.Error as e:
            print(f"Ошибка при получении количества городов: {e}")
            return 0

    def has_army_units(self):
        """
        Проверяет, есть ли у текущей фракции боевые юниты в гарнизонах.
        :return: True, если найдены юниты фракции, False иначе.
        """
        try:
            self.cursor.execute("""
                SELECT COUNT(*)
                FROM garrisons g
                JOIN units u ON g.unit_name = u.unit_name
                WHERE u.faction = ?
            """, (self.faction,))
            row = self.cursor.fetchone()
            return bool(row and row[0] > 0)
        except sqlite3.Error as e:
            print(f"Ошибка при проверке наличия армии у фракции {self.faction}: {e}")
            return False

    def check_all_relations_high(self):
        """
        Проверяет, превышают ли все отношения текущей фракции с НЕУНИЧТОЖЕННЫМИ фракциями 93%.
        Мятежники исключаются из проверки.
        :return: True, если все активные отношения > 93% или если других фракций нет, иначе False.
        """
        try:
            # Используем LEFT JOIN, чтобы включить фракции без статуса
            self.cursor.execute('''
                SELECT r.faction2, r.relationship, d.relationship AS diplomacy_status
                FROM relations r
                LEFT JOIN diplomacies d ON r.faction2 = d.faction2
                WHERE r.faction1 = ?
                  AND (d.relationship IS NULL OR d.relationship != 'уничтожена')  -- неуничтоженные или без статуса
                  AND r.faction2 != r.faction1        -- исключаем саму себя
                  AND r.faction2 != 'Мятежники'       -- исключаем Мятежников
                  AND r.faction2 != 'Нежить'          -- исключаем Нежить
            ''', (self.faction,))
            rows = self.cursor.fetchall()

            if not rows:
                print("Нет активных фракций для проверки отношений. Условие выполнено.")
                return True  # Если других фракций нет, условие выполнено

            # Проверяем каждое отношение
            for faction2, relationship, diplomacy_status in rows:
                if int(relationship) <= 93:
                    print(f"Отношение с {faction2} <= 93% ({relationship}%)")
                    return False  # Если хотя бы одно отношение <= 93, игра не завершается

            print("Все активные отношения > 93%. Условие завершения игры выполнено.")
            return True

        except sqlite3.Error as e:
            print(f"Ошибка при проверке отношений: {e}")
            return False

    def check_remaining_factions(self):
        """
        Проверяет, остались ли активные фракции (не уничтоженные и не 'Мятежники') в таблице relations.
        :return: True, если есть активные фракции, кроме Мятежников, False, если все (кроме Мятежников) уничтожены/отсутствуют.
        """
        try:
            # Используем JOIN для проверки статуса фракции [[6]]
            self.cursor.execute('''
                SELECT DISTINCT r.faction2
                FROM relations r
                LEFT JOIN diplomacies f ON r.faction2 = f.faction2
                WHERE r.faction1 = ?
                  AND f.relationship != 'уничтожена'  -- фильтруем уничтоженные
                  AND r.faction2 != r.faction1   -- исключаем текущую фракцию
                  AND r.faction2 != 'Мятежники'      -- исключаем Мятежников
                  AND r.faction2 != 'Нежить'         -- исключаем Нежить
            ''', (self.faction,))

            rows = self.cursor.fetchall()
            remaining_factions = {faction2 for (faction2,) in rows}

            if not remaining_factions:
                print("Все фракции уничтожены или отсутствуют.")
                return False

            return True

        except sqlite3.Error as e:
            print(f"Ошибка проверки фракций: {e}")
            return False

    def end_game(self):
        """
        Проверяет условия завершения игры:
        - Нулевое население.
        - Отсутствие городов.
        - Все отношения > 95%.
        - Остались ли другие фракции.
        :return: Кортеж (bool, str), где:
            - bool: True, если игра продолжается, False, если игра завершена.
            - str: Сообщение с описанием условий завершения игры.
        """
        try:
            # Условия завершения игры
            if self.population <= 0:
                message = "Города опустели...."
                print(message)
                return False, message

            if self.get_city_count() == 0:
                if self.has_army_units():
                    print("У фракции нет городов, но армия ещё есть. Игра продолжается.")
                    return True, ""
                message = "Противник завоевал все города"
                print(message)
                return False, message

            # Проверка все отношения > 95%
            if self.check_all_relations_high():
                message = "Мир во всем мире"
                print(message)
                return False, message

            # Проверка остались ли другие фракции
            if not self.check_remaining_factions():
                message = "Все фракции были уничтожены"
                print(message)
                return False, message

            # Если ни одно из условий не выполнено, игра продолжается
            return True, "Игра продолжается."

        except Exception as e:
            message = f"Ошибка при проверке завершения игры: {e}"
            print(message)
            return False, message

    def buildings_info_fraction(self):
        if self.faction == 'Север':
            return 15
        if self.faction == 'Эльфы':
            return 18
        if self.faction == 'Вампиры':
            return 21
        if self.faction == 'Адепты':
            return 24
        if self.faction == 'Элины':
            return 27

    def update_economic_efficiency(self, efficiency_value):
        """
        Обновляет или создает запись в таблице results для колонки Average_Deal_Ratio эффективность торговых сделок.
        :param efficiency_value: Новое значение эффективности для обработки.
        """
        try:
            # Проверяем существование записи для фракции
            self.cursor.execute('''
                SELECT Average_Deal_Ratio
                FROM results 
                WHERE faction = ?
            ''', (self.faction,))
            row = self.cursor.fetchone()

            if row:
                # Если запись существует - обновляем среднее значение
                current_efficiency = row[0]
                # Округляем результат до двух знаков после запятой
                new_efficiency = round((current_efficiency + efficiency_value) / 2, 2)
                self.cursor.execute('''
                    UPDATE results 
                    SET Average_Deal_Ratio = ? 
                    WHERE faction = ?
                ''', (new_efficiency, self.faction))
            else:
                # Если записи нет - создаем новую
                # Округляем входное значение до двух знаков после запятой
                self.cursor.execute('''
                    INSERT INTO results (faction, Average_Deal_Ratio)
                    VALUES (?, ?)
                ''', (self.faction, round(efficiency_value, 2)))

            self.conn.commit()
        except sqlite3.Error as e:
            print(f"Ошибка при обновлении экономической эффективности: {e}")

    def initialize_raw_material_prices(self):
        """Инициализация истории цен на Кристаллы"""
        for _ in range(25):  # Генерируем 25 случайных цен
            self.generate_raw_material_price()

    def generate_raw_material_price(self):
        """
        Генерация случайной цены на Кристаллы.
        Цена генерируется только при изменении номера хода.
        """
        # Загрузка номера хода из таблицы turn
        try:
            self.cursor.execute('''
                SELECT turn_count 
                FROM turn
                ORDER BY turn_count DESC
                LIMIT 1
            ''')
            row = self.cursor.fetchone()
            if row:
                current_turn = row[0]  # Текущий номер хода
            else:
                current_turn = 1  # Если записей нет, начинаем с 1
        except sqlite3.Error as e:
            print(f"Ошибка при загрузке номера хода: {e}")
            current_turn = 1  # В случае ошибки устанавливаем значение по умолчанию

        # Проверка, был ли уже загружен текущий ход
        if current_turn == self.last_turn_loaded:
            return  # Цена уже сгенерирована для этого хода

        # Генерация новой цены
        if current_turn == 1:  # Если это первый ход
            self.current_raw_material_price = round(random.uniform(76.3, 148.7), 2)
            self.raw_material_price_history.append(self.current_raw_material_price)
        else:
            # Генерация изменения цены (дробное число)
            price_change = random.uniform(-4.5, 4.5)
            self.current_raw_material_price = self.raw_material_price_history[-1] + price_change
            # Ограничиваем диапазон
            self.current_raw_material_price = round(max(76.3, min(148.7, self.current_raw_material_price)), 2)
            self.raw_material_price_history.append(self.current_raw_material_price)

        # Ограничение длины истории цен до 25 элементов
        if len(self.raw_material_price_history) > 25:
            self.raw_material_price_history.pop(0)

        # Обновляем значение последнего загруженного хода
        self.last_turn_loaded = current_turn

    def _sync_resources(self):
        """Синхронизирует self.resources dict с внутренними полями и обновляет UI."""
        # Принудительные лимиты перед синхронизацией
        self.money = max(min(self.money, 10_000_000), 0)
        self.raw_material = max(min(self.raw_material, 10_000_000), 0)
        self.population = max(min(self.population, 100_000_000), 0)
        self.free_peoples = max(min(self.free_peoples, 500_000), 0)

        self.resources['Кроны'] = self.money
        self.resources['Рабочие'] = self.free_peoples
        self.resources['Кристаллы'] = self.raw_material
        self.resources['Население'] = self.population
        self.resources['Потребление'] = self.current_consumption
        self.resources['Лимит Армии'] = self.max_army_limit
        # Моментальное обновление UI
        if self._on_resources_changed:
            try:
                self._on_resources_changed()
            except Exception:
                pass

    def trade_raw_material(self, action, quantity):
        """
        Торговля Кристаллами через таблицу resources.
        :param action: Действие ('buy' для покупки, 'sell' для продажи).
        :param quantity: Количество лотов (1 лот = 100 единиц Кристаллы).
        """
        total_quantity = quantity * 100
        total_cost = round(self.current_raw_material_price * quantity, 2)

        if action == 'buy':
            if self.money >= total_cost:
                self.money -= total_cost
                self.raw_material += total_quantity
                self._sync_resources()
                self.save_resources_to_db()
                return True
            else:
                show_message("Недостаточно денег", "У вас недостаточно денег для покупки Кристаллов.")
                return False

        elif action == 'sell':
            if self.raw_material >= total_quantity:
                self.money += total_cost
                self.raw_material -= total_quantity
                self._sync_resources()
                self.save_resources_to_db()
                return True
            else:
                show_message("Недостаточно Кристаллов", "У вас недостаточно Кристаллов для продажи.")
                return False

        return False

    def get_raw_material_price_history(self):
        """Получение табличного представления истории цен на Кристаллы"""
        history = []
        for i, price in enumerate(self.raw_material_price_history):
            # Вместо строки создаем кортеж (номер хода, цена)
            history.append((f"Ход {i + 1}", price))
        return history

    def get_available_raw_material_lots(self) -> int:
        """Возвращает количество доступных для торговли лотов Кристаллы"""
        return self.raw_material // 100


from ui_components import show_message, show_error_message


def open_build_popup(faction):
    def rebuild_popup(*args):
        build_popup.dismiss()
        open_build_popup(faction)

    build_popup = Popup(
        title="Состояние государства",
        size_hint=(0.9, 0.85),
        title_size=sp(20),
        title_align='center',
        title_color=(1, 1, 1, 1),
        background_color=(0.1, 0.1, 0.1, 0.95),
        separator_color=(0.3, 0.3, 0.3, 1),
        auto_dismiss=False
    )

    main_layout = BoxLayout(
        orientation='vertical',
        spacing=dp(12),
        padding=[dp(16), dp(16), dp(16), dp(16)]
    )

    scroll_view = ScrollView(
        size_hint=(1, 1),
        do_scroll_x=False,
        do_scroll_y=True
    )

    screen_w, _ = Window.size
    cols_count = 1 if screen_w < dp(600) else 2

    stats_grid = GridLayout(
        cols=cols_count,
        size_hint_y=None,
        spacing=dp(12),
        row_force_default=True,
        row_default_height=dp(80)
    )
    stats_grid.bind(minimum_height=stats_grid.setter('height'))

    # Адаптивный шрифт
    def calculate_font_size():
        w, _ = Window.size
        base = 14 + (w - dp(360)) / (dp(720)) * 4
        return sp(max(14, min(18, base)))

    adaptive_font = calculate_font_size()

    # 1) Объединённый блок «Постройки за ход» — увеличили высоту до dp(120)
    build_card = BoxLayout(
        orientation='vertical',
        padding=[dp(12), dp(8), dp(12), dp(8)],
        spacing=dp(4),
        size_hint_y=None,
        height=dp(120)
    )
    with build_card.canvas.before:
        Color(0.2, 0.2, 0.2, 1)
        build_card.bg_rect = RoundedRectangle(
            pos=build_card.pos,
            size=build_card.size,
            radius=[12]
        )

    def update_build_rect(instance, val):
        instance.bg_rect.pos = instance.pos
        instance.bg_rect.size = instance.size

    build_card.bind(pos=update_build_rect, size=update_build_rect)

    # Подпись для больницы
    hosp_label = Label(
        text=f"1 больница: +50 раб./-{faction.buildings_info_fraction()} крон",
        font_size=adaptive_font,
        color=(1, 1, 1, 1),
        size_hint_y=None,
        height=dp(28),
        halign='left',
        valign='middle'
    )
    hosp_label.bind(size=lambda inst, val: setattr(inst, 'text_size', (inst.width, inst.height)))
    build_card.add_widget(hosp_label)

    # Подпись для фабрики
    fact_label = Label(
        text="1 фабрика: +100 крист./-20 рабочих",
        font_size=adaptive_font,
        color=(1, 1, 1, 1),
        size_hint_y=None,
        height=dp(28),
        halign='left',
        valign='middle'
    )
    fact_label.bind(size=lambda inst, val: setattr(inst, 'text_size', (inst.width, inst.height)))
    build_card.add_widget(fact_label)

    stats_grid.add_widget(build_card)

    # 2) Оставшиеся данные статистики
    stats_data = [
        ("Количество больниц:", format_number(faction.hospitals)),
        ("Количество фабрик:", format_number(faction.factories)),
        ("Рабочих на фабриках:", format_number(faction.work_peoples)),
        ("Прирост рабочих:", format_number(faction.clear_up_peoples)),
        ("Расход денег больницами:", format_number(faction.money_info)),
        ("Прирост кристаллов:", format_number(faction.food_info)),
        ("Чистый прирост денег:", format_number(faction.money_up)),
        ("Доход от налогов:", format_number(faction.taxes_info)),
        ("Эффект от налогов:",
         format_number(faction.apply_tax_effect(int(faction.current_tax_rate[:-1]))) if faction.tax_set else "–")
    ]

    for label_text, value in stats_data:
        card = BoxLayout(
            orientation='vertical',
            padding=[dp(12), dp(8), dp(12), dp(8)],
            spacing=dp(4),
            size_hint_y=None,
            height=dp(80)
        )
        with card.canvas.before:
            Color(0.2, 0.2, 0.2, 1)
            card.bg_rect = RoundedRectangle(
                pos=card.pos,
                size=card.size,
                radius=[12]
            )

        def update_card_rect(instance, val):
            instance.bg_rect.pos = instance.pos
            instance.bg_rect.size = instance.size

        card.bind(pos=update_card_rect, size=update_card_rect)

        lbl = Label(
            text=label_text,
            font_size=adaptive_font,
            color=(1, 1, 1, 1),
            bold=True,
            size_hint_y=None,
            height=dp(24),
            halign='left',
            valign='middle'
        )
        lbl.bind(size=lambda inst, val: setattr(inst, 'text_size', (inst.width, inst.height)))
        card.add_widget(lbl)

        if isinstance(value, (int, float)):
            val_color = (0, 1, 0, 1) if value >= 0 else (1, 0, 0, 1)
            val_text = str(value)
        else:
            val_color = (1, 1, 1, 1)
            val_text = str(value)

        val = Label(
            text=val_text,
            font_size=adaptive_font,
            color=val_color,
            bold=True,
            size_hint_y=None,
            height=dp(28),
            halign='right',
            valign='middle'
        )
        val.bind(size=lambda inst, val: setattr(inst, 'text_size', (inst.width, inst.height)))
        card.add_widget(val)

        stats_grid.add_widget(card)

    scroll_view.add_widget(stats_grid)
    main_layout.add_widget(scroll_view)

    btn_box = BoxLayout(
        orientation='horizontal',
        spacing=dp(12),
        size_hint=(1, None),
        height=dp(50)
    )

    btn_close = Button(
        text="Закрыть",
        size_hint=(1, 1),
        background_normal='',
        background_color=(0.7, 0.2, 0.2, 1),
        font_size=adaptive_font,
        bold=True,
        color=(1, 1, 1, 1)
    )
    btn_close.bind(on_release=lambda x: build_popup.dismiss())

    btn_box.add_widget(btn_close)
    main_layout.add_widget(btn_box)

    build_popup.content = main_layout
    build_popup.open()


# ---------------------------------------------------------------


def open_trade_popup(game_instance):
    game_instance.get_resources()
    game_instance.generate_raw_material_price()

    trade_layout = BoxLayout(
        orientation='vertical',
        padding=dp(16),
        spacing=dp(12)
    )
    with trade_layout.canvas.before:
        Color(0.07, 0.08, 0.13, 1)
        trade_layout._bg = Rectangle(pos=trade_layout.pos, size=trade_layout.size)
    trade_layout.bind(pos=lambda i, v: setattr(i._bg, 'pos', v),
                      size=lambda i, v: setattr(i._bg, 'size', v))

    # === РАСЧЕТ ЛИМИТОВ ДЛЯ СЛАЙДЕРА ===
    current_price = game_instance.current_raw_material_price
    crowns = game_instance.resources.get("Кроны", 0)

    # Максимум покупки: сколько лотов влезает в кроны
    max_buy_lots = int(crowns // current_price) if current_price > 0 else 0

    # Максимум продажи: сколько лотов есть в наличии
    max_sell_lots = game_instance.get_available_raw_material_lots()
    crystals_available = game_instance.resources.get("Кристаллы", 0)

    # Значение 0 - центр. Влево минус (продажа), вправо плюс (покупка)
    slider_min = -max_sell_lots
    slider_max = max_buy_lots

    # === ИНФОРМАЦИЯ О ЦЕНЕ И РЕСУРСАХ ===
    prev_price = game_instance.raw_material_price_history[-2] if len(
        game_instance.raw_material_price_history) > 1 else current_price
    arrow_color = (0, 1, 0, 1) if current_price > prev_price else \
        (1, 0, 0, 1) if current_price < prev_price else (0.8, 0.8, 0.8, 1)

    # Карточка-заголовок с ценой
    price_card = BoxLayout(
        orientation='horizontal',
        size_hint=(1, None),
        height=dp(54),
        spacing=dp(10),
        padding=[dp(14), dp(8), dp(14), dp(8)]
    )
    with price_card.canvas.before:
        Color(0.13, 0.17, 0.28, 1)
        price_card._bg = RoundedRectangle(pos=price_card.pos, size=price_card.size, radius=[dp(12)])
    price_card.bind(pos=lambda i, v: setattr(i._bg, 'pos', v),
                    size=lambda i, v: setattr(i._bg, 'size', v))

    current_price_label = Label(
        text=f"[b]Цена 1 лота (100 ед.):[/b]  {current_price} крон",
        markup=True,
        font_size=sp(16),
        color=arrow_color,
        halign="left",
        valign="middle",
        size_hint=(1, 1)
    )
    current_price_label.bind(size=current_price_label.setter('text_size'))
    price_card.add_widget(current_price_label)
    trade_layout.add_widget(price_card)

    # === ЧЕКБОКС "ПРОДАТЬ ВСЁ" ===
    sell_all_layout = BoxLayout(
        orientation='horizontal',
        size_hint=(1, None),
        height=dp(40),
        spacing=dp(10)
    )
    sell_all_checkbox = CheckBox(
        size_hint=(None, None),
        size=(dp(30), dp(30)),
        active=False,
        color=(1, 1, 1, 1)
    )

    sell_all_label = Label(
        text="Продать все",
        font_size=sp(16),
        color=(1, 1, 1, 1),
        halign="left",
        size_hint_x=None,
        width=dp(150)
    )

    sell_all_layout.add_widget(sell_all_checkbox)
    sell_all_layout.add_widget(sell_all_label)
    sell_all_layout.add_widget(Widget())  # Заполнитель
    trade_layout.add_widget(sell_all_layout)

    # === СОЗДАНИЕ КНОПОК ===
    def _trade_btn(txt, clr):
        b = Button(
            text=txt, font_size=sp(16), bold=True,
            background_color=(0, 0, 0, 0), color=(1, 1, 1, 1),
            size_hint=(0.5, 1), background_normal='', background_down='',
            disabled=True
        )
        with b.canvas.before:
            b._bc = Color(*clr)
            b._br = RoundedRectangle(pos=b.pos, size=b.size, radius=[dp(12)])
        b.bind(pos=lambda i, v: setattr(i._br, 'pos', v),
               size=lambda i, v: setattr(i._br, 'size', v))
        return b

    buy_btn = _trade_btn("Купить", (0.12, 0.52, 0.18, 1))
    sell_btn = _trade_btn("Продать", (0.60, 0.10, 0.10, 1))

    # === СЛАЙДЕР И ОТОБРАЖЕНИЕ ЗНАЧЕНИЯ ===
    slider_layout = BoxLayout(orientation='vertical', spacing=dp(5), size_hint=(1, None), height=dp(80))

    trade_info_label = Label(
        text="Нет операции",
        font_size=sp(18),
        bold=True,
        color=(0.8, 0.8, 0.8, 1),
        halign="center",
        size_hint=(1, None),
        height=dp(30)
    )
    trade_info_label.bind(size=trade_info_label.setter('text_size'))

    trade_slider = Slider(
        min=slider_min,
        max=slider_max,
        value=0,
        step=1,
        size_hint=(1, None),
        height=dp(50),
        cursor_size=(dp(20), dp(40)),
    )

    # Функция обновления слайдера
    def update_slider_label(instance, value):
        if sell_all_checkbox.active:
            return  # Если чекбокс активен, не обновляем по слайдеру

        val = int(value)
        if val > 0:
            crystals_gain = val * 100
            cost = int(val * current_price)
            trade_info_label.text = f"Купить {format_number(crystals_gain)} кристаллов за {format_number(cost)} крон"
            trade_info_label.color = (0, 1, 0, 1)
        elif val < 0:
            lots = abs(val)
            crystals_spent = lots * 100
            income = int(lots * current_price)
            trade_info_label.text = f"Продать {format_number(crystals_spent)} кристаллов за {format_number(income)} крон"
            trade_info_label.color = (1, 0, 0, 1)
        else:
            trade_info_label.text = "Нет операции"
            trade_info_label.color = (0.8, 0.8, 0.8, 1)

        # Блокировка кнопок в зависимости от направления
        buy_btn.disabled = (val <= 0)
        sell_btn.disabled = (val >= 0)

    # Функция обработки чекбокса "Продать всё"
    def on_sell_all_toggle(instance, value):
        if value:
            # Активирована продажа всех лотов
            trade_slider.disabled = True
            trade_slider.value = -max_sell_lots
            crystals_spent = max_sell_lots * 100
            income = int(max_sell_lots * current_price)
            trade_info_label.text = f"Продать ВСЁ: {format_number(crystals_spent)} кристаллов за {format_number(income)} крон"
            trade_info_label.color = (1, 0, 0, 1)
            buy_btn.disabled = True
            sell_btn.disabled = False
        else:
            # Возвращаем слайдер в нейтральное положение
            trade_slider.disabled = False
            trade_slider.value = 0
            update_slider_label(None, 0)

    trade_slider.bind(value=update_slider_label)
    sell_all_checkbox.bind(active=on_sell_all_toggle)

    slider_layout.add_widget(trade_info_label)
    slider_layout.add_widget(trade_slider)
    trade_layout.add_widget(slider_layout)

    # === ДОБАВЛЕНИЕ КНОПОК В LAYOUT ===
    button_layout = BoxLayout(spacing=dp(16), size_hint=(1, None), height=dp(60))
    button_layout.add_widget(buy_btn)
    button_layout.add_widget(sell_btn)
    trade_layout.add_widget(button_layout)

    # === ПОПАП ===
    popup = Popup(
        title="Рынок Кристаллов",
        content=trade_layout,
        size_hint=(0.95, 0.72),
        background_color=(0.07, 0.08, 0.13, 1),
        separator_color=(0.25, 0.52, 0.92, 0.6),
        title_color=(0.65, 0.88, 1, 1),
        title_size=sp(18),
        title_align='center'
    )

    def on_press_wrapper(action):
        def handler(instance):
            if sell_all_checkbox.active:
                quantity = max_sell_lots
            else:
                quantity = abs(int(trade_slider.value))
            handle_trade(game_instance, action, quantity, popup)
        return handler

    buy_btn.bind(on_release=on_press_wrapper('buy'))
    sell_btn.bind(on_release=on_press_wrapper('sell'))

    popup.open()


def handle_trade(game_instance, action, quantity, trade_popup):
    """Обработка торговли (покупка/продажа Кристаллы)"""
    try:
        if quantity <= 0:
            raise ValueError("Выберите количество лотов на слайдере.")

        price_per_lot = game_instance.current_raw_material_price

        if action == 'buy':
            total_cost = price_per_lot * quantity
            crowns = game_instance.resources.get("Кроны", 0)
            if total_cost > crowns:
                raise ValueError("Недостаточно крон для покупки.")

        elif action == 'sell':
            available_lots = game_instance.get_available_raw_material_lots()
            if quantity > available_lots:
                raise ValueError("Недостаточно кристаллов для продажи.")

        result = game_instance.trade_raw_material(action, quantity)

        if result:
            economic_efficiency = round(price_per_lot / 100, 2)
            game_instance.update_economic_efficiency(economic_efficiency)

            if action == 'buy':
                total_cost = price_per_lot * quantity
                show_message("Успех",
                             f"Куплено {format_number(quantity)} лотов Кристаллов за {format_number(total_cost)} крон.")
            elif action == 'sell':
                profit = price_per_lot * quantity
                show_message("Успех",
                             f"Получено: {format_number(profit)} крон\n(Соотношение: {economic_efficiency} крон/ед. Кристалла)")
        else:
            show_message("Ошибка", "Не удалось завершить операцию.")

    except ValueError as e:
        show_message("Ошибка", str(e))
    except Exception as e:
        show_message("Ошибка", f"Неизвестная ошибка: {str(e)}")

    trade_popup.dismiss()


# -----------------------------------
def open_tax_popup(faction):
    is_android = platform == 'android'
    popup_size_hint = (0.85, 0.55) if is_android else (0.72, 0.50)

    try:
        current_tax_rate = int(faction.current_tax_rate.strip('%')) \
            if isinstance(faction.current_tax_rate, str) else int(faction.current_tax_rate)
    except:
        current_tax_rate = 0

    def _effect_color(effect):
        if effect > 0:
            return (0.35, 1.0, 0.45, 1)
        elif effect < 0:
            return (1.0, 0.38, 0.38, 1)
        return (1.0, 0.90, 0.35, 1)

    def _effect_text(effect):
        prefix = "+" if effect > 0 else ""
        return f"{prefix}{effect}% прироста населения"

    # === Основной контейнер ===
    main_layout = BoxLayout(orientation='vertical', padding=dp(16), spacing=dp(12))
    with main_layout.canvas.before:
        Color(0.07, 0.08, 0.13, 1)
        main_layout._bg = Rectangle(pos=main_layout.pos, size=main_layout.size)
    main_layout.bind(pos=lambda i, v: setattr(i._bg, 'pos', v),
                     size=lambda i, v: setattr(i._bg, 'size', v))

    # === Карточка с отображением налога ===
    card = BoxLayout(orientation='vertical', size_hint_y=None, height=dp(70),
                     padding=dp(10), spacing=dp(4))
    with card.canvas.before:
        Color(0.12, 0.15, 0.24, 1)
        card._bg = RoundedRectangle(pos=card.pos, size=card.size, radius=[dp(12)])
    card.bind(pos=lambda i, v: setattr(i._bg, 'pos', v),
              size=lambda i, v: setattr(i._bg, 'size', v))

    initial_effect = faction.tax_effect(current_tax_rate)
    tax_label = Label(
        text=f"Налог: {current_tax_rate}%",
        color=(0.65, 0.88, 1, 1),
        font_size=sp(22) if is_android else sp(20),
        bold=True,
        halign='center',
        size_hint_y=None,
        height=dp(30)
    )
    effect_label = Label(
        text=_effect_text(initial_effect),
        color=_effect_color(initial_effect),
        font_size=sp(14),
        halign='center',
        size_hint_y=None,
        height=dp(22)
    )
    card.add_widget(tax_label)
    card.add_widget(effect_label)
    main_layout.add_widget(card)

    # === Ползунок ===
    tax_slider = Slider(
        min=0, max=100, value=current_tax_rate, step=1,
        orientation='horizontal',
        size_hint=(1, None),
        height=dp(44) if is_android else dp(38),
        background_width=dp(8),
        cursor_size=(dp(36), dp(36)),
        value_track=False
    )

    def update_tax_label(instance, value):
        rate = int(value)
        effect = faction.tax_effect(rate)
        tax_label.text = f"Налог: {rate}%"
        effect_label.text = _effect_text(effect)
        effect_label.color = _effect_color(effect)

    tax_slider.bind(value=update_tax_label)
    main_layout.add_widget(tax_slider)

    # Распорка
    main_layout.add_widget(BoxLayout(size_hint_y=1))

    # === Кнопка "Применить" ===
    set_tax_button = Button(
        text="Применить",
        size_hint=(1, None),
        height=dp(46) if is_android else dp(42),
        background_color=(0, 0, 0, 0),
        color=(1, 1, 1, 1),
        font_size=sp(18) if is_android else sp(16),
        bold=True
    )
    with set_tax_button.canvas.before:
        set_tax_button._bc = Color(0.18, 0.55, 0.22, 1)
        set_tax_button._br = RoundedRectangle(
            size=set_tax_button.size, pos=set_tax_button.pos, radius=[dp(12)]
        )
    set_tax_button.bind(
        pos=lambda i, v: setattr(i._br, 'pos', v),
        size=lambda i, v: setattr(i._br, 'size', v)
    )

    def set_tax(instance):
        tax_rate = int(tax_slider.value)
        faction.current_tax_rate = f"{tax_rate}%"
        faction.set_taxes(tax_rate)
        faction.apply_tax_effect(tax_rate)
        tax_popup.dismiss()

    set_tax_button.bind(on_release=set_tax)
    main_layout.add_widget(set_tax_button)

    tax_popup = Popup(
        title="Управление налогами",
        content=main_layout,
        size_hint=popup_size_hint,
        background_color=(0.07, 0.08, 0.13, 1),
        separator_color=(0.25, 0.72, 0.35, 0.7),
        title_color=(0.65, 0.88, 1, 1),
        title_size=sp(18) if is_android else sp(16),
        title_align='center',
        auto_dismiss=True
    )
    tax_popup.open()


def open_auto_build_popup(faction):
    from kivy.graphics import Color, RoundedRectangle
    from kivy.metrics import dp, sp
    from kivy.uix.image import Image

    # Соотношения с описаниями
    RATIOS = [
        (5, 2, "Агрессивный рост", "Больше рабочих для быстрого расширения"),
        (3, 2, "Баланс+", "Умеренный прирост населения и ресурсов"),
        (3, 1, "Рост населения", "Фокус на увеличение рабочей силы"),
        (2, 1, "Умеренный рост", "Сбалансированное развитие"),
        (1, 1, "Идеальный баланс", "Равное развитие больниц и фабрик"),
        (1, 2, "Умеренная промышленность", "Небольшой уклон в производство"),
        (1, 3, "Промышленность", "Фокус на добычу кристаллов"),
        (2, 3, "Промышленность+", "Усиленное производство ресурсов"),
        (2, 5, "Максимальная добыча", "Приоритет — кристаллы для армии")
    ]

    auto_popup = Popup(
        title="",
        size_hint=(0.92, 0.85),
        background_color=(0.12, 0.15, 0.22, 0.97),
        separator_height=0,
        auto_dismiss=False
    )

    main_layout = BoxLayout(orientation='vertical', padding=[dp(18), dp(22), dp(18), dp(18)], spacing=dp(18))

    # Заголовок
    header = BoxLayout(size_hint_y=None, height=dp(55), spacing=dp(12))
    icon_container = BoxLayout(size_hint=(None, None), size=(dp(42), dp(42)))
    with icon_container.canvas:
        Color(0.25, 0.45, 0.85, 1)
        RoundedRectangle(pos=icon_container.pos, size=icon_container.size, radius=[dp(12)])
    icon_img = Image(source='files/status/icons/building.png', size_hint=(0.6, 0.6),
                     pos_hint={'center_x': 0.5, 'center_y': 0.5})
    icon_container.add_widget(icon_img)
    header.add_widget(icon_container)

    title_label = Label(
        text="[b]Министерство развития[/b]",
        markup=True,
        font_size=sp(24),
        color=(1, 0.95, 0.85, 1),
        halign='left',
        valign='middle',
        size_hint_x=0.85
    )
    title_label.bind(size=title_label.setter('text_size'))
    header.add_widget(title_label)
    main_layout.add_widget(header)

    # Визуальный индикатор соотношения
    ratio_visual = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(60), padding=[dp(8), 0, dp(8), 0],
                             spacing=dp(6))

    hospitals_bar = BoxLayout(size_hint=(0.5, 1))
    with hospitals_bar.canvas.before:
        Color(0.85, 0.35, 0.35, 1)
        hospitals_bar.rect = RoundedRectangle(pos=hospitals_bar.pos, size=hospitals_bar.size,
                                              radius=[dp(8), 0, 0, dp(8)])
        hospitals_bar.bind(pos=lambda inst, val: setattr(hospitals_bar.rect, 'pos', val))
        hospitals_bar.bind(size=lambda inst, val: setattr(hospitals_bar.rect, 'size', val))
    hospitals_label = Label(text="H 1", font_size=sp(18), bold=True, color=(1, 1, 1, 1), halign='center',
                            valign='middle')
    hospitals_label.bind(size=hospitals_label.setter('text_size'))
    hospitals_bar.add_widget(hospitals_label)
    ratio_visual.add_widget(hospitals_bar)

    factories_bar = BoxLayout(size_hint=(0.5, 1))
    with factories_bar.canvas.before:
        Color(0.35, 0.75, 0.45, 1)
        factories_bar.rect = RoundedRectangle(pos=factories_bar.pos, size=factories_bar.size,
                                              radius=[0, dp(8), dp(8), 0])
        factories_bar.bind(pos=lambda inst, val: setattr(factories_bar.rect, 'pos', val))
        factories_bar.bind(size=lambda inst, val: setattr(factories_bar.rect, 'size', val))
    factories_label = Label(text="1", font_size=sp(18), bold=True, color=(1, 1, 1, 1), halign='center', valign='middle')
    factories_label.bind(size=factories_label.setter('text_size'))
    factories_bar.add_widget(factories_label)
    ratio_visual.add_widget(factories_bar)

    main_layout.add_widget(ratio_visual)

    # Слайдер
    slider_container = BoxLayout(orientation='vertical', spacing=dp(10), size_hint_y=None, height=dp(100))
    ratio_display = Label(text="1 : 1", font_size=sp(32), bold=True, color=(1, 0.95, 0.8, 1), halign='center',
                          valign='middle', size_hint_y=None, height=dp(40))
    ratio_display.bind(size=ratio_display.setter('text_size'))
    slider_container.add_widget(ratio_display)

    slider = Slider(min=0, max=8, value=4, step=1, cursor_size=(dp(40), dp(40)), background_width=dp(12),
                    size_hint_y=None, height=dp(40))
    slider_container.add_widget(slider)
    main_layout.add_widget(slider_container)

    # Описание стратегии
    strategy_card = BoxLayout(orientation='vertical', size_hint_y=None, height=dp(95),
                              padding=[dp(15), dp(12), dp(15), dp(12)], spacing=dp(4))
    with strategy_card.canvas.before:
        Color(0.18, 0.22, 0.32, 1)
        strategy_card.bg = RoundedRectangle(radius=[dp(14)], size=strategy_card.size, pos=strategy_card.pos)
        strategy_card.bind(pos=lambda inst, val: setattr(strategy_card.bg, 'pos', val))
        strategy_card.bind(size=lambda inst, val: setattr(strategy_card.bg, 'size', val))

    strategy_name = Label(text="[b]Идеальный баланс[/b]", markup=True, font_size=sp(19), color=(0.65, 0.95, 1, 1),
                          halign='center', valign='top', size_hint_y=None, height=dp(28))
    strategy_name.bind(size=strategy_name.setter('text_size'))
    strategy_desc = Label(text="Равное развитие больниц и фабрик", font_size=sp(15), color=(0.85, 0.85, 0.9, 1),
                          halign='center', valign='top', size_hint_y=None, height=dp(45))
    strategy_desc.bind(size=strategy_desc.setter('text_size'))
    strategy_card.add_widget(strategy_name)
    strategy_card.add_widget(strategy_desc)
    main_layout.add_widget(strategy_card)

    # Кнопки
    buttons_layout = BoxLayout(orientation='horizontal', spacing=dp(15), size_hint_y=None, height=dp(65))

    def create_button(text, bg_color):
        btn = Button(text=text, font_size=sp(19), bold=True, background_color=(0, 0, 0, 0), color=(1, 1, 1, 1),
                     size_hint=(0.5, 1))
        with btn.canvas.before:
            Color(*bg_color)
            btn.bg = RoundedRectangle(radius=[dp(16)], size=btn.size, pos=btn.pos)
            btn.bind(pos=lambda inst, val: setattr(btn.bg, 'pos', val))
            btn.bind(size=lambda inst, val: setattr(btn.bg, 'size', val))
        return btn

    cancel_btn = create_button("Отмена", (0.65, 0.25, 0.25, 1))
    save_btn = create_button("Применить", (0.35, 0.7, 0.35, 1))
    buttons_layout.add_widget(cancel_btn)
    buttons_layout.add_widget(save_btn)
    main_layout.add_widget(buttons_layout)

    # === ИСПРАВЛЕНА СИГНАТУРА ОБРАБОТЧИКА ===
    def update_display(instance, value):
        idx = int(value)
        hospitals, factories, name, desc = RATIOS[idx]

        # Обновление визуального индикатора
        hospitals_label.text = f"H {hospitals}"
        factories_label.text = f"F {factories}"

        # Обновление пропорций баров
        total = hospitals + factories
        hospitals_bar.size_hint_x = hospitals / total
        factories_bar.size_hint_x = factories / total

        # Обновление крупного дисплея
        ratio_display.text = f"{hospitals} : {factories}"

        # Обновление описания стратегии
        strategy_name.text = f"[b]{name}[/b]"
        strategy_desc.text = desc

    # Загрузка текущих настроек
    if hasattr(faction, 'auto_build_ratio'):
        for idx, (h, f, _, _) in enumerate(RATIOS):
            if (h, f) == faction.auto_build_ratio:
                slider.value = idx
                break

    update_display(None, slider.value)  # Инициализация
    slider.bind(value=update_display)  # Привязка с правильной сигнатурой

    # Обработка кнопок
    def save_settings(instance):
        idx = int(slider.value)
        hospitals, factories, _, _ = RATIOS[idx]
        faction.auto_build_ratio = (hospitals, factories)
        faction.auto_build_enabled = True
        faction.save_auto_build_settings()
        auto_popup.dismiss()
        show_message("Сохранено", f"Строить: {hospitals} больниц и {factories} фабрик за ход")

    cancel_btn.bind(on_release=lambda x: auto_popup.dismiss())
    save_btn.bind(on_release=save_settings)

    auto_popup.content = main_layout
    auto_popup.open()


def open_development_popup(faction):
    from kivy.uix.tabbedpanel import TabbedPanel, TabbedPanelItem
    from kivy.uix.scrollview import ScrollView
    from kivy.uix.gridlayout import GridLayout
    from kivy.uix.boxlayout import BoxLayout
    from kivy.uix.button import Button
    from kivy.uix.label import Label
    from kivy.graphics import Color, RoundedRectangle
    from kivy.metrics import dp, sp
    from kivy.uix.image import Image
    from kivy.uix.slider import Slider
    from kivy.uix.popup import Popup
    from kivy import platform

    # Вспомогательная функция форматирования чисел
    def format_number(value):
        if isinstance(value, (int, float)):
            return f"{value:,.0f}".replace(",", " ")
        return str(value)

    # Определяем размеры для мобильных устройств
    current_platform = platform
    is_mobile = current_platform in ['android', 'ios']

    if is_mobile:
        # Более компактные размеры для Android
        popup_size_hint = (0.98, 0.95)
        tab_height = dp(40)
        header_height = dp(45)
        spacing = dp(8)
        padding = [dp(8), dp(10), dp(8), dp(8)]
    else:
        popup_size_hint = (0.94, 0.9)
        tab_height = dp(50)
        header_height = dp(60)
        spacing = dp(16)
        padding = [dp(16), dp(20), dp(16), dp(16)]

    dev_popup = Popup(
        title="Стратегия развития",
        size_hint=popup_size_hint,
        background_color=(0.08, 0.10, 0.16, 0.98),
        separator_color=(0.25, 0.52, 0.92, 0.55),
        title_color=(0.75, 0.92, 1, 1),
        title_size=sp(18) if is_mobile else sp(20),
        title_align='center',
        auto_dismiss=False
    )

    main_layout = BoxLayout(orientation='vertical', padding=padding, spacing=spacing)

    # Tabbed Panel - компактный
    tab_panel = TabbedPanel(
        do_default_tab=False,
        tab_width=dp(120) if is_mobile else dp(160),
        tab_height=tab_height,
        background_color=(0, 0, 0, 0)
    )

    # === Вкладка "Строительство" ===
    build_tab = TabbedPanelItem(
        text=" Строительство",
        font_size=sp(15) if is_mobile else sp(17),
        color=(0.9, 0.95, 1, 1),
        background_normal='',
        background_down='',
        background_color=(0.25, 0.35, 0.65, 1)
    )

    # Контейнер для вкладки строительства
    build_content_container = BoxLayout(orientation='vertical')

    with build_content_container.canvas.before:
        Color(0.0, 0.0, 0.0, 1)
        build_content_container.bg = RoundedRectangle(
            radius=[dp(10)],
            size=build_content_container.size,
            pos=build_content_container.pos
        )
        build_content_container.bind(
            pos=lambda inst, val: setattr(build_content_container.bg, 'pos', val),
            size=lambda inst, val: setattr(build_content_container.bg, 'size', val)
        )

    # ScrollView для мобильных устройств - обязательно!
    build_scroll = ScrollView(
        size_hint=(1, 1),
        do_scroll_x=False,
        bar_width=dp(4) if is_mobile else dp(6),
        bar_color=(0.5, 0.5, 0.5, 0.3)
    )

    build_content = BoxLayout(
        orientation='vertical',
        spacing=dp(4) if is_mobile else dp(8),  # Уменьшил spacing
        padding=[dp(6), dp(6), dp(6), dp(6)],  # Уменьшил padding
        size_hint_y=None
    )
    build_content.bind(minimum_height=build_content.setter('height'))

    # 1. Название стратегии и описание под ним - сделал компактнее
    strategy_display = BoxLayout(
        orientation='vertical',
        size_hint_y=None,
        height=dp(70) if is_mobile else dp(100),  # Уменьшил высоту
        padding=[dp(4), dp(2), dp(4), dp(0)]  # Убрал нижний padding
    )

    # Название стратегии
    strategy_main_name = Label(
        text="Баланс",
        font_size=sp(20) if is_mobile else sp(26),  # Чуть меньше
        bold=True,
        color=(1, 0.95, 0.8, 1),
        halign='center',
        valign='middle'
    )
    strategy_main_name.bind(size=strategy_main_name.setter('text_size'))

    # Описание стратегии под названием - сделал компактнее
    strategy_description = Label(
        text="Идеально если не знаете что выбрать",
        font_size=sp(12) if is_mobile else sp(14),  # Меньше шрифт
        color=(0.85, 0.9, 0.95, 0.9),
        halign='center',
        valign='top',
        size_hint_y=None,
        height=dp(30) if is_mobile else dp(45)  # Сильно уменьшил высоту
    )
    strategy_description.bind(size=strategy_description.setter('text_size'))

    strategy_display.add_widget(strategy_main_name)
    strategy_display.add_widget(strategy_description)
    build_content.add_widget(strategy_display)

    # 2. Слайдер с компактной индикацией - уменьшил высоту
    slider_container = BoxLayout(
        orientation='vertical',
        spacing=dp(0),  # Убрал spacing
        size_hint_y=None,
        height=dp(45) if is_mobile else dp(55)  # Уменьшил высоту
    )

    # Сам слайдер
    slider = Slider(
        min=0,
        max=8,
        value=4,
        step=1,
        cursor_size=(dp(38) if is_mobile else dp(42), dp(38) if is_mobile else dp(42)),  # Чуть меньше курсор
        background_width=dp(8),
        size_hint_y=None,
        height=dp(25) if is_mobile else dp(30)  # Уменьшил высоту слайдера
    )
    slider_container.add_widget(slider)
    build_content.add_widget(slider_container)

    # 3. Быстрые пресеты для слайдера
    quick_buttons = BoxLayout(
        orientation='horizontal',
        spacing=dp(4) if is_mobile else dp(6),
        size_hint_y=None,
        height=dp(38) if is_mobile else dp(44),
        padding=[0, 0, 0, 0]
    )

    PRESET_LABELS = ["Больн x2.5", "Баланс", "Фабр x2.5"]
    PRESET_VALS   = [0, 4, 8]

    def _preset_btn(txt, val):
        b = Button(
            text=txt, font_size=sp(12) if is_mobile else sp(13),
            bold=True, background_color=(0, 0, 0, 0),
            color=(0.82, 0.94, 1, 1)
        )
        with b.canvas.before:
            b._bc = Color(0.18, 0.26, 0.42, 1)
            b._br = RoundedRectangle(pos=b.pos, size=b.size, radius=[dp(8)])
        b.bind(pos=lambda i, v: setattr(i._br, 'pos', v),
               size=lambda i, v: setattr(i._br, 'size', v))
        return b

    for p_label, p_val in zip(PRESET_LABELS, PRESET_VALS):
        pb = _preset_btn(p_label, p_val)
        pb.bind(on_release=lambda inst, v=p_val: setattr(slider, 'value', v))
        quick_buttons.add_widget(pb)

    build_content.add_widget(quick_buttons)

    # 4. Основные кнопки действия
    action_buttons = BoxLayout(
        orientation='horizontal',
        spacing=dp(6) if is_mobile else dp(10),
        size_hint_y=None,
        height=dp(48) if is_mobile else dp(56),
        padding=[0, 0, 0, 0]
    )

    def _action_dev_btn(txt, clr):
        b = Button(
            text=txt,
            font_size=sp(15) if is_mobile else sp(17),
            bold=True, background_color=(0, 0, 0, 0),
            color=(1, 1, 1, 1)
        )
        with b.canvas.before:
            b._bc = Color(*clr)
            b._br = RoundedRectangle(pos=b.pos, size=b.size, radius=[dp(12)])
        b.bind(pos=lambda i, v: setattr(i._br, 'pos', v),
               size=lambda i, v: setattr(i._br, 'size', v))
        return b

    cancel_btn = _action_dev_btn("Отмена", (0.60, 0.18, 0.18, 1))
    apply_btn  = _action_dev_btn("Применить", (0.18, 0.62, 0.28, 1))

    cancel_btn.size_hint_x = 0.45
    apply_btn.size_hint_x  = 0.55

    action_buttons.add_widget(cancel_btn)
    action_buttons.add_widget(apply_btn)
    build_content.add_widget(action_buttons)

    # Устанавливаем минимальную высоту контента - пересчитал с новыми размерами
    build_content.height = (
            strategy_display.height +
            slider_container.height +
            quick_buttons.height +
            action_buttons.height +
            (build_content.spacing * 3)  # Учитываем spacing между элементами
    )

    build_scroll.add_widget(build_content)
    build_content_container.add_widget(build_scroll)
    build_tab.content = build_content_container

    # === Вкладка "Статистика" ===
    stat_tab = TabbedPanelItem(
        text="Статистика",
        font_size=sp(15) if is_mobile else sp(17),
        color=(0.9, 0.95, 1, 1),
        background_normal='',
        background_down='',
        background_color=(0.25, 0.35, 0.65, 1)
    )

    # Контейнер для статистики
    stat_content_container = BoxLayout(orientation='vertical')

    with stat_content_container.canvas.before:
        Color(0.0, 0.0, 0.0, 1)
        stat_content_container.bg = RoundedRectangle(
            radius=[dp(10)],
            size=stat_content_container.size,
            pos=stat_content_container.pos
        )
        stat_content_container.bind(
            pos=lambda inst, val: setattr(stat_content_container.bg, 'pos', val),
            size=lambda inst, val: setattr(stat_content_container.bg, 'size', val)
        )

    # ScrollView для статистики
    stat_scroll = ScrollView(
        size_hint=(1, 1),
        do_scroll_x=False,
        bar_width=dp(4) if is_mobile else dp(6),
        bar_color=(0.5, 0.5, 0.5, 0.3)
    )

    stats_grid = GridLayout(
        cols=1,
        size_hint_y=None,
        spacing=dp(4) if is_mobile else dp(8),  # Уменьшил spacing
        padding=[dp(4), dp(4), dp(4), dp(4)] if is_mobile else [dp(8), dp(8), dp(8), dp(8)]  # Уменьшил padding
    )
    stats_grid.bind(minimum_height=stats_grid.setter('height'))

    # Данные статистики - более компактные
    stats_data = [
        ("Больницы", format_number(faction.hospitals), (0.85, 0.4, 0.4, 1)),
        ("Фабрики", format_number(faction.factories), (0.4, 0.85, 0.5, 1)),
        ("Рабочих на фабриках", format_number(faction.work_peoples), (0.9, 0.7, 0.4, 1)),
        ("Прирост рабочих", format_number(faction.clear_up_peoples), (0.5, 0.7, 0.95, 1)),
        ("Расход на больницы", format_number(faction.money_info), (0.95, 0.5, 0.5, 1)),
        ("Прирост кристаллов", format_number(faction.food_info), (0.6, 0.6, 1, 1)),
        ("Доход от налогов", format_number(faction.taxes_info), (0.95, 0.9, 0.5, 1)),
        ("Эффект налогов (дополнительно пришло людей)",
         format_number(faction.apply_tax_effect(int(faction.current_tax_rate[:-1]))) if faction.tax_set else "–",
         (0.95, 0.6, 0.95, 1)),
        ("Чистый доход", format_number(faction.money_up), (0.5, 0.95, 0.6, 1))
    ]

    for label_text, value, color in stats_data:
        card = BoxLayout(
            orientation='horizontal',
            size_hint_y=None,
            height=dp(40) if is_mobile else dp(50),  # Уменьшил высоту карточек
            padding=[dp(4), dp(2), dp(4), dp(2)] if is_mobile else [dp(8), dp(4), dp(8), dp(4)]  # Меньше padding
        )
        with card.canvas.before:
            Color(0.18, 0.23, 0.38, 1)
            card.bg = RoundedRectangle(radius=[dp(6)], size=card.size, pos=card.pos)  # Меньше радиус
            card.bind(
                pos=lambda inst, val, bg=card.bg: setattr(bg, 'pos', val),
                size=lambda inst, val, bg=card.bg: setattr(bg, 'size', val)
            )

        left_col = BoxLayout(orientation='vertical', size_hint_x=0.7, spacing=dp(0))
        title = Label(
            text=label_text,
            font_size=sp(12) if is_mobile else sp(14),  # Меньше шрифт
            bold=True,
            color=(0.92, 0.95, 1, 1),
            halign='left',
            valign='middle',
            text_size=(dp(130) if is_mobile else None, None)
        )
        title.bind(size=title.setter('text_size'))
        left_col.add_widget(title)

        value_label = Label(
            text=str(value),
            font_size=sp(14) if is_mobile else sp(16),  # Меньше шрифт
            bold=True,
            color=color,
            halign='right',
            valign='middle',
            size_hint_x=0.3
        )
        value_label.bind(size=value_label.setter('text_size'))

        card.add_widget(left_col)
        card.add_widget(value_label)
        stats_grid.add_widget(card)

    stat_scroll.add_widget(stats_grid)
    stat_content_container.add_widget(stat_scroll)
    stat_tab.content = stat_content_container

    # Добавление вкладок
    tab_panel.add_widget(build_tab)
    tab_panel.add_widget(stat_tab)
    main_layout.add_widget(tab_panel)

    # === ЛОГИКА ===
    RATIOS = [(5, 2), (3, 2), (3, 1), (2, 1), (1, 1), (1, 2), (1, 3), (2, 3), (2, 5)]
    RATIO_NAMES = [
        "x2.5 рост населения", "Небольшой прирост", "Тройной рост населения",
        "Двойной рост населения", "Баланс", "Двойной рост добычи",
        "Тройной рост добычи", "Небольшой рост добычи", "x2.5 рост добычи"
    ]
    RATIO_DESCS = [
        "Средний рост населения и потребление кристаллов",
        "Умеренный прирост населения",
        "Сильный рост населения и потребление кристаллов",
        "Серьезный акцент на рост населения, стоит задуматься о закупке кристаллов",
        "Идеально если не знаете что выбрать",
        "Серьезный уклон в производство, людей может не хватать",
        "Усиленный фокус на добычу кристаллов может ощущаться острая нехватка людей",
        "Умеренный уклон в производство кристаллов",
        "Средний рост кристаллов"
    ]

    def update_ui(instance, value):
        idx = int(value)
        h, f = RATIOS[idx]

        # Обновляем главное название стратегии
        strategy_main_name.text = RATIO_NAMES[idx]

        # Обновляем описание под названием
        strategy_description.text = RATIO_DESCS[idx]

    # Загрузка текущих настроек
    if hasattr(faction, 'auto_build_ratio') and faction.auto_build_ratio in RATIOS:
        slider.value = RATIOS.index(faction.auto_build_ratio)

    update_ui(None, slider.value)
    slider.bind(value=update_ui)

    def apply_settings(instance):
        idx = int(slider.value)
        faction.auto_build_ratio = RATIOS[idx]
        faction.auto_build_enabled = True
        faction.save_auto_build_settings()
        dev_popup.dismiss()
        show_message("Сохранение...", f"Как прикажете!")

    apply_btn.bind(on_release=apply_settings)
    cancel_btn.bind(on_release=lambda _: dev_popup.dismiss())

    dev_popup.content = main_layout
    dev_popup.open()


# --------------------------
def start_economy_mode(faction, game_area, db_conn, season_manager):
    """Инициализация экономического режима для выбранной фракции"""
    from kivy.metrics import dp, sp
    from kivy.uix.widget import Widget
    is_android = platform == 'android'

    economy_layout = BoxLayout(
        orientation='horizontal',
        size_hint=(1, None),
        height=dp(70) if is_android else 60,
        pos_hint={'x': -0.34, 'y': 0},
        spacing=dp(10) if is_android else 10,
        padding=[dp(10), dp(5), dp(10), dp(5)] if is_android else [10, 5, 10, 5]
    )

    # Добавляем пустое пространство слева
    economy_layout.add_widget(Widget(size_hint_x=None, width=dp(20)))

    def create_styled_button(text, on_press_callback):
        button = Button(
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
        with button.canvas.before:
            Color(0.2, 0.8, 0.2, 1)
            button.rect = RoundedRectangle(pos=button.pos, size=button.size, radius=[15])

        def update_rect(instance, value):
            instance.rect.pos = instance.pos
            instance.rect.size = instance.size

        button.bind(pos=update_rect, size=update_rect)
        button.bind(on_release=on_press_callback)
        return button

    dev_btn = create_styled_button("Развитие", lambda x: open_development_popup(faction))
    trade_btn = create_styled_button("Рынок", lambda x: open_trade_popup(faction))
    tax_btn = create_styled_button("Налоги", lambda x: open_tax_popup(faction))

    economy_layout.add_widget(create_styled_button("Мастерская", lambda x: workshop(faction, db_conn)))
    economy_layout.add_widget(
        create_styled_button("Артефакты", lambda x: open_artifacts_popup(faction, season_manager)))
    economy_layout.add_widget(dev_btn)
    economy_layout.add_widget(trade_btn)
    economy_layout.add_widget(tax_btn)

    game_area.add_widget(economy_layout)
