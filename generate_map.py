
from lerdon_libraries import *

# Список доступных карт
MAP_IMAGES_DIR = "files/map/generate"
AVAILABLE_MAPS = [f for f in os.listdir(MAP_IMAGES_DIR) if f.startswith("map_") and f.endswith(".png")]

# Фракции
FACTIONS = ["Север", "Эльфы", "Вампиры", "Адепты", "Элины"]
# Пул имён для городов
CITY_NAMES_POOL = [
    "Аргенвилль", "Партон", "Миргород", "Владонск", "Эледрин",
    "Селария", "Миреллия", "Каландор", "Валориан", "Гилион",
    "Холмград", "Тарпин", "Бастария", "Дарриан", "Арданис",
    "Ауренбург", "Феррадан", "Альтария", "Терра", "Каларин",
    "Хантир", "Лоредо", "Гарбор", "Новакар", "Сантигон",
    "Ривелло", "Остмара", "Замфир", "Индария", "Талисса",
    "Гельмут", "Виндгар", "Фениксия", "Этернис", "Лирандор",
    "Кальдира", "Солмера", "Ундрия", "Мардрак", "Ориона"
]

# Цвета для фракций
FACTION_COLORS = {
    'Вампиры': 'files/buildings/giperion.png',
    'Север': 'files/buildings/arkadia.png',
    'Эльфы': 'files/buildings/celestia.png',
    'Адепты': 'files/buildings/eteria.png',
    'Элины': 'files/buildings/halidon.png'
}

# Константы
TOTAL_CITIES = 23
FACTION_CITIES = 5
NEUTRAL_CITIES = TOTAL_CITIES - FACTION_CITIES
ALL_CITIES = FACTION_CITIES + TOTAL_CITIES
# Константы перемещения (синхронизированы с правилами движения = 280 Manhattan)
MAX_NEIGHBOURS = 4  # Максимум 4 соседа для лучшей связности
MIN_DISTANCE_PX = 120   # Минимальное евклидово расстояние между городами
MAX_DISTANCE_PX = 300   # Максимальное евклидово расстояние для рассмотрения связей
MANHATTAN_MOVE_LIMIT = 280  # Максимальное Manhattan расстояние для движения
MAP_SIZE = (1200, 800)
MARGIN = 100            # Отступ от краев карты
MAX_ROADS_PER_CITY = 5  # Максимум явных дорог между городами (для визуализации)

def generate_city_coords(prev_point=None):
    """Генерирует координаты следующего города относительно предыдущего"""
    if prev_point is None:
        # Первая точка — случайная, но с отступом от края
        x = random.randint(MARGIN, MAP_SIZE[0] - MARGIN)
        y = random.randint(MARGIN, MAP_SIZE[1] - MARGIN)
        return x, y
    else:
        x_prev, y_prev = prev_point
        attempts = 0
        while attempts < 100:
            distance = random.randint(MIN_DISTANCE_PX, MAX_DISTANCE_PX)
            angle = random.uniform(0, 2 * math.pi)
            dx = distance * math.cos(angle)
            dy = distance * math.sin(angle)
            x = x_prev + dx
            y = y_prev + dy
            if MARGIN <= x <= MAP_SIZE[0] - MARGIN and MARGIN <= y <= MAP_SIZE[1] - MARGIN:
                return int(x), int(y)
            attempts += 1
        # Если не получилось — возвращаем случайную точку с отступом
        return (
            random.randint(MARGIN, MAP_SIZE[0] - MARGIN),
            random.randint(MARGIN, MAP_SIZE[1] - MARGIN)
        )

def select_faction_cities(positions):
    """Выбирает 5 городов, все пары которых находятся на расстоянии >= 300 px друг от друга."""
    n = len(positions)
    min_required_distance = 200  # Минимальное расстояние между фракционными городами
    attempts = 0
    max_attempts = 100  # Максимум попыток подбора

    while attempts < max_attempts:
        # Случайно выбираем 5 индексов
        candidate_indices = random.sample(range(n), 5)
        valid = True

        # Проверяем каждую пару
        for i in range(5):
            for j in range(i + 1, 5):
                idx1 = candidate_indices[i]
                idx2 = candidate_indices[j]
                x1, y1 = positions[idx1]
                x2, y2 = positions[idx2]
                dist = math.hypot(x2 - x1, y2 - y1)
                if dist < min_required_distance:
                    valid = False
                    break
            if not valid:
                break

        if valid:
            print(f"[INFO] Найдены 5 фракционных городов, все на расстоянии ≥ {min_required_distance} px.")
            return candidate_indices

        attempts += 1

    # Если за max_attempts не нашлось подходящих — выбрасываем исключение
    raise RuntimeError(
        f"Не удалось найти 5 городов, удовлетворяющих условию минимального расстояния {min_required_distance}px"
    )

