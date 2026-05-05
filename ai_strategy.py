# -*- coding: utf-8 -*-
"""
ai_strategy.py — улучшения ИИ v6 (патч-модуль)
================================================

Что починено в v6 (на основе реального лога):
  • [FIX-1] Нумерация ходов: в ii.py ход начинается с turn=0.
    То есть turn=0 — это 1-й игровой ход. Убрана путаница.
    Теперь:
      turn == 0 → 1-й ход (только стройка)
      turn >= 1 → 2-й и далее (найм + захват + стройка)
  • [FIX-2] Аварийная продажа кристаллов:
    Если у ИИ 0 крон, нет юнитов 1 класса и есть кристаллы — ПРОДАЁМ
    их даже при низкой цене (выживание важнее экономии).
  • [FIX-3] Понижен порог "хорошей" цены для ИИ.
  • [FIX-4] Порядок в make_turn: продажа кристаллов вызывается ПЕРЕД
    ensure_scout, чтобы у ИИ были деньги на разведчика.

УСТАНОВКА:
  В САМОМ КОНЦЕ ii.py:
      from ai_strategy import apply_ai_improvements
      apply_ai_improvements(AIController)
"""

import random
import sqlite3


# ============================================================
# БАЛАНСНЫЕ КОНСТАНТЫ
# ============================================================

# === Стадии игры (turn ВНУТРИ ИИ — начинается с 0!) ===
EARLY_GAME_END = 9
MID_GAME_END = 30

# === Бюджет на здания (% от крон) на ходах 4+ ===
BUDGET_BUILDINGS_EARLY_SAFE = 0.50
BUDGET_BUILDINGS_EARLY_THREATENED = 0.25
BUDGET_BUILDINGS_MID_SAFE = 0.55
BUDGET_BUILDINGS_MID_THREATENED = 0.25
BUDGET_BUILDINGS_LATE = 0.40

# === Расписание ходов (turn в ИИ начинается с 0) ===
# turn = 0 → 1-й игровой ход → ТОЛЬКО стройка
# turn >= 1 → 2-й и далее → найм + захват + стройка
TURN_BUILD_ONLY = 0                  # 1-й игровой ход (turn=0): только стройка
GUARANTEED_BUILDING_LAST_TURN = 2    # ходы 0,1,2 — гарантированная стройка
GUARANTEED_HOSPITALS = 1
GUARANTEED_FACTORIES = 2

# === Гарантированный найм 1 юнита ===
ENSURE_SCOUT_FROM_TURN = 1           # с turn=1 (2-й ход) ИИ нанимает разведчика

# === Атака — коэффициент уверенности ===
ATTACK_CONFIDENCE = 1.5
ATTACK_CONFIDENCE_MIN = 1.2
ATTACK_FORCE_DESPERATE = 0.85

# === Лидер-давление ===
LEADER_PRESSURE_TURN_START = 10
LEADER_PRESSURE_TURN_END = 30
LEADER_DOMINANCE_THRESHOLD = 1.5
LEADER_RELATIONS_PENALTY = 30

# === Захват нейтралов ===
EXPANSION_START_TURN = 1             # с turn=1 (2-й ход) можно захватывать
EXPANSION_END_TURN = 25
MAX_MOVE_DISTANCE = 280               # тот же радиус перемещения, что у игрока
NEUTRAL_SEARCH_RADIUS = MAX_MOVE_DISTANCE
NEUTRAL_ATTACKER_COUNT = 1

# === Объявление войны ===
WAR_RATIO_EARLY = 1.05
WAR_RATIO_MID = 1.20
WAR_RATIO_LATE = 1.40

# === Продажа кристаллов ===
CRYSTAL_PRICE_GOOD = 150             # понижено со 200 — продаём чаще
CRYSTAL_HOARD_LIMIT = 3000           # понижено с 5000
CRYSTAL_EMERGENCY_THRESHOLD = 100    # если кристаллов больше — можно продать в крайнем случае

# === Разнообразие армии ===
DIVERSITY_PER_TYPE_MAX = 0.5

# === ДИАГНОСТИКА ===
DIAG_ENABLED = True
DIAG_LAST_TURN = 5


def _diag(self, msg):
    if DIAG_ENABLED and self.turn <= DIAG_LAST_TURN:
        print(f"[DIAG turn={self.turn} {self.faction}] {msg}")


# ============================================================
# ОЦЕНКА СИТУАЦИИ
# ============================================================

