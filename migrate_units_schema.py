# -*- coding: utf-8 -*-
"""
migrate_units_schema.py
=======================
Одноразовая миграция БД для новой боевой системы.

Что делает:
  1. Добавляет в таблицы `units` и `units_default` новые колонки
     (initiative, unit_type, morale, aura_attack, aura_defense, crit_chance)
     если их ещё нет — безопасно через PRAGMA table_info.
  2. Проставляет осмысленные дефолты по unit_class:
        - класс 1 (обычные): инициатива 50, мораль 100, без аур
        - класс 2 (герой):   инициатива 80, мораль 100, ауры +10/+10, крит 10%
        - класс 3 (мифический): инициатива 90, мораль 100, ауры +20/+20, крит 15%
        - класс 4 (легендарный): инициатива 95, мораль 100, ауры +30/+30, крит 20%
  3. Не трогает существующие данные (attack/defense/durability).
  4. Идемпотентна: запуск повторно ничего не сломает.

Использование:
    python migrate_units_schema.py [путь_к_базе]

По умолчанию ищется game_data.db в текущей папке.
"""

import sqlite3
import sys
import os


# ---------- Описание новых колонок ----------
NEW_COLUMNS = [
    # (имя,            SQL-тип,   default)
    ("initiative",     "INTEGER", 50),
    ("unit_type",      "TEXT",    "'infantry'"),
    ("morale",         "INTEGER", 100),
    ("aura_attack",    "INTEGER", 0),
    ("aura_defense",   "INTEGER", 0),
    ("crit_chance",    "INTEGER", 5),
]

# Таблицы, в которые нужно добавить колонки
TARGET_TABLES = ["units", "units_default"]


def get_existing_columns(cursor, table_name):
    """Возвращает множество имён колонок таблицы."""
    cursor.execute(f"PRAGMA table_info({table_name})")
    return {row[1] for row in cursor.fetchall()}


def table_exists(cursor, table_name):
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,)
    )
    return cursor.fetchone() is not None


def add_columns(cursor, table_name):
    """Добавляет недостающие колонки в таблицу."""
    if not table_exists(cursor, table_name):
        print(f"[SKIP] Таблица '{table_name}' не существует.")
        return 0

    existing = get_existing_columns(cursor, table_name)
    added = 0

    for col_name, col_type, col_default in NEW_COLUMNS:
        if col_name in existing:
            print(f"  [=] {table_name}.{col_name} уже существует.")
            continue

        sql = (
            f"ALTER TABLE {table_name} "
            f"ADD COLUMN {col_name} {col_type} DEFAULT {col_default}"
        )
        cursor.execute(sql)
        print(f"  [+] {table_name}.{col_name} добавлена.")
        added += 1

    return added


def apply_class_defaults(cursor, table_name):
    """
    Проставляет осмысленные значения по unit_class для строк,
    у которых дефолты ещё не были изменены.

    Аккуратно: правим только если значения совпадают со стартовым дефолтом
    (initiative=50, aura=0, crit=5). Это позволяет повторно гонять миграцию
    без затирания того, что юзер мог уже отбалансить вручную.
    """
    if not table_exists(cursor, table_name):
        return

    # Класс 1 — обычные юниты (по сути дефолты уже подходят, но обновим явно)
    cursor.execute(f"""
        UPDATE {table_name}
        SET initiative = 50,
            morale = 100,
            aura_attack = 0,
            aura_defense = 0,
            crit_chance = 5
        WHERE CAST(unit_class AS TEXT) IN ('1', '1 класс')
          AND initiative = 50 AND aura_attack = 0 AND crit_chance = 5
    """)

    # Класс 2 — герои
    cursor.execute(f"""
        UPDATE {table_name}
        SET initiative = 80,
            morale = 100,
            aura_attack = 10,
            aura_defense = 10,
            crit_chance = 10
        WHERE CAST(unit_class AS TEXT) IN ('2', '2 класс')
          AND initiative = 50 AND aura_attack = 0 AND crit_chance = 5
    """)

    # Класс 3 — мифические герои
    cursor.execute(f"""
        UPDATE {table_name}
        SET initiative = 90,
            morale = 100,
            aura_attack = 20,
            aura_defense = 20,
            crit_chance = 15
        WHERE CAST(unit_class AS TEXT) IN ('3', '3 класс')
          AND initiative = 50 AND aura_attack = 0 AND crit_chance = 5
    """)

    # Класс 4 — легендарные
    cursor.execute(f"""
        UPDATE {table_name}
        SET initiative = 95,
            morale = 100,
            aura_attack = 30,
            aura_defense = 30,
            crit_chance = 20
        WHERE CAST(unit_class AS TEXT) IN ('4', '4 класс')
          AND initiative = 50 AND aura_attack = 0 AND crit_chance = 5
    """)

    print(f"  [✓] Дефолты по unit_class применены в {table_name}.")


def migrate(db_path):
    if not os.path.exists(db_path):
        print(f"[ERROR] Файл БД не найден: {db_path}")
        return False

    print(f"[INFO] Подключение к {db_path}")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        cursor.execute("BEGIN IMMEDIATE")

        total_added = 0
        for table_name in TARGET_TABLES:
            print(f"\n[STEP] Обработка таблицы '{table_name}'...")
            total_added += add_columns(cursor, table_name)
            apply_class_defaults(cursor, table_name)

        conn.commit()
        print(f"\n[SUCCESS] Миграция завершена. Добавлено колонок: {total_added}.")
        print("Теперь units_default готова к перезаливу в units.")
        return True

    except sqlite3.Error as e:
        conn.rollback()
        print(f"\n[ERROR] Ошибка миграции: {e}")
        return False
    finally:
        conn.close()


if __name__ == "__main__":
    db_path = sys.argv[1] if len(sys.argv) > 1 else "game_data.db"
    success = migrate(db_path)
    sys.exit(0 if success else 1)