def generate_all_cities():
    """Генерирует города с гарантией связности и возможности выбрать 5 фракционных с расстоянием > 200px"""
    while True:
        cities = []
        used_positions = set()
        first_point = generate_city_coords()
        cities.append(first_point)
        used_positions.add(first_point)
        attempts = 0
        while len(cities) < TOTAL_CITIES and attempts < 1000:
            base_point = random.choice(cities)
            new_point = generate_city_coords(base_point)
            if new_point in used_positions:
                attempts += 1
                continue
            too_close = any(
                math.hypot(new_point[0] - p[0], new_point[1] - p[1]) < MIN_DISTANCE_PX
                for p in cities
            )
            if too_close:
                attempts += 1
                continue
            # Проверяем, есть ли хотя бы одна связь по Манхэттену (синхронизировано с движением = 280)
            if any(manhattan(new_point, p) <= MANHATTAN_MOVE_LIMIT for p in cities):
                cities.append(new_point)
                used_positions.add(new_point)
                attempts = 0  # сбрасываем попытки
            else:
                attempts += 1
        if len(cities) == TOTAL_CITIES:
            print(f"[SUCCESS] Сгенерировано {TOTAL_CITIES} уникальных городов.")
            # Проверяем, можно ли выбрать 5 фракционных с нужным расстоянием
            try:
                select_faction_cities(cities)
                return cities
            except RuntimeError as e:
                print(f"[WARN] Не удалось подобрать фракционные города: {e}. Перегенерация карты...")
        else:
            print("[WARN] Не удалось сгенерировать все города, пробуем заново...")


def build_city_graph(cities):
    """
    Строит граф связей между городами, используя Manhattan distance.
    Дороги соответствуют правилам движения (280 Manhattan).
    Граф структурирован так, чтобы создавать естественные маршруты.
    """
    graph = {i: [] for i in range(TOTAL_CITIES)}
    positions = [city["position"] for city in cities]

    # Список всех пар городов, которые находятся на расстоянии <= MANHATTAN_MOVE_LIMIT
    edges = []
    for i in range(TOTAL_CITIES):
        for j in range(i + 1, TOTAL_CITIES):
            manhattan_dist = abs(positions[i][0] - positions[j][0]) + abs(positions[i][1] - positions[j][1])
            if manhattan_dist <= MANHATTAN_MOVE_LIMIT:
                # Приоритет: чем ближе по Manhattan, тем выше приоритет
                edges.append((manhattan_dist, i, j))

    # Сортируем по Manhattan расстоянию
    edges.sort()

    # Фракционные города
    faction_indices = [i for i, city in enumerate(cities) if city["type"] == "faction"]

    # Строим минимальное связное дерево (MST) для гарантии связности
    parent = list(range(TOTAL_CITIES))
    def find(u):
        while parent[u] != u:
            parent[u] = parent[parent[u]]
            u = parent[u]
        return u
    def union(u, v):
        pu, pv = find(u), find(v)
        if pu != pv:
            parent[pu] = pv
            return True
        return False

    mst_edges = set()
    # Добавляем ребра MST
    for manhattan_dist, u, v in edges:
        if union(u, v):
            # Проверяем: не соединяем две фракции напрямую
            if not (cities[u]["type"] == "faction" and cities[v]["type"] == "faction"):
                graph[u].append(v)
                graph[v].append(u)
                mst_edges.add((u, v))
                mst_edges.add((v, u))

    # Добавляем промежуточные дороги для естественности и разнообразия маршрутов
    # Каждый город должен иметь минимум 2 и максимум MAX_NEIGHBOURS соседей
    for i in range(TOTAL_CITIES):
        current_neighbors = set(graph[i])
        needed = max(0, 2 - len(current_neighbors))
        if needed > 0:
            # Добавляем ближайших кандидатов
            candidates = []
            for manhattan_dist, u, v in edges:
                if u == i and v not in current_neighbors:
                    # Не добавляем связи между фракциями
                    if not (cities[i]["type"] == "faction" and cities[v]["type"] == "faction"):
                        candidates.append((manhattan_dist, v))
                elif v == i and u not in current_neighbors:
                    # Не добавляем связи между фракциями
                    if not (cities[i]["type"] == "faction" and cities[u]["type"] == "faction"):
                        candidates.append((manhattan_dist, u))

            candidates.sort()
            added = 0
            for _, neighbor_idx in candidates:
                if neighbor_idx not in current_neighbors:
                    graph[i].append(neighbor_idx)
                    graph[neighbor_idx].append(i)
                    current_neighbors.add(neighbor_idx)
                    added += 1
                    if added >= needed:
                        break

    # Убеждаемся, что фракционные города имеют минимум 2 нейтральных соседа
    for faction_idx in faction_indices:
        neutral_neighbors = [n for n in graph[faction_idx] if cities[n]["type"] == "neutral"]
        if len(neutral_neighbors) < 2:
            needed = 2 - len(neutral_neighbors)
            candidates = []
            for manhattan_dist, u, v in edges:
                if u == faction_idx and cities[v]["type"] == "neutral" and v not in graph[faction_idx]:
                    candidates.append((manhattan_dist, v))
                elif v == faction_idx and cities[u]["type"] == "neutral" and u not in graph[faction_idx]:
                    candidates.append((manhattan_dist, u))
            candidates.sort()
            for _, neutral_idx in candidates[:needed]:
                if neutral_idx not in graph[faction_idx]:
                    graph[faction_idx].append(neutral_idx)
                    graph[neutral_idx].append(faction_idx)

    # Ограничиваем максимальное число соседей для визуальной ясности
    for i in range(TOTAL_CITIES):
        if len(graph[i]) > MAX_NEIGHBOURS:
            # Оставляем только ближайшие соседи
            neighbors_with_dist = []
            for neighbor_idx in graph[i]:
                manhattan_dist = abs(positions[i][0] - positions[neighbor_idx][0]) + abs(positions[i][1] - positions[neighbor_idx][1])
                neighbors_with_dist.append((manhattan_dist, neighbor_idx))
            neighbors_with_dist.sort()
            graph[i] = [neighbor_idx for _, neighbor_idx in neighbors_with_dist[:MAX_NEIGHBOURS]]

    return graph

