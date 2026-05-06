
from fight import fight
from db_lerdon_connect import *

def format_number(number):
    """Форматирует число с добавлением приставок (тыс., млн., млрд., трлн., квадр., квинт., секст., септил., октил., нонил., децил., андец.)"""
    if not isinstance(number, (int, float)):
        return str(number)
    if number == 0:
        return "0"

    absolute = abs(number)
    sign = -1 if number < 0 else 1

    if absolute >= 1_000_000_000_000_000_000_000_000_000_000_000_000:  # 1e36
        return f"{sign * absolute / 1e36:.1f} андец."
    elif absolute >= 1_000_000_000_000_000_000_000_000_000_000_000:  # 1e33
        return f"{sign * absolute / 1e33:.1f} децил."
    elif absolute >= 1_000_000_000_000_000_000_000_000_000_000:  # 1e30
        return f"{sign * absolute / 1e30:.1f} нонил."
    elif absolute >= 1_000_000_000_000_000_000_000_000_000:  # 1e27
        return f"{sign * absolute / 1e27:.1f} октил."
    elif absolute >= 1_000_000_000_000_000_000_000_000:  # 1e24
        return f"{sign * absolute / 1e24:.1f} септил."
    elif absolute >= 1_000_000_000_000_000_000_000:  # 1e21
        return f"{sign * absolute / 1e21:.1f} секст."
    elif absolute >= 1_000_000_000_000_000_000:  # 1e18
        return f"{sign * absolute / 1e18:.1f} квинт."
    elif absolute >= 1_000_000_000_000_000:  # 1e15
        return f"{sign * absolute / 1e15:.1f} квадр."
    elif absolute >= 1_000_000_000_000:  # 1e12
        return f"{sign * absolute / 1e12:.1f} трлн."
    elif absolute >= 1_000_000_000:  # 1e9
        return f"{sign * absolute / 1e9:.1f} млрд."
    elif absolute >= 1_000_000:  # 1e6
        return f"{sign * absolute / 1e6:.1f} млн."
    elif absolute >= 1_000:  # 1e3
        return f"{sign * absolute / 1e3:.1f} тыс."
    else:
        return f"{number}"

