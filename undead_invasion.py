# -*- coding: utf-8 -*-
"""
undead_invasion.py — Система нашествия Нежити (Царь Мёртвых)
============================================================

Механика вдохновлена Белыми Ходоками из "Игры Престолов":
  - 3 скрытых города нежити на карте (выглядят как нейтральные до инвазии)
  - На случайном ходу 22-26 начинается нашествие
  - Армия 30 000 призраков появляется в ОДНОМ случайном городе из 3
  - Остальные 2 города остаются нейтральными
  - Царь Мёртвых агрессивно атакует ближайшие города каждый ход
  - Все пленные превращаются в призраков и присоединяются к армии мёртвых
  - Все фракции бросают все силы против нежити
"""

import random
import sqlite3


# Ход начала инвазии (рандом 22-26)
INVASION_TURN_MIN = 22
INVASION_TURN_MAX = 26

# Начальная армия нежити
UNDEAD_INITIAL_ARMY = 75000

# Подкрепления за первые 3 хода: (250000 - 75000) / 3 ≈ 58333 за ход
UNDEAD_SURGE_TURNS = 3
UNDEAD_SURGE_TARGET = 250000
# Обычные подкрепления после набора
UNDEAD_REINFORCEMENTS_MIN = 2000
UNDEAD_REINFORCEMENTS_MAX = 5000

# Характеристики Царя Мёртвых
KING_OF_DEAD_ATTACK = 500
KING_OF_DEAD_DEFENSE = 600
KING_OF_DEAD_DURABILITY = 50
KING_OF_DEAD_NAME = "Царь Мёртвых"

# Характеристики юнитов нежити
UNDEAD_UNIT_NAME = "Призрак"
UNDEAD_UNIT_ATTACK = 29
UNDEAD_UNIT_DEFENSE = 7
UNDEAD_UNIT_DURABILITY = 3
UNDEAD_UNIT_COST = 2.5
UNDEAD_UNIT_CONSUMPTION = 0.8

UNDEAD_FACTION_NAME = "Нежить"


