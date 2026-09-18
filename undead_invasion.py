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


# Ход начала инвазии (рандом 18-26)
INVASION_TURN_MIN = 18
INVASION_TURN_MAX = 26

# Начальная армия нежити — 250к разово
UNDEAD_INITIAL_ARMY = 250000

# Подкрепления: 40к/ход в течение 10 ходов после инвазии (сёрдж)
UNDEAD_SURGE_TURNS = 10
UNDEAD_SURGE_PER_TURN = 40000

# Характеристики Царя Мёртвых
KING_OF_DEAD_ATTACK = 800
KING_OF_DEAD_DEFENSE = 950
KING_OF_DEAD_DURABILITY = 80
KING_OF_DEAD_NAME = "Царь Мёртвых"

# Характеристики юнитов нежити
UNDEAD_UNIT_NAME = "Призрак"
UNDEAD_UNIT_ATTACK = 29
UNDEAD_UNIT_DEFENSE = 7
UNDEAD_UNIT_DURABILITY = 3
UNDEAD_UNIT_COST = 2.5
UNDEAD_UNIT_CONSUMPTION = 0.8

# Зомби — пехота, массовый юнит, чуть сильнее Призрака
ZOMBIE_UNIT_NAME = "Зомби"
ZOMBIE_UNIT_ATTACK = 38
ZOMBIE_UNIT_DEFENSE = 15
ZOMBIE_UNIT_DURABILITY = 8
ZOMBIE_UNIT_COST = 4.0
ZOMBIE_UNIT_CONSUMPTION = 1.0

# Банши — маг, высокий урон, хрупкая
BANSHEE_UNIT_NAME = "Банши"
BANSHEE_UNIT_ATTACK = 55
BANSHEE_UNIT_DEFENSE = 5
BANSHEE_UNIT_DURABILITY = 2
BANSHEE_UNIT_COST = 6.0
BANSHEE_UNIT_CONSUMPTION = 1.5

# Костяной Голем — осадный, танк
GOLEM_UNIT_NAME = "Костяной Голем"
GOLEM_UNIT_ATTACK = 250
GOLEM_UNIT_DEFENSE = 600
GOLEM_UNIT_DURABILITY = 120
GOLEM_UNIT_COST = 50.0
GOLEM_UNIT_CONSUMPTION = 5.0

# Конверсия пленных — 20% убитых врагов
UNDEAD_CONVERSION_RATE = 0.20

