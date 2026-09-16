# seasons.py

import sqlite3
from db_lerdon_connect import db_path

class SeasonManager:
    """
    Менеджер сезонов.
    """

    # Для удобства: названия сезонов (индексы 0–3)
    SEASON_NAMES = ['Зима', 'Весна', 'Лето', 'Осень']

    # Для каждого сезона (по индексу) храним словарь:
    #   ключ = название фракции,
    #   значение = { 'stat': коэффициент для attack/defense, 'cost': коэффициент для cost_money/cost_time }
    FACTION_EFFECTS = [
        # 0 = Зима
        {
            'Север':  {'stat': 1.25,  'cost': 0.65},   # +25% атак/защита, -35% стоимости
            'Эльфы': {'stat': 0.65,  'cost': 1.25},   # -35% атак/защита, +25% стоимости
            'Вампиры': {'stat': 0.97,  'cost': 1.00},   # -3% атак/защита, нет эффекта стоимости
            'Адепты':   {'stat': 0.90,  'cost': 1.17},   # -10% атак/защита, +17% стоимости
            'Элины':  {'stat': 0.45,  'cost': 1.45},   # -55% атак/защита, +45% стоимости
        },
        # 1 = Весна
        {
            'Север':  {'stat': 0.90,  'cost': 1.17},   # -10% атак/защита, +17% стоимости
            'Эльфы': {'stat': 0.97,  'cost': 1.00},   # -3% атак/защита, нет эффекта стоимости
            'Вампиры': {'stat': 1.25,  'cost': 0.65},   # +25% атак/защита, -35% стоимости
            'Адепты':   {'stat': 0.65,  'cost': 1.25},   # -35% атак/защита, +25% стоимости
            'Элины':  {'stat': 1.1,  'cost': 0.90},   # +10% атак/защита, -10% стоимости
        },
        # 2 = Лето
        {
            'Север':  {'stat': 0.65,  'cost': 1.25},   # -35% атак/защита, +25% стоимости
            'Эльфы': {'stat': 1.25,  'cost': 0.65},   # +25% атак/защита, -35% стоимости
            'Вампиры': {'stat': 0.90,  'cost': 1.17},   # -10% атак/защита, +17% стоимости
            'Адепты':   {'stat': 0.97,  'cost': 1.00},   # -3% атак/защита, нет эффекта стоимости
            'Элины':  {'stat': 1.75,  'cost': 0.60},   # +75% атак/защита, -40% стоимости
        },
        # 3 = Осень
        {
            'Север':  {'stat': 0.97,  'cost': 1.00},   # -3% атак/защита, нет эффекта стоимости
            'Эльфы': {'stat': 0.90,  'cost': 1.17},   # -10% атак/защита, +17% стоимости
            'Вампиры': {'stat': 0.65,  'cost': 1.25},   # -35% атак/защита, +25% стоимости
            'Адепты':   {'stat': 1.25,  'cost': 0.65},   # +25% атак/защита, -35% стоимости
            'Элины':  {'stat': 0.90,  'cost': 1.17},   # -10% атак/защита, +17% стоимости
        },
    ]

    # Сопоставление полей артефактов с полями юнитов
    ARTIFACT_STAT_MAPPING = {
        'attack': 'attack',
        'defense': 'defense',
        'health': 'durability',
    }

    def __init__(self):
        # last_idx = индекс сезона, бафф которого уже наложен.
        # None означает, что до этого ни один сезон не применялся.
        self.last_idx = None
        # Кэш артефактов - словарь {artifact_id: (attack, defense, season_name)}
        self._artifact_cache = {}

    # Смещение ID для артефактов ИИ, чтобы избежать коллизий с артефактами игрока
    AI_ARTIFACT_ID_OFFSET = 1_000_000

    def _load_artifact_cache(self, conn, faction_type="both"):
        """
        Загружает или обновляет кэш артефактов из БД.
        AI артефакты хранятся со смещением ID чтобы не перезаписывать артефакты игрока.
        faction_type: "player", "ai", "both"
        """
        cur = conn.cursor()
        self._artifact_cache = {}

        # Сначала загружаем артефакты игрока (без смещения ID)
        if faction_type in ["player", "both"]:
            try:
                cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='artifacts'")
                if cur.fetchone():
                    cur.execute("SELECT id, attack, defense, season_name FROM artifacts")
                    for row in cur.fetchall():
                        artifact_id, attack, defense, season_name = row
                        self._artifact_cache[artifact_id] = (attack, defense, season_name)
            except sqlite3.Error as e:
                print(f"[ERROR] Ошибка при загрузке артефактов из artifacts: {e}")

        # Затем загружаем артефакты ИИ (со смещением ID)
        if faction_type in ["ai", "both"]:
            try:
                cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='artifacts_ai'")
                if cur.fetchone():
                    cur.execute("SELECT id, attack, defense, season_name FROM artifacts_ai")
                    for row in cur.fetchall():
                        artifact_id, attack, defense, season_name = row
                        cache_key = artifact_id + self.AI_ARTIFACT_ID_OFFSET
                        self._artifact_cache[cache_key] = (attack, defense, season_name)
            except sqlite3.Error as e:
                print(f"[ERROR] Ошибка при загрузке артефактов из artifacts_ai: {e}")

        print(f"[SEASON] Всего артефактов в кэше: {len(self._artifact_cache)}")

    def update(self, new_idx: int, conn):
        """
        Вызывается при смене сезона на new_idx (0–3).
        Обновляет last_idx и пересчитывает все эффекты.
        """
        self.last_idx = new_idx
        # Обновляем кэш артефактов перед пересчётом
        self._load_artifact_cache(conn, "both")
        # Пересчитываем все характеристики
        self._recalculate_all_units(conn, new_idx)

    def _recalculate_all_units(self, conn, season_idx):
        """
        Пересчитывает все характеристики в таблице units на основе:
        1. Базовых значений из units_default.
        2. Бонусов от артефактов (из artifact_effects_log).
        3. Сезонного коэффициента (из FACTION_EFFECTS).
        """
        if season_idx is None:
            print("[SEASON] Season index is None, cannot recalculate units.")
            return

        cur = conn.cursor()

        # Получаем все юниты из units_default
        cur.execute("SELECT unit_name, faction, attack, defense, durability, cost_money, cost_time FROM units_default")
        default_units = {row[0]: {'faction': row[1], 'attack': row[2], 'defense': row[3], 'durability': row[4], 'cost_money': row[5], 'cost_time': row[6]} for row in cur.fetchall()}

        # Получаем накопленные бонусы артефактов из лога
        cur.execute("""
            SELECT hero_name, stat_name, SUM(value_change) as total_change
            FROM artifact_effects_log
            GROUP BY hero_name, stat_name
        """)
        artifact_effects = {}
        for row in cur.fetchall():
            hero_name, stat_name, total_change = row
            if hero_name not in artifact_effects:
                artifact_effects[hero_name] = {}
            artifact_effects[hero_name][stat_name] = total_change

        # Получаем сезонный коэффициент для статов (attack, defense)
        current_season_effects = self.FACTION_EFFECTS[season_idx]

        # Пересчитываем характеристики (batch)
        update_batch = []
        for unit_name, base_data in default_units.items():
            base_atk = base_data['attack']
            base_def = base_data['defense']
            base_hp = base_data['durability']
            base_cost_money = base_data['cost_money']
            base_cost_time = base_data['cost_time']
            faction = base_data['faction']

            # Бонусы от артефактов
            unit_effects = artifact_effects.get(unit_name, {})
            artifact_bonus_atk = unit_effects.get('attack', 0)
            artifact_bonus_def = unit_effects.get('defense', 0)
            artifact_bonus_hp = unit_effects.get('durability', 0)
            artifact_bonus_cost_money = unit_effects.get('cost_money', 0)
            artifact_bonus_cost_time = unit_effects.get('cost_time', 0)

            artifact_coeff_atk = 1.0 + (artifact_bonus_atk / 100.0) if base_atk != 0 else 1.0
            artifact_coeff_def = 1.0 + (artifact_bonus_def / 100.0) if base_def != 0 else 1.0
            artifact_coeff_hp = 1.0 + (artifact_bonus_hp / 100.0) if base_hp != 0 else 1.0

            temp_atk = int(round(base_atk * artifact_coeff_atk)) if base_atk != 0 else base_atk + artifact_bonus_atk
            temp_def = int(round(base_def * artifact_coeff_def)) if base_def != 0 else base_def + artifact_bonus_def
            temp_hp = int(round(base_hp * artifact_coeff_hp)) if base_hp != 0 else base_hp + artifact_bonus_hp

            # Сезонный коэффициент
            faction_season_effects = current_season_effects.get(faction, {'stat': 1.0, 'cost': 1.0})
            season_stat_coeff = faction_season_effects['stat']
            season_cost_coeff = faction_season_effects['cost']

            final_atk = int(round(temp_atk * season_stat_coeff))
            final_def = int(round(temp_def * season_stat_coeff))
            final_hp = int(round(temp_hp * season_stat_coeff))
            final_cost_money = int(round((base_cost_money + artifact_bonus_cost_money) * season_cost_coeff))
            final_cost_time = int(round((base_cost_time + artifact_bonus_cost_time) * season_cost_coeff))

            update_batch.append((final_atk, final_def, final_hp, final_cost_money, final_cost_time, unit_name))

        # Один batch-запрос вместо 50+ отдельных UPDATE
        cur.executemany("""
            UPDATE units
            SET attack = ?, defense = ?, durability = ?, cost_money = ?, cost_time = ?
            WHERE unit_name = ?
        """, update_batch)
        conn.commit()
        print(f"[SEASON] Пересчитаны характеристики в units для сезона {self.SEASON_NAMES[season_idx]}")

    def apply_artifact_bonuses(self, conn):
        """
        Обновляет лог артефактов и пересчитывает характеристики.
        """
        if self.last_idx is None:
            print("[ARTIFACT] Season not set, skipping artifact application.")
            return

        # Обновляем кэш артефактов перед применением бонусов
        self._load_artifact_cache(conn, "both")

        cur = conn.cursor()
        current_season = self.SEASON_NAMES[self.last_idx]

        # 1. Получаем список всех экипированных артефактов из ОБОИХ таблиц
        # Для hero_equipment (игрок) — ID без смещения
        cur.execute("""
            SELECT hero_name, artifact_id FROM hero_equipment
            WHERE artifact_id IS NOT NULL
        """)
        player_equipped_artifacts = [(h, a) for h, a in cur.fetchall()]

        # Для ai_hero_equipment (ИИ) — ID со смещением для уникальности в кэше
        cur.execute("""
            SELECT hero_name, artifact_id FROM ai_hero_equipment
            WHERE artifact_id IS NOT NULL
        """)
        ai_equipped_artifacts = [(h, a + self.AI_ARTIFACT_ID_OFFSET) for h, a in cur.fetchall()]

        # Объединяем списки
        all_equipped_artifacts = player_equipped_artifacts + ai_equipped_artifacts

        # 2. Получаем список уже примененных эффов
        cur.execute("""
            SELECT hero_name, artifact_id FROM artifact_effects_log
            GROUP BY hero_name, artifact_id
        """)
        applied_effects = set(cur.fetchall())  # Множество (hero_name, artifact_id)

        # 3. Определяем, что нужно сделать
        # Артефакты, которые должны быть активны
        should_be_active = set()
        # Артефакты, которые нужно проверить/применить
        to_check_apply = set()

        for hero_name, artifact_id in all_equipped_artifacts:
            should_be_active.add((hero_name, artifact_id))
            if (hero_name, artifact_id) not in applied_effects:
                # Новый артефакт, нужна проверка и возможное применение
                to_check_apply.add((hero_name, artifact_id))

        # Артефакты, которые нужно отменить (были применены, но больше не экипированы или не подходят по сезону)
        to_revert = applied_effects - should_be_active

        # 4. Отменяем ненужные эффекты
        for hero_name, artifact_id in to_revert:
            self._revert_artifact_effect(hero_name, artifact_id, conn)

        # 5. Проверяем и применяем новые/измененные эффекты
        for hero_name, artifact_id in to_check_apply:
            # Получаем данные артефакта из кэша
            if artifact_id not in self._artifact_cache:
                print(f"[WARNING] Артефакт ID {artifact_id} не найден в кэше, пропускаем.")
                continue

            a_atk, a_def, a_season_name = self._artifact_cache[artifact_id]

            # Проверяем сезон
            season_ok = True
            if a_season_name is not None and a_season_name.strip() != "":
                allowed_seasons = [s.strip() for s in a_season_name.split(',')]
                if current_season not in allowed_seasons:
                    season_ok = False

            if season_ok:
                # Применяем бонусы
                bonuses = {
                    'attack': a_atk,
                    'defense': a_def
                }
                self._apply_artifact_effect(hero_name, artifact_id, bonuses, conn)
            else:
                print(f"[INFO] Артефакт {artifact_id} не подходит по сезону '{current_season}', пропускаем.")

        # 6. Проверяем существующие эффекты на соответствие сезону
        # (на случай, если сезон сменился, а артефакт остался тот же)
        # Получаем все примененные эффекты с их артефактами
        ai_offset = self.AI_ARTIFACT_ID_OFFSET
        cur.execute(f"""
            SELECT DISTINCT ael.hero_name, ael.artifact_id, a.season_name
            FROM artifact_effects_log ael
            JOIN (
                SELECT id, season_name FROM artifacts
                UNION ALL
                SELECT id + {ai_offset}, season_name FROM artifacts_ai
            ) a ON ael.artifact_id = a.id
        """)
        active_artifact_details = cur.fetchall()

        for hero_name, artifact_id, a_season_name in active_artifact_details:
            season_ok = True
            if a_season_name is not None and a_season_name.strip() != "":
                allowed_seasons = [s.strip() for s in a_season_name.split(',')]
                if current_season not in allowed_seasons:
                    season_ok = False

            if not season_ok:
                self._revert_artifact_effect(hero_name, artifact_id, conn)
                # Этот артефакт теперь нужно проверить заново, если он все еще экипирован
                if (hero_name, artifact_id) in should_be_active:
                    to_check_apply.add((hero_name, artifact_id))

        # После всех изменений в artifact_effects_log, пересчитываем ВСЕ характеристики
        self._recalculate_all_units(conn, self.last_idx)

    def _calculate_stat_change_from_default(self, unit_name, stat_name, bonus_percent, conn):
        """
        Рассчитывает абсолютное изменение характеристики на основе БАЗОВОГО значения из units_default.
        Это НЕ итоговое изменение, а просто (база * процент / 100).
        """
        cur = conn.cursor()
        # Получаем БАЗОВОЕ значение из units_default
        cur.execute(f"SELECT {stat_name} FROM units_default WHERE unit_name = ?", (unit_name,))
        base_row = cur.fetchone()

        if not base_row or base_row[0] is None:
            print(f"[ARTIFACT] Базовое значение {stat_name} для {unit_name} не найдено в units_default.")
            return 0

        base_value = base_row[0]
        if bonus_percent == 0 or bonus_percent is None:
            return 0

        # change = int(round(base_value * (bonus_percent / 100))) # Это было бы итоговое изменение
        change = base_value * (bonus_percent / 100) # Оставим как float для более точного хранения в логе
        return change

    def _apply_artifact_effect(self, hero_name: str, artifact_id: int, bonuses: dict, conn):
        """
        Рассчитывает и записывает эффект артефакта в artifact_effects_log.
        ВАЖНО: Рассчитывает бонус на основе БАЗОВОГО значения, но записывает в лог.
        Итоговое значение в units пересчитывается отдельно.
        """
        cur = conn.cursor()

        effects_to_apply = []

        # Рассчитываем изменения для каждой характеристики на основе БАЗОВОГО значения
        for artifact_stat, unit_stat in self.ARTIFACT_STAT_MAPPING.items():
            bonus_value = bonuses.get(artifact_stat)
            if bonus_value is None or bonus_value == 0:
                continue

            # Рассчитываем изменение на основе БАЗОВОГО значения (это будет процент в виде числа)
            # Мы храним именно процент (как он есть в артефакте), а не абсолютное изменение
            # Это позволяет корректно пересчитать итог при смене базового значения или сезона.
            # Для пересчёта нам нужен сам процент, а не его результат на базе.
            change = bonus_value # Сохраняем сам процент

            if change != 0:  # Только если есть изменение
                effects_to_apply.append((unit_stat, change))

        if not effects_to_apply:
            print(f"[ARTIFACT] No applicable effects for {hero_name} from artifact {artifact_id}")
            return

        # Записываем эффект в лог (INSERT OR REPLACE заменяет старые значения для этой пары hero_name, artifact_id)
        for stat_name, change in effects_to_apply:
            cur.execute("""
                INSERT OR REPLACE INTO artifact_effects_log 
                (hero_name, artifact_id, stat_name, value_change)
                VALUES (?, ?, ?, ?)
            """, (hero_name, artifact_id, stat_name, change))

        conn.commit()
        print(f"[ARTIFACT] Записан эффект артефакта {artifact_id} для {hero_name}: {effects_to_apply}")

    def _revert_artifact_effect(self, hero_name: str, artifact_id: int, conn):
        """
        Удаляет запись об эффекте артефакта из artifact_effects_log.
        """
        cur = conn.cursor()

        # Удаляем записи об эффектах из лога для этого артефакта
        cur.execute("""
            DELETE FROM artifact_effects_log
            WHERE hero_name = ? AND artifact_id = ?
        """, (hero_name, artifact_id))

        conn.commit()
        print(f"[ARTIFACT] Удалён эффект артефакта {artifact_id} для {hero_name}")

    def reset_absent_third_class_units(self, conn):
        """
        Проверяет каждый юнит 3 класса в таблице units. Если юнит 3 класса отсутствует в garrisons,
        сбрасывает его характеристики к значениям из units_default с пересчетом на эффект текущего сезона.
        """
        try:
            cursor = conn.cursor()

            # Получаем все юниты 3 класса из таблицы units
            cursor.execute("""
                SELECT unit_name, faction 
                FROM units 
                WHERE unit_class = 3
            """)

            third_class_units = cursor.fetchall()

            if not third_class_units:
                print("[INFO] Нет юнитов 3 класса в таблице units.")
                return

            reset_count = 0

            for unit_name, faction in third_class_units:
                # Проверяем, есть ли этот юнит в garrisons
                cursor.execute("""
                    SELECT COUNT(*) 
                    FROM garrisons 
                    WHERE unit_name = ?
                """, (unit_name,))

                count_in_garrisons = cursor.fetchone()[0]

                # Если юнит отсутствует в garrisons, сбрасываем его характеристики
                if count_in_garrisons == 0:
                    print(
                        f"[INFO] Юнит '{unit_name}' (фракция '{faction}') отсутствует в garrisons. Сброс характеристик...")

                    # Сбрасываем характеристики к значениям по умолчанию
                    cursor.execute("""
                        UPDATE units 
                        SET 
                            attack = (SELECT attack FROM units_default WHERE units_default.unit_name = units.unit_name),
                            defense = (SELECT defense FROM units_default WHERE units_default.unit_name = units.unit_name),
                            durability = (SELECT durability FROM units_default WHERE units_default.unit_name = units.unit_name),
                            cost_money = (SELECT cost_money FROM units_default WHERE units_default.unit_name = units.unit_name),
                            cost_time = (SELECT cost_time FROM units_default WHERE units_default.unit_name = units.unit_name)
                        WHERE unit_name = ?
                    """, (unit_name,))

                    # Применяем бонусы текущего сезона и артефактов
                    if self.last_idx is not None:
                        # Пересчитываем характеристики для этого юнита
                        self._recalculate_all_units(conn, self.last_idx)
                        print(
                            f"[SUCCESS] Сезонные и артефактные бонусы применены к юниту '{unit_name}' для сезона {self.SEASON_NAMES[self.last_idx]}.")

                    reset_count += 1
                    print(f"[SUCCESS] Характеристики юнита '{unit_name}' сброшены и пересчитаны.")

            if reset_count > 0:
                conn.commit()
                print(f"[INFO] Сброшены характеристики {reset_count} юнитов 3 класса.")
            else:
                print("[INFO] Все юниты 3 класса присутствуют в garrisons. Сброс не требуется.")

            return reset_count

        except sqlite3.Error as e:
            print(f"[ERROR] Ошибка базы данных при сбросе характеристик юнитов 3 класса: {e}")
            try:
                conn.rollback()
            except:
                pass
            return 0
        except Exception as e:
            print(f"[ERROR] Неожиданная ошибка при сбросе характеристик юнитов 3 класса: {e}")
            import traceback
            traceback.print_exc()
            try:
                conn.rollback()
            except:
                pass
            return 0