def initialize_undead_invasion(conn):
    """
    Инициализирует систему инвазии нежити при старте игры.
    Генерирует случайный ход начала инвазии и сохраняет в БД.
    Создаёт юнитов нежити в таблицах units и units_default.
    """
    cursor = conn.cursor()

    # Создаём таблицу для состояния инвазии
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS undead_invasion (
            id INTEGER PRIMARY KEY DEFAULT 1,
            invasion_turn INTEGER NOT NULL,
            invasion_started INTEGER DEFAULT 0,
            king_alive INTEGER DEFAULT 1,
            army_limit INTEGER DEFAULT 30000
        )
    """)

    # Проверяем, есть ли уже запись
    cursor.execute("SELECT COUNT(*) FROM undead_invasion")
    if cursor.fetchone()[0] == 0:
        invasion_turn = random.randint(INVASION_TURN_MIN, INVASION_TURN_MAX)
        cursor.execute(
            "INSERT INTO undead_invasion (id, invasion_turn, invasion_started, king_alive, army_limit) VALUES (1, ?, 0, 1, ?)",
            (invasion_turn, UNDEAD_INITIAL_ARMY)
        )
        print(f"[UNDEAD] Инвазия запланирована на ход {invasion_turn}")
    else:
        cursor.execute("SELECT invasion_turn, invasion_started FROM undead_invasion WHERE id = 1")
        row = cursor.fetchone()
        if row:
            old_turn, started = row
            if started:
                # Инвазия "началась", но проверяем — есть ли нежить вообще
                cursor.execute("SELECT COUNT(*) FROM cities WHERE faction = ?", (UNDEAD_FACTION_NAME,))
                undead_cities = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM garrisons WHERE unit_name = ?", (KING_OF_DEAD_NAME,))
                king_exists = cursor.fetchone()[0]

                if undead_cities == 0 and king_exists == 0:
                    # Инвазия провалилась — сбрасываем для повторного запуска
                    cursor.execute("SELECT turn_count FROM turn LIMIT 1")
                    turn_row = cursor.fetchone()
                    current_turn = turn_row[0] if turn_row else 1
                    # Не раньше INVASION_TURN_MIN, не позже INVASION_TURN_MAX
                    new_turn = max(INVASION_TURN_MIN, min(current_turn + random.randint(2, 4), INVASION_TURN_MAX))
                    cursor.execute(
                        "UPDATE undead_invasion SET invasion_turn = ?, invasion_started = 0, king_alive = 1, army_limit = ? WHERE id = 1",
                        (new_turn, UNDEAD_INITIAL_ARMY)
                    )
                    print(f"[UNDEAD] Инвазия провалилась — перезапуск на ход {new_turn}")
            else:
                # Инвазия ещё не началась — корректируем ход если вне диапазона
                if old_turn < INVASION_TURN_MIN or old_turn > INVASION_TURN_MAX:
                    new_turn = random.randint(INVASION_TURN_MIN, INVASION_TURN_MAX)
                    cursor.execute("UPDATE undead_invasion SET invasion_turn = ? WHERE id = 1", (new_turn,))
                    print(f"[UNDEAD] Ход инвазии скорректирован: {old_turn} -> {new_turn}")

    # Создаём юнитов нежити если их ещё нет
    _create_undead_units(cursor)

    conn.commit()


def _create_undead_units(cursor):
    """Создаёт юнитов нежити в таблицах units и units_default."""
    cursor.execute("SELECT COUNT(*) FROM units WHERE faction = ?", (UNDEAD_FACTION_NAME,))
    if cursor.fetchone()[0] > 0:
        return

    unit_data_class1 = (
        UNDEAD_FACTION_NAME, UNDEAD_UNIT_NAME,
        UNDEAD_UNIT_COST, 1,
        'files/army/death/solder.png',
        UNDEAD_UNIT_ATTACK, UNDEAD_UNIT_DEFENSE, UNDEAD_UNIT_DURABILITY,
        '1', UNDEAD_UNIT_CONSUMPTION,
        55, 'infantry', 100,
        0, 0, 7
    )

    unit_data_king = (
        UNDEAD_FACTION_NAME, KING_OF_DEAD_NAME,
        50000, 1,
        'files/army/death/king_.png',
        KING_OF_DEAD_ATTACK, KING_OF_DEAD_DEFENSE, KING_OF_DEAD_DURABILITY,
        '2', 100,
        85, 'infantry', 100,
        15, 15, 12
    )

    insert_sql = """
        INSERT INTO units (faction, unit_name, cost_money, cost_time, image_path,
                          attack, defense, durability, unit_class, consumption,
                          initiative, unit_type, morale, aura_attack, aura_defense, crit_chance)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """

    insert_default_sql = """
        INSERT INTO units_default (faction, unit_name, cost_money, cost_time, image_path,
                                  attack, defense, durability, unit_class, consumption,
                                  initiative, unit_type, morale, aura_attack, aura_defense, crit_chance)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """

    for unit_data in [unit_data_class1, unit_data_king]:
        cursor.execute(insert_sql, unit_data)
        try:
            cursor.execute(insert_default_sql, unit_data)
        except sqlite3.Error:
            pass

    print(f"[UNDEAD] Созданы юниты нежити: {UNDEAD_UNIT_NAME} и {KING_OF_DEAD_NAME}")


def check_and_trigger_invasion(conn, current_turn, player_faction):
    """
    Проверяет, пора ли начинать инвазию нежити.
    Армия 30000 призраков + Царь Мёртвых появляется в ОДНОМ случайном городе из 3.
    Остальные 2 города остаются нейтральными.
    """
    cursor = conn.cursor()

    cursor.execute("SELECT invasion_turn, invasion_started FROM undead_invasion WHERE id = 1")
    row = cursor.fetchone()
    if not row:
        return False, None

    invasion_turn, invasion_started = row
    if invasion_started:
        return False, None
    if current_turn < invasion_turn:
        return False, None

    # === НАЧИНАЕМ ИНВАЗИЮ ===
    print(f"[UNDEAD] === ИНВАЗИЯ НАЧИНАЕТСЯ НА ХОДУ {current_turn}! ===")

    cursor.execute("UPDATE undead_invasion SET invasion_started = 1 WHERE id = 1")

    # Получаем все 3 города нежити
    cursor.execute("SELECT id, name FROM cities WHERE is_undead = 1")
    undead_cities = cursor.fetchall()

    if not undead_cities:
        return False, None

    # Выбираем ОДИН случайный город для армии
    chosen_city_id, chosen_city_name = random.choice(undead_cities)

    # Только выбранный город становится "Нежить"
    cursor.execute(
        "UPDATE cities SET faction = ?, color_faction = ? WHERE id = ?",
        (UNDEAD_FACTION_NAME, '#33BF99', chosen_city_id)
    )

    # Спавним 50000 призраков + Царя Мёртвых в одном городе
    cursor.execute("""
        INSERT INTO garrisons (city_name, unit_name, unit_count, unit_image)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(city_name, unit_name) DO UPDATE SET
            unit_count = unit_count + excluded.unit_count
    """, (chosen_city_name, UNDEAD_UNIT_NAME, UNDEAD_INITIAL_ARMY, 'files/army/death/solder.png'))

    cursor.execute("""
        INSERT INTO garrisons (city_name, unit_name, unit_count, unit_image)
        VALUES (?, ?, 1, ?)
    """, (chosen_city_name, KING_OF_DEAD_NAME, 'files/army/death/king_.png'))

    # Объявляем войну всем фракциям
    _declare_war_to_all(cursor)

    conn.commit()

    invasion_message = (
        f"ПРИХОД МОРА!\n\n"
        f"Из древнего некрополя восстала армия мёртвых!\n"
        f"{KING_OF_DEAD_NAME} ведёт 75 000 призраков.\n\n"
        f"Город {chosen_city_name} захвачен нежитью.\n"
        f"Мор распространяется — армия мёртвых будет расти!"
    )

    return True, invasion_message


def _declare_war_to_all(cursor):
    """Объявляет войну всем фракциям от имени Нежити."""
    factions = ["Север", "Эльфы", "Вампиры", "Адепты", "Элины", "Мятежники"]
    for faction in factions:
        cursor.execute(
            "SELECT COUNT(*) FROM diplomacies WHERE faction1 = ? AND faction2 = ?",
            (UNDEAD_FACTION_NAME, faction)
        )
        if cursor.fetchone()[0] == 0:
            cursor.execute(
                "INSERT INTO diplomacies (faction1, faction2, relationship) VALUES (?, ?, ?)",
                (UNDEAD_FACTION_NAME, faction, "война")
            )
            cursor.execute(
                "INSERT OR IGNORE INTO diplomacies (faction1, faction2, relationship) VALUES (?, ?, ?)",
                (faction, UNDEAD_FACTION_NAME, "война")
            )
        else:
            cursor.execute(
                "UPDATE diplomacies SET relationship = 'война' WHERE faction1 = ? AND faction2 = ?",
                (UNDEAD_FACTION_NAME, faction)
            )
            cursor.execute(
                "UPDATE diplomacies SET relationship = 'война' WHERE faction1 = ? AND faction2 = ?",
                (faction, UNDEAD_FACTION_NAME)
            )
    # Также добавляем в relations
    for faction in factions:
        try:
            cursor.execute(
                "INSERT OR IGNORE INTO relations (faction1, faction2, value) VALUES (?, ?, ?)",
                (UNDEAD_FACTION_NAME, faction, 0)
            )
            cursor.execute(
                "INSERT OR IGNORE INTO relations (faction1, faction2, value) VALUES (?, ?, ?)",
                (faction, UNDEAD_FACTION_NAME, 0)
            )
        except sqlite3.Error:
            pass
    print(f"[UNDEAD] Война объявлена всем фракциям!")


def convert_prisoners_to_ghosts(cursor, captured_count, city_name):
    """
    Превращает пленных в призраков. Призраки присоединяются
    к армии Царя Мёртвых (в город где он находится).
    """
    if captured_count <= 0:
        return

    # Находим город Царя — пленные идут к нему
    king_city = _get_king_city(cursor)
    target_city = king_city if king_city else city_name

    cursor.execute("""
        INSERT INTO garrisons (city_name, unit_name, unit_count, unit_image)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(city_name, unit_name) DO UPDATE SET
            unit_count = unit_count + excluded.unit_count
    """, (target_city, UNDEAD_UNIT_NAME, captured_count, 'files/army/death/solder.png'))

    print(f"[UNDEAD] {captured_count} пленных превращены в призраков в {target_city}")


def _get_king_city(cursor):
    """Находит город где стоит Царь Мёртвых."""
    cursor.execute(
        "SELECT city_name FROM garrisons WHERE unit_name = ?",
        (KING_OF_DEAD_NAME,)
    )
    row = cursor.fetchone()
    return row[0] if row else None


def _respawn_king_if_dead(cursor):
    """
    Если Царь Мёртвых погиб — возрождает его в городе нежити
    с наибольшим гарнизоном призраков.
    """
    # Проверяем жив ли Царь
    cursor.execute("SELECT COUNT(*) FROM garrisons WHERE unit_name = ?", (KING_OF_DEAD_NAME,))
    if cursor.fetchone()[0] > 0:
        return  # Царь жив

    # Ищем город нежити с наибольшим количеством призраков
    cursor.execute("""
        SELECT g.city_name, COALESCE(SUM(g.unit_count), 0) as total
        FROM garrisons g
        JOIN cities c ON g.city_name = c.name
        WHERE c.faction = ? AND c.is_undead = 1
        GROUP BY g.city_name
        ORDER BY total DESC
        LIMIT 1
    """, (UNDEAD_FACTION_NAME,))
    best = cursor.fetchone()

    if not best:
        # Нет гарнизонов — ищем любой город нежити
        cursor.execute("SELECT name FROM cities WHERE faction = ? AND is_undead = 1 LIMIT 1",
                       (UNDEAD_FACTION_NAME,))
        city_row = cursor.fetchone()
        if not city_row:
            return  # Все города захвачены
        respawn_city = city_row[0]
    else:
        respawn_city = best[0]

    cursor.execute("""
        INSERT INTO garrisons (city_name, unit_name, unit_count, unit_image)
        VALUES (?, ?, 1, ?)
    """, (respawn_city, KING_OF_DEAD_NAME, 'files/army/death/king_.png'))

    print(f"[UNDEAD] {KING_OF_DEAD_NAME} возродился в {respawn_city}!")


def process_undead_turn(conn, current_turn):
    """
    Обработка хода нежити. Все подкрепления идут в город Царя Мёртвых.
    """
    cursor = conn.cursor()

    cursor.execute("SELECT invasion_started, king_alive, invasion_turn FROM undead_invasion WHERE id = 1")
    row = cursor.fetchone()
    if not row or not row[0]:
        return

    invasion_turn = row[2]
    turns_since_invasion = current_turn - invasion_turn

    # Царь Мёртвых бессмертен — если погиб, возрождается
    _respawn_king_if_dead(cursor)

    # Захватываем нейтральные города нежити (is_undead=1) — мор распространяется
    cursor.execute("SELECT id, name FROM cities WHERE is_undead = 1 AND faction = 'Нейтрал'")
    neutral_undead = cursor.fetchall()
    for city_id, city_name in neutral_undead:
        cursor.execute(
            "UPDATE cities SET faction = ?, color_faction = ? WHERE id = ?",
            (UNDEAD_FACTION_NAME, '#33BF99', city_id)
        )
        print(f"[UNDEAD] Мор распространился на {city_name}")

    # Проверяем города нежити
    cursor.execute("SELECT COUNT(*) FROM cities WHERE faction = ?", (UNDEAD_FACTION_NAME,))
    if cursor.fetchone()[0] == 0:
        print("[UNDEAD] Все города нежити захвачены. Нашествие остановлено!")
        return

    # Находим город Царя Мёртвых — все подкрепления идут к нему
    king_city = _get_king_city(cursor)
    if not king_city:
        # Царь погиб — спавним подкрепления в первом городе нежити
        cursor.execute("SELECT name FROM cities WHERE faction = ? LIMIT 1", (UNDEAD_FACTION_NAME,))
        r = cursor.fetchone()
        king_city = r[0] if r else None

    if not king_city:
        return

    # Считаем текущую армию призраков
    cursor.execute("""
        SELECT COALESCE(SUM(g.unit_count), 0)
        FROM garrisons g
        JOIN cities c ON g.city_name = c.name
        WHERE c.faction = ? AND g.unit_name = ?
    """, (UNDEAD_FACTION_NAME, UNDEAD_UNIT_NAME))
    current_army = cursor.fetchone()[0]

    # Все подкрепления идут в город Царя
    if turns_since_invasion <= UNDEAD_SURGE_TURNS:
        # Массивный набор до 250к за 3 хода
        remaining_to_target = max(0, UNDEAD_SURGE_TARGET - current_army)
        remaining_turns = max(1, UNDEAD_SURGE_TURNS - turns_since_invasion + 1)
        surge = remaining_to_target // remaining_turns

        cursor.execute("""
            INSERT INTO garrisons (city_name, unit_name, unit_count, unit_image)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(city_name, unit_name) DO UPDATE SET
                unit_count = unit_count + excluded.unit_count
        """, (king_city, UNDEAD_UNIT_NAME, surge, 'files/army/death/solder.png'))

        print(f"[UNDEAD] Набор армии в {king_city}: +{surge} призраков "
              f"(ход {turns_since_invasion}/{UNDEAD_SURGE_TURNS}, всего ~{current_army + surge})")
    else:
        reinforcements = random.randint(UNDEAD_REINFORCEMENTS_MIN, UNDEAD_REINFORCEMENTS_MAX)
        cursor.execute("""
            INSERT INTO garrisons (city_name, unit_name, unit_count, unit_image)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(city_name, unit_name) DO UPDATE SET
                unit_count = unit_count + excluded.unit_count
        """, (king_city, UNDEAD_UNIT_NAME, reinforcements, 'files/army/death/solder.png'))

    # Попытка купить артефакт для Царя Мёртвых (всегда жив после респавна)
    _buy_artifact_for_king(cursor)

    _ensure_undead_resources(cursor)
    conn.commit()


def _ensure_undead_resources(cursor):
    """Создаёт запись ресурсов для фракции Нежить если её нет."""
    cursor.execute("SELECT COUNT(*) FROM resources WHERE faction = ?", (UNDEAD_FACTION_NAME,))
    if cursor.fetchone()[0] == 0:
        resources = [
            (UNDEAD_FACTION_NAME, 'Кроны', 5000),
            (UNDEAD_FACTION_NAME, 'Рабочие', 0),
            (UNDEAD_FACTION_NAME, 'Кристаллы', 500),
            (UNDEAD_FACTION_NAME, 'Население', 5000),
        ]
        for faction, res_type, amount in resources:
            cursor.execute(
                "INSERT OR IGNORE INTO resources (faction, resource_type, amount) VALUES (?, ?, ?)",
                (faction, res_type, amount)
            )


def _buy_artifact_for_king(cursor):
    """Царь Мёртвых покупает случайный доступный артефакт."""
    try:
        cursor.execute("""
            SELECT id, name, attack, defense, cost, artifact_type
            FROM artifacts
            WHERE is_created = 1
            ORDER BY (attack + defense) DESC
            LIMIT 5
        """)
        available = cursor.fetchall()

        if not available:
            return

        artifact = random.choice(available)
        art_id, art_name, art_atk, art_def, cost, art_type = artifact

        print(f"[UNDEAD] {KING_OF_DEAD_NAME} приобретает артефакт: {art_name} (+{art_atk} атк, +{art_def} защ)")

    except sqlite3.Error as e:
        print(f"[UNDEAD] Ошибка покупки артефакта: {e}")


def get_undead_army_limit(conn):
    """Возвращает текущий лимит армии нежити."""
    cursor = conn.cursor()
    cursor.execute("SELECT army_limit FROM undead_invasion WHERE id = 1")
    row = cursor.fetchone()
    return row[0] if row else UNDEAD_INITIAL_ARMY


def is_invasion_active(conn):
    """Проверяет, активна ли инвазия нежити."""
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT invasion_started FROM undead_invasion WHERE id = 1")
        row = cursor.fetchone()
        return bool(row and row[0])
    except sqlite3.Error:
        return False


def get_invasion_turn(conn):
    """Возвращает ход начала инвазии."""
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT invasion_turn FROM undead_invasion WHERE id = 1")
        row = cursor.fetchone()
        return row[0] if row else None
    except sqlite3.Error:
        return None