class AIController:
    def __init__(self, faction, conn=None, season_manager=None):
        """

        :type season_manager: экземпляр SeasonManager из game_process.py
        """
        self.faction = faction
        self.season_manager = season_manager
        self.turn = 0
        self.db_connection = conn
        self.cursor = self.db_connection.cursor()
        self.garrison = self.load_garrison()
        self.relations = self.load_relations()
        self.previous_crowns = 0
        self.previous_raw = 0
        self.buildings = {}
        self.hospitals = 0
        self.factories = 0
        self.taxes = 0
        self.food_info = 0
        self.work_peoples = 0
        self.money_info = 0
        self.born_peoples = 0
        self.money_up = 0
        self.taxes_info = 0
        self.food_peoples = 0
        self.tax_effects = 0
        self.total_consumption = 0
        self.city_count = 0
        self.army = self.load_army()
        self.cities = self.load_cities()
        self.army_limit = self.calculate_army_limit()
        self.attacking_army = []
        self.average_deal_ratio = 0
        self.hero_used_in_turn = False
        # Инициализация ресурсов по умолчанию
        self.money = 2000
        self.free_peoples = 0
        self.raw_material = 0
        self.population = 100
        self.resources = {
            'Кроны': self.money,
            'Рабочие': self.free_peoples,
            'Кристаллы': self.raw_material,
            'Население': self.population,
            'Текущее потребление': self.total_consumption,
            'Лимит армии': self.army_limit
        }

    # Методы загрузки данных из БД
    def load_resources(self):
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

        except sqlite3.Error as e:
            print(f"Ошибка при загрузке ресурсов: {e}")

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

            for row in rows:
                city_name, building_type, count = row
                if city_name not in self.cities_buildings:
                    self.cities_buildings[city_name] = {"Больница": 0, "Фабрика": 0}

                # Обновление данных для конкретного города
                if building_type == "Больница":
                    self.cities_buildings[city_name]["Больница"] += count
                    total_hospitals += count
                elif building_type == "Фабрика":
                    self.cities_buildings[city_name]["Фабрика"] += count
                    total_factories += count

            # Обновление глобальных показателей
            self.hospitals = total_hospitals
            self.factories = total_factories

        except sqlite3.Error as e:
            print(f"Ошибка при загрузке зданий: {e}")

    def load_relations(self):
        """
        Загружает отношения текущей фракции с остальными из базы данных.
        Возвращает словарь, где ключи — названия фракций, а значения — уровни отношений.
        """
        try:
            # Выполняем запрос к таблице relations
            self.cursor.execute('''
                SELECT faction2, relationship
                FROM relations
                WHERE faction1 = ?
            ''', (self.faction,))
            rows = self.cursor.fetchall()

            # Преобразуем результат в словарь
            relations = {faction2: relationship for faction2, relationship in rows}
            return relations

        except sqlite3.Error as e:
            print(f"Ошибка при загрузке отношений: {e}")
            return {}

    def load_garrison(self):
        """
        Загружает гарнизон фракции из базы данных.
        Использует JOIN с таблицей units для фильтрации по faction.
        """
        try:
            # SQL-запрос с JOIN для получения гарнизона
            query = """
                SELECT g.city_name, g.unit_name, g.unit_count, u.faction
                FROM garrisons g
                JOIN units u ON g.unit_name = u.unit_name
                WHERE u.faction = ?
            """
            self.cursor.execute(query, (self.faction,))
            rows = self.cursor.fetchall()
            garrison = {}
            for row in rows:
                city_name, unit_name, count, faction = row
                if faction != self.faction:
                    continue  # Пропускаем юниты, не принадлежащие текущей фракции
                if city_name not in garrison:
                    garrison[city_name] = []
                garrison[city_name].append({
                    "unit_name": unit_name,
                    "unit_count": count
                })
            print(f"Гарнизон для фракции {self.faction} успешно загружен: {garrison}")
            return garrison
        except Exception as e:
            print(f"Ошибка при загрузке гарнизона для фракции {self.faction}: {e}")
            return {}

    def load_army(self):
        query = """
            SELECT unit_name, cost_money, cost_time, attack, defense, durability, unit_class, consumption 
            FROM units 
            WHERE faction = ?
        """
        self.cursor.execute(query, (self.faction,))
        return {
            row[0]: {  # unit_name
                "cost": {  # Стоимость юнита
                    "money": row[1],  # cost_money
                    "time": row[2]  # cost_time
                },
                "stats": {  # Характеристики юнита
                    "Атака": row[3],
                    "Защита": row[4],
                    "Прочность": row[5],
                    "Класс": row[6]
                },
                "consumption": row[7]
            } for row in self.cursor.fetchall()
        }

    def load_cities(self):
        """
        Загружает список городов для текущей фракции из таблицы cities.
        Выводит отладочную информацию о загруженных городах.
        Также подсчитывает количество городов и сохраняет его в self.city_count.
        """
        try:
            # SQL-запрос для получения списка городов
            query = """
                SELECT id, name 
                FROM cities 
                WHERE faction = ?
            """
            self.cursor.execute(query, (self.faction,))
            rows = self.cursor.fetchall()

            # Преобразуем результат в словарь {id: name}
            cities = {row[0]: row[1] for row in rows}

            # Подсчет количества городов
            self.city_count = len(cities)  # Сохраняем количество городов

            # Отладочный вывод: информация о загруженных городах
            print(f"Загружены города для фракции '{self.faction}':")
            if cities:
                for city_name, city_name in cities.items():
                    print(f"  ID: {city_name}, Название: {city_name}")
            else:
                print("  Города не найдены.")

            return cities
        except sqlite3.Error as e:
            print(f"Ошибка при загрузке городов для фракции '{self.faction}': {e}")
            return {}

    # Методы сохранения данных в БД
    def save_resources_to_db(self):
        """
        Сохраняет текущие ресурсы фракции в таблицу resources.
        Обновляет только существующие записи, не добавляет новые.
        """
        try:
            for resource_type, amount in self.resources.items():
                # Проверяем, существует ли запись
                self.cursor.execute('''
                    SELECT amount
                    FROM resources
                    WHERE faction = ? AND resource_type = ?
                ''', (self.faction, resource_type))
                existing_record = self.cursor.fetchone()

                if existing_record:
                    # Обновляем существующую запись
                    self.cursor.execute('''
                        UPDATE resources
                        SET amount = ?
                        WHERE faction = ? AND resource_type = ?
                    ''', (amount, self.faction, resource_type))
                else:
                    # Если записи нет, пропускаем её (не добавляем новую)
                    pass

            # Сохраняем изменения в базе данных
            self.db_connection.commit()
        except sqlite3.Error as e:
            print(f"Ошибка при сохранении ресурсов: {e}")

    def save_buildings(self):
        """
        Сохраняет данные о зданиях в базу данных.
        Удаляет старые записи для текущей фракции и добавляет новые.
        """
        try:
            # Удаляем старые записи для текущей фракции
            self.cursor.execute("DELETE FROM buildings WHERE faction = ?", (self.faction,))

            # Вставляем новые записи для каждого города и типа здания
            for city_name, data in self.buildings.items():
                for building_type, count in data["Здания"].items():
                    if count > 0:  # Сохраняем только те здания, количество которых больше 0
                        self.cursor.execute("""
                            INSERT INTO buildings (faction, city_name, building_type, count)
                            VALUES (?, ?, ?, ?)
                        """, (self.faction, city_name, building_type, count))

            # Сохраняем изменения в базе данных
            self.db_connection.commit()
            print("Данные о зданиях успешно сохранены в БД.")
        except sqlite3.Error as e:
            print(f"Ошибка при сохранении данных о зданиях: {e}")

    def save_buildings_to_db(self):
        """
        Сохраняет текущие значения больниц и фабрик в базу данных.
        """
        try:
            # Удаляем старые записи для текущей фракции
            self.cursor.execute("""
                DELETE FROM buildings
                WHERE faction = ?
            """, (self.faction,))

            # Вставляем новые записи
            for city_name, data in self.buildings.items():
                hospital_count = data["Здания"]["Больница"]
                factory_count = data["Здания"]["Фабрика"]

                if hospital_count > 0:
                    self.cursor.execute("""
                        INSERT INTO buildings (faction, city_name, building_type, count)
                        VALUES (?, ?, ?, ?)
                    """, (self.faction, city_name, "Больница", hospital_count))

                if factory_count > 0:
                    self.cursor.execute("""
                        INSERT INTO buildings (faction, city_name, building_type, count)
                        VALUES (?, ?, ?, ?)
                    """, (self.faction, city_name, "Фабрика", factory_count))

            # Сохраняем изменения
            self.db_connection.commit()
            print("Данные о зданиях успешно сохранены в БД.")
        except sqlite3.Error as e:
            print(f"Ошибка при сохранении данных о зданиях: {e}")

    def save_garrison(self):
        """
        Сохраняет гарнизон в базу данных.
        Обновляет существующие записи или создает новые, если их нет, ориентируясь на city_name и unit_name.
        Также обновляет данные в таблице results с учетом фракции и количества юнитов.
        """
        try:
            # Для каждого города обновляем или добавляем записи гарнизона
            for city_name, units in self.garrison.items():
                # Проверяем, принадлежит ли город текущей фракции
                self.cursor.execute("""
                    SELECT faction
                    FROM cities
                    WHERE name = ?
                """, (city_name,))
                result = self.cursor.fetchone()
                if not result or result[0] != self.faction:
                    print(f"Город {city_name} не принадлежит фракции {self.faction}. Пропускаем сохранение гарнизона.")
                    continue

                # Если город принадлежит фракции, сохраняем юниты
                for unit in units:
                    unit_name = unit['unit_name']
                    unit_count = unit['unit_count']
                    unit_image = self.get_unit_image(unit_name)
                    print(f"  Обработка юнита: {unit_name}, Количество: {unit_count}, Изображение: {unit_image}")

                    # Проверяем, существует ли уже запись для данного city_name и unit_name
                    self.cursor.execute("""
                        SELECT unit_count
                        FROM garrisons
                        WHERE city_name = ? AND unit_name = ?
                    """, (city_name, unit_name))
                    existing_record = self.cursor.fetchone()

                    if existing_record:
                        # Если запись существует, обновляем количество юнитов
                        new_count = existing_record[0] + unit_count
                        self.cursor.execute("""
                            UPDATE garrisons
                            SET unit_count = ?
                            WHERE city_name = ? AND unit_name = ?
                        """, (new_count, city_name, unit_name))
                    else:
                        # Если записи нет, добавляем новую
                        self.cursor.execute("""
                            INSERT INTO garrisons (city_name, unit_name, unit_count, unit_image)
                            VALUES (?, ?, ?, ?)
                        """, (city_name, unit_name, unit_count, unit_image))

                    # Обновляем данные в таблице results
                    self.cursor.execute("""
                        INSERT INTO results (faction, Units_Combat)
                        VALUES (?, ?)
                        ON CONFLICT(faction) DO UPDATE SET Units_Combat = Units_Combat + excluded.Units_Combat
                    """, (self.faction, unit_count))

            # Сохраняем изменения в базе данных
            self.db_connection.commit()
            print("Гарнизон успешно сохранен в БД.")
        except sqlite3.Error as e:
            print(f"Ошибка при сохранении гарнизона: {e}")

    def manage_buildings(self):
        """
        Управляет строительством зданий для ИИ.
        Строит больницы и фабрики во всех городах до достижения лимита (12 каждого типа, 24 всего).
        """
        try:
            crowns = self.resources['Кроны']
            building_budget = int(crowns * 0.99)

            if building_budget < 10:
                print("Недостаточно средств для строительства.")
                return

            # Лимиты на город: 12 больниц + 12 фабрик = 24 всего
            max_hospitals_per_city = 12
            max_factories_per_city = 12

            # Загружаем города, чтобы знать сколько их
            self.cities = self.load_cities()
            num_cities = max(len(self.cities), 1)

            # Передаём достаточно большой count: build_in_city сам ограничивает по лимиту города и деньгам
            self.build_in_city("Больница", max_hospitals_per_city * num_cities)
            self.build_in_city("Фабрика", max_factories_per_city * num_cities)

            self.save_all_data()
        except Exception as e:
            print(f"Ошибка в manage_buildings: {e}")

    def build_in_city(self, building_type, count):
        """
        Строительство зданий во всех городах фракции до достижения лимита.
        :param building_type: Тип здания ("Больница" или "Фабрика").
        :param count: Максимальное суммарное количество зданий для постройки за вызов.
        """
        cost = 10

        # Загружаем актуальные данные о городах фракции
        self.cities = self.load_cities()
        if not self.cities:
            print(f"Нет доступных городов для строительства у фракции '{self.faction}'.")
            return False

        # Загружаем актуальные данные о зданиях (в self.cities_buildings)
        self.load_buildings()

        max_buildings_per_city = 24
        max_type_per_city = 12  # Лимит одного типа здания на город

        total_built = 0

        for target_city in self.cities.values():
            if count <= 0:
                break
            if self.resources['Кроны'] < cost:
                print("Недостаточно крон для дальнейшего строительства.")
                break

            city_b = self.cities_buildings.get(target_city, {"Больница": 0, "Фабрика": 0})
            current_hospitals = city_b.get("Больница", 0)
            current_factories = city_b.get("Фабрика", 0)
            total_buildings = current_hospitals + current_factories
            current_type = current_hospitals if building_type == 'Больница' else current_factories

            remaining_total = max_buildings_per_city - total_buildings
            remaining_type = max_type_per_city - current_type
            remaining_slots = min(remaining_total, remaining_type)

            if remaining_slots <= 0:
                print(f"В городе {target_city} достигнут лимит {building_type}.")
                continue

            can_afford = self.resources['Кроны'] // cost
            count_to_build = min(count, remaining_slots, can_afford)

            if count_to_build <= 0:
                continue

            total_cost = cost * count_to_build

            # Обновляем self.buildings (используется в save_buildings)
            self.buildings.setdefault(target_city, {"Здания": {"Больница": 0, "Фабрика": 0}})
            self.buildings[target_city]["Здания"][building_type] += count_to_build

            # Обновляем self.cities_buildings, чтобы учитывать постройки в рамках этого вызова
            self.cities_buildings.setdefault(target_city, {"Больница": 0, "Фабрика": 0})
            self.cities_buildings[target_city][building_type] = (
                self.cities_buildings[target_city].get(building_type, 0) + count_to_build
            )

            if building_type == 'Больница':
                self.hospitals += count_to_build
            elif building_type == 'Фабрика':
                self.factories += count_to_build

            self.resources['Кроны'] -= total_cost
            count -= count_to_build
            total_built += count_to_build

            print(f"Построено {count_to_build} {building_type} в городе {target_city}")

        return total_built > 0

    def sell_resources(self):
        if self.resources['Кристаллы'] > 100:
            amount_to_sell = int(self.resources['Кристаллы'] * 0.95)
            earned_crowns = int(amount_to_sell * self.raw_material_price)
            self.resources['Кристаллы'] -= amount_to_sell
            self.resources['Кроны'] += earned_crowns

            # Рассчитываем эффективность сделки (цена за единицу Кристаллы)
            price_per_lot = self.raw_material_price / 100
            self.update_economic_efficiency(price_per_lot)  # Обновляем эффективность

            print(f"Продано {amount_to_sell} Кристаллы за {earned_crowns} крон.")
            return True
        else:
            print("Недостаточно Кристаллы для продажи.")
            return False

    def hire_army(self):
        """
        Найм армии с учётом количества городов и классов юнитов:
        - Меньше 5 городов: строятся атакующие юниты и герои (атакующий + 2 класс, если есть).
        - 5 или более городов: строятся рандомные герои 3 класса и юниты 1 класса.
        - После 14 хода: возможен найм героя 4 класса.
        - Ресурсы распределяются: 40% на юниты, остаток на героев.
        """
        self.update_buildings_for_current_cities()

        # Текущие ресурсы
        crowns = self.resources['Кроны']
        works = self.resources['Рабочие']

        if crowns <= 0 or works <= 0:
            print("Недостаточно средств для найма армии.")
            return

        # Рассчитываем текущее потребление
        self.calculate_current_consumption()
        available_consumption = self.army_limit - self.total_consumption

        if available_consumption <= 0:
            print("Потребление полностью исчерпано. Наем невозможен.")
            return

        # Выбираем город с максимальным развитием
        target_city = max(
            self.buildings.items(),
            key=lambda x: sum(x[1]['Здания'].values()),
            default=(None, None)
        )[0]

        if not target_city:
            print("Нет доступных городов для найма.")
            return

        new_garrison = {target_city: []}

        # --- Шаг 1: Распределяем ресурсы ---
        resource_percentage_for_units = 0.4  # 40% на юниты
        crowns_for_units = int(crowns * resource_percentage_for_units)
        works_for_units = int(works * resource_percentage_for_units)
        consumption_for_units = int(available_consumption * resource_percentage_for_units)

        crowns_for_heroes = crowns - crowns_for_units
        works_for_heroes = works - works_for_units
        consumption_for_heroes = available_consumption - consumption_for_units

        # --- Шаг 2: Найм юнитов ---
        self.hire_units(new_garrison, crowns_for_units, works_for_units, consumption_for_units)

        # --- Шаг 3: Найм героев ---
        city_count = self.get_city_count_for_faction()
        hired_hero_3_class_name = None  # Для хранения имени нанятого героя 3 класса

        if city_count < 5:
            hired_hero_3_class = self.hire_for_less_than_5_cities(new_garrison, crowns_for_heroes, works_for_heroes,
                                                                  consumption_for_heroes)
            # Если был нанят герой 3 класса, получаем его имя
            if hired_hero_3_class:
                for unit in new_garrison[target_city]:
                    unit_name = unit["unit_name"]
                    unit_data = self.army.get(unit_name)
                    if unit_data and unit_data["stats"]["Класс"] == "3":
                        hired_hero_3_class_name = unit_name
                        break
        else:
            hired_hero_3_class = self.hire_for_more_than_5_cities(new_garrison, crowns_for_heroes, works_for_heroes,
                                                                  consumption_for_heroes)
            # Если был нанят герой 3 класса, получаем его имя
            if hired_hero_3_class:
                for unit in new_garrison[target_city]:
                    unit_name = unit["unit_name"]
                    unit_data = self.army.get(unit_name)
                    if unit_data and unit_data["stats"]["Класс"] == "3":
                        hired_hero_3_class_name = unit_name
                        break

        # --- Шаг 4: После 14 хода — герой 4 класса ---
        if self.turn > 14:
            self.try_hire_class_4_hero(new_garrison, crowns_for_heroes, works_for_heroes, consumption_for_heroes)

        # --- Шаг 5: Сохранение изменений и экипировка героя ИИ ---
        if any(new_garrison[target_city]):
            self.garrison.update(new_garrison)
            self.save_garrison()
            self.calculate_and_deduct_consumption()
            print(f"Гарнизон обновлён: {new_garrison}")

            # --- НОВЫЙ КОД: Экипировка героя ИИ после сохранения всех данных ---
            if hired_hero_3_class_name:
                # Планируем выполнение экипировки на следующем кадре, чтобы убедиться,
                # что все данные сохранены в БД
                from kivy.clock import Clock
                Clock.schedule_once(lambda dt: self.try_equip_random_artifacts_for_ai_hero(hired_hero_3_class_name), 0)

        else:
            print("Не удалось нанять ни одного юнита.")

    def hire_units(self, new_garrison, crowns, works, available_consumption):
        """
        Найм юнитов для текущего города.
        """
        target_city = list(new_garrison.keys())[0]

        # Класс 1 юниты
        class_1_units = {
            name: data for name, data in self.army.items()
            if data["stats"]["Класс"] == "1"
        }

        for unit_name, unit_data in class_1_units.items():
            cost_money = unit_data['cost']['money']
            cost_time = unit_data['cost']['time']
            consumption = unit_data['consumption']

            max_affordable = min(
                crowns // cost_money,
                works // cost_time,
                available_consumption // consumption
            )

            if max_affordable > 0:
                self.resources['Кроны'] -= cost_money * max_affordable
                self.resources['Рабочие'] -= cost_time * max_affordable
                available_consumption -= consumption * max_affordable

                new_garrison[target_city].append({
                    "unit_name": unit_name,
                    "unit_count": max_affordable
                })
                print(f"Нанято {max_affordable} юнитов '{unit_name}'")

    def hire_for_more_than_5_cities(self, new_garrison, crowns, works, available_consumption):
        """
        Логика найма героев для фракций с 5 или более городами.
        - Герои 2 класса нанимаются без проверки характеристик.
        - Герои 3 класса могут быть любыми.
        """
        target_city = list(new_garrison.keys())[0]

        # Герои 2 и 3 класса
        hero_candidates = {
            name: data for name, data in self.army.items()
            if data["stats"]["Класс"] in ["2", "3"]
        }

        hired_hero_3_class = False  # Флаг для отслеживания найма героя 3 класса

        for unit_name, unit_data in hero_candidates.items():
            if self.is_unit_already_hired(unit_name):
                continue

            # Проверяем, есть ли уже герой этого класса
            hero_class = unit_data["stats"]["Класс"]

            # Разрешаем одновременный найм героев 2 и 3 класса
            if hero_class == "2" and self.has_hero_of_class("2"):
                continue  # Если уже есть герой 2 класса, пропускаем
            if hero_class == "3" and self.has_hero_of_class("3"):
                continue  # Если уже есть герой 3 класса, пропускаем

            cost_money = unit_data['cost']['money']
            cost_time = unit_data['cost']['time']
            consumption = unit_data['consumption']

            if (crowns >= cost_money and works >= cost_time and
                    available_consumption >= consumption):
                self.resources['Кроны'] -= cost_money
                self.resources['Рабочие'] -= cost_time
                available_consumption -= consumption

                new_garrison[target_city].append({
                    "unit_name": unit_name,
                    "unit_count": 1
                })
                print(f"Нанят герой '{unit_name}' ({hero_class} класс)")

                # --- НОВЫЙ КОД: Создание слотов и экипировка для героя 3 класса ---
                if hero_class == "3":
                    hired_hero_3_class = True
                    self.create_empty_equipment_slots_for_ai_hero(unit_name)
                    # Планируем экипировку после сохранения всех данных
                    # Вызовем позже в hire_army после сохранения гарнизона

                break  # Только один герой за раз

        # Возвращаем флаг, чтобы знать, был ли нанят герой 3 класса
        return hired_hero_3_class

    def hire_for_less_than_5_cities(self, new_garrison, crowns, works, available_consumption):
        """
        Логика найма героев для фракций с менее чем 5 городами.
        - Герои 2 класса нанимаются без проверки характеристик.
        - Герои 3 класса должны быть атакующими (атака > защиты).
        """
        target_city = list(new_garrison.keys())[0]

        # Все герои 2 и 3 класса
        hero_candidates = {
            name: data for name, data in self.army.items()
            if data["stats"]["Класс"] in ["2", "3"]
        }

        hired_hero_3_class = False  # Флаг для отслеживания найма героя 3 класса

        for unit_name, unit_data in hero_candidates.items():
            if self.is_unit_already_hired(unit_name):
                continue

            # Проверяем, есть ли уже герой этого класса
            hero_class = unit_data["stats"]["Класс"]

            # Разрешаем одновременный найм героев 2 и 3 класса
            if hero_class == "2" and self.has_hero_of_class("2"):
                continue  # Если уже есть герой 2 класса, пропускаем
            if hero_class == "3" and self.has_hero_of_class("3"):
                continue  # Если уже есть герой 3 класса, пропускаем

            # Для героев 3 класса проверяем характеристики (атака > защиты)
            if hero_class == "3":
                if unit_data["stats"]["Атака"] <= unit_data["stats"]["Защита"]:
                    continue

            cost_money = unit_data['cost']['money']
            cost_time = unit_data['cost']['time']
            consumption = unit_data['consumption']

            if (crowns >= cost_money and works >= cost_time and
                    available_consumption >= consumption):
                self.resources['Кроны'] -= cost_money
                self.resources['Рабочие'] -= cost_time
                available_consumption -= consumption

                new_garrison[target_city].append({
                    "unit_name": unit_name,
                    "unit_count": 1
                })
                print(f"Нанят герой '{unit_name}' ({hero_class} класс)")

                # --- НОВЫЙ КОД: Создание слотов и экипировка для героя 3 класса ---
                if hero_class == "3":
                    hired_hero_3_class = True
                    self.create_empty_equipment_slots_for_ai_hero(unit_name)
                    # Планируем экипировку после сохранения всех данных
                    # Вызовем позже в hire_army после сохранения гарнизона

                break  # Только один герой за раз

        # Возвращаем флаг, чтобы знать, был ли нанят герой 3 класса
        return hired_hero_3_class

    def create_empty_equipment_slots_for_ai_hero(self, hero_name):
        """
        Создает пустые слоты экипировки в таблице ai_hero_equipment для только что нанятого героя.
        """
        print(f"[DEBUG] Создание пустых слотов экипировки для героя ИИ '{hero_name}' фракции '{self.faction}'")

        try:
            cursor = self.db_connection.cursor()
            # Создаем 5 пустых слотов для героя
            for slot_type in ['0', '1', '2', '3', '4']:
                # Используем INSERT OR IGNORE, чтобы избежать ошибок, если запись уже существует
                cursor.execute('''
                    INSERT OR IGNORE INTO ai_hero_equipment (faction_name, hero_name, slot_type, artifact_id)
                    VALUES (?, ?, ?, ?)
                ''', (self.faction, hero_name, slot_type, None))
            self.db_connection.commit()
            print(f"[SUCCESS] Созданы пустые слоты экипировки в ai_hero_equipment для героя '{hero_name}'")
        except sqlite3.Error as e:
            print(f"[ERROR] Ошибка при создании слотов экипировки для героя '{hero_name}': {e}")
            self.db_connection.rollback()

    def try_hire_class_4_hero(self, new_garrison, crowns, works, available_consumption):
        """
        Логика найма героя 4 класса после 14 хода.
        """
        target_city = list(new_garrison.keys())[0]

        # Герои 4 класса
        hero_candidates = {
            name: data for name, data in self.army.items()
            if data["stats"]["Класс"] == "4"
        }

        for unit_name, unit_data in hero_candidates.items():
            if self.is_unit_already_hired(unit_name):
                continue

            # Проверяем, есть ли уже герой этого класса
            hero_class = unit_data["stats"]["Класс"]
            if self.has_hero_of_class(hero_class):  # Вызываем метод проверки
                continue

            cost_money = unit_data['cost']['money']
            cost_time = unit_data['cost']['time']
            consumption = unit_data['consumption']

            if (crowns >= cost_money and works >= cost_time and
                    available_consumption >= consumption):
                self.resources['Кроны'] -= cost_money
                self.resources['Рабочие'] -= cost_time
                available_consumption -= consumption

                new_garrison[target_city].append({
                    "unit_name": unit_name,
                    "unit_count": 1
                })
                print(f"Нанят герой '{unit_name}'")
                break  # Только один герой за раз

    def try_equip_random_artifacts_for_ai_hero(self, hero_name):
        """
        Пытается купить и экипировать до 5 случайных артефактов герою ИИ.
        Проверяет наличие монет и свободные слоты.
        """
        print(f"[DEBUG] Попытка экипировки случайных артефактов для героя ИИ '{hero_name}' фракции '{self.faction}'")

        try:
            # 1. Загружаем список всех доступных артефактов из БД
            cursor = self.db_connection.cursor()
            cursor.execute("SELECT id, cost, artifact_type FROM artifacts_ai")
            all_artifacts = cursor.fetchall()

            if not all_artifacts:
                print("[INFO] Нет доступных артефактов для покупки.")
                return

            # Преобразуем в список словарей для удобства
            artifact_list = [{"id": row[0], "cost": row[1], "artifact_type": row[2]} for row in all_artifacts]

            # 2. Загружаем текущую экипировку героя из ai_hero_equipment
            cursor.execute('''
                SELECT slot_type, artifact_id
                FROM ai_hero_equipment
                WHERE faction_name = ? AND hero_name = ?
            ''', (self.faction, hero_name))
            equipped_rows = cursor.fetchall()

            # Создаем словарь: slot_type -> artifact_id (None если пуст)
            current_equipment = {row[0]: row[1] for row in equipped_rows}
            print(f"[DEBUG] Текущая экипировка героя {hero_name}: {current_equipment}")

            # 3. Определяем сопоставление artifact_type -> slot_type
            artifact_type_to_slot = {
                0: '0',  # Оружие
                1: '1',  # Голова
                2: '2',  # Сапоги
                3: '3',  # Туловище
                4: '4'  # Аксессуар
            }

            # 4. Перемешиваем список артефактов для случайности
            import random
            random.shuffle(artifact_list)

            # 5. Пытаемся купить и экипировать артефакты
            artifacts_equipped_count = 0
            for artifact in artifact_list:
                art_id = artifact['id']
                art_cost = artifact['cost']
                art_type = artifact['artifact_type']

                slot_type = artifact_type_to_slot.get(art_type)
                if slot_type is None:
                    # print(f"[DEBUG] Пропущен артефакт ID {art_id}, неизвестный тип {art_type}")
                    continue  # Пропускаем артефакты с неизвестным типом

                # Проверяем, свободен ли слот
                if current_equipment.get(slot_type) is not None:
                    # print(f"[DEBUG] Слот {slot_type} уже занят для героя {hero_name}")
                    continue  # Слот занят

                # Проверяем, достаточно ли денег
                if self.resources.get('Кроны', 0) < art_cost:
                    # print(f"[DEBUG] Недостаточно крон для покупки артефакта ID {art_id} (стоимость {art_cost})")
                    continue  # Недостаточно денег

                # --- Покупка артефакта ---
                print(
                    f"[INFO] ИИ '{self.faction}' покупает артефакт ID {art_id} (стоимость {art_cost}) для героя '{hero_name}' в слот {slot_type}")

                # Списываем деньги
                self.resources['Кроны'] -= art_cost
                # Обновляем запись в БД
                cursor.execute('''
                    UPDATE ai_hero_equipment
                    SET artifact_id = ?
                    WHERE faction_name = ? AND hero_name = ? AND slot_type = ?
                ''', (art_id, self.faction, hero_name, slot_type))

                # Обновляем локальную копию экипировки
                current_equipment[slot_type] = art_id

                artifacts_equipped_count += 1

                # Ограничиваем количество покупаемых артефактов, например, 5
                if artifacts_equipped_count >= 5:
                    break

            self.db_connection.commit()  # Сохраняем изменения в БД
            print(f"[SUCCESS] ИИ '{self.faction}' экипировал {artifacts_equipped_count} артефактов герою '{hero_name}'")

        except sqlite3.Error as e:
            print(f"[ERROR] Ошибка при попытке экипировки артефактов герою ИИ '{hero_name}': {e}")
            try:
                self.db_connection.rollback()
            except:
                pass
        except Exception as e:
            print(f"[ERROR] Неожиданная ошибка при экипировке артефактов герою ИИ '{hero_name}': {e}")
            import traceback
            traceback.print_exc()

    def generate_and_buy_artifacts_for_ai_hero(self):
        """
        Генерирует и покупает случайные артефакты для героя ИИ после 40 хода,
        если есть деньги и свободные слоты.
        """
        if self.turn <= 40:
            print(f"[INFO] ИИ '{self.faction}': Пока не достигнуто 40 ходов для генерации артефактов.")
            return

        # Находим всех героев 3-го класса, которые могут носить артефакты
        ai_heroes = self.get_ai_heroes_3_class()
        if not ai_heroes:
            print(f"[INFO] ИИ '{self.faction}': Нет героев 3 класса для экипировки.")
            return

        print(f"[INFO] ИИ '{self.faction}': Проверка возможности генерации артефактов для героев: {ai_heroes}")

        # Проверяем наличие свободных слотов у героев
        hero_with_slot = self.find_hero_with_free_slot(ai_heroes)
        if not hero_with_slot:
            print(f"[INFO] ИИ '{self.faction}': Нет героев с пустыми слотами для артефактов.")
            return

        # Проверяем, достаточно ли денег для покупки артефакта (минимальная стоимость)
        min_cost = 2_000_000  # 2 мл.
        if self.resources.get('Кроны', 0) < min_cost:
            print(
                f"[INFO] ИИ '{self.faction}': Недостаточно крон для генерации артефакта (требуется минимум {format_number(min_cost)}).")
            return

        # --- Генерация артефакта ---
        import random

        # Случайный выбор параметров
        param_choice = random.choice(["attack", "defense", "both"])

        if param_choice == "attack":
            attack = random.randint(8000, 14000)
            defense = 0
        elif param_choice == "defense":
            attack = 0
            defense = random.randint(8000, 14000)
        else:  # both
            attack = random.randint(4000, 13000)
            defense = random.randint(4000, 13000)

        # Случайный выбор слота (0: Оружие, 1: Голова, 2: Сапоги, 3: Туловище, 4: Аксессуар)
        artifact_type = random.choice([0, 1, 2, 3, 4])
        artifact_type_to_slot = {0: '0', 1: '1', 2: '2', 3: '3', 4: '4'}
        slot_type = artifact_type_to_slot[artifact_type]

        # Случайное название
        prefixes = ["Артефакт", "Квантовый", "Атомной", "Сингулярной", "Молекулярной"]
        suffixes = ["Силы", "Защиты", "Быстроты", "Власти", "Хаоса", "Порядка", "Кода"]
        name = f"{random.choice(prefixes)} {random.choice(suffixes)}"

        # Случайная стоимость
        cost = random.randint(2_000_000, 10_000_000)  # 2-10 мл.

        # Сезон (может быть пустым или случайным)
        seasons_list = [[], ["Весна"], ["Лето"], ["Осень"], ["Зима"], ["Весна", "Лето"], ["Лето", "Осень"],
                        ["Осень", "Зима"], ["Зима", "Весна"], ["Весна", "Осень"], ["Лето", "Зима"],
                        ["Весна", "Лето", "Осень"], ["Весна", "Лето", "Зима"], ["Весна", "Осень", "Зима"],
                        ["Лето", "Осень", "Зима"], ["Все"]]
        season_name = ', '.join(random.choice(seasons_list))

        # Случайное изображение (предположим, что у ИИ есть доступ к папке с изображениями артефактов)
        # В реальности, вы можете генерировать изображения или использовать стандартные
        artifact_images_path = "files/pict/artifacts/custom"  # Или другая директория для ИИ
        import os
        if os.path.exists(artifact_images_path):
            image_files = [f for f in os.listdir(artifact_images_path) if
                           f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp'))]
            if image_files:
                image_url = os.path.join(artifact_images_path, random.choice(image_files))
            else:
                print(f"[WARNING] Не найдены изображения в {artifact_images_path}, используем заглушку.")
                image_url = "files/pict/artifacts/custom/default_artifact.png"  # Заглушка
        else:
            print(f"[WARNING] Папка с изображениями артефактов {artifact_images_path} не найдена, используем заглушку.")
            image_url = "files/pict/artifacts/custom/default_artifact.png"  # Заглушка

        # --- Проверка, подходит ли артефакт по слоту и стоимости ---
        # Проверяем, свободен ли слот у выбранного героя
        current_equipment = self.get_current_equipment_for_hero(hero_with_slot)
        if current_equipment.get(slot_type) is not None:
            print(f"[INFO] ИИ '{self.faction}': Слот {slot_type} у героя {hero_with_slot} уже занят.")
            return  # Попробовать другой слот или героя, если нужно, но для простоты возвращаемся

        # Проверяем, хватает ли денег на сгенерированный артефакт
        if self.resources.get('Кроны', 0) < cost:
            print(
                f"[INFO] ИИ '{self.faction}': Недостаточно крон для покупки сгенерированного артефакта (стоимость {format_number(cost)}).")
            return

        # --- Покупка (вставка в БД и списание денег) ---
        try:
            cursor = self.db_connection.cursor()

            # Генерация ID на основе максимального ID в таблице artifacts_ai
            cursor.execute("SELECT MAX(id) FROM artifacts_ai")
            max_id_result = cursor.fetchone()
            new_artifact_id = (max_id_result[0] or 0) + 1

            # Вставка сгенерированного артефакта в таблицу artifacts_ai с указанным ID
            cursor.execute('''
                   INSERT INTO artifacts_ai (id, attack, defense, season_name, image_url, name, cost, artifact_type)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)
               ''', (new_artifact_id, attack, defense, season_name, image_url, name, cost, artifact_type))

            # Списываем деньги
            self.resources['Кроны'] -= cost

            # Экипируем артефакт герою
            cursor.execute('''
                   UPDATE ai_hero_equipment
                   SET artifact_id = ?
                   WHERE faction_name = ? AND hero_name = ? AND slot_type = ?
               ''', (new_artifact_id, self.faction, hero_with_slot, slot_type))

            # ОБЯЗАТЕЛЬНО делаем commit перед применением бонусов!
            self.db_connection.commit()

            # Применяем бонусы артефактов через переданный экземпляр SeasonManager
            # ИСПРАВЛЕНО: используем self.db_connection соединение ИИ с базой
            if self.season_manager:
                self.season_manager.apply_artifact_bonuses(self.db_connection)
                print(f"[INFO] Бонусы артефактов применены для ИИ '{self.faction}' через SeasonManager.")

            print(
                f"[SUCCESS] ИИ '{self.faction}' сгенерировал и экипировал артефакт '{name}' (ID {new_artifact_id}, Атк: {attack}, Защ: {defense}, Стоимость: {format_number(cost)}) герою '{hero_with_slot}' в слот {slot_type}.")

        except Exception as e:
            print(f"[ERROR] ИИ '{self.faction}': Ошибка при генерации/покупке артефакта: {e}")
            import traceback
            traceback.print_exc()  # Для отладки
            try:
                self.db_connection.rollback()
            except:
                pass

    def get_ai_heroes_3_class(self):
        """
        Получает список всех героев 3 класса текущей фракции из БД.
        """
        try:
            cursor = self.db_connection.cursor()
            # Предполагаем, что герои 3 класса хранятся в таблице garrisons
            # и их можно идентифицировать по unit_class в таблице units
            cursor.execute("""
                SELECT DISTINCT g.unit_name
                FROM garrisons g
                JOIN units u ON g.unit_name = u.unit_name
                WHERE u.faction = ? AND u.unit_class = '3'
            """, (self.faction,))
            heroes = [row[0] for row in cursor.fetchall()]
            return heroes
        except sqlite3.Error as e:
            print(f"[ERROR] ИИ '{self.faction}': Ошибка при получении героев 3 класса: {e}")
            return []

    def find_hero_with_free_slot(self, heroes_list):
        """
        Находит первого героя из списка, у которого есть свободный слот.
        """
        for hero_name in heroes_list:
            current_equipment = self.get_current_equipment_for_hero(hero_name)
            # Проверяем, есть ли хотя бы один слот без артефакта (None)
            if any(v is None for v in current_equipment.values()):
                print(f"[INFO] ИИ '{self.faction}': Найден герой {hero_name} с пустыми слотами.")
                return hero_name
        return None

    def get_current_equipment_for_hero(self, hero_name):
        """
        Загружает текущую экипировку героя из ai_hero_equipment.
        """
        try:
            cursor = self.db_connection.cursor()
            cursor.execute('''
                SELECT slot_type, artifact_id
                FROM ai_hero_equipment
                WHERE faction_name = ? AND hero_name = ?
            ''', (self.faction, hero_name))
            equipped_rows = cursor.fetchall()
            # Создаем словарь: slot_type -> artifact_id (None если пуст)
            current_equipment = {str(row[0]): row[1] for row in equipped_rows}
            # Убедимся, что все 5 слотов (0-4) представлены
            for i in range(5):
                slot_key = str(i)
                if slot_key not in current_equipment:
                    current_equipment[slot_key] = None
            return current_equipment
        except sqlite3.Error as e:
            print(f"[ERROR] ИИ '{self.faction}': Ошибка при получении экипировки для {hero_name}: {e}")
            return {}

    def get_city_count_for_faction(self):
        """
        Возвращает количество городов, принадлежащих текущей фракции.
        """
        self.cursor.execute("""
            SELECT COUNT(*) FROM cities 
            WHERE faction = ?
        """, (self.faction,))
        result = self.cursor.fetchone()
        return result[0]

    def has_hero_of_class(self, class_number):
        """Проверяет, есть ли у фракции хотя бы один юнит указанного класса."""
        try:
            # Проверка в текущем гарнизоне (в памяти)
            for units in self.garrison.values():
                for unit in units:
                    unit_name = unit["unit_name"]
                    self.cursor.execute("SELECT unit_class FROM units WHERE unit_name = ?", (unit_name,))
                    result = self.cursor.fetchone()
                    if result and result[0] == str(class_number):
                        return True

            # Проверка в БД (историческая)
            query = """
            SELECT 1
            FROM garrisons g
            JOIN units u ON g.unit_name = u.unit_name
            WHERE u.faction = ? AND u.unit_class = ?
            LIMIT 1
            """
            self.cursor.execute(query, (self.faction, str(class_number)))
            result = self.cursor.fetchone()
            return bool(result)
        except sqlite3.Error as e:
            print(f"[ERROR] Ошибка при проверке наличия героя класса {class_number}: {e}")
            return False

    def is_unit_already_hired(self, unit_name):
        """Проверяет, есть ли указанный юнит в гарнизоне текущей фракции."""
        try:
            query = """
            SELECT 1
            FROM garrisons g
            JOIN units u ON g.unit_name = u.unit_name
            WHERE u.faction = ? AND g.unit_name = ?
            LIMIT 1
            """
            self.cursor.execute(query, (self.faction, unit_name))
            result = self.cursor.fetchone()
            return bool(result)
        except sqlite3.Error as e:
            print(f"[ERROR] Ошибка при проверке наличия юнита '{unit_name}': {e}")
            return False

    def calculate_army_limit(self):
        """
        Рассчитывает максимальный лимит армии на основе базового значения и бонуса от городов.
        """
        base_limit = 6000  # Базовый лимит 11к(6+5)
        city_bonus = 5000 * len(self.cities)  # Бонус за каждый город
        total_limit = base_limit + city_bonus
        return total_limit

    def calculate_current_consumption(self):
        """
        Рассчитывает текущее потребление армии.
        """
        try:
            self.total_consumption = 0  # Сбрасываем предыдущее значение

            # Выгрузка всех гарнизонов из таблицы garrisons
            self.cursor.execute("""
                SELECT city_name, unit_name, unit_count 
                FROM garrisons
            """)
            garrisons = self.cursor.fetchall()

            # Для каждого гарнизона находим соответствующий юнит в таблице units
            for garrison in garrisons:
                city_name, unit_name, unit_count = garrison

                # Получаем потребление юнита
                self.cursor.execute("""
                    SELECT consumption, faction 
                    FROM units 
                    WHERE unit_name = ?
                """, (unit_name,))
                unit_data = self.cursor.fetchone()

                if unit_data:
                    consumption, unit_faction = unit_data
                    if unit_faction == self.faction:
                        # Добавляем потребление данного типа юнита
                        self.total_consumption += consumption * unit_count

            print(f"Текущее потребление Кристаллы: {self.total_consumption}")

        except Exception as e:
            print(f"Ошибка при расчете текущего потребления: {e}")

    def calculate_and_deduct_consumption(self):
        """
        Метод для расчета потребления Кристаллы гарнизонами текущей фракции
        и вычета суммарного потребления из self.raw_material.
        """
        try:
            # Шаг 1: Выгрузка всех гарнизонов из таблицы garrisons
            self.cursor.execute("""
                SELECT city_name, unit_name, unit_count 
                FROM garrisons
            """)
            garrisons = self.cursor.fetchall()

            # Шаг 2: Для каждого гарнизона находим соответствующий юнит в таблице units
            for garrison in garrisons:
                city_name, unit_name, unit_count = garrison

                # Проверяем, к какой фракции принадлежит юнит
                self.cursor.execute("""
                    SELECT consumption, faction 
                    FROM units 
                    WHERE unit_name = ?
                """, (unit_name,))
                unit_data = self.cursor.fetchone()

                if unit_data:
                    consumption, faction = unit_data

                    # Учитываем только юниты текущей фракции
                    if faction == self.faction:
                        # Расчет потребления для данного типа юнита
                        self.total_consumption = consumption * unit_count

            # Шаг 3: Вычитание общего потребления из денег фракции
            self.raw_material -= self.total_consumption
            print(f"Общее потребление Кристаллы: {self.total_consumption}")
            print(f"Остаток Кристаллы у фракции: {self.raw_material}")

        except Exception as e:
            print(f"Произошла ошибка: {e}")

    def calculate_tax_income(self):
        """
        Рассчитывает налоговый доход на основе населения.
        """
        tax_rate = 0.34  # Базовая налоговая ставка (34%)
        return int(self.resources['Население'] * tax_rate)

    def update_buildings_from_db(self):
        """
        Загружает данные о количестве больниц и фабрик из базы данных.
        """
        try:
            query = """
                SELECT building_type, SUM(count)
                FROM buildings
                WHERE faction = ?
                GROUP BY building_type
            """
            self.cursor.execute(query, (self.faction,))
            rows = self.cursor.fetchall()

            # Обновляем количество зданий
            self.hospitals = next((count for b_type, count in rows if b_type == "Больница"), 0)
            self.factories = next((count for b_type, count in rows if b_type == "Фабрика"), 0)

            print(f"Загружены здания: Больницы={self.hospitals}, Фабрики={self.factories}")
        except sqlite3.Error as e:
            print(f"Ошибка при загрузке данных о зданиях: {e}")

    def generate_raw_material_price(self):
        """
        Генерирует новую цену на Кристаллы.
        """
        # Простая реализация: случайная цена в диапазоне
        self.raw_material_price = round(random.uniform(150, 200), 8)
        print(f"Новая цена на Кристаллы: {self.raw_material_price}")

    def update_trade_resources_from_db(self):
        """
        Обновляет ресурсы на основе торговых соглашений из базы данных.
        Учитывает текущую фракцию как инициатора или целевую фракцию.
        """
        try:
            # Убедитесь, что self.faction — это строка (или одиночное значение)
            if isinstance(self.faction, (list, tuple)):
                raise ValueError("self.faction должен быть строкой, а не коллекцией.")

            # Запрос для получения всех торговых соглашений, где текущая фракция участвует
            query = """
                SELECT initiator, target_faction, initiator_type_resource, target_type_resource,
                       initiator_summ_resource, target_summ_resource
                FROM trade_agreements
                WHERE target_faction = ?
            """
            # Передаем self.faction как одиночное значение
            self.cursor.execute(query, (self.faction,))
            rows = self.cursor.fetchall()

            for row in rows:
                initiator, target_faction, initiator_type_resource, target_type_resource, \
                    initiator_summ_resource, target_summ_resource = row

                # Если текущая фракция является инициатором сделки
                if initiator == self.faction:
                    # Отнимаем ресурс, который отдает инициатор
                    if initiator_type_resource in self.resources:
                        self.resources[initiator_type_resource] -= initiator_summ_resource

                    # Добавляем ресурс, который получает инициатор
                    if target_type_resource in self.resources:
                        self.resources[target_type_resource] += target_summ_resource

                # Если текущая фракция является целевой фракцией
                elif target_faction == self.faction:
                    # Отнимаем ресурс, который отдает целевая фракция
                    if target_type_resource in self.resources:
                        self.resources[target_type_resource] -= target_summ_resource

                    # Добавляем ресурс, который получает целевая фракция
                    if initiator_type_resource in self.resources:
                        self.resources[initiator_type_resource] += initiator_summ_resource

            print(f"Ресурсы из торговых соглашений обновлены: {self.resources}")
        except sqlite3.Error as e:
            print(f"Ошибка при обновлении ресурсов из торговых соглашений: {e}")
        except ValueError as ve:
            print(f"Ошибка в данных: {ve}")

    def load_resources_from_db(self):
        """
        Загружает текущие значения ресурсов из базы данных.
        Обновляет глобальные переменные self.money, self.free_peoples,
        self.raw_material, self.population и словарь self.resources.
        """
        try:
            query = "SELECT resource_type, amount FROM resources WHERE faction = ?"
            self.cursor.execute(query, (self.faction,))
            rows = self.cursor.fetchall()

            # Обновление ресурсов на основе данных из базы данных
            for row in rows:
                resource_type, amount = row
                if resource_type == "Кроны":
                    self.money = amount
                elif resource_type == "Рабочие":
                    self.free_peoples = amount
                elif resource_type == "Кристаллы":
                    self.raw_material = amount
                elif resource_type == "Население":
                    self.population = amount

            # Обновление словаря self.resources
            self.resources = {
                'Кроны': self.money,
                'Рабочие': self.free_peoples,
                'Кристаллы': self.raw_material,
                'Население': self.population
            }

            print(f"Ресурсы успешно загружены из БД: {self.resources}")
        except sqlite3.Error as e:
            print(f"Ошибка при загрузке ресурсов из БД: {e}")

    def update_resources(self):
        """
        Обновление текущих ресурсов с учетом данных из базы данных.
        Все расчеты выполняются на основе таблиц в базе данных.
        """

        try:
            self.update_buildings_from_db()

            # Генерируем новую цену на Кристаллы
            self.generate_raw_material_price()

            # Обновляем ресурсы на основе торговых соглашений из таблицы trade_agreements
            self.update_trade_resources_from_db()

            self.process_trade_agreements()

            # Коэффициенты для каждой фракции
            faction_coefficients = {
                'Север': {'money_loss': 15, 'food_loss': 0.4},
                'Эльфы': {'money_loss': 18, 'food_loss': 0.1},
                'Вампиры': {'money_loss': 21, 'food_loss': 0.09},
                'Адепты': {'money_loss': 24, 'food_loss': 0.05},
                'Элины': {'money_loss': 27, 'food_loss': 0.04},
            }

            # Получение коэффициентов для текущей фракции
            faction = self.faction
            if faction not in faction_coefficients:
                raise ValueError(f"Фракция '{faction}' не найдена.")

            coeffs = faction_coefficients[faction]

            # Обновление ресурсов с учетом коэффициентов
            self.born_peoples = int(self.hospitals * 50)
            self.work_peoples = int(self.factories * 20)
            self.clear_up_peoples = (self.born_peoples - self.work_peoples + self.tax_effects) + int(
                self.city_count * (self.population / 100))

            # Загружаем текущие значения ресурсов из базы данных
            self.load_resources_from_db()

            # Выполняем расчеты
            self.free_peoples += self.clear_up_peoples
            self.money += int(self.calculate_tax_income() - (self.hospitals * coeffs['money_loss']))
            self.money_info = int(self.hospitals * coeffs['money_loss'])
            self.money_up = int(self.calculate_tax_income() - (self.hospitals * coeffs['money_loss']))
            self.taxes_info = int(self.calculate_tax_income())


            # Учитываем, что одна фабрика может прокормить 100 людей
            self.raw_material += int((self.factories * 100) - (self.population * coeffs['food_loss']))
            # food_info — база для бонуса «Борьба»: не вычитаем потребление армии,
            # так как армия уже списывает кристаллы напрямую.
            # max(0, ...) — фракция с отрицательным производством просто не получает бонус.
            self.food_info = max(0, int((self.factories * 100) - (self.population * coeffs['food_loss'])))
            self.food_peoples = int(self.population * coeffs['food_loss'])


            # Проверяем, будет ли население увеличиваться
            if self.raw_material > 0:
                self.population += int(self.clear_up_peoples)  # Увеличиваем население только если есть Кристаллы
            else:
                # Логика убыли населения при недостатке Кристаллы
                if self.population > 100:
                    loss = int(self.population * 0.45)  # 45% от населения
                    self.population -= loss
                else:
                    loss = min(self.population, 50)  # Обнуление по 50, но не ниже 0
                    self.population -= loss
                self.free_peoples = 0  # Все рабочие обнуляются, так как Кристаллы нет


            # Проверка, чтобы ресурсы не опускались ниже 0 и не превышали максимальные значения

            self.resources.update({
                "Кроны": max(min(round(self.money, 2), 10_000_000), 0),  # Не более 10 млн, 2 знака
                "Рабочие": max(min(round(self.free_peoples, 2), 500_000), 0),  # Не более 500 тыс, 2 знака
                "Кристаллы": max(min(round(self.raw_material, 2), 10_000_000), 0),  # Не более 10 млн, 2 знака
                "Население": max(min(round(self.population, 2), 1_000_000), 0),  # Не более 1 млн, 2 знака
                "Текущее потребление": self.total_consumption,  # Используем рассчитанное значение
                "Лимит армии": self.army_limit
            })

            self.money = self.resources['Кроны']
            self.free_peoples = self.resources['Рабочие']
            self.raw_material = self.resources['Кристаллы']
            self.population = self.resources['Население']
            self.army_limit = self.resources['Лимит армии']
            self.total_consumption = self.resources['Текущее потребление']
            # Потребление армии
            self.calculate_and_deduct_consumption()
            self.save_resources_to_db()
            print(f"Ресурсы обновлены: {self.resources}, Больницы: {self.hospitals}, Фабрики: {self.factories}")

        except sqlite3.Error as e:
            print(f"Ошибка при обновлении ресурсов: {e}")

    def save_all_data(self):
        try:
            self.save_resources_to_db()
            self.save_buildings()
            self.save_results_to_db()
            print("Все данные успешно сохранены в БД")
        except Exception as e:
            print(f"Ошибка при сохранении данных: {e}")

    def get_unit_image(self, unit_name):
        """
        Получает путь к изображению юнита из базы данных.

        Args:
            unit_name (str): Название юнита

        Returns:
            str: Путь к изображению юнита или пустая строка, если не найдено
        """
        try:
            query = """
                SELECT image_path 
                FROM units 
                WHERE faction = ? AND unit_name = ?
            """
            self.cursor.execute(query, (self.faction, unit_name))
            result = self.cursor.fetchone()
            if result:
                return result[0]  # Возвращаем путь к изображению
            else:
                print(f"Предупреждение: Изображение для юнита '{unit_name}' не найдено")
                return ""
        except Exception as e:
            print(f"Ошибка при получении изображения юнита '{unit_name}': {e}")
            return ""

    def process_trade_agreements(self):
        """
        Обрабатывает торговые соглашения для текущей фракции.
        Если текущая фракция является target_faction, исполняет сделку без проверки выгодности.
        """
        try:
            # Загружаем текущие отношения с другими фракциями
            self.relations = self.load_relations()

            # Запрос для получения всех торговых соглашений, где текущая фракция является целевой
            query = """
                SELECT id, initiator, target_faction, initiator_type_resource, target_type_resource,
                       initiator_summ_resource, target_summ_resource
                FROM trade_agreements
                WHERE target_faction = ? AND agree = 0
            """
            self.cursor.execute(query, (self.faction,))
            rows = self.cursor.fetchall()

            for row in rows:
                trade_id, initiator, target_faction, initiator_type_resource, target_type_resource, \
                    initiator_summ_resource, target_summ_resource = row

                # Проверяем наличие ресурсов у целевой фракции
                has_enough_resources = self.resources.get(target_type_resource, 0) >= target_summ_resource

                if not has_enough_resources:
                    print(f"Отказ от сделки с {initiator}. Недостаточно ресурсов для выполнения сделки.")
                    self.update_agreement_status(trade_id, False)  # Проставляем agree = false
                    continue

                # Проверяем минимальный уровень отношений (если нужен, можно убрать и эту проверку)
                relation_level = int(self.relations.get(initiator, 0))
                if relation_level < 10:  # Минимальный порог отношений
                    print(f"Отказ от сделки с {initiator}. Слишком низкий уровень отношений ({relation_level}).")
                    self.update_agreement_status(trade_id, False)
                    continue

                # Исполняем сделку
                print(
                    f"Исполнение сделки с {initiator}. Ресурсы: отдаем {target_summ_resource} {target_type_resource}, получаем {initiator_summ_resource} {initiator_type_resource}")

                # Выполняем обмен ресурсами
                success = self.execute_trade(initiator, target_faction, initiator_type_resource, target_type_resource,
                                             initiator_summ_resource, target_summ_resource)

                if success:
                    self.update_agreement_status(trade_id, True)  # Проставляем agree = true
                else:
                    self.update_agreement_status(trade_id, False)  # Проставляем agree = false

        except sqlite3.Error as e:
            print(f"Ошибка при обработке торговых соглашений: {e}")

    def update_agreement_status(self, trade_id, status):
        """
        Обновляет значение agree в таблице trade_agreements.
        :param trade_id: ID торгового соглашения
        :param status: True или False
        """
        try:
            query = """
                UPDATE trade_agreements
                SET agree = ?
                WHERE id = ?
            """
            self.cursor.execute(query, (status, trade_id))
            self.db_connection.commit()
            print(f"Статус сделки ID={trade_id} обновлен: agree={status}")
        except sqlite3.Error as e:
            print(f"Ошибка при обновлении статуса сделки: {e}")

    def return_resource_to_player(self, initiator, resource_type, amount):
        """
        Возвращает ресурсы инициатору сделки в случае отказа.
        """
        try:
            self.cursor.execute("""
                UPDATE resources
                SET amount = amount + ?
                WHERE faction = ? AND resource_type = ?
            """, (amount, initiator, resource_type))
            self.db_connection.commit()
            print(f"Возвращено {amount} {resource_type} фракции {initiator}.")
        except sqlite3.Error as e:
            print(f"Ошибка при возврате ресурсов: {e}")

    def execute_trade(self, initiator, target_faction, initiator_type_resource, target_type_resource,
                      initiator_summ_resource, target_summ_resource):
        """
        Выполняет обмен ресурсами между фракциями.
        """
        try:
            # Отнимаем ресурсы у инициатора
            self.cursor.execute("""
                UPDATE resources
                SET amount = amount - ?
                WHERE faction = ? AND resource_type = ?
            """, (initiator_summ_resource, initiator, initiator_type_resource))

            # Добавляем ресурсы целевой фракции
            self.cursor.execute("""
                UPDATE resources
                SET amount = amount + ?
                WHERE faction = ? AND resource_type = ?
            """, (target_summ_resource, target_faction, target_type_resource))

            # Добавляем ресурсы целевой фракции инициатору
            self.cursor.execute("""
                UPDATE resources
                SET amount = amount + ?
                WHERE faction = ? AND resource_type = ?
            """, (initiator_summ_resource, target_faction, initiator_type_resource))

            # Отнимаем ресурсы у целевой фракции
            self.cursor.execute("""
                UPDATE resources
                SET amount = amount - ?
                WHERE faction = ? AND resource_type = ?
            """, (target_summ_resource, initiator, target_type_resource))

            self.db_connection.commit()
            print(f"Обмен ресурсами выполнен: {initiator} <-> {target_faction}.")
        except sqlite3.Error as e:
            print(f"Ошибка при выполнении обмена ресурсами: {e}")

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

    def calculate_army_strength(self):
        """
        Рассчитывает силу армий для каждой фракции.
        :return: Словарь, где ключи — названия фракций, а значения — сила армии.
        """
        class_coefficients = {
            "1": 1.3,  # Класс 1: базовые юниты
            "2": 1.7,  # Класс 2: улучшенные юниты
            "3": 2.0,  # Класс 3: элитные юниты
            "4": 3.0,  # Класс 4: легендарные юниты
            "5": 4.0  # Класс 5: экстраординарные юниты
        }

        army_strength = {}

        try:
            # Получаем все юниты из таблицы garrisons и их характеристики из таблицы units
            query = """
                SELECT g.unit_name, g.unit_count, u.faction, u.attack, u.defense, u.durability, u.unit_class 
                FROM garrisons g
                JOIN units u ON g.unit_name = u.unit_name
            """
            self.cursor.execute(query)
            garrison_data = self.cursor.fetchall()

            # Рассчитываем силу армии для каждой фракции
            for row in garrison_data:
                unit_name, unit_count, faction, attack, defense, durability, unit_class = row

                if not faction:
                    continue

                # Коэффициент класса
                coefficient = class_coefficients.get(unit_class, 1.0)

                # Рассчитываем силу юнита
                unit_strength = (attack * coefficient) + defense + durability

                # Умножаем на количество юнитов
                total_strength = unit_strength * unit_count

                # Добавляем к общей силе фракции
                if faction not in army_strength:
                    army_strength[faction] = 0
                army_strength[faction] += total_strength

        except sqlite3.Error as e:
            print(f"Ошибка при расчете силы армии: {e}")
            return {}

        return army_strength

    def notify_player_about_war(self, faction):
        """
        Создает уведомление для игрока о том, что фракция объявила войну.
        :param faction: Название фракции
        """
        try:
            # Здесь можно интегрировать логику для отображения окна уведомления
            print(f"!!! ВНИМАНИЕ !!! Фракция {self.faction} объявила войну фракции {faction}.")
            # Пример: вызов GUI-функции для отображения уведомления
            # show_notification(f"Фракция {self.faction} объявила войну!")
        except Exception as e:
            print(f"Ошибка при уведомлении игрока: {e}")

    def update_diplomacy_status(self, faction, status):
        """
        Обновляет статус дипломатии с указанной фракцией.
        :param faction: Название фракции
        :param status: Новый статус ("война" или "мир")
        """
        try:
            # Обновляем запись A-B
            query = """
                UPDATE diplomacies
                SET relationship = ?
                WHERE faction1 = ? AND faction2 = ?
            """
            self.cursor.execute(query, (status, self.faction, faction))

            # Обновляем запись B-A
            query = """
                UPDATE diplomacies
                SET relationship = ?
                WHERE faction1 = ? AND faction2 = ?
            """
            self.cursor.execute(query, (status, faction, self.faction))

            self.db_connection.commit()
            print(f"Статус дипломатии между {self.faction} и {faction} обновлен на '{status}'.")
        except sqlite3.Error as e:
            print(f"Ошибка при обновлении статуса дипломатии: {e}")

    def find_nearest_allied_city(self, faction):
        """
        Находит собственный город для передислокации войск.
        :param faction: Название фракции (своей или союзной)
        :return: Имя подходящего города или None, если своих городов нет
        """
        try:
            query = "SELECT name FROM cities WHERE faction = ?"
            self.cursor.execute(query, (self.faction,))
            our_cities = [row[0] for row in self.cursor.fetchall()]
            if not our_cities:
                return None

            best_city = None
            best_strength = -1
            for city_name in our_cities:
                self.cursor.execute(
                    """
                    SELECT COALESCE(SUM(g.unit_count * (u.attack + u.defense + u.durability)), 0)
                    FROM garrisons g JOIN units u ON g.unit_name = u.unit_name
                    WHERE g.city_name = ?
                    """,
                    (city_name,)
                )
                row = self.cursor.fetchone()
                strength = row[0] if row else 0
                if strength > best_strength:
                    best_strength = strength
                    best_city = city_name

            return best_city if best_city else our_cities[0]
        except sqlite3.Error as e:
            print(f"Ошибка при поиске ближайшего союзного города: {e}")
            return None

    def get_city_owner(self, city_name):
        try:
            self.cursor.execute("""
                SELECT faction FROM cities 
                WHERE name = ?
            """, (city_name,))
            result = self.cursor.fetchone()
            if not result:
                print(f"Город '{city_name}' не найден в таблице cities.")
                return None

            return result[0]
        except sqlite3.Error as e:
            print(f"Ошибка при получении владельца города: {e}")
            return None

    def has_road_between_cities(self, city1_name, city2_name):
        """Проверяет, есть ли дорога между двумя городами."""
        try:
            # Получаем id городов
            self.cursor.execute("SELECT id FROM cities WHERE name = ?", (city1_name,))
            city1_id = self.cursor.fetchone()
            self.cursor.execute("SELECT id FROM cities WHERE name = ?", (city2_name,))
            city2_id = self.cursor.fetchone()
            if not city1_id or not city2_id:
                return False
            city1_id, city2_id = city1_id[0], city2_id[0]
            # Проверяем наличие дороги
            self.cursor.execute("""
                SELECT 1 FROM roads 
                WHERE (city1 = ? AND city2 = ?) OR (city1 = ? AND city2 = ?)
            """, (city1_id, city2_id, city2_id, city1_id))
            return self.cursor.fetchone() is not None
        except sqlite3.Error as e:
            print(f"Ошибка при проверке дороги: {e}")
            return False

    def has_own_territory_path(self, source_city, destination_city, faction):
        """Проверяет наличие пути по дорогам внутри собственной территории."""
        try:
            self.cursor.execute("SELECT id FROM cities WHERE name = ?", (source_city,))
            source_row = self.cursor.fetchone()
            self.cursor.execute("SELECT id FROM cities WHERE name = ?", (destination_city,))
            destination_row = self.cursor.fetchone()
            if not source_row or not destination_row:
                return False

            source_id = source_row[0]
            destination_id = destination_row[0]
            if source_id == destination_id:
                return True

            visited = {source_id}
            queue = [source_id]

            while queue:
                current = queue.pop(0)
                self.cursor.execute("""
                    SELECT city1, city2 FROM roads
                    WHERE city1 = ? OR city2 = ?
                """, (current, current))
                for city1_id, city2_id in self.cursor.fetchall():
                    neighbor = city2_id if city1_id == current else city1_id
                    if neighbor in visited:
                        continue
                    self.cursor.execute("SELECT faction FROM cities WHERE id = ?", (neighbor,))
                    neighbor_row = self.cursor.fetchone()
                    if not neighbor_row or neighbor_row[0] != faction:
                        continue
                    if neighbor == destination_id:
                        return True
                    visited.add(neighbor)
                    queue.append(neighbor)

            return False
        except sqlite3.Error as e:
            print(f"Ошибка при проверке пути по своей территории: {e}")
            return False

    def find_nearest_city(self, faction):
        """Находит ближайший город противника для атаки, с которым есть дорога.
        :param faction: Название фракции
        :return: Имя ближайшего города или None, если подходящий город не найден"""
        try:
            # Получаем координаты всех городов текущей фракции
            query = "SELECT name, coordinates FROM cities WHERE faction = ?"
            self.cursor.execute(query, (self.faction,))
            our_cities = self.cursor.fetchall()

            # Получаем координаты всех городов противника
            query = "SELECT name, coordinates FROM cities WHERE faction = ?"
            self.cursor.execute(query, (faction,))
            enemy_cities = self.cursor.fetchall()

            min_distance = float('inf')
            nearest_city = None

            for our_city_name, our_coords in our_cities:
                our_coords = our_coords.strip("[]")  # Убираем [ и ]
                our_x, our_y = map(int, our_coords.split(','))

                for enemy_city_name, enemy_coords in enemy_cities:
                    enemy_coords = enemy_coords.strip("[]")  # Убираем [ и ]
                    enemy_x, enemy_y = map(int, enemy_coords.split(','))

                    # Проверяем наличие дороги
                    if self.has_road_between_cities(our_city_name, enemy_city_name):
                        # Расчет расстояния
                        distance = abs(our_x - enemy_x) + abs(our_y - enemy_y)
                        if distance < min_distance:
                            min_distance = distance
                            nearest_city = enemy_city_name

            return nearest_city
        except sqlite3.Error as e:
            print(f"Ошибка при поиске ближайшего города: {e}")
            return None

    def relocate_units(self, from_city_name, to_city_name, unit_name, unit_count, unit_image):
        try:
            # Проверяем, что города разные
            if from_city_name == to_city_name:
                print(f"Передислокация в тот же город невозможна: {from_city_name}")
                return

            # Проверяем наличие пути
            from_owner = self.get_city_owner(from_city_name)
            to_owner = self.get_city_owner(to_city_name)
            if from_owner == self.faction and to_owner == self.faction:
                if not (self.has_road_between_cities(from_city_name, to_city_name) or
                        self.has_own_territory_path(from_city_name, to_city_name, self.faction)):
                    print(f"Нет пути между {from_city_name} и {to_city_name} по своей территории.")
                    return
            else:
                if not self.has_road_between_cities(from_city_name, to_city_name):
                    print(f"Нет дороги между {from_city_name} и {to_city_name}.")
                    return

            # Уменьшаем количество юнитов в исходном городе
            self.cursor.execute("""
                UPDATE garrisons
                SET unit_count = unit_count - ?
                WHERE city_name = ? AND unit_name = ?
            """, (unit_count, from_city_name, unit_name))

            # Удаляем запись, если юнитов больше нет
            self.cursor.execute("""
                DELETE FROM garrisons
                WHERE city_name = ? AND unit_name = ? AND unit_count <= 0
            """, (from_city_name, unit_name))

            # Добавляем юниты в целевой город
            self.cursor.execute("""
                INSERT INTO garrisons (city_name, unit_name, unit_count, unit_image)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(city_name, unit_name) DO UPDATE SET
                unit_count = unit_count + excluded.unit_count,
                unit_image = excluded.unit_image
            """, (to_city_name, unit_name, unit_count, unit_image))

            self.db_connection.commit()
            print(f"Передислокация {unit_count} юнитов {unit_name} из {from_city_name} в {to_city_name} выполнена.")
        except sqlite3.Error as e:
            print(f"Ошибка при передислокации: {e}")

    def launch_attack_on_city(self, city_name, target_faction):
        """
        Запускает атаку на указанный город от лица текущей фракции.
        Атака возможна только при наличии юнитов класса 1.
        Герои (2-4 класс) усиливают атаку, но не могут нападать без поддержки.
        """
        print(f"[INFO] Фракция {self.faction} начинает атаку на город {city_name}")

        # Получаем ближайший союзный город для сбора войск
        allied_city = self.find_nearest_allied_city(self.faction)
        if not allied_city:
            print("Союзный город не найден.")
            return

        # Собираем все доступные юниты из всех городов
        all_units = self.collect_all_units()
        if not all_units:
            print("Нет юнитов для атаки.")
            return

        # Разделяем юниты по классам
        class_1_units = []
        hero_units = []

        for unit in all_units:
            unit_class = self.get_unit_class(unit["unit_name"])
            if unit_class == 1:
                class_1_units.append(unit)
            elif unit_class in [2, 3, 4]:
                hero_units.append(unit)

        # Проверяем наличие юнитов 1 класса — обязательное условие
        if not class_1_units:
            print("Нет юнитов 1 класса для атаки. Герои не могут нападать без поддержки.")
            return

        # Формируем атакующую армию
        attack_army = []

        # Берём до 60% юнитов 1 класса
        total_class_1 = sum(u["unit_count"] for u in class_1_units)
        units_to_take = int(total_class_1 * 0.6)
        remaining = units_to_take

        for unit in class_1_units:
            take = min(unit["unit_count"], remaining)
            attack_army.append({
                "city_name": unit["city_name"],
                "unit_name": unit["unit_name"],
                "unit_count": take,
                "unit_image": unit["unit_image"]
            })
            remaining -= take
            if remaining <= 0:
                break

        # Если остались места и есть герои — добавляем одного
        if hero_units and remaining < units_to_take and not self.hero_used_in_turn:
            chosen_hero = random.choice(hero_units)
            attack_army.append({
                "city_name": chosen_hero["city_name"],
                "unit_name": chosen_hero["unit_name"],
                "unit_count": 1,
                "unit_image": chosen_hero["unit_image"]
            })
            print(f"К атаке присоединён герой: {chosen_hero['unit_name']}")
            self.hero_used_in_turn = True

        # Передислоцируем юниты в ближайший союзный город
        for unit in attack_army:
            self.relocate_units(
                from_city_name=unit["city_name"],
                to_city_name=allied_city,
                unit_name=unit["unit_name"],
                unit_count=unit["unit_count"],
                unit_image=unit["unit_image"]
            )

        print(f"Все атакующие юниты передислоцированы в город {allied_city}.")

        # Проверяем общее количество войск
        self.cursor.execute("""
            SELECT SUM(unit_count) 
            FROM garrisons 
            WHERE city_name = ?
        """, (allied_city,))
        total_units = self.cursor.fetchone()[0] or 0

        if total_units == 0:
            print("Гарнизон пуст. Невозможно начать атаку.")
            return

        # Формируем армию для атаки
        attacking_army = []
        for unit in attack_army:
            self.cursor.execute("""
                SELECT attack, defense, durability, unit_class
                FROM units
                WHERE unit_name = ?
            """, (unit["unit_name"],))
            stats = self.cursor.fetchone()
            if stats:
                attack, defense, durability, unit_class = stats
                attacking_army.append({
                    "unit_name": unit["unit_name"],
                    "unit_count": unit["unit_count"],
                    "unit_image": unit["unit_image"],
                    "units_stats": {
                        "Урон": attack,
                        "Защита": defense,
                        "Живучесть": durability,
                        "Класс юнита": str(unit_class) + " класс"
                    }
                })

        # Запуск боя
        result = fight(
            attacking_city=allied_city,
            defending_city=city_name,
            defending_army=self.get_defending_army(city_name),
            attacking_army=attacking_army,
            attacking_fraction=self.faction,
            defending_fraction=target_faction,
            conn=self.db_connection
        )

        print(f"Результат битвы: {result}")

        # Обработка победы
        if result["winner"] == "attacker":
            self.army_efficiency_ratio = result["efficiency_ratio"]

            defensive_units = []
            remaining_units = []

            for unit in attacking_army:
                defense = unit["units_stats"]["Защита"]
                if defense > 50:
                    defensive_units.append(unit)
                else:
                    remaining_units.append(unit)

            # Оставшиеся войска остаются в городе или возвращаются
            print(f"Оставшиеся войска возвращаются в союзный город.")
        else:
            print(f"Атака на город {city_name} провалилась.")

    def collect_all_units(self):
        """Собирает все юниты из всех городов текущей фракции"""
        try:
            query = """
            SELECT g.city_name, g.unit_name, g.unit_count, g.unit_image
            FROM garrisons g
            JOIN units u ON g.unit_name = u.unit_name
            WHERE u.faction = ?
            """
            self.cursor.execute(query, (self.faction,))
            rows = self.cursor.fetchall()

            all_units = []
            for row in rows:
                city_name, unit_name, unit_count, unit_image = row
                all_units.append({
                    "city_name": city_name,
                    "unit_name": unit_name,
                    "unit_count": unit_count,
                    "unit_image": unit_image
                })
            return all_units
        except sqlite3.Error as e:
            print(f"[ERROR] Не удалось собрать юниты: {e}")
            return []

    def get_unit_class(self, unit_name):
        """Получает класс юнита из таблицы units"""
        try:
            self.cursor.execute("SELECT unit_class FROM units WHERE unit_name = ?", (unit_name,))
            result = self.cursor.fetchone()
            if result:
                cls_str = result[0].strip()
                return int(cls_str.split()[0])  # Например, "2 класс" → 2
        except Exception as e:
            print(f"[ERROR] Не удалось получить класс юнита '{unit_name}': {e}")
        return -1

    def get_defending_army(self, city_name):
        """
        Получает данные об обороняющейся армии в указанном городе.
        :param city_name: Имя города
        :return: Список обороняющихся юнитов
        """
        try:
            query = """
                SELECT g.unit_name, g.unit_count, u.attack, u.defense, u.durability, u.unit_class, g.unit_image
                FROM garrisons g
                JOIN units u ON g.unit_name = u.unit_name
                WHERE g.city_name = ?
            """
            self.cursor.execute(query, (city_name,))
            defending_units = self.cursor.fetchall()

            defending_army = []
            for unit_name, unit_count, attack, defense, durability, unit_class, unit_image in defending_units:
                defending_army.append({
                    "unit_name": unit_name,
                    "unit_count": int(unit_count),
                    "unit_image": unit_image,
                    "units_stats": {
                        "Урон": int(attack),
                        "Защита": int(defense),
                        "Живучесть": int(durability),
                        "Класс юнита": unit_class,
                    }
                })
            return defending_army
        except sqlite3.Error as e:
            print(f"Ошибка при получении обороняющейся армии: {e}")
            return []

    def attack_city(self, city_name, faction):
        """
        Организует атаку на указанный город.
        Атака возможна только при наличии юнитов класса 1.
        Герои (2, 3, 4 класс) усиливают атаку, но не могут действовать без базовой армии.
        """
        try:
            # Находим ближайший союзный город для атаки
            allied_city = self.find_nearest_allied_city(self.faction)
            if not allied_city:
                print("Не удалось найти ближайший союзный город.")
                return

            print(f"Ближайший союзный город для атаки: {allied_city}")

            # Собираем все доступные юниты из всех городов
            all_units = self.collect_all_units()
            if not all_units:
                print("Нет доступных юнитов для атаки.")
                return

            # Разделяем юниты по классам
            class_1_units = []
            hero_units = []

            for unit in all_units:
                unit_class = self.get_unit_class(unit["unit_name"])
                if unit_class == 1:
                    class_1_units.append(unit)
                elif unit_class in [2, 3, 4]:
                    hero_units.append(unit)

            # Проверяем наличие юнитов класса 1 — обязательное условие
            if not class_1_units:
                print("Нет юнитов 1 класса для атаки. Герои не могут нападать без поддержки.")
                return

            # Формируем атакующую армию
            attack_army = []

            # Берём до 60% юнитов 1 класса
            total_class_1 = sum(u["unit_count"] for u in class_1_units)
            units_to_take = int(total_class_1 * 0.6)
            remaining = units_to_take

            for unit in class_1_units:
                take = min(unit["unit_count"], remaining)
                attack_army.append({
                    "city_name": unit["city_name"],
                    "unit_name": unit["unit_name"],
                    "unit_count": take,
                    "unit_image": unit["unit_image"]
                })
                remaining -= take
                if remaining <= 0:
                    break

            # Если остались места и есть герои — добавляем одного
            if hero_units and remaining < units_to_take:
                chosen_hero = random.choice(hero_units)
                attack_army.append({
                    "city_name": chosen_hero["city_name"],
                    "unit_name": chosen_hero["unit_name"],
                    "unit_count": 1,
                    "unit_image": chosen_hero["unit_image"]
                })
                print(f"К атаке присоединён герой: {chosen_hero['unit_name']}")

            # Передислоцируем юниты в ближайший союзный город
            for unit in attack_army:
                self.relocate_units(
                    from_city_name=unit["city_name"],
                    to_city_name=allied_city,
                    unit_name=unit["unit_name"],
                    unit_count=unit["unit_count"],
                    unit_image=unit["unit_image"]
                )

            print(f"Все атакующие юниты передислоцированы в город {allied_city}.")

            # Проверяем общее количество войск
            self.cursor.execute("""
                SELECT SUM(unit_count) FROM garrisons WHERE city_name = ?
            """, (allied_city,))
            total_units = self.cursor.fetchone()[0] or 0

            if total_units == 0:
                print("Гарнизон пуст. Невозможно начать атаку.")
                return

            # Формируем армию для атаки
            attacking_army = []
            for unit in attack_army:
                self.cursor.execute("""
                    SELECT attack, defense, durability, unit_class
                    FROM units
                    WHERE unit_name = ?
                """, (unit["unit_name"],))
                stats = self.cursor.fetchone()
                if stats:
                    attack, defense, durability, unit_class = stats
                    attacking_army.append({
                        "unit_name": unit["unit_name"],
                        "unit_count": unit["unit_count"],
                        "unit_image": unit["unit_image"],
                        "units_stats": {
                            "Урон": attack,
                            "Защита": defense,
                            "Живучесть": durability,
                            "Класс юнита": unit_class
                        }
                    })

            # Запуск боя
            result = fight(
                attacking_city=allied_city,
                defending_city=city_name,
                defending_army=self.get_defending_army(city_name),
                attacking_army=attacking_army,
                attacking_fraction=self.faction,
                defending_fraction=faction,
                conn=self.db_connection
            )
            print(f"Результат битвы: {result}")

            # Обработка победы
            if result["winner"] == "attacker":
                self.army_efficiency_ratio = result["efficiency_ratio"]
                # Распределяем войска после победы
                defensive_units = []
                remaining_units = []

                for unit in attacking_army:
                    defense = unit["units_stats"]["Защита"]
                    unit_count = unit["unit_count"]

                    # Разделение на оборонительные и оставшиеся
                    if defense > 50:
                        defensive_units.append(unit)
                    else:
                        remaining_units.append(unit)

                # Размещаем 30% сил с высокой защитой в захваченном городе
                for unit in defensive_units:
                    defense_count = int(unit["unit_count"] * 0.3)
                    if defense_count > 0:
                        self.relocate_units(
                            allied_city,
                            city_name,
                            unit["unit_name"],
                            defense_count,
                            unit["unit_image"]
                        )
                        print(
                            f"Размещено {defense_count} юнитов '{unit['unit_name']}' в городе {city_name} для обороны.")

                # Остальные войска остаются или возвращаются в союзный город
                for unit in remaining_units:
                    remaining_count = unit["unit_count"]
                    if remaining_count > 0:
                        self.relocate_units(
                            allied_city,
                            allied_city,
                            unit["unit_name"],
                            remaining_count,
                            unit["unit_image"]
                        )
                        print(f"Отведено {remaining_count} юнитов '{unit['unit_name']}' обратно в город {allied_city}.")

                # Обновляем принадлежность города
                self.cursor.execute("""
                    UPDATE cities
                    SET faction = ?
                    WHERE name = ?
                """, (self.faction, city_name))
                print(f"Город {city_name} захвачен и укреплён оборонительными войсками.")
            else:
                print(f"Атака на город {city_name} провалилась.")

        except Exception as e:
            print(f"[ERROR] Ошибка при атаке города: {e}")

    def capture_city(self, city_name, new_owner, attacking_units):
        """Захватывает город под контроль текущей фракции."""
        try:
            with self.db_connection:
                cursor = self.db_connection.cursor()
                # 1. Перемещаем войска атакующего отряда
                for unit in attacking_units:
                    cursor.execute("""
                        UPDATE garrisons 
                        SET unit_count = unit_count - ? 
                        WHERE city_name = ? AND unit_name = ?
                    """, (unit["unit_count"], unit["city_name"], unit["unit_name"]))
                    cursor.execute("""
                        DELETE FROM garrisons 
                        WHERE city_name = ? AND unit_name = ? AND unit_count <= 0
                    """, (unit["city_name"], unit["unit_name"]))
                    cursor.execute("""
                        INSERT INTO garrisons (city_name, unit_name, unit_count, unit_image)
                        VALUES (?, ?, ?, ?)
                        ON CONFLICT(city_name, unit_name) DO UPDATE SET
                            unit_count = unit_count + excluded.unit_count,
                            unit_image = excluded.unit_image
                    """, (city_name, unit["unit_name"], unit["unit_count"], unit["unit_image"]))

                # 2. Обновляем принадлежность зданий
                cursor.execute("""
                    UPDATE buildings 
                    SET faction = ? 
                    WHERE city_name = ?
                """, (new_owner, city_name))

        except sqlite3.Error as e:
            print(f"[ERROR] Ошибка при захвате города: {e}")

    def update_buildings_for_current_cities(self):
        """
        Обновляет self.buildings, учитывая только города, которые на данный момент принадлежат фракции.
        """
        try:
            # Загружаем актуальный список городов текущей фракции
            query = """
                SELECT id, name 
                FROM cities 
                WHERE faction = ?
            """
            self.cursor.execute(query, (self.faction,))
            rows = self.cursor.fetchall()
            current_cities = {row[0]: row[1] for row in rows}

            # Очищаем self.buildings и обновляем его только для актуальных городов
            updated_buildings = {}
            for city_name, city_name in current_cities.items():
                updated_buildings[city_name] = {"Здания": {"Больница": 0, "Фабрика": 0}}

            # Загружаем данные о зданиях для актуальных городов
            query = """
                SELECT city_name, building_type, count 
                FROM buildings 
                WHERE faction = ?
            """
            self.cursor.execute(query, (self.faction,))
            rows = self.cursor.fetchall()

            for row in rows:
                city_name, building_type, count = row
                if city_name in updated_buildings:
                    updated_buildings[city_name]["Здания"][building_type] += count

            # Обновляем self.buildings
            self.buildings = updated_buildings
            print(f"Обновлены данные о зданиях для фракции {self.faction}: {self.buildings}")

        except sqlite3.Error as e:
            print(f"Ошибка при обновлении данных о зданиях: {e}")

    def check_and_declare_war(self):
        """
        Проверяет уровень отношений с другими фракциями.
        Если отношения падают ниже 12% И сила армии потенциального противника
        ниже в 1.5 раза, чем сила текущей фракции, объявляет войну.
        Также проверяет, находится ли фракция в состоянии войны, и если да,
        сразу атакует ближайший город.
        """
        try:
            # Загружаем текущие отношения с другими фракциями
            self.relations = self.load_relations()
            # Рассчитываем силу армий для всех фракций
            army_strength = self.calculate_army_strength()
            our_strength = army_strength.get(self.faction, 0)
            print("our_strength:", type(our_strength), our_strength)

            for faction, relationship in self.relations.items():
                # Проверяем текущий статус дипломатии с фракцией
                query = """
                    SELECT relationship FROM diplomacies
                    WHERE faction1 = ? AND faction2 = ?
                """
                self.cursor.execute(query, (self.faction, faction))
                result = self.cursor.fetchone()

                if result is None:
                    # Если записи нет, считаем, что статус "мир"
                    diplomacy_status = "мир"
                    print(f"Дипломатический статус с фракцией {faction} не найден. Установлен статус 'мир'.")
                else:
                    diplomacy_status = result[0]

                if diplomacy_status == "война":
                    # Если уже объявлена война, атакуем ближайший город
                    print(f"Фракция {self.faction} уже находится в состоянии войны с фракцией {faction}.")
                    target_city = self.find_nearest_city(faction)
                    if target_city:
                        print(f"Ближайший вражеский город для атаки: {target_city}")
                        self.attack_city(target_city, faction)
                    else:
                        print(f"Не удалось найти подходящий город для атаки у фракции {faction}.")
                    continue

                # Если нет войны, проверяем условия для объявления войны
                if self.turn < 13:
                    print(f"{self.faction}: ещё рано объявлять войну (ход {self.turn + 1}). Ждём 14-й ход.")
                    continue

                if int(relationship) < 30:  # Если отношения достаточно плохие
                    enemy_strength = army_strength.get(faction, 0)
                    # Проверяем, что наша сила армии больше в 1.3 раза
                    if our_strength > 1.3 * enemy_strength:
                        print(f"Отношения с фракцией {faction} упали ниже 30%. "
                              f"Сила нашей армии: {our_strength}, сила противника: {enemy_strength}. Объявление войны.")
                        # Обновляем статус дипломатии на "война"
                        self.update_diplomacy_status(faction, "война")
                        # Уведомляем игрока о начале войны
                        self.notify_player_about_war(faction)
                        # Определяем ближайший город для атаки
                        target_city = self.find_nearest_city(faction)
                        if target_city:
                            print(f"Ближайший вражеский город для атаки: {target_city}")
                            # Наносим удар по ближайшему городу
                            self.attack_city(target_city, faction)
                        else:
                            print(f"Не удалось найти подходящий город для атаки у фракции {faction}.")
                    else:
                        print(f"Отношения с фракцией {faction} упали ниже 12%, "
                              f"но сила противника слишком велика. Война не объявлена.")
            if our_strength > 0:
                target_city = self.find_nearest_neutral_city()
                if target_city:
                    print(f"Обнаружен нейтральный город: {target_city}. Начинаем захват.")
                    self.attack_city(target_city, "Нейтрал")
                    self.capture_city(target_city, self.faction, self.attacking_army)
        except Exception as e:
            print(f"Ошибка при проверке и объявлении войны: {e}")

    def process_queries(self):
        """
        Обрабатывает запросы из таблицы queries И торговые соглашения из trade_agreements.
        Исполняет ВСЕ доступные сделки без каких-либо проверок.
        """
        try:
            # Обрабатываем ВСЕ торговые соглашения
            trade_query = """
                SELECT id, initiator, target_faction, 
                       initiator_type_resource, initiator_summ_resource,
                       target_type_resource, target_summ_resource
                FROM trade_agreements
                WHERE target_faction = ? AND agree = 0
            """
            self.cursor.execute(trade_query, (self.faction,))
            trade_rows = self.cursor.fetchall()

            for trade_row in trade_rows:
                trade_id, initiator, target_faction, give_type, give_amount, get_type, get_amount = trade_row

                print(f"Исполнение торгового соглашения #{trade_id} от {initiator}")

                # ПЫТАЕМСЯ ВЫПОЛНИТЬ СДЕЛКУ
                success = self.execute_trade_from_agreement(
                    trade_id=trade_id,
                    initiator=initiator,
                    give_type=give_type,
                    give_amount=give_amount,
                    get_type=get_type,
                    get_amount=get_amount
                )

                if success:
                    print(f"Сделка #{trade_id} исполнена")
                else:
                    print(f"Не удалось исполнить сделку #{trade_id}")
                    self.cursor.execute("""
                        UPDATE trade_agreements 
                        SET agree = 1 
                        WHERE id = ?
                    """, (trade_id,))

            self.db_connection.commit()
            print(f"Исполнение сделок завершено. Обработано: {len(trade_rows)}")

        except Exception as e:
            print(f"Ошибка при обработке торговых соглашений: {e}")

    def _get_ai_resources(self, faction):
        """
        Получает все ресурсы указанной фракции.
        Возвращает словарь {тип_ресурса: количество}
        """
        resources = {}
        self.cursor.execute('''
            SELECT resource_type, amount 
            FROM resources 
            WHERE faction = ?
        ''', (faction,))

        for row in self.cursor.fetchall():
            resource_type, amount = row
            resources[resource_type] = amount

        return resources

    def execute_trade_from_agreement(self, trade_id, initiator, give_type, give_amount, get_type, get_amount):
        """
        Выполняет торговое соглашение и обновляет ресурсы обеих сторон.
        """
        try:
            # 1. Получаем текущие ресурсы ИИ (целевой фракции)
            ai_resources = {}
            self.cursor.execute('''
                SELECT resource_type, amount 
                FROM resources 
                WHERE faction = ?
            ''', (self.faction,))

            for row in self.cursor.fetchall():
                resource_type, amount = row
                ai_resources[resource_type] = amount

            # 2. Проверяем наличие нужного ресурса у ИИ (ресурса, который нужно отдать инициатору)
            if ai_resources.get(get_type, 0) < get_amount:
                print(
                    f"У ИИ {self.faction} недостаточно {get_type} для сделки: {ai_resources.get(get_type, 0)} < {get_amount}")
                return False

            # 3. Вычитаем ресурсы у ИИ (то, что ИИ отдает инициатору)
            ai_resources[get_type] -= get_amount

            # 4. Добавляем полученные ресурсы ИИ (то, что ИИ получает от инициатора)
            ai_resources[give_type] = ai_resources.get(give_type, 0) + give_amount

            # 5. Сохраняем ресурсы ИИ
            for resource_type, amount in ai_resources.items():
                self.cursor.execute('''
                    UPDATE resources 
                    SET amount = ?
                    WHERE faction = ? AND resource_type = ?
                ''', (amount, self.faction, resource_type))

            # 6. Теперь обновляем ресурсы инициатора (игрока)
            # Получаем ресурсы инициатора
            player_resources = {}
            self.cursor.execute('''
                SELECT resource_type, amount 
                FROM resources 
                WHERE faction = ?
            ''', (initiator,))

            for row in self.cursor.fetchall():
                resource_type, amount = row
                player_resources[resource_type] = amount

            # Проверяем, есть ли у инициатора достаточно ресурсов (то, что он должен отдать ИИ)
            if player_resources.get(give_type, 0) >= give_amount:
                # Вычитаем у игрока (то, что игрок отдает ИИ)
                player_resources[give_type] -= give_amount

                # Добавляем игроку то, что отдает ИИ (то, что игрок получает от ИИ)
                player_resources[get_type] = player_resources.get(get_type, 0) + get_amount

                # Сохраняем ресурсы игрока
                for resource_type, amount in player_resources.items():
                    self.cursor.execute('''
                        UPDATE resources 
                        SET amount = ?
                        WHERE faction = ? AND resource_type = ?
                    ''', (amount, initiator, resource_type))
            else:
                print(
                    f"У инициатора {initiator} недостаточно {give_type} для сделки: {player_resources.get(give_type, 0)} < {give_amount}")
                # Откатываем изменения у ИИ, если у игрока недостаточно ресурсов
                self.db_connection.rollback()
                return False

            # 7. Помечаем сделку как выполненную
            self.cursor.execute('''
                UPDATE trade_agreements 
                SET agree = 1 
                WHERE id = ?
            ''', (trade_id,))

            self.db_connection.commit()

            # Логируем успешную сделку
            print(f"Сделка {trade_id} успешно выполнена:")
            print(f"  {self.faction} отдал {get_amount} {get_type}, получил {give_amount} {give_type}")
            print(f"  {initiator} отдал {give_amount} {give_type}, получил {get_amount} {get_type}")

            return True

        except Exception as e:
            print(f"Ошибка при выполнении торгового соглашения: {e}")
            self.db_connection.rollback()
            return False

    def _save_ai_resources(self, faction, resources):
        """Сохраняет ресурсы ИИ фракции"""
        cursor = self.db_connection.cursor()
        for resource_type, amount in resources.items():
            cursor.execute('''
                UPDATE resources 
                SET amount = ? 
                WHERE faction = ? AND resource_type = ?
            ''', (amount, faction, resource_type))

    def execute_chat_trade(self, faction, ai_gives_resource, ai_gives_amount, ai_gets_resource, ai_gets_amount):
        """
        Выполняет торговую сделку из чата.
        ИИ отдает ai_gives_resource:ai_gives_amount
        ИИ получает ai_gets_resource:ai_gets_amount
        """
        try:
            # Загружаем текущие ресурсы ИИ
            ai_resources = self._get_ai_resources(faction)

            # Проверяем, достаточно ли у ИИ ресурсов для передачи
            if ai_resources.get(ai_gives_resource, 0) < ai_gives_amount:
                print(
                    f"У ИИ фракции {faction} недостаточно {ai_gives_resource}: {ai_resources.get(ai_gives_resource, 0)} < {ai_gives_amount}")
                return False

            # Вычитаем ресурсы у ИИ
            ai_resources[ai_gives_resource] -= ai_gives_amount

            # Добавляем полученные ресурсы ИИ
            ai_resources[ai_gets_resource] = ai_resources.get(ai_gets_resource, 0) + ai_gets_amount

            # Сохраняем ресурсы ИИ обратно в БД
            self._save_ai_resources(faction, ai_resources)

            # Теперь нужно добавить ресурсы игроку
            # Получаем ресурсы игрока
            player_resources = self._get_player_resources()

            # Игрок отдает то, что получает ИИ
            if player_resources.get(ai_gets_resource, 0) < ai_gets_amount:
                print(f"У игрока недостаточно {ai_gets_resource}")
                return False

            # Вычитаем у игрока
            player_resources[ai_gets_resource] -= ai_gets_amount

            # Добавляем игроку то, что отдает ИИ
            player_resources[ai_gives_resource] = player_resources.get(ai_gives_resource, 0) + ai_gives_amount

            # Сохраняем ресурсы игрока
            self._save_player_resources(player_resources)

            print(
                f"Торговый обмен завершен: ИИ {faction} отдал {ai_gives_amount} {ai_gives_resource}, получил {ai_gets_amount} {ai_gets_resource}")
            return True

        except Exception as e:
            print(f"Ошибка при выполнении торговой сделки: {e}")
            return False

    def _get_player_resources(self):
        """Получает ресурсы игрока"""
        # Предполагаем, что у контроллера есть доступ к ресурсам игрока
        # Нужно адаптировать под вашу структуру
        cursor = self.db_connection.cursor()
        cursor.execute('''
            SELECT Кроны, Кристаллы, Рабочие, Население 
            FROM resources 
            WHERE faction = ?
        ''', (self.faction,))
        row = cursor.fetchone()

        if row:
            return {
                'Кроны': row[0],
                'Кристаллы': row[1],
                'Рабочие': row[2],
                'Население': row[3]
            }
        return {'Кроны': 0, 'Кристаллы': 0, 'Рабочие': 0, 'Население': 0}

    def _save_player_resources(self, resources):
        """Сохраняет ресурсы игрока"""
        cursor = self.db_connection.cursor()
        cursor.execute('''
            UPDATE resources 
            SET Кроны = ?, Кристаллы = ?, Рабочие = ?, Население = ?
            WHERE faction = ?
        ''', (
            resources.get('Кроны', 0),
            resources.get('Кристаллы', 0),
            resources.get('Рабочие', 0),
            resources.get('Население', 0),
            self.faction
        ))
        self.db_connection.commit()

    def mark_query_completed(self, query_id):
        """Помечает запрос как выполненный"""
        try:
            self.cursor.execute('''
                UPDATE queries 
                SET status = 'completed' 
                WHERE id = ?
            ''', (query_id,))
            self.db_connection.commit()
        except Exception as e:
            print(f"Ошибка при обновлении статуса запроса: {e}")

    def clear_processed_queries(self):
        """Удаляет обработанные запросы"""
        try:
            self.cursor.execute('''
                DELETE FROM queries 
                WHERE status = 'completed' 
                   OR (resource IS NULL AND defense_city IS NULL AND attack_city IS NULL)
            ''')
            self.db_connection.commit()
        except Exception as e:
            print(f"Ошибка при очистке запросов: {e}")

    def clear_queries_table(self):
        """
        Очищает таблицу queries.
        """
        try:
            query = "DELETE FROM queries"
            self.cursor.execute(query)
            self.db_connection.commit()
            print("Таблица queries успешно очищена.")
        except sqlite3.Error as e:
            print(f"Ошибка при очистке таблицы queries: {e}")

    def is_faction_ally(self, faction):
        """
        Проверяет, является ли указанная фракция союзником текущей фракции.
        :param faction: Название фракции
        :return: True, если союзник ('союз'); False, если нет
        """
        try:
            # Загружаем статус дипломатии с указанной фракцией
            query = """
                SELECT relationship
                FROM diplomacies
                WHERE faction1 = ? AND faction2 = ?
            """
            self.cursor.execute(query, (self.faction, faction))
            result = self.cursor.fetchone()

            # Если запись найдена и статус равен 'союз', возвращаем True
            if result and result[0] == 'союз':
                return True

            # Во всех остальных случаях возвращаем False
            return False
        except sqlite3.Error as e:
            print(f"Ошибка при проверке союзника: {e}")
            return False

    def transfer_resource_to_ally(self, faction, resource_type):
        """
        Передает 15% ресурса указанного типа союзной фракции.
        Данные о передаче записываются в таблицу trade_agreements.
        :param faction: Название союзной фракции (target_faction)
        :param resource_type: Тип ресурса (initiator_type_resource и target_type_resource)
        """
        try:
            # Получаем текущее количество ресурса у текущей фракции
            current_amount = self.resources.get(resource_type, 0)
            if current_amount <= 0:
                print(f"Нет доступных ресурсов типа {resource_type} для передачи.")
                return

            # Вычисляем 15% от текущего количества ресурса
            amount_to_transfer = int(current_amount * 0.15)

            # Уменьшаем количество ресурса у текущей фракции
            self.resources[resource_type] -= amount_to_transfer

            # Записываем данные о передаче в таблицу trade_agreements
            self.cursor.execute("""
                INSERT INTO trade_agreements (
                    initiator, 
                    target_faction, 
                    initiator_type_resource, 
                    initiator_summ_resource, 
                    target_type_resource, 
                    target_summ_resource,
                    agree
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                self.faction,  # initiator (текущая фракция)
                faction,  # target_faction (союзная фракция)
                resource_type,  # initiator_type_resource (тип ресурса)
                amount_to_transfer,  # initiator_summ_resource (переданное количество)
                "",  # target_type_resource (тип ресурса у союзника)
                "",  # target_summ_resource (полученное количество)
                1  # agree (статус сделки
            ))

            # Сохраняем изменения в базе данных
            self.db_connection.commit()

            print(f"Передано {amount_to_transfer} {resource_type} союзной фракции {faction}.")
        except sqlite3.Error as e:
            print(f"Ошибка при передаче ресурсов: {e}")

    def reinforce_defense_in_city(self, city_name, faction):
        """
        Направляет 40% защитных юнитов в указанный город.
        :param city_name: Название города
        :param faction: Название союзной фракции
        """
        try:
            # Собираем защитные юниты из всех городов текущей фракции
            defensive_units = self.collect_all_units()

            if not defensive_units:
                print("Нет доступных защитных юнитов для передислокации.")
                return

            # Вычисляем 40% от общего количества защитных юнитов
            total_units = sum(unit["unit_count"] for unit in defensive_units)
            units_to_relocate = int(total_units * 0.4)

            # Распределяем юниты между городами
            relocated_units = []
            remaining_units = units_to_relocate
            for unit in defensive_units:
                if remaining_units <= 0:
                    break
                units_from_this = min(unit["unit_count"], remaining_units)
                relocated_units.append({
                    "city_name": unit["city_name"],  # Город отправления
                    "unit_name": unit["unit_name"],
                    "unit_count": units_from_this,
                    "unit_image": unit["unit_image"]
                })
                remaining_units -= units_from_this

            print('*******************************************relocated_units :', relocated_units)

            # Передислоцируем юниты в указанный город
            for unit in relocated_units:
                self.relocate_units(
                    from_city_name=unit["city_name"],
                    to_city_name=city_name,
                    unit_name=unit["unit_name"],
                    unit_count=unit["unit_count"],
                    unit_image=unit["unit_image"]
                )

            print(f"Передислоцировано {units_to_relocate} защитных юнитов в город {city_name}.")
        except Exception as e:
            print(f"Ошибка при усилении обороны: {e}")

    def apply_political_system_bonus(self):
        """
        Применяет бонусы от политической системы.
        """
        system = self.load_political_system()
        if system == "Смирение":
            crowns_bonus = int(self.money_up * 1.85)
            self.resources['Кроны'] = int(self.resources.get('Кроны', 0)) + crowns_bonus
            print(f"Бонус от смирения: +{crowns_bonus} Крон")
        elif system == "Борьба":
            raw_material_bonus = int(self.food_info * 0.25)
            self.resources['Кристаллы'] = int(self.resources.get('Кристаллы', 0)) + raw_material_bonus
            print(f"Бонус от борьбы: +{raw_material_bonus} Кристаллы")

    def update_relations_based_on_political_system(self):
        """
        Изменяет отношения на основе политической системы каждые 3 хода.
        """
        if self.turn % 3 != 0:
            return

        current_system = self.load_political_system()
        all_factions = self.load_relations()

        for faction, relation_level in all_factions.items():
            if faction == self.faction:
                continue  # пропускаем собственную фракцию

            other_system = self.load_political_system_for_faction(faction)

            # Преобразуем relation_level в число
            relation_level = int(relation_level)

            if current_system.strip() == other_system.strip():
                new_relation = min(relation_level + 3, 100)
            else:
                new_relation = max(relation_level - 7, 0)

            self.update_relation_in_db(faction, new_relation)

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

    def update_relation_in_db(self, faction, new_relation):
        """
        Обновляет уровень отношений в базе данных.
        """
        try:
            query = """
                UPDATE relations
                SET relationship = ?
                WHERE faction1 = ? AND faction2 = ?
            """
            self.cursor.execute(query, (new_relation, self.faction, faction))
            self.db_connection.commit()
        except sqlite3.Error as e:
            print(f"Ошибка при обновлении отношений для фракции {faction}: {e}")


    def update_economic_efficiency(self, efficiency_value):
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
                current_efficiency = row[0] if row[0] is not None else 0
                new_efficiency = (current_efficiency + efficiency_value) / 2
                self.average_deal_ratio = new_efficiency  # Обновляем атрибут
            else:
                # Если записи нет - сохраняем новое значение
                new_efficiency = efficiency_value
                self.average_deal_ratio = new_efficiency

            # Сохраняем в БД через метод save_results_to_db
            self.save_results_to_db()
        except sqlite3.Error as e:
            print(f"Ошибка при обновлении экономической эффективности: {e}")

    def save_results_to_db(self):
        try:
            # Обновляем только коэффициент сделок
            self.cursor.execute('''SELECT Average_Deal_Ratio FROM results WHERE faction = ?''', (self.faction,))
            existing = self.cursor.fetchone()

            new_deal_ratio = self.average_deal_ratio

            if existing:
                updated_ratio = (existing[0] * 0.3 + new_deal_ratio * 0.7) if existing[0] else new_deal_ratio
                self.cursor.execute('''UPDATE results SET Average_Deal_Ratio = ? WHERE faction = ?''',
                                    (updated_ratio, self.faction))
            else:
                self.cursor.execute('''INSERT INTO results (Average_Deal_Ratio, faction) VALUES (?, ?)''',
                                    (new_deal_ratio, self.faction))

            self.db_connection.commit()
        except sqlite3.Error as e:
            print(f"Ошибка сохранения результатов: {e}")

    def find_nearest_neutral_city(self):
        """
        Находит ближайший нейтральный город для атаки, с которым есть дорога.
        :return: Имя ближайшего нейтрального города или None
        """
        try:
            # Получаем координаты всех своих городов
            query = "SELECT name, coordinates FROM cities WHERE faction = ?"
            self.cursor.execute(query, (self.faction,))
            our_cities = self.cursor.fetchall()

            # Получаем все нейтральные города
            query = "SELECT name, coordinates FROM cities WHERE faction = 'Нейтрал'"
            self.cursor.execute(query)
            neutral_cities = self.cursor.fetchall()

            min_distance = float('inf')
            nearest_city = None

            for our_city_name, our_coords in our_cities:
                our_coords = our_coords.strip("[]")
                our_x, our_y = map(int, our_coords.split(','))
                for city_name, city_coords in neutral_cities:
                    city_coords = city_coords.strip("[]")
                    enemy_x, enemy_y = map(int, city_coords.split(','))
                    # Проверяем наличие дороги
                    if self.has_road_between_cities(our_city_name, city_name):
                        distance = abs(our_x - enemy_x) + abs(our_y - enemy_y)
                        if distance < min_distance:
                            min_distance = distance
                            nearest_city = city_name
            return nearest_city
        except sqlite3.Error as e:
            print(f"Ошибка при поиске нейтрального города: {e}")
            return None

    def attack_enemy_cities(self):
        """
        Организует атаки на вражеские города.
        """
        try:
            # Получаем список всех фракций, с которыми ведется война
            at_war_with = self.get_factions_at_war()
            if not at_war_with:
                print("Нет фракций, с которыми ведется война.")
                return

            for enemy_faction in at_war_with:
                target_city = self.find_nearest_city(enemy_faction)
                if target_city:
                    print(f"Атакуем город {target_city} фракции {enemy_faction}")
                    self.attack_city(target_city, enemy_faction)
                else:
                    print(f"Не удалось найти подходящий город для атаки у фракции {enemy_faction}.")

        except Exception as e:
            print(f"Ошибка при атаке вражеских городов: {e}")

    def send_help_request_if_needed(self):
        """
        Отправляет сообщение с просьбой о помощи, если выполняются условия:
        - Осталось 3 и менее городов
        - Текущая армия слабее армии противника
        - Отношения с игроком > 40
        """
        try:
            # 1. Проверяем количество городов
            current_city_count = self.get_city_count_for_faction()
            if current_city_count > 3:
                return  # Условие не выполняется

            # 2. Находим противников, с которыми ведется война
            enemies = self.get_factions_at_war()
            if not enemies:
                return  # Нет врагов

            # 3. Рассчитываем нашу силу армии
            our_strength = self._calculate_army_strength(self.faction)

            # 4. Находим самого сильного противника
            strongest_enemy = None
            strongest_enemy_strength = 0

            for enemy in enemies:
                enemy_strength = self._calculate_army_strength(enemy)
                if enemy_strength > strongest_enemy_strength:
                    strongest_enemy_strength = enemy_strength
                    strongest_enemy = enemy

            # 5. Проверяем, слабее ли мы противника
            if our_strength >= strongest_enemy_strength:
                return  # Мы не слабее

            # 6. Получаем отношения с игроком
            cursor = self.db_connection.cursor()
            cursor.execute("""
                SELECT relationship 
                FROM relations 
                WHERE faction1 = ? AND faction2 = ?
            """, (self.faction, "Игрок"))

            result = cursor.fetchone()
            if not result:
                return  # Нет отношений с игроком

            relations_with_player = int(result[0])

            # 7. Определяем тип сообщения в зависимости от уровня отношений
            message_content = ""
            resource_offer = ""

            if relations_with_player > 95:
                # Предлагаем союз и помощь в войне
                message_content = f"[СОЮЗ] {self.faction} предлагает вам военный союз и помощь в войнах."

                # Проверяем, воюет ли игрок с кем-то
                cursor.execute("""
                    SELECT faction2 FROM diplomacies 
                    WHERE faction1 = 'Игрок' AND relationship = 'война'
                """)
                player_enemies = [row[0] for row in cursor.fetchall()]

                if player_enemies:
                    message_content += f" Мы готовы помочь вам против {', '.join(player_enemies)}."

                resource_offer = self._generate_resource_offer(50)  # 50% ресурсов
                if resource_offer:
                    message_content += f" {resource_offer}"

            elif relations_with_player > 80:
                # Умоляем о помощи с предложением ресурсов
                message_content = f"[УМОЛЯЮ] {self.faction} умоляет о помощи! Враг ({strongest_enemy}) слишком силен. Городов осталось: {current_city_count}"
                resource_offer = self._generate_resource_offer(30)  # 30% ресурсов
                if resource_offer:
                    message_content += f" {resource_offer}"

            elif relations_with_player > 40:
                # Просим о помощи
                message_content = f"[ПОМОЩЬ] {self.faction} просит о помощи против {strongest_enemy}. Городов осталось: {current_city_count}"
            else:
                return  # Отношения слишком низкие

            # 8. Создаем сообщение в таблице negotiation_history
            self._create_message_in_negotiation_history(
                faction1=self.faction,
                faction2="Игрок",
                message=message_content,
                is_player=False,
                is_incoming=True
            )

            print(f"[AI MESSAGE] Отправлено сообщение от {self.faction}: {message_content}")

        except Exception as e:
            print(f"Ошибка при отправке сообщения о помощи: {e}")

    def send_mercy_request_if_needed(self):
        """
        Отправляет сообщение с просьбой о пощаде и мире, если:
        - ИИ воюет с игроком
        - У ИИ осталось меньше 3 городов
        """
        try:
            # 1. Проверяем, воюем ли мы с игроком
            cursor = self.db_connection.cursor()
            cursor.execute("""
                SELECT relationship 
                FROM diplomacies 
                WHERE faction1 = ? AND faction2 = ? AND relationship = 'война'
            """, (self.faction, "Игрок"))

            result = cursor.fetchone()
            if not result:
                return  # Не воюем с игроком

            # 2. Проверяем количество городов
            current_city_count = self.get_city_count_for_faction()
            if current_city_count >= 3:
                return  # Условие не выполняется

            # 3. Рассчитываем силу армии
            our_strength = self._calculate_army_strength(self.faction)
            player_strength = self._calculate_army_strength("Игрок")

            # 4. Проверяем, проигрываем ли мы войну
            if our_strength >= player_strength * 0.7:  # Если наша сила > 70% от силы игрока
                return  # Не проигрываем критически

            # 5. Получаем текущие отношения
            cursor.execute("""
                SELECT relationship 
                FROM relations 
                WHERE faction1 = ? AND faction2 = ?
            """, (self.faction, "Игрок"))

            result = cursor.fetchone()
            if not result:
                return

            relations_with_player = int(result[0])

            # 6. Создаем сообщение о пощаде
            message_content = f"[ПОЩАДА] {self.faction} умоляет о пощаде! Мы проигрываем войну. Городов осталось: {current_city_count}"

            # Добавляем предложение ресурсов в зависимости от отношений
            if relations_with_player > 20:
                resource_offer = self._generate_resource_offer(40)  # 40% ресурсов
                message_content += f" {resource_offer}"

            # 7. Добавляем предложение мира
            message_content += " Мы готовы заключить мир на ваших условиях."

            # 8. Создаем сообщение в таблице negotiation_history
            self._create_message_in_negotiation_history(
                faction1=self.faction,
                faction2="Игрок",
                message=message_content,
                is_player=False,
                is_incoming=True
            )

            print(f"[AI MESSAGE] Отправлено сообщение о пощаде от {self.faction}")

        except Exception as e:
            print(f"Ошибка при отправке сообщения о пощаде: {e}")

    def _calculate_army_strength(self, faction):
        """
        Рассчитывает силу армии фракции
        """
        try:
            cursor = self.db_connection.cursor()

            cursor.execute("""
                SELECT g.unit_name, g.unit_count, u.attack, u.defense, u.durability, u.unit_class 
                FROM garrisons g
                JOIN units u ON g.unit_name = u.unit_name
                WHERE u.faction = ?
            """, (faction,))
            units_data = cursor.fetchall()

            total_strength = 0
            class_1_count = 0
            hero_bonus = 0
            others_stats = 0

            for unit_name, unit_count, attack, defense, durability, unit_class in units_data:
                stats_sum = attack + defense + durability

                if unit_class == "1":
                    class_1_count += unit_count
                    total_strength += stats_sum * unit_count
                elif unit_class in ("2", "3"):
                    hero_bonus += stats_sum * unit_count
                else:
                    others_stats += stats_sum * unit_count

            if class_1_count > 0:
                total_strength += hero_bonus * class_1_count

            total_strength += others_stats

            return total_strength

        except Exception as e:
            print(f"Ошибка при расчете силы армии: {e}")
            return 0

    def _generate_resource_offer(self, percentage):
        """
        Генерирует предложение ресурсов в процентах от текущих запасов
        """
        try:
            resources_to_offer = []

            # Проверяем каждый ресурс
            for resource_type in ['Кроны', 'Кристаллы', 'Рабочие']:
                if resource_type in self.resources and self.resources[resource_type] > 0:
                    amount = int(self.resources[resource_type] * percentage / 100)
                    if amount > 0:
                        resources_to_offer.append(f"{amount} {resource_type}")

            if resources_to_offer:
                return f"Предлагаем: {', '.join(resources_to_offer)}."
            return ""

        except Exception as e:
            print(f"Ошибка при генерации предложения ресурсов: {e}")
            return ""

    def _create_message_in_negotiation_history(self, faction1, faction2, message, is_player=False, is_incoming=True):
        """
        Создает сообщение в таблице negotiation_history
        """
        try:
            cursor = self.db_connection.cursor()

            cursor.execute("""
                INSERT INTO negotiation_history (faction1, faction2, message, is_player, is_incoming, timestamp)
                VALUES (?, ?, ?, ?, ?, datetime('now'))
            """, (faction1, faction2, message, is_player, is_incoming))

            self.db_connection.commit()

            print(f"[MESSAGE SAVED] Сохранено сообщение в negotiation_history: {faction1} -> {faction2}")

        except Exception as e:
            print(f"Ошибка при создании сообщения в negotiation_history: {e}")

    def get_factions_at_war(self):
        """
        Возвращает список фракций, с которыми текущая фракция находится в состоянии войны.
        """
        try:
            cursor = self.db_connection.cursor()
            query = """SELECT faction2 FROM diplomacies WHERE faction1 = ? AND relationship = 'война'"""
            cursor.execute(query, (self.faction,))
            rows = cursor.fetchall()
            return [row[0] for row in rows]
        except Exception as e:
            print(f"Ошибка при получении списка вражеских фракций: {e}")
            return []

    # ---------------------------------------------------------------------

    # Основная логика хода ИИ
    def make_turn(self):
        """
        Основная логика хода ИИ фракции.
        Для фракции 'Мятежники' — только военные действия.
        """
        print(f'---------ХОДИТ ФРАКЦИЯ: {self.faction}-------------------')
        try:
            # 0. Обнуляем использование героя на этом ходу
            self.hero_used_in_turn = False

            # Проверяем, является ли фракция "Мятежники"
            if self.faction == "Мятежники":
                print("Фракция 'Мятежники' выполняет только военные действия.")
                # Выполняем атаки на вражеские города
                self.attack_enemy_cities()
            else:
                # Для всех других фракций — полный ход
                # 1. Обновляем ресурсы из базы данных
                self.update_resources()
                self.process_queries()
                # 2. Проверяем и объявляем войну, если необходимо
                self.check_and_declare_war()
                # 3. Применяем бонусы от политической системы
                self.apply_political_system_bonus()
                # 4. Изменяем отношения на основе политической системы
                self.update_relations_based_on_political_system()
                # 5. Загружаем данные о зданиях
                self.update_buildings_from_db()
                # 6. Управление строительством (99% крон на строительство)
                self.manage_buildings()
                # 7. Продажа Кристаллы (99% Кристаллы, если его больше 1000)
                self.sell_resources()
                # 8. Найм армии (на оставшиеся деньги после строительства и продажи Кристаллы)
                if self.resources['Кроны'] > 0:
                    self.hire_army()
                # 9. Генерация и покупка артефактов ИИ (после 50 хода)
                self.generate_and_buy_artifacts_for_ai_hero()
                # 10. Проверяем и отправляем дипломатические сообщения если нужно
                self.send_help_request_if_needed()
                self.send_mercy_request_if_needed()
            # 10. Сохраняем все изменения в базу данных
            self.save_all_data()
            # Увеличиваем счетчик ходов
            self.turn += 1
            print(f'-----------КОНЕЦ {self.turn} ХОДА----------------  ФРАКЦИИ', self.faction)
        except Exception as e:
            print(f"Ошибка при выполнении хода: {e}")
            import traceback
            traceback.print_exc()

from ai_strategy import apply_ai_improvements
apply_ai_improvements(AIController)