def assign_factions_to_cities(positions):
    """Назначает фракции 5 наиболее удалённым городам, остальным — нейтралитет"""
    cities = []
    available_names = CITY_NAMES_POOL.copy()
    random.shuffle(available_names)

    # Шаг 1: Выбираем 5 наиболее удалённых городов
    faction_indices = select_faction_cities(positions)

    # Шаг 2: Назначаем им фракции
    assigned = 0
    used_names = set()
    faction_assignments = {}

    # Создаём список фракций в случайном порядке
    shuffled_factions = random.sample(FACTIONS, len(FACTIONS))

    for idx in faction_indices:
        faction = shuffled_factions[assigned % len(FACTIONS)]
        name = None
        while available_names:
            name = available_names.pop()
            if name not in used_names:
                used_names.add(name)
                break
        if not name:
            name = f"Город {idx + 1}"

        city = {
            "type": "faction",
            "name": f"{name}",
            "position": positions[idx],
            "faction": faction,
            "color_faction": FACTION_COLORS[faction]
        }
        cities.append(city)
        faction_assignments[idx] = city
        assigned += 1

    # Шаг 3: Добавляем оставшиеся города как нейтралы
    neutral_cities = []
    for idx in range(len(positions)):
        if idx in faction_assignments:
            continue
        name = None
        while available_names:
            name = available_names.pop()
            if name not in used_names:
                used_names.add(name)
                break
        if not name:
            name = f"Нейтрал Город {idx + 1}"

        city = {
            "type": "neutral",
            "name": f"{name}",
            "position": positions[idx],
            "faction": None,
            "color_faction": "#AAAAAA"
        }
        cities.append(city)

    # Возвращаем список в том же порядке, что и positions
    result = [None] * len(positions)
    for idx in faction_assignments:
        result[idx] = faction_assignments[idx]
    for city in cities:
        if city["position"] in positions and result[positions.index(city["position"])] is None:
            result[positions.index(city["position"])] = city

    return result