def assess_situation(self):
    try:
        if self.turn <= EARLY_GAME_END:
            stage = 'early'
        elif self.turn <= MID_GAME_END:
            stage = 'mid'
        else:
            stage = 'late'

        try:
            army_strength = self.calculate_army_strength()
        except Exception:
            army_strength = {}

        our_strength = army_strength.get(self.faction, 0)

        try:
            enemies = self.get_factions_at_war()
        except Exception:
            enemies = []

        max_enemy_strength = 0
        for enemy in enemies:
            es = army_strength.get(enemy, 0)
            if es > max_enemy_strength:
                max_enemy_strength = es

        if max_enemy_strength == 0:
            threat_level = 'safe'
        elif max_enemy_strength > our_strength * 1.3:
            threat_level = 'critical'
        elif max_enemy_strength > our_strength * 0.7:
            threat_level = 'threatened'
        else:
            threat_level = 'safe'

        is_leader = False
        if army_strength:
            sorted_strengths = sorted(army_strength.values(), reverse=True)
            if sorted_strengths and sorted_strengths[0] == our_strength and our_strength > 0:
                if len(sorted_strengths) > 1:
                    is_leader = our_strength > sorted_strengths[1] * LEADER_DOMINANCE_THRESHOLD
                else:
                    is_leader = True

        try:
            city_count = self.get_city_count_for_faction()
        except Exception:
            city_count = 1

        return {
            'stage': stage, 'threat_level': threat_level,
            'our_strength': our_strength, 'max_enemy_strength': max_enemy_strength,
            'is_leader': is_leader, 'city_count': city_count,
            'army_strength': army_strength,
        }
    except Exception as e:
        print(f"[AI] assess_situation: {e}")
        return {'stage': 'early', 'threat_level': 'safe', 'our_strength': 0,
                'max_enemy_strength': 0, 'is_leader': False, 'city_count': 1,
                'army_strength': {}}


# ============================================================
# ДАВЛЕНИЕ НА ЛИДЕРА
# ============================================================

def apply_leader_pressure(self, situation):
    if situation['stage'] != 'mid':
        return
    if self.turn < LEADER_PRESSURE_TURN_START or self.turn > LEADER_PRESSURE_TURN_END:
        return

    army_strength = situation['army_strength']
    if not army_strength or len(army_strength) < 2:
        return

    leader_faction = max(army_strength, key=lambda f: army_strength[f])
    leader_strength = army_strength[leader_faction]

    sorted_strengths = sorted(army_strength.values(), reverse=True)
    if len(sorted_strengths) < 2:
        return
    if leader_strength <= sorted_strengths[1] * LEADER_DOMINANCE_THRESHOLD:
        return
    if leader_faction == self.faction:
        return

    try:
        cursor = self.db_connection.cursor()
        cursor.execute("""
            SELECT relationship FROM relations
            WHERE faction1 = ? AND faction2 = ?
        """, (self.faction, leader_faction))
        row = cursor.fetchone()
        if row:
            current = int(row[0])
            new_val = max(0, current - LEADER_RELATIONS_PENALTY)
            if new_val < current:
                cursor.execute("""
                    UPDATE relations SET relationship = ?
                    WHERE faction1 = ? AND faction2 = ?
                """, (new_val, self.faction, leader_faction))
                self.db_connection.commit()
                print(f"[AI] {self.faction} раздражён доминированием {leader_faction}: {current} -> {new_val}")
    except Exception as e:
        print(f"[AI] apply_leader_pressure: {e}")


# ============================================================
# 1. УПРАВЛЕНИЕ СТРОИТЕЛЬСТВОМ
# ============================================================

def manage_buildings_v2(self):
    """
    Гарантированная стройка на ходах 0,1,2 (=1-3 игровых хода).
    Динамический бюджет с хода 3 (=4-й игровой ход).
    """
    try:
        situation = self._situation if hasattr(self, '_situation') else assess_situation(self)
        crowns = self.resources.get('Кроны', 0)

        # === Гарантированная стройка ===
        if self.turn <= GUARANTEED_BUILDING_LAST_TURN:
            min_cost = (GUARANTEED_HOSPITALS + GUARANTEED_FACTORIES) * 10
            if crowns >= min_cost:
                print(f"[AI] {self.faction} (ход {self.turn+1}): гарантированное строительство — "
                      f"{GUARANTEED_HOSPITALS} больница + {GUARANTEED_FACTORIES} фабрики")
                self.build_in_city("Больница", GUARANTEED_HOSPITALS)
                self.build_in_city("Фабрика", GUARANTEED_FACTORIES)
                self.save_all_data()
                return
            else:
                print(f"[AI] {self.faction} (ход {self.turn+1}): не хватает крон на минимум зданий ({crowns} < {min_cost}).")
                return

        # === Динамическая логика ===
        stage = situation['stage']
        threat = situation['threat_level']

        if stage == 'early':
            pct = BUDGET_BUILDINGS_EARLY_THREATENED if threat in ('threatened', 'critical') else BUDGET_BUILDINGS_EARLY_SAFE
        elif stage == 'mid':
            pct = BUDGET_BUILDINGS_MID_THREATENED if threat in ('threatened', 'critical') else BUDGET_BUILDINGS_MID_SAFE
        else:
            pct = BUDGET_BUILDINGS_LATE

        building_budget = int(crowns * pct)
        if building_budget < 20:
            return

        max_hospitals = 12
        max_factories = 12
        max_by_money = building_budget // 10
        total_possible = min(max_hospitals + max_factories, max_by_money)

        hospitals_to_build = int(total_possible * (max_hospitals / (max_hospitals + max_factories)))
        factories_to_build = total_possible - hospitals_to_build

        print(f"[AI] {self.faction} стадия={stage} угроза={threat} бюджет_здания={pct*100:.0f}%")

        if hospitals_to_build > 0:
            self.build_in_city("Больница", hospitals_to_build)
        if factories_to_build > 0:
            self.build_in_city("Фабрика", factories_to_build)

        self.save_all_data()
    except Exception as e:
        print(f"[AI] manage_buildings_v2: {e}")