# Постоянные подкрепления (без спада)
UNDEAD_REINFORCEMENTS_CONSTANT = 18000

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
                    # Проверяем — все ли 3 города захвачены навсегда
                    cursor.execute("""
                        SELECT COUNT(*) FROM cities
                        WHERE is_undead = 1 AND faction != ? AND faction != 'Нейтрал'
                    """, (UNDEAD_FACTION_NAME,))
                    captured = cursor.fetchone()[0]
                    cursor.execute("SELECT COUNT(*) FROM cities WHERE is_undead = 1")
                    total = cursor.fetchone()[0]

                    if captured >= total:
                        # Все 3 города захвачены — нашествие окончательно побеждено
                        cursor.execute(
                            "UPDATE undead_invasion SET invasion_started = 0, king_alive = 0 WHERE id = 1"
                        )
                        print("[UNDEAD] Все города нежити захвачены! Нашествие окончено.")
                    else:
                        # Ещё есть нейтральные города — волны продолжатся через process_undead_turn
                        print(f"[UNDEAD] Города нежити потеряны, но {total - captured} ещё не захвачены. Волны продолжатся.")
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
    existing = cursor.fetchone()[0]

    insert_sql = """
        INSERT OR REPLACE INTO units (faction, unit_name, cost_money, cost_time, image_path,
                          attack, defense, durability, unit_class, consumption,
                          initiative, unit_type, morale, aura_attack, aura_defense, crit_chance)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    insert_default_sql = """
        INSERT OR REPLACE INTO units_default (faction, unit_name, cost_money, cost_time, image_path,
                                  attack, defense, durability, unit_class, consumption,
                                  initiative, unit_type, morale, aura_attack, aura_defense, crit_chance)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """

    # Призрак — пехота
    unit_ghost = (
        UNDEAD_FACTION_NAME, UNDEAD_UNIT_NAME,
        UNDEAD_UNIT_COST, 1,
        'files/army/death/solder.png',
        UNDEAD_UNIT_ATTACK, UNDEAD_UNIT_DEFENSE, UNDEAD_UNIT_DURABILITY,
        '1', UNDEAD_UNIT_CONSUMPTION,
        55, 'infantry', 100,
        0, 0, 7
    )

    # Зомби — пехота, крепче Призрака
    unit_zombie = (
        UNDEAD_FACTION_NAME, ZOMBIE_UNIT_NAME,
        ZOMBIE_UNIT_COST, 1,
        'files/army/death/zombie.png',
        ZOMBIE_UNIT_ATTACK, ZOMBIE_UNIT_DEFENSE, ZOMBIE_UNIT_DURABILITY,
        '1', ZOMBIE_UNIT_CONSUMPTION,
        40, 'infantry', 100,
        0, 0, 5
    )

    # Банши — маг, высокий урон
    unit_banshee = (
        UNDEAD_FACTION_NAME, BANSHEE_UNIT_NAME,
        BANSHEE_UNIT_COST, 1,
        'files/army/death/banshi.png',
        BANSHEE_UNIT_ATTACK, BANSHEE_UNIT_DEFENSE, BANSHEE_UNIT_DURABILITY,
        '1', BANSHEE_UNIT_CONSUMPTION,
        70, 'mage', 100,
        0, 0, 15
    )

    # Костяной Голем — осадный танк
    unit_golem = (
        UNDEAD_FACTION_NAME, GOLEM_UNIT_NAME,
        GOLEM_UNIT_COST, 1,
        'files/army/death/golem.png',
        GOLEM_UNIT_ATTACK, GOLEM_UNIT_DEFENSE, GOLEM_UNIT_DURABILITY,
        '1', GOLEM_UNIT_CONSUMPTION,
        20, 'siege', 100,
        0, 0, 3
    )

    # Царь Мёртвых — герой (класс 2)
    unit_king = (
        UNDEAD_FACTION_NAME, KING_OF_DEAD_NAME,
        50000, 1,
        'files/army/death/king_.png',
        KING_OF_DEAD_ATTACK, KING_OF_DEAD_DEFENSE, KING_OF_DEAD_DURABILITY,
        '2', 100,
        85, 'infantry', 100,
        25, 25, 18
    )

    all_units = [unit_ghost, unit_zombie, unit_banshee, unit_golem, unit_king]
    for unit_data in all_units:
        cursor.execute(insert_sql, unit_data)
        try:
            cursor.execute(insert_default_sql, unit_data)
        except sqlite3.Error:
            pass

    if existing == 0:
        print(f"[UNDEAD] Созданы юниты нежити: Призрак, Зомби, Банши, Костяной Голем, Царь Мёртвых")
    else:
        print(f"[UNDEAD] Статы юнитов нежити обновлены")


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

    # Спавним разнообразную армию нежити + Царя Мёртвых
    # 60% Призраки, 20% Зомби, 10% Банши, 500 Големов + Царь
    ghost_count = int(UNDEAD_INITIAL_ARMY * 0.60)
    zombie_count = int(UNDEAD_INITIAL_ARMY * 0.20)
    banshee_count = int(UNDEAD_INITIAL_ARMY * 0.10)
    golem_count = 500

    _spawn_undead_unit = """
        INSERT INTO garrisons (city_name, unit_name, unit_count, unit_image)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(city_name, unit_name) DO UPDATE SET
            unit_count = unit_count + excluded.unit_count
    """
    cursor.execute(_spawn_undead_unit, (chosen_city_name, UNDEAD_UNIT_NAME, ghost_count, 'files/army/death/solder.png'))
    cursor.execute(_spawn_undead_unit, (chosen_city_name, ZOMBIE_UNIT_NAME, zombie_count, 'files/army/death/zombie.png'))
    cursor.execute(_spawn_undead_unit, (chosen_city_name, BANSHEE_UNIT_NAME, banshee_count, 'files/army/death/banshi.png'))
    cursor.execute(_spawn_undead_unit, (chosen_city_name, GOLEM_UNIT_NAME, golem_count, 'files/army/death/golem.png'))

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
        f"{KING_OF_DEAD_NAME} ведёт 250 000 призраков.\n\n"
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
                "INSERT OR IGNORE INTO relations (faction1, faction2, relationship) VALUES (?, ?, ?)",
                (UNDEAD_FACTION_NAME, faction, 0)
            )
            cursor.execute(
                "INSERT OR IGNORE INTO relations (faction1, faction2, relationship) VALUES (?, ?, ?)",
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

    # Царь возрождается с разнообразной армией
    _spawn_sql = """
        INSERT INTO garrisons (city_name, unit_name, unit_count, unit_image)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(city_name, unit_name) DO UPDATE SET
            unit_count = unit_count + excluded.unit_count
    """
    cursor.execute("""
        INSERT INTO garrisons (city_name, unit_name, unit_count, unit_image)
        VALUES (?, ?, 1, ?)
    """, (respawn_city, KING_OF_DEAD_NAME, 'files/army/death/king_.png'))
    cursor.execute(_spawn_sql, (respawn_city, UNDEAD_UNIT_NAME, 6000, 'files/army/death/solder.png'))
    cursor.execute(_spawn_sql, (respawn_city, ZOMBIE_UNIT_NAME, 3000, 'files/army/death/zombie.png'))
    cursor.execute(_spawn_sql, (respawn_city, BANSHEE_UNIT_NAME, 1500, 'files/army/death/banshi.png'))
    cursor.execute(_spawn_sql, (respawn_city, GOLEM_UNIT_NAME, 100, 'files/army/death/golem.png'))

    print(f"[UNDEAD] {KING_OF_DEAD_NAME} возродился в {respawn_city} с 10 600 юнитов!")


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
    undead_city_count = cursor.fetchone()[0]

    if undead_city_count == 0:
        # Проверяем, остались ли незахваченные города нежити (is_undead=1 но faction != Нежить)
        cursor.execute("SELECT COUNT(*) FROM cities WHERE is_undead = 1")
        total_undead_cities = cursor.fetchone()[0]

        # Считаем сколько is_undead=1 городов уже навсегда захвачены
        cursor.execute("""
            SELECT COUNT(*) FROM cities
            WHERE is_undead = 1 AND faction != ? AND faction != 'Нейтрал'
        """, (UNDEAD_FACTION_NAME,))
        captured_permanently = cursor.fetchone()[0]

        if captured_permanently >= total_undead_cities:
            # ВСЕ 3 города нежити захвачены — нашествие побеждено окончательно!
            cursor.execute(
                "UPDATE undead_invasion SET invasion_started = 0, king_alive = 0 WHERE id = 1"
            )
            conn.commit()
            print("[UNDEAD] Все 3 города нежити захвачены! Нашествие побеждено окончательно!")
            return
        else:
            # Есть нейтральные города нежити — запускаем новую волну!
            cursor.execute(
                "SELECT id, name FROM cities WHERE is_undead = 1 AND faction = 'Нейтрал' LIMIT 1"
            )
            neutral = cursor.fetchone()
            if neutral:
                wave_city_id, wave_city_name = neutral
                wave_army = random.randint(80000, 150000)
                cursor.execute(
                    "UPDATE cities SET faction = ?, color_faction = ? WHERE id = ?",
                    (UNDEAD_FACTION_NAME, '#33BF99', wave_city_id)
                )
                # Разнообразная армия волны
                _wave_sql = """
                    INSERT INTO garrisons (city_name, unit_name, unit_count, unit_image)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(city_name, unit_name) DO UPDATE SET
                        unit_count = unit_count + excluded.unit_count
                """
                cursor.execute(_wave_sql, (wave_city_name, UNDEAD_UNIT_NAME, int(wave_army * 0.55), 'files/army/death/solder.png'))
                cursor.execute(_wave_sql, (wave_city_name, ZOMBIE_UNIT_NAME, int(wave_army * 0.25), 'files/army/death/zombie.png'))
                cursor.execute(_wave_sql, (wave_city_name, BANSHEE_UNIT_NAME, int(wave_army * 0.12), 'files/army/death/banshi.png'))
                cursor.execute(_wave_sql, (wave_city_name, GOLEM_UNIT_NAME, max(50, int(wave_army * 0.005)), 'files/army/death/golem.png'))
                _respawn_king_if_dead(cursor)
                conn.commit()
                print(f"[UNDEAD] Новая волна! {wave_army} юнитов в {wave_city_name}!")
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

    # Подкрепления: сёрдж 10 ходов, потом постоянные 18к/ход (без спада)
    _reinforce_sql = """
        INSERT INTO garrisons (city_name, unit_name, unit_count, unit_image)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(city_name, unit_name) DO UPDATE SET
            unit_count = unit_count + excluded.unit_count
    """

    if turns_since_invasion <= UNDEAD_SURGE_TURNS:
        total = UNDEAD_SURGE_PER_TURN
        label = f"(сёрдж {turns_since_invasion}/{UNDEAD_SURGE_TURNS})"
    else:
        total = UNDEAD_REINFORCEMENTS_CONSTANT
        label = "(постоянные)"

    # Распределяем подкрепления: 55% призраки, 25% зомби, 12% банши, 50 големов
    ghost_r = int(total * 0.55)
    zombie_r = int(total * 0.25)
    banshee_r = int(total * 0.12)
    golem_r = max(30, int(total * 0.005))

    cursor.execute(_reinforce_sql, (king_city, UNDEAD_UNIT_NAME, ghost_r, 'files/army/death/solder.png'))
    cursor.execute(_reinforce_sql, (king_city, ZOMBIE_UNIT_NAME, zombie_r, 'files/army/death/zombie.png'))
    cursor.execute(_reinforce_sql, (king_city, BANSHEE_UNIT_NAME, banshee_r, 'files/army/death/banshi.png'))
    cursor.execute(_reinforce_sql, (king_city, GOLEM_UNIT_NAME, golem_r, 'files/army/death/golem.png'))

    print(f"[UNDEAD] Подкрепление в {king_city}: +{total} юнитов {label}")

    # Чума — города рядом с нежитью теряют население
    _apply_plague(cursor)

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


def _apply_plague(cursor):
    """
    Чума Нежити: города соседние с городами нежити теряют население каждый ход.
    Радиус заражения — 200 единиц координат. Потери: -3% населения.
    """
    import math
    import ast
    try:
        # Получаем координаты городов нежити
        cursor.execute("SELECT name, coordinates FROM cities WHERE faction = ?", (UNDEAD_FACTION_NAME,))
        undead_cities = cursor.fetchall()
        if not undead_cities:
            return

        undead_coords = []
        for _, coords_str in undead_cities:
            try:
                undead_coords.append(ast.literal_eval(coords_str))
            except Exception:
                continue

        if not undead_coords:
            return

        # Получаем все не-нежить города
        cursor.execute(
            "SELECT name, coordinates, faction FROM cities WHERE faction != ? AND faction != 'Нейтрал'",
            (UNDEAD_FACTION_NAME,)
        )
        other_cities = cursor.fetchall()

        plague_radius = 200
        plague_rate = 0.03  # -3% населения

        for city_name, coords_str, city_faction in other_cities:
            try:
                cc = ast.literal_eval(coords_str)
            except Exception:
                continue

            # Проверяем расстояние до ближайшего города нежити
            min_dist = min(math.hypot(cc[0] - uc[0], cc[1] - uc[1]) for uc in undead_coords)
            if min_dist > plague_radius:
                continue

            # Уменьшаем население города
            cursor.execute(
                "SELECT population FROM cities WHERE name = ?", (city_name,)
            )
            pop_row = cursor.fetchone()
            if not pop_row or not pop_row[0]:
                continue

            pop = pop_row[0]
            loss = max(1, int(pop * plague_rate))
            new_pop = max(10, pop - loss)  # Минимум 10

            cursor.execute(
                "UPDATE cities SET population = ? WHERE name = ?",
                (new_pop, city_name)
            )

            # Также уменьшаем гарнизон на 1% (мор среди солдат)
            cursor.execute(
                "UPDATE garrisons SET unit_count = MAX(1, unit_count - MAX(1, unit_count / 100)) "
                "WHERE city_name = ?",
                (city_name,)
            )

        print(f"[UNDEAD PLAGUE] Чума распространяется от {len(undead_cities)} городов нежити")
    except Exception as e:
        print(f"[UNDEAD PLAGUE] Ошибка: {e}")


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