def save_to_database(conn, cities, graph):
    """Сохраняет данные о городах и дорогах в базу данных"""
    cursor = conn.cursor()
    cursor.execute("DELETE FROM cities")
    cursor.execute("DELETE FROM roads")

    # Сохраняем города
    for i, city in enumerate(cities):
        faction = city["faction"] if city["faction"] else "Нейтрал"
        coords = str(list(city["position"]))
        icon_coords = str([city["position"][0], city["position"][1]])
        label_coords = str([city["position"][0], city["position"][1] - 30])
        cursor.execute(
            "INSERT INTO cities (id, name, coordinates, faction, icon_coordinates, label_coordinates, color_faction) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (i + 1, city["name"], coords, faction, icon_coords, label_coords, city["color_faction"])
        )

    # Сохраняем дороги
    road_id = 1
    added_roads = set()
    for city_namex, neighbors in graph.items():
        for neighbor_idx in neighbors:
            if (city_namex, neighbor_idx) in added_roads or (neighbor_idx, city_namex) in added_roads:
                continue
            added_roads.add((city_namex, neighbor_idx))
            added_roads.add((neighbor_idx, city_namex))
            cursor.execute(
                "INSERT INTO roads (id, city1, city2) VALUES (?, ?, ?)",
                (road_id, city_namex + 1, neighbor_idx + 1)
            )
            road_id += 1

    # --- НОВАЯ ЛОГИКА: Генерация значений kf_crystal по заданному распределению ---
    total_cities_count = len(cities)
    # Проверяем, что общее количество городов соответствует
    assert total_cities_count == 23, f"Ожидается 23 города, получено {total_cities_count}"

    kf_crystal_values = []

    # 1. Генерируем 15 значений для диапазона [1.0, 1.2)
    for _ in range(15):
        kf_crystal_values.append(round(random.uniform(1.0, 1.2), 2))

    # 2. Генерируем 6 значений для диапазона [1.8, 2.3)
    for _ in range(6):
        kf_crystal_values.append(round(random.uniform(1.8, 2.3), 2))

    # 3. Генерируем 2 значений для диапазона [5.3, 7.75]
    for _ in range(2):
        kf_crystal_values.append(round(random.uniform(5.3, 7.75), 2))

    # Перемешиваем список, чтобы распределение было случайным по городам
    random.shuffle(kf_crystal_values)

    # --- КОНЕЦ НОВОЙ ЛОГИКИ ---

    # Обновляем таблицу cities, устанавливая kf_crystal для каждого id
    for i, kf_val in enumerate(kf_crystal_values):
        city_id = i + 1  # Предполагаем, что id города начинаются с 1
        cursor.execute(
            "UPDATE cities SET kf_crystal = ? WHERE id = ?",
            (kf_val, city_id)
        )

    conn.commit()
    print(f"[INFO] Сохранено {len(cities)} городов и {road_id - 1} дорог.")
    # Опционально: сообщить о заполнении kf_crystal
    print(f"[INFO] Столбец kf_crystal заполнен по заданному распределению: 10 значений [1.0, 1.7), 7 значений [1.7, 2.9), 6 значений [2.9, 4.8].")



def manhattan(a, b):
    """Манхэттенское расстояние между точками a и b."""
    return abs(a[0] - b[0]) + abs(a[1] - b[1])

def is_connected(positions):
    """
    Проверяет, что граф, где ребро между i и j есть если
    manhattan(positions[i], positions[j]) <= MANHATTAN_THRESHOLD,
    связен (от любой вершины достижимы все).
    """
    n = len(positions)
    visited = [False] * n
    queue = deque([0])
    visited[0] = True

    while queue:
        u = queue.popleft()
        for v in range(n):
            if not visited[v] and manhattan(positions[u], positions[v]) <= MANHATTAN_THRESHOLD:
                visited[v] = True
                queue.append(v)

    return all(visited)


def generate_map_and_cities(conn):
    """Основная функция: генерация связного набора городов → остальное."""

    # Шаг 1: Генерация координат городов с гарантией связности по манхэттену
    print("[INFO] Генерация координат городов с гарантией связности...")
    positions = generate_all_cities()

    # Шаг 2: Назначаем фракции и остальные параметры
    cities = assign_factions_to_cities(positions)

    # Шаг 3: Строим граф дорог (можно оставить старый Kruskal‑подход или переделать под манхэттен)
    print("[INFO] Построение графа связей между городами...")
    graph = build_city_graph(cities)

    # Шаг 4: Сохраняем всё в БД
    save_to_database(conn, cities, graph)

    print("[SUCCESS] Координаты для городов успешно сгенерированы!")
    print("[SUCCESS] GENERATE MAP COMPLETE!")