# ============================================================
# 2. НАЙМ ЮНИТОВ — разнообразный состав
# ============================================================

def hire_units_v2(self, new_garrison, crowns, works, available_consumption):
    try:
        target_city = list(new_garrison.keys())[0]

        class_1_units = {
            name: data for name, data in self.army.items()
            if data["stats"]["Класс"] == "1"
        }

        if not class_1_units:
            return

        unit_names = list(class_1_units.keys())
        num_types = len(unit_names)
        random.shuffle(unit_names)

        crowns_per_type_cap = int(crowns * DIVERSITY_PER_TYPE_MAX) if num_types > 1 else crowns

        for unit_name in unit_names:
            unit_data = class_1_units[unit_name]
            cost_money = unit_data['cost']['money']
            cost_time = unit_data['cost']['time']
            consumption = unit_data['consumption']

            if cost_money <= 0 or cost_time <= 0 or consumption <= 0:
                continue

            budget_for_this = min(crowns, crowns_per_type_cap)

            max_affordable = min(
                budget_for_this // cost_money,
                works // cost_time,
                available_consumption // consumption
            )

            if max_affordable > 0:
                cost_total_money = cost_money * max_affordable
                cost_total_time = cost_time * max_affordable
                cost_total_consumption = consumption * max_affordable

                self.resources['Кроны'] -= cost_total_money
                self.resources['Рабочие'] -= cost_total_time
                crowns -= cost_total_money
                works -= cost_total_time
                available_consumption -= cost_total_consumption

                new_garrison[target_city].append({
                    "unit_name": unit_name,
                    "unit_count": max_affordable
                })
                print(f"[AI] Нанято {max_affordable} '{unit_name}'")

            if crowns <= 0 or works <= 0 or available_consumption <= 0:
                break
    except Exception as e:
        print(f"[AI] hire_units_v2: {e}")


# ============================================================
# 3. АВАРИЙНАЯ ПРОДАЖА КРИСТАЛЛОВ (новинка v6)
# ============================================================

def emergency_sell_crystals(self):
    """
    ВЫЖИВАНИЕ: если у ИИ 0 крон и есть кристаллы — продаём ВСЕГДА,
    игнорируя цену. Лучше получить мало крон, чем 0.

    Вызывается ДО ensure_scout, чтобы у ИИ были деньги на разведчика.
    """
    try:
        crowns = self.resources.get('Кроны', 0)
        crystals = self.resources.get('Кристаллы', 0)

        # Условия аварийной продажи:
        # 1. Крон <= 50 (мало денег)
        # 2. Кристаллов > CRYSTAL_EMERGENCY_THRESHOLD (есть что продать)
        if crowns > 50:
            return False  # денег хватает, аварийная продажа не нужна
        if crystals <= CRYSTAL_EMERGENCY_THRESHOLD:
            return False  # нечего продавать

        price = getattr(self, 'raw_material_price', 0) or 0
        if price <= 0:
            return False

        # Продаём 95% кристаллов независимо от цены
        amount_to_sell = int(crystals * 0.95)
        earned_crowns = int(amount_to_sell * price)
        self.resources['Кристаллы'] -= amount_to_sell
        self.resources['Кроны'] += earned_crowns

        try:
            self.update_economic_efficiency(price / 100)
        except Exception:
            pass

        print(f"[AI] {self.faction}: АВАРИЙНАЯ продажа {amount_to_sell} кристаллов "
              f"за {earned_crowns} крон (цена {price:.0f}).")
        return True
    except Exception as e:
        print(f"[AI] emergency_sell_crystals: {e}")
        return False


# ============================================================
# 4. ГАРАНТИРОВАННЫЙ НАЙМ 1 ДЕШЁВОГО ЮНИТА
# ============================================================

def ensure_scout_unit(self):
    """
    Гарантирует 1 юнит 1 класса для захвата нейтрала.
    Если юнитов нет — нанимает самый дешёвый.
    """
    if self.turn < ENSURE_SCOUT_FROM_TURN:
        _diag(self, "ensure_scout: пропуск (рано, 1-й игровой ход)")
        return False

    try:
        existing_units = self.collect_all_units()
    except Exception as e:
        _diag(self, f"ensure_scout: collect_all_units упал: {e}")
        existing_units = []

    have_class_1 = False
    for u in existing_units:
        try:
            if self.get_unit_class(u["unit_name"]) == 1 and u.get("unit_count", 0) > 0:
                have_class_1 = True
                break
        except Exception:
            pass

    if have_class_1:
        _diag(self, "ensure_scout: юнит 1 класса уже есть")
        return True

    army = getattr(self, 'army', {}) or {}
    class_1_options = [
        (name, data) for name, data in army.items()
        if data.get("stats", {}).get("Класс") == "1"
    ]

    if not class_1_options:
        _diag(self, "ensure_scout: нет юнитов 1 класса в self.army")
        return False

    class_1_options.sort(key=lambda kv: kv[1].get("cost", {}).get("money", float('inf')))
    cheapest_name, cheapest_data = class_1_options[0]

    cost_money = cheapest_data['cost']['money']
    cost_time = cheapest_data['cost']['time']
    consumption = cheapest_data['consumption']

    crowns = self.resources.get('Кроны', 0)
    works = self.resources.get('Рабочие', 0)

    try:
        self.calculate_current_consumption()
        available_consumption = self.army_limit - self.total_consumption
    except Exception as e:
        _diag(self, f"ensure_scout: ошибка расчёта потребления: {e}")
        available_consumption = 999

    if crowns < cost_money:
        _diag(self, f"ensure_scout: не хватает крон ({crowns} < {cost_money})")
        return False
    if works < cost_time:
        _diag(self, f"ensure_scout: не хватает рабочих ({works} < {cost_time})")
        return False
    if available_consumption < consumption:
        _diag(self, f"ensure_scout: не хватает потребления ({available_consumption} < {consumption})")
        return False

    target_city = None
    try:
        if self.buildings:
            target_city = next(iter(self.buildings.keys()))
    except Exception:
        pass

    if not target_city:
        try:
            self.cursor.execute("SELECT name FROM cities WHERE faction = ? LIMIT 1", (self.faction,))
            row = self.cursor.fetchone()
            if row:
                target_city = row[0]
        except Exception:
            pass

    if not target_city:
        _diag(self, "ensure_scout: нет своих городов")
        return False

    try:
        self.cursor.execute("SELECT image_path FROM units WHERE unit_name = ?", (cheapest_name,))
        img_row = self.cursor.fetchone()
        unit_image = img_row[0] if img_row else ''

        self.resources['Кроны'] -= cost_money
        self.resources['Рабочие'] -= cost_time

        self.cursor.execute("""
            INSERT INTO garrisons (city_name, unit_name, unit_count, unit_image)
            VALUES (?, ?, 1, ?)
            ON CONFLICT(city_name, unit_name) DO UPDATE SET
                unit_count = unit_count + 1,
                unit_image = excluded.unit_image
        """, (target_city, cheapest_name, unit_image))
        self.db_connection.commit()

        print(f"[AI] {self.faction}: нанят 1 разведчик '{cheapest_name}' за {cost_money} крон в '{target_city}'")
        return True
    except Exception as e:
        print(f"[AI] ensure_scout_unit: ошибка найма: {e}")
        import traceback
        traceback.print_exc()
        return False


# ============================================================
# 5. ПОИСК САМОЙ СЛАБОЙ ЦЕЛИ
# ============================================================

def find_best_attack_target(self, faction):
    try:
        self.cursor.execute("SELECT name, coordinates FROM cities WHERE faction = ?", (self.faction,))
        our_cities = self.cursor.fetchall()
        self.cursor.execute("SELECT name, coordinates FROM cities WHERE faction = ?", (faction,))
        enemy_cities = self.cursor.fetchall()

        if not our_cities or not enemy_cities:
            return None

        garrisons_strength = {}
        for ec_name, _ in enemy_cities:
            try:
                self.cursor.execute("""
                    SELECT COALESCE(SUM(g.unit_count * (u.attack + u.defense + u.durability)), 0)
                    FROM garrisons g JOIN units u ON g.unit_name = u.unit_name
                    WHERE g.city_name = ?
                """, (ec_name,))
                row = self.cursor.fetchone()
                garrisons_strength[ec_name] = row[0] if row else 0
            except Exception:
                garrisons_strength[ec_name] = 0

        candidates = []
        for our_name, our_coords in our_cities:
            try:
                ox, oy = map(int, our_coords.strip("[]").split(','))
            except Exception:
                continue
            for enemy_name, enemy_coords in enemy_cities:
                try:
                    ex, ey = map(int, enemy_coords.strip("[]").split(','))
                except Exception:
                    continue
                # Проверяем наличие дороги
                if self.has_road_between_cities(our_name, enemy_name):
                    distance = abs(ox - ex) + abs(oy - ey)
                    candidates.append((enemy_name, garrisons_strength.get(enemy_name, 0), distance))

        if not candidates:
            return None

        candidates.sort(key=lambda c: (c[1], c[2]))
        target_name = candidates[0][0]
        print(f"[AI] {self.faction} цель атаки: {target_name} (сила гарнизона={candidates[0][1]}, дистанция={candidates[0][2]})")
        return target_name
    except sqlite3.Error as e:
        print(f"[AI] find_best_attack_target: {e}")
        return None


# ============================================================
# 6. ОЦЕНКА АТАКИ
# ============================================================

def can_attack_target(self, target_city, our_total_strength):
    try:
        self.cursor.execute("""
            SELECT COALESCE(SUM(g.unit_count * (u.attack + u.defense + u.durability)), 0)
            FROM garrisons g JOIN units u ON g.unit_name = u.unit_name
            WHERE g.city_name = ?
        """, (target_city,))
        row = self.cursor.fetchone()
        target_strength = row[0] if row else 0
    except Exception:
        target_strength = 0

    if target_strength <= 0:
        return True, 0.4
    if our_total_strength <= 0:
        return False, 0.0

    ratio = our_total_strength / target_strength

    if ratio >= ATTACK_CONFIDENCE:
        needed_force = min(0.85, max(0.4, (target_strength * ATTACK_CONFIDENCE) / our_total_strength))
        return True, needed_force
    elif ratio >= ATTACK_CONFIDENCE_MIN:
        return True, ATTACK_FORCE_DESPERATE
    else:
        print(f"[AI] {self.faction}: атака на {target_city} отменена "
              f"(наша {our_total_strength:.0f} vs цель {target_strength:.0f}, ratio={ratio:.2f})")
        return False, 0.0


# ============================================================
# 7. АТАКА ВРАЖЕСКОГО ГОРОДА
# ============================================================

def attack_city_v2(self, city_name, faction):
    if getattr(self, '_action_taken_this_turn', False):
        print(f"[AI] {self.faction}: уже совершено действие в этом ходу, пропуск атаки.")
        return

    try:
        from fight import fight
    except ImportError as e:
        print(f"[AI] Не удалось импортировать fight: {e}")
        return

    try:
        allied_city = self._find_closest_own_city_in_range(city_name)
        if not allied_city:
            print(f"[AI] attack_city_v2: нет собственного города в радиусе {MAX_MOVE_DISTANCE} от {city_name}")
            return
    except Exception as e:
        print(f"[AI] attack_city_v2: find_closest_own_city_in_range упал: {e}")
        return

    try:
        all_units = self.collect_all_units()
        if not all_units:
            return

        our_total = 0
        class_1_units = []
        hero_units = []
        for unit in all_units:
            try:
                self.cursor.execute(
                    "SELECT attack, defense, durability FROM units WHERE unit_name = ?",
                    (unit["unit_name"],))
                stats = self.cursor.fetchone()
                if stats:
                    a, d, du = stats
                    our_total += unit["unit_count"] * (a + d + du)
            except Exception:
                pass

            try:
                uc = self.get_unit_class(unit["unit_name"])
            except Exception:
                uc = 1
            if uc == 1:
                class_1_units.append(unit)
            elif uc in (2, 3, 4):
                hero_units.append(unit)

        attack_sources = class_1_units
        if not attack_sources:
            attack_sources = [u for u in all_units if u not in hero_units and u.get("unit_count", 0) > 0]
            if not attack_sources:
                attack_sources = [u for u in all_units if u.get("unit_count", 0) > 0]

        should_attack, force_ratio = can_attack_target(self, city_name, our_total)
        if not should_attack:
            return

        total_available = sum(u["unit_count"] for u in attack_sources)
        units_to_take = max(1, int(total_available * force_ratio))

        attack_army = []
        remaining = units_to_take
        random.shuffle(attack_sources)
        for unit in attack_sources:
            if remaining <= 0:
                break
            take = min(unit["unit_count"], remaining)
            if take > 0:
                attack_army.append({
                    "city_name": unit["city_name"], "unit_name": unit["unit_name"],
                    "unit_count": take, "unit_image": unit["unit_image"]
                })
            remaining -= take

        if not attack_army:
            return

        if hero_units and not self.hero_used_in_turn:
            chosen_hero = random.choice(hero_units)
            attack_army.append({
                "city_name": chosen_hero["city_name"], "unit_name": chosen_hero["unit_name"],
                "unit_count": 1, "unit_image": chosen_hero["unit_image"]
            })
            print(f"[AI] К атаке присоединён герой: {chosen_hero['unit_name']}")
            self.hero_used_in_turn = True

        for unit in attack_army:
            try:
                self.relocate_units(
                    from_city_name=unit["city_name"], to_city_name=allied_city,
                    unit_name=unit["unit_name"], unit_count=unit["unit_count"],
                    unit_image=unit["unit_image"]
                )
            except Exception as e:
                print(f"[AI] relocate_units: {e}")

        self.cursor.execute("SELECT SUM(unit_count) FROM garrisons WHERE city_name = ?", (allied_city,))
        if (self.cursor.fetchone()[0] or 0) == 0:
            return

        attacking_army = []
        for unit in attack_army:
            self.cursor.execute("""
                SELECT attack, defense, durability, unit_class
                FROM units WHERE unit_name = ?
                """, (unit["unit_name"],))
            stats = self.cursor.fetchone()
            if stats:
                a, d, du, uc = stats
                attacking_army.append({
                    "unit_name": unit["unit_name"], "unit_count": unit["unit_count"],
                    "unit_image": unit["unit_image"],
                    "units_stats": {"Урон": a, "Защита": d, "Живучесть": du, "Класс юнита": str(uc)}
                })

        result = fight(
            attacking_city=allied_city, defending_city=city_name,
            defending_army=self.get_defending_army(city_name),
            attacking_army=attacking_army,
            attacking_fraction=self.faction, defending_fraction=faction,
            conn=self.db_connection
        )
        print(f"[AI] Битва: winner={result.get('winner')}, ratio={result.get('efficiency_ratio')}")

        self._action_taken_this_turn = True

        if result.get("winner") == "attacker":
            self.army_efficiency_ratio = result.get("efficiency_ratio", 0)
            for unit in attacking_army:
                if unit["units_stats"]["Защита"] > 50:
                    dc = int(unit["unit_count"] * 0.3)
                    if dc > 0:
                        try:
                            self.relocate_units(allied_city, city_name, unit["unit_name"], dc, unit["unit_image"])
                        except Exception:
                            pass
            try:
                self.cursor.execute("UPDATE cities SET faction = ? WHERE name = ?", (self.faction, city_name))
                self.db_connection.commit()
            except Exception as e:
                print(f"[AI] update city: {e}")
            print(f"[AI] Город {city_name} захвачен.")
    except Exception as e:
        print(f"[AI] attack_city_v2: {e}")
        import traceback
        traceback.print_exc()


# ============================================================
# 8. ОБЫЧНАЯ ПРОДАЖА КРИСТАЛЛОВ
# ============================================================

def sell_resources_v2(self):
    """Обычная продажа: при хорошей цене или переизбытке."""
    try:
        crystals = self.resources.get('Кристаллы', 0)
        if crystals <= 100:
            return False

        price = getattr(self, 'raw_material_price', 0) or 0

        good_price = price >= CRYSTAL_PRICE_GOOD
        too_much = crystals >= CRYSTAL_HOARD_LIMIT

        if not good_price and not too_much:
            print(f"[AI] {self.faction}: цена кристаллов низкая ({price:.1f}), копим.")
            return False

        amount_to_sell = int(crystals * 0.95)
        earned_crowns = int(amount_to_sell * price)
        self.resources['Кристаллы'] -= amount_to_sell
        self.resources['Кроны'] += earned_crowns

        try:
            self.update_economic_efficiency(price / 100)
        except Exception:
            pass

        reason = "хорошая цена" if good_price else "переизбыток"
        print(f"[AI] {self.faction}: продано {amount_to_sell} кристаллов за {earned_crowns} крон ({reason}).")
        return True
    except Exception as e:
        print(f"[AI] sell_resources_v2: {e}")
        return False


# ============================================================
# 9. ЗАХВАТ НЕЙТРАЛА — 1 СОЛДАТОМ
# ============================================================

def early_expansion(self):
    if self.turn < EXPANSION_START_TURN:
        _diag(self, f"early_expansion: пропуск (turn < {EXPANSION_START_TURN})")
        return
    if self.turn > EXPANSION_END_TURN:
        return

    if getattr(self, '_action_taken_this_turn', False):
        _diag(self, "early_expansion: уже было действие")
        return

    try:
        from fight import fight
    except ImportError as e:
        print(f"[AI] early_expansion: import fight: {e}")
        return

    target_city = _find_neutral_in_radius(self, NEUTRAL_SEARCH_RADIUS)
    if not target_city:
        _diag(self, f"early_expansion: нейтралов в радиусе {NEUTRAL_SEARCH_RADIUS} НЕТ")
        return
    _diag(self, f"early_expansion: цель = {target_city}")

    try:
        all_units = self.collect_all_units()
    except Exception as e:
        _diag(self, f"early_expansion: collect_all_units упал: {e}")
        return

    if not all_units:
        _diag(self, "early_expansion: collect_all_units пустой")
        return

    class_1_units = []
    for u in all_units:
        try:
            uc = self.get_unit_class(u["unit_name"])
        except Exception:
            uc = 1
        if uc == 1 and u.get("unit_count", 0) > 0:
            class_1_units.append(u)

    if not class_1_units:
        _diag(self, "early_expansion: нет юнитов 1 класса в гарнизонах")
        return

    cheapest_unit = _find_cheapest_unit(self, class_1_units)
    if not cheapest_unit:
        return

    chosen = cheapest_unit
    _diag(self, f"early_expansion: выбран '{chosen['unit_name']}' из '{chosen['city_name']}'")

    try:
        allied_city = self._find_closest_own_city_in_range(target_city)
    except Exception as e:
        _diag(self, f"early_expansion: _find_closest_own_city_in_range упал: {e}")
        return
    if not allied_city:
        return

    if chosen["city_name"] != allied_city:
        try:
            self.relocate_units(
                from_city_name=chosen["city_name"], to_city_name=allied_city,
                unit_name=chosen["unit_name"], unit_count=NEUTRAL_ATTACKER_COUNT,
                unit_image=chosen["unit_image"]
            )
        except Exception as e:
            print(f"[AI] early_expansion relocate: {e}")
            return

    try:
        self.cursor.execute(
            "SELECT attack, defense, durability, unit_class FROM units WHERE unit_name = ?",
            (chosen["unit_name"],))
        stats = self.cursor.fetchone()
    except Exception as e:
        return

    if not stats:
        return

    a, d, dur, uc = stats
    attacking_army = [{
        "unit_name": chosen["unit_name"], "unit_count": NEUTRAL_ATTACKER_COUNT,
        "unit_image": chosen["unit_image"],
        "units_stats": {"Урон": a, "Защита": d, "Живучесть": dur, "Класс юнита": str(uc)}
    }]

    print(f"[AI] {self.faction} (ход {self.turn+1}): отправляет 1 '{chosen['unit_name']}' на нейтрала {target_city}.")
    try:
        result = fight(
            attacking_city=allied_city, defending_city=target_city,
            defending_army=self.get_defending_army(target_city),
            attacking_army=attacking_army,
            attacking_fraction=self.faction, defending_fraction="Нейтрал",
            conn=self.db_connection
        )
        print(f"[AI] {self.faction} захват {target_city}: winner={result.get('winner')}")
        self._action_taken_this_turn = True

        if result.get("winner") == "attacker":
            self.army_efficiency_ratio = result.get("efficiency_ratio", 0)
            try:
                self.cursor.execute("UPDATE cities SET faction = ? WHERE name = ?", (self.faction, target_city))
                self.cursor.execute("UPDATE buildings SET faction = ? WHERE city_name = ?", (self.faction, target_city))
                self.db_connection.commit()
                print(f"[AI] {self.faction} захватил нейтральный город {target_city}!")
            except Exception as e:
                print(f"[AI] update owner: {e}")
    except Exception as e:
        print(f"[AI] early_expansion fight: {e}")
        import traceback
        traceback.print_exc()


def _find_cheapest_unit(self, class_1_units):
    if not class_1_units:
        return None
    army = getattr(self, 'army', None)
    if not army:
        return class_1_units[0]
    best = None
    best_cost = float('inf')
    for u in class_1_units:
        name = u["unit_name"]
        if name in army:
            try:
                cost = army[name]['cost']['money']
            except (KeyError, TypeError):
                continue
            if cost < best_cost:
                best_cost = cost
                best = u
    return best if best else class_1_units[0]


def _find_neutral_in_radius(self, radius):
    try:
        self.cursor.execute("SELECT name, coordinates FROM cities WHERE faction = ?", (self.faction,))
        our_cities = self.cursor.fetchall()
        self.cursor.execute("SELECT name, coordinates FROM cities WHERE faction = 'Нейтрал'")
        neutral_cities = self.cursor.fetchall()
        if not our_cities or not neutral_cities:
            return None

        best = None
        best_dist = radius + 1
        for our_name, our_coords in our_cities:
            try:
                ox, oy = map(int, our_coords.strip("[]").split(','))
            except Exception:
                continue
            for n_name, n_coords in neutral_cities:
                try:
                    nx, ny = map(int, n_coords.strip("[]").split(','))
                except Exception:
                    continue
                dist = abs(ox - nx) + abs(oy - ny)
                if dist < best_dist:
                    best_dist = dist
                    best = n_name
        return best
    except sqlite3.Error as e:
        print(f"[AI] _find_neutral_in_radius: {e}")
        return None


def _find_closest_own_city_in_range(self, target_city_name, max_distance=MAX_MOVE_DISTANCE):
    try:
        self.cursor.execute("SELECT coordinates FROM cities WHERE name = ?", (target_city_name,))
        row = self.cursor.fetchone()
        if not row:
            return None

        try:
            tx, ty = map(int, row[0].strip("[]").split(','))
        except Exception:
            return None

        self.cursor.execute("SELECT name, coordinates FROM cities WHERE faction = ?", (self.faction,))
        our_cities = self.cursor.fetchall()
        best_city = None
        best_dist = max_distance + 1

        for name, coords in our_cities:
            try:
                ox, oy = map(int, coords.strip("[]").split(','))
            except Exception:
                continue
            dist = abs(ox - tx) + abs(oy - ty)
            if dist < max_distance and dist < best_dist:
                best_dist = dist
                best_city = name

        return best_city
    except sqlite3.Error as e:
        print(f"[AI] _find_closest_own_city_in_range: {e}")
        return None


# ============================================================
# 10. УЛУЧШЕННЫЙ make_turn — расписание v6
# ============================================================

def make_turn_v2(self):
    """
    РАСПИСАНИЕ v6 (turn в ИИ начинается с 0!):
      turn=0 (1-й ход):
        - только постройка зданий (1 больница + 2 фабрики)
      turn=1+ (2-й и далее):
        1. emergency_sell_crystals — если 0 крон, продаём кристаллы
        2. ensure_scout_unit — нанимаем 1 разведчика если нет юнитов 1 класса
        3. early_expansion — захват нейтрала 1 юнитом
        4. hire_army — обычный найм
        5. check_and_declare_war — войны и атаки
        6. manage_buildings — стройка на остатки (с ходов 0,1,2 — гарантированно)
        7. sell_resources — обычная продажа кристаллов
        8. артефакты, дипломатия
    """
    print(f'---------ХОДИТ ФРАКЦИЯ: {self.faction}-------------------')
    try:
        self.hero_used_in_turn = False
        self._action_taken_this_turn = False

        if self.faction == "Мятежники":
            print("Фракция 'Мятежники' выполняет только военные действия.")
            self.attack_enemy_cities()
        else:
            self.update_resources()
            self.process_queries()

            self._situation = assess_situation(self)
            print(f"[AI] {self.faction}: turn={self.turn} stage={self._situation['stage']} "
                  f"threat={self._situation['threat_level']} "
                  f"strength={self._situation['our_strength']:.0f}")

            apply_leader_pressure(self, self._situation)

            self.apply_political_system_bonus()
            self.update_relations_based_on_political_system()
            self.update_buildings_from_db()

            # ===== РАСПИСАНИЕ =====
            if self.turn == TURN_BUILD_ONLY:
                # turn=0 = 1-й игровой ход: ТОЛЬКО стройка
                _diag(self, "1-й ход: только постройка, без атак и найма армии")
                self.manage_buildings()

            else:
                # turn>=1 = 2-й и далее ход

                # Шаг 0: АВАРИЙНАЯ продажа кристаллов (если 0 крон)
                _diag(self, "шаг 0: emergency_sell_crystals")
                emergency_sell_crystals(self)

                # Шаг 1: гарантированный найм 1 разведчика
                _diag(self, "шаг 1: ensure_scout_unit")
                ensure_scout_unit(self)

                # Шаг 2: захват нейтрала
                _diag(self, "шаг 2: early_expansion")
                try:
                    early_expansion(self)
                except Exception as e:
                    print(f"[AI] early_expansion: {e}")

                # Шаг 3: обычный найм
                _diag(self, "шаг 3: hire_army")
                if self.resources.get('Кроны', 0) > 0:
                    self.hire_army()

                # Шаг 4: войны и атаки
                _diag(self, "шаг 4: check_and_declare_war")
                self.check_and_declare_war()

                # Шаг 5: стройка
                _diag(self, "шаг 5: manage_buildings")
                self.manage_buildings()

                # Шаг 6: обычная продажа
                self.sell_resources()

                # Шаг 7: артефакты + дипломатия
                self.generate_and_buy_artifacts_for_ai_hero()
                self.send_help_request_if_needed()
                self.send_mercy_request_if_needed()

        self.save_all_data()
        self.turn += 1
        print(f'-----------КОНЕЦ {self.turn} ХОДА----------------  ФРАКЦИИ', self.faction)
    except Exception as e:
        print(f"Ошибка при выполнении хода: {e}")
        import traceback
        traceback.print_exc()


# ============================================================
# ПРИМЕНЕНИЕ ПАТЧЕЙ
# ============================================================

def apply_ai_improvements(AIControllerCls):
    def _save_orig(name):
        backup = '_orig_' + name
        if not hasattr(AIControllerCls, backup) and hasattr(AIControllerCls, name):
            setattr(AIControllerCls, backup, getattr(AIControllerCls, name))

    for n in ('manage_buildings', 'hire_units', 'find_nearest_city',
              'attack_city', 'sell_resources', 'make_turn'):
        _save_orig(n)

    AIControllerCls.manage_buildings = manage_buildings_v2
    AIControllerCls.hire_units = hire_units_v2
    AIControllerCls.find_nearest_city = find_best_attack_target
    AIControllerCls.attack_city = attack_city_v2
    AIControllerCls.sell_resources = sell_resources_v2
    AIControllerCls.make_turn = make_turn_v2

    AIControllerCls.assess_situation = assess_situation
    AIControllerCls.apply_leader_pressure = apply_leader_pressure
    AIControllerCls.find_best_attack_target = find_best_attack_target
    AIControllerCls.can_attack_target = can_attack_target
    AIControllerCls.early_expansion = early_expansion
    AIControllerCls.ensure_scout_unit = ensure_scout_unit
    AIControllerCls.emergency_sell_crystals = emergency_sell_crystals
    AIControllerCls._find_closest_own_city_in_range = _find_closest_own_city_in_range

    print("[AI] Стратегические улучшения ИИ применены (ai_strategy v6).")


def revert_ai_improvements(AIControllerCls):
    for n in ('manage_buildings', 'hire_units', 'find_nearest_city',
              'attack_city', 'sell_resources', 'make_turn'):
        backup = '_orig_' + n
        if hasattr(AIControllerCls, backup):
            setattr(AIControllerCls, n, getattr(AIControllerCls, backup))
    print("[AI] Откат к стандартному поведению ИИ.")
