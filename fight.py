# -*- coding: utf-8 -*-
"""
fight.py — боевая система v2 (всё в одном файле)
=================================================

Новая математика боя:
  • Симметричные пропорциональные потери с обеих сторон.
  • Рандом ±10% и крит 5-20%.
  • Длинные эпичные бои (~3-5% потерь за стычку у равных армий).
  • Герои бьются как обычные юниты + дают процентные ауры союзникам.
  • Тип-преимущество (cavalry > archer > infantry > cavalry и т.д.).
  • Инициатива решает порядок ударов; контрудар защитника слабее.

Совместимость:
  • Сигнатура fight(...) та же, что и раньше.
  • winner возвращается как 'attacker'/'defender' (это ждёт ii.py),
    + добавлен efficiency_ratio.
  • Все функции работы с БД и UI сохранены без изменений.
  • Если миграция units не пройдена — работает на дефолтах по unit_class.

Перед использованием рекомендуется выполнить migrate_units_schema.py,
который добавит колонки initiative, unit_type, aura_attack, aura_defense,
crit_chance в units и units_default.
"""

import random
import sqlite3
from db_lerdon_connect import *
import copy


# ======================================================================
#                       БАЛАНСНЫЕ КОНСТАНТЫ
# ======================================================================

BASE_LETHALITY = 18.0          # летальность: чем меньше, тем кровавее бой
COUNTER_ATTACK_RATIO = 0.65    # контрудар защитника слабее
RANDOM_MIN = 0.90              # рандом ±10%
RANDOM_MAX = 1.10
AURA_CAP_PERCENT = 100         # максимум суммарной ауры героев на армию
DEFAULT_CRIT_CHANCE = 5
CRIT_MULTIPLIER = 1.5
MAX_ROUNDS = 100               # антизацикливание

# Тип-модификаторы (камень-ножницы-бумага).
TYPE_MOD = {
    "infantry": {"cavalry": 1.25, "archer": 0.9,  "infantry": 1.0, "mage": 1.1, "beast": 0.9,  "siege": 1.4},
    "cavalry":  {"archer": 1.30,  "mage": 1.20,   "infantry": 0.8, "cavalry": 1.0, "beast": 1.0, "siege": 1.2},
    "archer":   {"infantry": 1.20, "siege": 1.30, "cavalry": 0.7,  "archer": 1.0, "mage": 1.1,  "beast": 1.0},
    "mage":     {"infantry": 1.30, "beast": 1.30, "mage": 0.7,     "cavalry": 0.9, "archer": 0.9, "siege": 1.1},
    "beast":    {"archer": 1.20,   "mage": 0.9,   "infantry": 1.1, "cavalry": 1.0, "beast": 1.0, "siege": 1.0},
    "siege":    {"infantry": 0.5,  "cavalry": 0.6, "archer": 0.7,  "mage": 0.8,   "beast": 0.7, "siege": 1.0},
}


# ======================================================================
#                  ВСПОМОГАТЕЛЬНЫЕ
# ======================================================================

def _get_stat(unit, key, default=0):
    """Безопасно достаёт целочисленный стат из units_stats."""
    stats = unit.get('units_stats', {}) or {}
    val = stats.get(key, default)
    if val is None:
        return default
    try:
        s = str(val).strip()
        if s in ('', 'None'):
            return default
        return int(float(s))
    except (ValueError, TypeError):
        return default


def get_unit_class(unit):
    """Класс юнита (1-4). Толерантна к форматам '1', '1 класс', 1, ' 2 КЛАСС '."""
    stats = unit.get('units_stats', {}) or {}
    raw = stats.get('Класс юнита', 1)
    if isinstance(raw, int):
        return raw
    try:
        return int(str(raw).strip().split()[0])
    except (ValueError, IndexError, AttributeError):
        return 1


def get_unit_type(unit):
    stats = unit.get('units_stats', {}) or {}
    t = stats.get('Тип', 'infantry') or 'infantry'
    t = str(t).strip().lower()
    return t if t in TYPE_MOD else 'infantry'


def get_initiative(unit):
    return _get_stat(unit, 'Инициатива', _default_initiative(get_unit_class(unit)))


def get_crit_chance(unit):
    return _get_stat(unit, 'Крит', _default_crit(get_unit_class(unit)))


def _default_initiative(unit_class):
    return {1: 50, 2: 80, 3: 90, 4: 95}.get(unit_class, 50)


def _default_aura(unit_class):
    return {1: 0, 2: 10, 3: 20, 4: 30}.get(unit_class, 0)


def _default_crit(unit_class):
    return {1: 5, 2: 10, 3: 15, 4: 20}.get(unit_class, 5)


def merge_units(army):
    """
    Объединяет юниты с одинаковым unit_name И одинаковыми статами.
    Стеки с разной экипировкой (т.е. разными статами) не сливаются —
    иначе теряется бонус от экипировки.
    """
    merged = []
    for unit in army:
        name = unit['unit_name']
        stats = unit.get('units_stats', {}) or {}
        sig = (
            name,
            stats.get('Урон', 0),
            stats.get('Защита', 0),
            stats.get('Живучесть', 0),
            str(stats.get('Класс юнита', '1')),
        )
        found = None
        for m in merged:
            if m['_sig'] == sig:
                found = m
                break
        if found:
            found['unit_count'] += unit['unit_count']
        else:
            merged.append({
                '_sig': sig,
                'unit_name': name,
                'unit_count': unit['unit_count'],
                'unit_image': unit.get('unit_image', ''),
                'units_stats': dict(stats),
            })
    for m in merged:
        m.pop('_sig', None)
    return merged


# ======================================================================
#               ОБОГАЩЕНИЕ ИЗ БД (инициатива, тип, ауры, крит)
# ======================================================================

def _enrich_with_db_stats(units, conn):
    """
    Дополняет units_stats полями 'Инициатива', 'Тип', 'Аура атаки',
    'Аура защиты', 'Крит'. Читает из таблицы units. БД не пишет.
    Если миграция не пройдена — использует дефолты по unit_class.
    """
    if not units:
        return
    try:
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(units)")
        cols = {row[1] for row in cur.fetchall()}
        has_new = {'initiative', 'unit_type', 'aura_attack', 'aura_defense', 'crit_chance'} <= cols

        if has_new:
            names = list({u['unit_name'] for u in units})
            placeholders = ','.join('?' * len(names))
            cur.execute(
                f"SELECT unit_name, initiative, unit_type, aura_attack, aura_defense, crit_chance "
                f"FROM units WHERE unit_name IN ({placeholders})",
                names
            )
            info = {row[0]: row for row in cur.fetchall()}
        else:
            info = {}

        for u in units:
            rec = info.get(u['unit_name']) if info else None
            u_class = get_unit_class(u)
            stats = u.setdefault('units_stats', {})
            if rec:
                _, ini, utype, aatk, adef, crit = rec
                stats.setdefault('Инициатива', ini if ini is not None else _default_initiative(u_class))
                stats.setdefault('Тип', (utype or 'infantry'))
                stats.setdefault('Аура атаки', aatk if aatk is not None else _default_aura(u_class))
                stats.setdefault('Аура защиты', adef if adef is not None else _default_aura(u_class))
                stats.setdefault('Крит', crit if crit is not None else _default_crit(u_class))
            else:
                stats.setdefault('Инициатива', _default_initiative(u_class))
                stats.setdefault('Тип', 'infantry')
                stats.setdefault('Аура атаки', _default_aura(u_class))
                stats.setdefault('Аура защиты', _default_aura(u_class))
                stats.setdefault('Крит', _default_crit(u_class))
    except Exception as e:
        print(f"[WARN] _enrich_with_db_stats: {e}. Использую дефолты по классу.")
        for u in units:
            u_class = get_unit_class(u)
            stats = u.setdefault('units_stats', {})
            stats.setdefault('Инициатива', _default_initiative(u_class))
            stats.setdefault('Тип', 'infantry')
            stats.setdefault('Аура атаки', _default_aura(u_class))
            stats.setdefault('Аура защиты', _default_aura(u_class))
            stats.setdefault('Крит', _default_crit(u_class))


def calculate_army_auras(army):
    """Суммарные ауры от живых героев (классы ≥2). Каждая ≤ AURA_CAP_PERCENT."""
    total_atk = 0
    total_def = 0
    for u in army:
        if u['unit_count'] <= 0:
            continue
        if get_unit_class(u) >= 2:
            total_atk += _get_stat(u, 'Аура атаки', 0)
            total_def += _get_stat(u, 'Аура защиты', 0)
    return min(total_atk, AURA_CAP_PERCENT), min(total_def, AURA_CAP_PERCENT)


# ======================================================================
#                СИЛА ЮНИТА (симметричная)
# ======================================================================

def calculate_unit_power(unit, is_attacking):
    """
    Симметричный расчёт.
      Атака:  attack
      Защита: defense + durability/2 (durability учитывается всегда)
    """
    attack = _get_stat(unit, 'Урон', 0)
    defense = _get_stat(unit, 'Защита', 0)
    durability = _get_stat(unit, 'Живучесть', 0)
    if is_attacking:
        return max(attack, 0)
    else:
        return max(defense + durability / 2.0, 1)


def calculate_army_power(army):
    """Суммарная атакующая мощь — для отчётов и ИИ."""
    return sum(_get_stat(u, 'Урон', 0) * u['unit_count'] for u in army)


def is_unit_combat_ready(unit, army=None):
    """Юнит готов к участию в текущем раунде боя."""
    if unit['unit_count'] <= 0:
        return False
    if not unit.get('hero_candidate', False):
        return True
    if unit.get('hero_engaged', False):
        return True
    if army is not None:
        non_hero_units = [u for u in army if not u.get('hero_candidate', False) and u['unit_count'] > 0]
        return len(non_hero_units) == 0
    return False


# ======================================================================
#                  ОДНА СТЫЧКА (battle_chain)
# ======================================================================

def battle_chain(attacker, defender, city, user_faction, conn,
                 atk_aura_atk=0, atk_aura_def=0,
                 def_aura_atk=0, def_aura_def=0):
    """Одна стычка: симметричные пропорциональные потери."""
    if attacker['unit_count'] <= 0 or defender['unit_count'] <= 0:
        return attacker, defender

    atk_attack = calculate_unit_power(attacker, is_attacking=True)
    atk_defense = calculate_unit_power(attacker, is_attacking=False)
    def_attack = calculate_unit_power(defender, is_attacking=True)
    def_defense = calculate_unit_power(defender, is_attacking=False)

    # Ауры
    atk_attack *= (1 + atk_aura_atk / 100.0)
    atk_defense *= (1 + atk_aura_def / 100.0)
    def_attack *= (1 + def_aura_atk / 100.0)
    def_defense *= (1 + def_aura_def / 100.0)

    # Тип-преимущество
    atk_type = get_unit_type(attacker)
    def_type = get_unit_type(defender)
    atk_attack *= TYPE_MOD.get(atk_type, {}).get(def_type, 1.0)
    def_attack *= TYPE_MOD.get(def_type, {}).get(atk_type, 1.0)

    # Контрудар слабее
    def_attack *= COUNTER_ATTACK_RATIO

    # Рандом + крит
    atk_roll = random.uniform(RANDOM_MIN, RANDOM_MAX)
    def_roll = random.uniform(RANDOM_MIN, RANDOM_MAX)
    if random.random() * 100 < get_crit_chance(attacker):
        atk_roll *= CRIT_MULTIPLIER
    if random.random() * 100 < get_crit_chance(defender):
        def_roll *= CRIT_MULTIPLIER
    atk_attack *= atk_roll
    def_attack *= def_roll

    incoming_to_def = atk_attack * attacker['unit_count']
    incoming_to_atk = def_attack * defender['unit_count']

    # Урон по инфраструктуре (как в старой системе — каждая стычка)
    try:
        damage_to_infrastructure(incoming_to_def, city, user_faction, conn)
    except Exception as e:
        print(f"[WARN] damage_to_infrastructure: {e}")

    # Симметричные потери
    def_losses = int(incoming_to_def / (def_defense * BASE_LETHALITY)) if def_defense > 0 else defender['unit_count']
    atk_losses = int(incoming_to_atk / (atk_defense * BASE_LETHALITY)) if atk_defense > 0 else attacker['unit_count']

    # Минимум 1 потеря если был хоть какой-то урон
    if incoming_to_def > 0 and def_losses < 1:
        def_losses = 1
    if incoming_to_atk > 0 and atk_losses < 1:
        atk_losses = 1

    # Капы
    def_losses = min(def_losses, defender['unit_count'])
    atk_losses = min(atk_losses, attacker['unit_count'])

    # Защита одиночных героев от мгновенной смерти
    if attacker['unit_count'] == 1 and atk_losses >= 1 and get_unit_class(attacker) >= 2:
        hero_hp = _get_stat(attacker, 'Живучесть', 1) + atk_defense
        survive_chance = max(0.0, min(0.85, (hero_hp - incoming_to_atk) / max(hero_hp, 1.0)))
        if random.random() < survive_chance:
            atk_losses = 0
    if defender['unit_count'] == 1 and def_losses >= 1 and get_unit_class(defender) >= 2:
        hero_hp = _get_stat(defender, 'Живучесть', 1) + def_defense
        survive_chance = max(0.0, min(0.85, (hero_hp - incoming_to_def) / max(hero_hp, 1.0)))
        if random.random() < survive_chance:
            def_losses = 0

    attacker['unit_count'] -= atk_losses
    defender['unit_count'] -= def_losses

    return attacker, defender


# ======================================================================
#                       ОСНОВНОЙ ЦИКЛ БОЯ
# ======================================================================

def fight(attacking_city, defending_city, defending_army, attacking_army,
          attacking_fraction, defending_fraction, conn):
    """
    Сигнатура совместима со старой версией.
    Возвращает: winner='attacker'|'defender', efficiency_ratio, rounds,
                attacking_losses, defending_losses, attacking_units, defending_units.
    """
    print('Армия attacking_army:', attacking_army)
    print('Армия defending_army:', defending_army)

    if not attacking_army:
        return _empty_result("defender", attacking_fraction, defending_fraction)
    if not defending_army:
        return _empty_result("attacker", attacking_fraction, defending_fraction)

    # Фракция игрока
    cursor = conn.cursor()
    user_faction = None
    try:
        cursor.execute("SELECT faction_name FROM user_faction")
        row = cursor.fetchone()
        user_faction = row[0] if row else None
    except Exception as e:
        print(f"[ERROR] Не удалось получить фракцию игрока: {e}")
    is_user_involved = user_faction in (attacking_fraction, defending_fraction)
    try:
        cursor.close()
    except Exception:
        pass

    # Слияние одинаковых стеков
    atk_army = merge_units(attacking_army)
    def_army = merge_units(defending_army)

    # Обогащение из БД
    _enrich_with_db_stats(atk_army, conn)
    _enrich_with_db_stats(def_army, conn)

    # Стартовые значения и выделение героев вне боя
    heroes = {'atk': None, 'def': None}
    new_atk_army = []
    new_def_army = []

    for u in atk_army:
        if get_unit_class(u) >= 3 and u['unit_count'] == 1:
            heroes['atk'] = u
            u['initial_count'] = 1
            u['killed_count'] = 0
            u['hero_engaged'] = False
            u['hero_candidate'] = True
            new_atk_army.append(u)
        else:
            u['initial_count'] = u['unit_count']
            u['killed_count'] = 0
            u['hero_engaged'] = False
            u['hero_candidate'] = False
            new_atk_army.append(u)

    for u in def_army:
        if get_unit_class(u) >= 3 and u['unit_count'] == 1:
            heroes['def'] = u
            u['initial_count'] = 1
            u['killed_count'] = 0
            u['hero_engaged'] = False
            u['hero_candidate'] = True
            new_def_army.append(u)
        else:
            u['initial_count'] = u['unit_count']
            u['killed_count'] = 0
            u['hero_engaged'] = False
            u['hero_candidate'] = False
            new_def_army.append(u)

    atk_army = new_atk_army
    def_army = new_def_army

    # Данные для анимации
    battle_rounds = []

    # Боевой цикл
    round_num = 0
    while round_num < MAX_ROUNDS:
        round_num += 1

        atk_alive = [u for u in atk_army if is_unit_combat_ready(u, atk_army)]
        def_alive = [u for u in def_army if is_unit_combat_ready(u, def_army)]
        if not atk_alive or not def_alive:
            break

        atk_aura_atk, atk_aura_def = calculate_army_auras(atk_army)
        def_aura_atk, def_aura_def = calculate_army_auras(def_army)

        all_combatants = [(get_initiative(u), 'A', u) for u in atk_alive] + \
                         [(get_initiative(u), 'D', u) for u in def_alive]
        all_combatants.sort(key=lambda t: -t[0])

        for _, side, unit in all_combatants:
            if unit['unit_count'] <= 0:
                continue
            if side == 'A':
                targets = [u for u in def_army if is_unit_combat_ready(u, def_army)]
            else:
                targets = [u for u in atk_army if is_unit_combat_ready(u, atk_army)]
            if not targets:
                break

            target = max(targets, key=lambda u: _get_stat(u, 'Урон', 0))

            if side == 'A':
                battle_chain(unit, target, defending_city, user_faction, conn,
                             atk_aura_atk=atk_aura_atk, atk_aura_def=atk_aura_def,
                             def_aura_atk=def_aura_atk, def_aura_def=def_aura_def)
            else:
                battle_chain(unit, target, defending_city, user_faction, conn,
                             atk_aura_atk=def_aura_atk, atk_aura_def=def_aura_def,
                             def_aura_atk=atk_aura_atk, def_aura_def=atk_aura_def)

        # Проверка на вступление героев при потерях > 85%
        for side in ['atk', 'def']:
            if heroes[side] is None:
                continue
            hero = heroes[side]
            army = atk_army if side == 'atk' else def_army
            active_units = [u for u in army if not u.get('hero_candidate', False)]

            total_initial = sum(u['initial_count'] for u in active_units)
            total_current = sum(u['unit_count'] for u in active_units)

            if not hero.get('hero_engaged', False):
                losses_percent = 100.0 if total_initial == 0 else ((total_initial - total_current) / total_initial) * 100
                if total_initial == 0 or losses_percent >= 85:
                    hero['hero_engaged'] = True
                    hero['unit_count'] = 1
                    stats = hero.get('units_stats', {})
                    if 'Урон' in stats:
                        stats['Урон'] = int(float(stats['Урон']) * 1.5)
                    if 'Защита' in stats:
                        stats['Защита'] = int(float(stats['Защита']) * 1.5)
                    print(f"[BattleHero] Герой '{hero['unit_name']}' вступил в бой! Урон и Защита +50%")

        # Сохраняем состояние после раунда
        atk_total = sum(u['unit_count'] for u in atk_army)
        def_total = sum(u['unit_count'] for u in def_army)
        atk_max = sum(u['initial_count'] for u in atk_army)
        def_max = sum(u['initial_count'] for u in def_army)
        battle_rounds.append({
            'round': round_num,
            'atk_total': atk_total,
            'def_total': def_total,
            'atk_max': atk_max,
            'def_max': def_max
        })

    # Подсчёт потерь
    for u in atk_army + def_army:
        if u.get('hero_engaged', False) or u['unit_count'] > 0 or u['initial_count'] > 0:
            u['killed_count'] = u['initial_count'] - u['unit_count']
        else:
            u['killed_count'] = 0

    atk_remaining = sum(u['unit_count'] for u in atk_army)
    def_remaining = sum(u['unit_count'] for u in def_army)

    if atk_remaining > 0 and def_remaining == 0:
        winner = 'attacker'
    elif def_remaining > 0 and atk_remaining == 0:
        winner = 'defender'
    elif atk_remaining > def_remaining:
        winner = 'attacker'
    elif def_remaining > atk_remaining:
        winner = 'defender'
    else:
        winner = 'defender'  # полный размен — побеждает защитник

    legacy_winner = 'attacking' if winner == 'attacker' else 'defending'

    # Гарнизоны
    try:
        update_garrisons_after_battle(
            winner=legacy_winner,
            attacking_city=attacking_city,
            defending_city=defending_city,
            attacking_army=atk_army,
            defending_army=def_army,
            attacking_fraction=attacking_fraction,
            defending_fraction=defending_fraction,
            conn=conn
        )
    except Exception as e:
        print(f"[ERROR] update_garrisons_after_battle: {e}")

    visible_atk_army = [u for u in atk_army if u.get('initial_count', 0) > 0]
    visible_def_army = [u for u in def_army if u.get('initial_count', 0) > 0]

    # results
    total_attacking_losses = sum(u['killed_count'] for u in visible_atk_army)
    total_defending_losses = sum(u['killed_count'] for u in visible_def_army)
    try:
        update_results_table(db_connection=conn, faction=attacking_fraction,
                             units_destroyed=total_attacking_losses,
                             enemy_losses=total_defending_losses)
        update_results_table(db_connection=conn, faction=defending_fraction,
                             units_destroyed=total_defending_losses,
                             enemy_losses=total_attacking_losses)
    except Exception as e:
        print(f"[ERROR] update_results_table: {e}")

    # efficiency_ratio для ии
    if winner == 'attacker':
        eff = (total_defending_losses / total_attacking_losses) if total_attacking_losses > 0 else float(total_defending_losses)
    else:
        eff = (total_attacking_losses / total_defending_losses) if total_defending_losses > 0 else float(total_attacking_losses)

    final_report_attacking = [{
        'unit_name': u['unit_name'], 'initial_count': u['initial_count'],
        'unit_count': u['unit_count'], 'killed_count': u['killed_count']
    } for u in visible_atk_army]
    final_report_defending = [{
        'unit_name': u['unit_name'], 'initial_count': u['initial_count'],
        'unit_count': u['unit_count'], 'killed_count': u['killed_count']
    } for u in visible_def_army]

    if is_user_involved:
        try:
            # Показываем анимацию боя
            def show_report():
                report_data = generate_battle_report(
                    atk_army, def_army,
                    winner=legacy_winner,
                    attacking_fraction=attacking_fraction,
                    defending_fraction=defending_fraction,
                    user_faction=user_faction,
                    city=defending_city
                )
                show_battle_report(report_data, is_user_involved=is_user_involved,
                                   user_faction=user_faction, conn=conn)
            
            show_battle_animation(battle_rounds, attacking_fraction, defending_fraction, winner, user_faction, attacking_city, defending_city, callback=show_report)
        except Exception as e:
            print(f"[ERROR] battle animation/report: {e}")

    try:
        cleanup_equipment_after_battle(conn)
    except Exception as e:
        print(f"[ERROR] cleanup_equipment_after_battle: {e}")

    return {
        "winner": winner,
        "efficiency_ratio": round(eff, 2),
        "rounds": round_num,
        "attacking_fraction": attacking_fraction,
        "defending_fraction": defending_fraction,
        "attacking_losses": total_attacking_losses,
        "defending_losses": total_defending_losses,
        "attacking_units": final_report_attacking,
        "defending_units": final_report_defending,
    }


def _empty_result(winner, atk_f, def_f):
    return {
        "winner": winner,
        "efficiency_ratio": 0,
        "rounds": 0,
        "attacking_fraction": atk_f,
        "defending_fraction": def_f,
        "attacking_losses": 0,
        "defending_losses": 0,
        "attacking_units": [],
        "defending_units": [],
    }


# ======================================================================
#  НИЖЕ — ВСЕ ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ИЗ ОРИГИНАЛЬНОГО fight.py
#  (БД, гарнизоны, инфраструктура, отчёт, экипировка, досье)
#  Логика этих функций НЕ менялась.
# ======================================================================


def update_results_table(db_connection, faction, units_destroyed, enemy_losses):
    """Обновляет или создает запись в таблице results для указанной фракции."""
    try:
        with db_connection:
            cursor = db_connection.cursor()
            units_destroyed = abs(units_destroyed)
            enemy_losses = abs(enemy_losses)

            cursor.execute("SELECT COUNT(*) FROM results WHERE faction = ?", (faction,))
            exists = cursor.fetchone()[0]

            if exists > 0:
                cursor.execute("""
                    UPDATE results
                    SET 
                        Units_Destroyed = Units_Destroyed + ?,
                        Units_killed = Units_killed + ?
                    WHERE faction = ?
                """, (units_destroyed, enemy_losses, faction))
            else:
                cursor.execute("""
                    INSERT INTO results (
                        Units_Destroyed, Units_killed, 
                        Army_Efficiency_Ratio, Average_Deal_Ratio, 
                        Average_Net_Profit_Coins, Average_Net_Profit_Raw, 
                        Economic_Efficiency, faction
                    )
                    VALUES (?, ?, 0, 0, 0, 0, 0, ?)
                """, (units_destroyed, enemy_losses, faction))

    except sqlite3.IntegrityError as e:
        print(f"[ERROR] Ошибка целостности данных в results: {e}")
    except sqlite3.Error as e:
        print(f"[ERROR] Ошибка базы данных в update_results_table: {e}")
    except Exception as e:
        print(f"[ERROR] Неожиданная ошибка в update_results_table: {e}")


def generate_battle_report(attacking_army, defending_army, winner,
                           attacking_fraction, defending_fraction, user_faction, city):
    """Генерирует отчет о бое."""
    attacking_result = None
    defending_result = None
    report_data = []

    def process_army(army, side, result=None):
        for unit in army:
            initial_count = unit.get('initial_count', 0)
            final_count = unit['unit_count']
            losses = abs(initial_count - final_count)
            report_data.append({
                'unit_name': unit['unit_name'],
                'initial_count': initial_count,
                'final_count': final_count,
                'losses': losses,
                'side': side,
                'result': result,
                'city': city
            })

    if user_faction:
        if winner == 'attacking' and attacking_fraction == user_faction:
            attacking_result = "Победа"
        elif winner == 'defending' and defending_fraction == user_faction:
            defending_result = "Победа"
        else:
            if attacking_fraction == user_faction:
                attacking_result = "Поражение"
            elif defending_fraction == user_faction:
                defending_result = "Поражение"

    process_army(attacking_army, 'attacking', attacking_result)
    process_army(defending_army, 'defending', defending_result)

    return report_data


def show_battle_report(report_data, is_user_involved=False, user_faction=None, conn=None):
    """Финальный отчёт о бою — Kivy popup."""
    if not report_data:
        print("Нет данных для отображения.")
        return

    from kivy.metrics import dp, sp
    from kivy.uix.label import Label
    from kivy.uix.popup import Popup
    from kivy.uix.anchorlayout import AnchorLayout
    from kivy.uix.boxlayout import BoxLayout
    from kivy.uix.button import Button
    from kivy.graphics import Color, Rectangle
    from kivy.core.window import Window

    def make_label(text, font_sp, markup=False, halign='center', valign='middle',
                   height_dp=None, size_hint_x=1.0, min_width=None, bold=False):
        if bold and not markup:
            text = f"[b]{text}[/b]"
            markup = True
        elif bold and markup and not text.startswith('[b]'):
            text = f"[b]{text}[/b]"

        lbl = Label(text=text, font_size=sp(font_sp), markup=markup,
                    halign=halign, valign=valign, size_hint=(size_hint_x, None))
        if height_dp is None:
            lbl.height = dp(int(font_sp * 2.0))
        else:
            lbl.height = dp(height_dp)
        lbl.text_size = (lbl.width, lbl.height)
        lbl.bind(width=lambda inst, w: setattr(inst, 'text_size', (w, inst.height)))
        lbl.bind(height=lambda inst, h: setattr(inst, 'text_size', (inst.width, h)))
        if min_width:
            lbl.bind(minimum_width=lambda inst, w: setattr(inst, 'width', max(w, min_width)))
        return lbl

    is_small = Window.height < dp(600)
    popup_rel_h = 0.95 if is_small else 0.98
    popup_rel_w = 0.98

    outer = AnchorLayout(anchor_x='center', anchor_y='center', size_hint=(1, 1))

    content = BoxLayout(orientation='vertical',
                        padding=[dp(8), dp(8), dp(8), dp(8)],
                        spacing=dp(8),
                        size_hint=(popup_rel_w, popup_rel_h))

    with content.canvas.before:
        Color(0.12, 0.12, 0.18, 1)
        content.rect = Rectangle(size=content.size, pos=content.pos)
        content.bind(pos=lambda inst, v: setattr(inst.rect, 'pos', v),
                     size=lambda inst, v: setattr(inst.rect, 'size', v))

    # Верхняя панель: Результат и Город
    top_h = dp(50) if not is_small else dp(40)
    top_bar = BoxLayout(orientation='horizontal', size_hint_y=None, height=top_h, spacing=dp(10))

    result_text, result_color = "", "#FFFFFF"
    for it in report_data:
        if it.get("result"):
            result_text = it["result"].upper()
            result_color = "#33FF57" if result_text in ("ПОБЕДА", "VICTORY") else "#FF5733"
            break

    result_label = make_label(f"[b][color={result_color}]{result_text}[/color][/b]",
                              font_sp=22 if not is_small else 18,
                              markup=True, halign='center', height_dp=top_h, size_hint_x=0.5)

    city_name = report_data[0].get('city', '—') if report_data else '—'
    city_label = make_label(f"[b][color=#FFD700]{city_name}[/color][/b]",
                            font_sp=18 if not is_small else 14,
                            markup=True, halign='center', height_dp=top_h, size_hint_x=0.5)

    center_layout = BoxLayout(orientation='horizontal', size_hint_x=1.0, padding=[dp(20), 0])
    center_layout.add_widget(result_label)
    center_layout.add_widget(Label(text=" — ", font_size=sp(20), size_hint_x=None, width=dp(20), halign='center'))
    center_layout.add_widget(city_label)

    top_bar.add_widget(Label(size_hint_x=0.1))
    top_bar.add_widget(center_layout)
    top_bar.add_widget(Label(size_hint_x=0.1))
    content.add_widget(top_bar)

    # Заголовки сторон
    player_side = None
    for it in report_data:
        if it.get('result') is not None:
            player_side = it.get('side')
            break

    if player_side == 'attacking':
        left_title = "[b][color=#F44336]ИИ[/color][/b]"
        right_title = "[b][color=#4CAF50]Игрок[/color][/b]"
    elif player_side == 'defending':
        left_title = "[b][color=#4CAF50]Игрок[/color][/b]"
        right_title = "[b][color=#F44336]ИИ[/color][/b]"
    else:
        left_title = "[b][color=#F44336]ИИ[/color][/b]"
        right_title = "[b][color=#4CAF50]Игрок[/color][/b]"

    titles_h = dp(40) if not is_small else dp(36)
    titles_bar = BoxLayout(orientation='horizontal', size_hint_y=None, height=titles_h)
    left_title_lbl = make_label(left_title, font_sp=20 if not is_small else 16, markup=True,
                                halign='left', height_dp=titles_h, size_hint_x=0.45)
    right_title_lbl = make_label(right_title, font_sp=20 if not is_small else 16, markup=True,
                                 halign='right', height_dp=titles_h, size_hint_x=0.45)
    titles_bar.add_widget(Label(size_hint_x=0.05))
    titles_bar.add_widget(left_title_lbl)
    titles_bar.add_widget(Label(size_hint_x=0.1))
    titles_bar.add_widget(right_title_lbl)
    titles_bar.add_widget(Label(size_hint_x=0.05))
    content.add_widget(titles_bar)

    # Таблица юнитов
    attacking_units = [item for item in report_data if item.get('side') == 'attacking']
    defending_units = [item for item in report_data if item.get('side') == 'defending']
    max_rows = max(len(attacking_units), len(defending_units))

    row_h = dp(36) if not is_small else dp(32)
    header_h = dp(40) if not is_small else dp(34)
    table_total_h = header_h + row_h * max_rows

    table_container = BoxLayout(orientation='vertical', size_hint_y=None, height=table_total_h)

    headers_row = BoxLayout(orientation='horizontal', size_hint_y=None, height=header_h)
    headers_row.add_widget(Label(size_hint_x=0.05))
    headers_row.add_widget(make_label("Юнит", font_sp=18 if not is_small else 16, markup=True,
                                      halign='left', height_dp=header_h, size_hint_x=0.2, bold=True))
    headers_row.add_widget(make_label("Потери | Осталось", font_sp=18 if not is_small else 16, markup=True,
                                      halign='left', height_dp=header_h, size_hint_x=0.25, bold=True))
    headers_row.add_widget(Label(size_hint_x=0.1))
    headers_row.add_widget(make_label("Юнит", font_sp=18 if not is_small else 16, markup=True,
                                      halign='left', height_dp=header_h, size_hint_x=0.2, bold=True))
    headers_row.add_widget(make_label("Потери | Осталось", font_sp=18 if not is_small else 16, markup=True,
                                      halign='left', height_dp=header_h, size_hint_x=0.25, bold=True))
    headers_row.add_widget(Label(size_hint_x=0.05))
    table_container.add_widget(headers_row)

    for i in range(max_rows):
        row = BoxLayout(orientation='horizontal', size_hint_y=None, height=row_h)
        row.add_widget(Label(size_hint_x=0.05))

        # Левая сторона (ИИ)
        if i < len(defending_units):
            u = defending_units[i]
            name = u.get('unit_name', '—')
            init, fin = u.get('initial_count', 0), u.get('final_count', 0)
            losses = u.get('losses', 0)

            if init == 1 and fin == 1:
                status = "[color=#4CAF50]Выжил![/color]"
            elif init == 1 and fin == 0:
                status = "[color=#FF5733]Погиб...[/color]"
            else:
                losses_color = "#FF5733"
                remaining_color = "#4CAF50" if fin > 0 else "#FF5733"
                status = f"[color={losses_color}]{losses}[/color] | [color={remaining_color}]{fin}[/color]"

            unit_lbl = make_label(f"[b]{name}[/b]", font_sp=16 if not is_small else 14, markup=True,
                                  halign='left', height_dp=row_h, size_hint_x=0.2, bold=True)
            status_lbl = make_label(status, font_sp=16 if not is_small else 14, markup=True,
                                    halign='left', height_dp=row_h, size_hint_x=0.25, bold=True)
        else:
            unit_lbl = make_label("", font_sp=16 if not is_small else 14, height_dp=row_h, size_hint_x=0.2)
            status_lbl = make_label("", font_sp=16 if not is_small else 14, height_dp=row_h, size_hint_x=0.25)
        row.add_widget(unit_lbl)
        row.add_widget(status_lbl)

        row.add_widget(Label(size_hint_x=0.1))

        # Правая сторона (Игрок)
        if i < len(attacking_units):
            u = attacking_units[i]
            name = u.get('unit_name', '—')
            init, fin = u.get('initial_count', 0), u.get('final_count', 0)
            losses = u.get('losses', 0)

            if init == 1 and fin == 1:
                status = "[color=#4CAF50]Выжил![/color]"
            elif init == 1 and fin == 0:
                status = "[color=#FF5733]Погиб...[/color]"
            else:
                losses_color = "#FF5733"
                remaining_color = "#4CAF50" if fin > 0 else "#FF5733"
                status = f"[color={losses_color}]{losses}[/color] | [color={remaining_color}]{fin}[/color]"

            unit_lbl = make_label(f"[b]{name}[/b]", font_sp=16 if not is_small else 14, markup=True,
                                  halign='left', height_dp=row_h, size_hint_x=0.2, bold=True)
            status_lbl = make_label(status, font_sp=16 if not is_small else 14, markup=True,
                                    halign='left', height_dp=row_h, size_hint_x=0.25, bold=True)
        else:
            unit_lbl = make_label("", font_sp=16 if not is_small else 14, height_dp=row_h, size_hint_x=0.2)
            status_lbl = make_label("", font_sp=16 if not is_small else 14, height_dp=row_h, size_hint_x=0.25)
        row.add_widget(unit_lbl)
        row.add_widget(status_lbl)
        row.add_widget(Label(size_hint_x=0.05))
        table_container.add_widget(row)

    content.add_widget(table_container)

    # Кнопка закрытия
    btn_box = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(48))
    close_button = Button(text="Закрыть", size_hint=(0.8, None), height=dp(40), font_size=sp(16),
                          background_color=(0.18, 0.56, 0.98, 1), color=(1, 1, 1, 1))
    btn_box.add_widget(close_button)
    content.add_widget(btn_box)

    outer.add_widget(content)

    popup = Popup(title="", content=outer, size_hint=(popup_rel_w, popup_rel_h),
                  background_color=(0.08, 0.08, 0.12, 1), auto_dismiss=True)
    close_button.bind(on_press=lambda inst: popup.dismiss())
    close_button.bind(on_release=lambda inst: popup.dismiss())

    # Обновление досье
    if is_user_involved and user_faction and report_data:
        is_victory = any(item.get('result') in ("Победа", "VICTORY") for item in report_data)
        try:
            update_dossier_battle_stats(conn, user_faction, is_victory)
        except Exception as e:
            print(f"[Ошибка] Не удалось обновить досье: {e}")

    popup.open()


def show_battle_animation(battle_rounds, attacking_fraction, defending_fraction, winner, user_faction, attacking_city, defending_city, callback=None):
    """Анимация боя: две глобальные полосы здоровья + раунд."""
    from kivy.clock import Clock
    from kivy.uix.popup import Popup
    from kivy.uix.boxlayout import BoxLayout
    from kivy.uix.label import Label
    from kivy.uix.button import Button
    from kivy.uix.widget import Widget
    from kivy.graphics import Color, RoundedRectangle
    from kivy.metrics import dp, sp
    from kivy.core.window import Window

    if len(battle_rounds) > 10:
        indices = [0, len(battle_rounds)//4, len(battle_rounds)//2, 3*len(battle_rounds)//4, -1]
        selected_rounds = [battle_rounds[i] for i in indices if i < len(battle_rounds)]
    else:
        selected_rounds = battle_rounds

    popup = Popup(title=f"Бой: {attacking_city} vs {defending_city}", size_hint=(0.9, 0.9), background_color=(0.05, 0.05, 0.08, 1))
    main_layout = BoxLayout(orientation='vertical', spacing=dp(12), padding=dp(12))

    with main_layout.canvas.before:
        Color(0.08, 0.08, 0.12, 1)
        main_layout.bg = RoundedRectangle(pos=main_layout.pos, size=main_layout.size, radius=[dp(10)])
    main_layout.bind(pos=lambda inst, v: setattr(inst.bg, 'pos', v), size=lambda inst, v: setattr(inst.bg, 'size', v))

    skip_button = Button(text="Пропустить", size_hint_y=None, height=dp(40), background_color=(0.8, 0.2, 0.2, 1), bold=True, font_size=sp(14))
    main_layout.add_widget(skip_button)

    round_label = Label(text="Раунд 1/1", font_size=sp(18), bold=True, size_hint_y=None, height=dp(32), color=(0.9, 0.9, 0.9, 1))
    main_layout.add_widget(round_label)

    info_layout = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(28), spacing=dp(10))
    atk_title = Label(text=f"[b][color=#4CAF50]{attacking_fraction}[/color][/b]", markup=True, halign='left', valign='middle', font_size=sp(14))
    def_title = Label(text=f"[b][color=#F44336]{defending_fraction}[/color][/b]", markup=True, halign='right', valign='middle', font_size=sp(14))
    info_layout.add_widget(atk_title)
    info_layout.add_widget(Label(size_hint_x=0.5))
    info_layout.add_widget(def_title)
    main_layout.add_widget(info_layout)

    def make_bar_widget(color):
        bar = Widget(size_hint_y=None, height=dp(28))
        bar.ratio = 1.0
        bar.color_rgb = color

        def redraw(widget, *_):
            widget.canvas.clear()
            with widget.canvas:
                Color(0.18, 0.18, 0.22, 1)
                RoundedRectangle(pos=widget.pos, size=(widget.width, widget.height), radius=[dp(12)])
                Color(*widget.color_rgb, 0.95)
                RoundedRectangle(pos=widget.pos, size=(widget.width * widget.ratio, widget.height), radius=[dp(12)])
        bar.bind(pos=redraw, size=redraw)
        return bar

    player_bar = make_bar_widget((0.2, 0.8, 0.2))
    enemy_bar = make_bar_widget((0.8, 0.2, 0.2))

    player_label = Label(text="Игрок: 0/0", font_size=sp(13), size_hint_y=None, height=dp(22), halign='left', valign='middle')
    enemy_label = Label(text="ИИ: 0/0", font_size=sp(13), size_hint_y=None, height=dp(22), halign='left', valign='middle')

    main_layout.add_widget(player_label)
    main_layout.add_widget(player_bar)
    main_layout.add_widget(enemy_label)
    main_layout.add_widget(enemy_bar)

    popup.content = main_layout

    current_round_idx = 0
    animation_event = {'event': None}

    def update_round(dt):
        nonlocal current_round_idx
        if current_round_idx >= len(selected_rounds):
            if animation_event['event'] is not None:
                animation_event['event'].cancel()
            popup.dismiss()
            if callback:
                Clock.schedule_once(lambda dt: callback(), 0.05)
            return False

        round_data = selected_rounds[current_round_idx]
        total_rounds = len(battle_rounds)
        round_label.text = f"Раунд {round_data['round']}/{total_rounds}"

        atk_ratio = (round_data['atk_total'] / round_data['atk_max']) if round_data['atk_max'] > 0 else 0
        def_ratio = (round_data['def_total'] / round_data['def_max']) if round_data['def_max'] > 0 else 0

        player_bar.ratio = atk_ratio
        enemy_bar.ratio = def_ratio

        player_label.text = f"{attacking_fraction}: {round_data['atk_total']} / {round_data['atk_max']}"
        enemy_label.text = f"{defending_fraction}: {round_data['def_total']} / {round_data['def_max']}"

        # Перерисовать полосы
        player_bar.canvas.clear()
        with player_bar.canvas:
            Color(0.18, 0.18, 0.22, 1)
            RoundedRectangle(pos=player_bar.pos, size=(player_bar.width, player_bar.height), radius=[dp(12)])
            Color(*player_bar.color_rgb, 0.95)
            RoundedRectangle(pos=player_bar.pos, size=(player_bar.width * player_bar.ratio, player_bar.height), radius=[dp(12)])

        enemy_bar.canvas.clear()
        with enemy_bar.canvas:
            Color(0.18, 0.18, 0.22, 1)
            RoundedRectangle(pos=enemy_bar.pos, size=(enemy_bar.width, enemy_bar.height), radius=[dp(12)])
            Color(*enemy_bar.color_rgb, 0.95)
            RoundedRectangle(pos=enemy_bar.pos, size=(enemy_bar.width * enemy_bar.ratio, enemy_bar.height), radius=[dp(12)])

        current_round_idx += 1
        return True

    def skip_animation(instance):
        if animation_event['event'] is not None:
            animation_event['event'].cancel()
        popup.dismiss()
        if callback:
            Clock.schedule_once(lambda dt: callback(), 0.05)

    skip_button.bind(on_press=skip_animation)

    popup.open()
    animation_event['event'] = Clock.schedule_interval(update_round, 0.3)


def update_garrisons_after_battle(winner, attacking_city, defending_city,
                                  attacking_army, defending_army,
                                  attacking_fraction, defending_fraction, conn):

    """Обновляет гарнизоны после боя."""
    try:
        cursor = conn.cursor()
        if winner == 'attacking':
            # Победила атакующая сторона
            cursor.execute("DELETE FROM garrisons WHERE city_name = ?", (defending_city,))

            for unit in attacking_army:
                if unit['unit_count'] > 0:
                    cursor.execute("""
                        INSERT INTO garrisons (city_name, unit_name, unit_count, unit_image)
                        VALUES (?, ?, ?, ?)
                        ON CONFLICT(city_name, unit_name) DO UPDATE SET
                            unit_count = excluded.unit_count,
                            unit_image = excluded.unit_image
                    """, (
                        defending_city,
                        unit['unit_name'],
                        unit['unit_count'],
                        unit.get('unit_image', '')
                    ))
            cursor.execute("UPDATE cities SET faction = ? WHERE name = ?", (attacking_fraction, defending_city))
            cursor.execute("UPDATE buildings SET faction = ? WHERE city_name = ?", (attacking_fraction, defending_city))

        else:
            # Победила обороняющаяся сторона
            cursor.execute("DELETE FROM garrisons WHERE city_name = ?", (defending_city,))
            for unit in defending_army:
                if unit['unit_count'] > 0:
                    cursor.execute("""
                        INSERT INTO garrisons (city_name, unit_name, unit_count, unit_image)
                        VALUES (?, ?, ?, ?)
                        ON CONFLICT(city_name, unit_name) DO UPDATE SET
                            unit_count = excluded.unit_count,
                            unit_image = excluded.unit_image
                    """, (
                        defending_city,
                        unit['unit_name'],
                        unit['unit_count'],
                        unit.get('unit_image', '')
                    ))

        # Обновляем гарнизон атакующего города
        original_counts = {}
        cursor.execute("SELECT unit_name, unit_count FROM garrisons WHERE city_name = ?", (attacking_city,))
        for row in cursor.fetchall():
            try:
                original_counts[row['unit_name']] = row['unit_count']
            except (TypeError, IndexError):
                original_counts[row[0]] = row[1]

        for unit in attacking_army:
            remaining_in_source = original_counts.get(unit['unit_name'], 0) - unit['initial_count']
            if remaining_in_source > 0:
                cursor.execute("""
                    UPDATE garrisons 
                    SET unit_count = ? 
                    WHERE city_name = ? AND unit_name = ?
                """, (remaining_in_source, attacking_city, unit['unit_name']))
            else:
                cursor.execute("""
                    DELETE FROM garrisons 
                    WHERE city_name = ? AND unit_name = ?
                """, (attacking_city, unit['unit_name']))

        # Сброс характеристик юнитов 3 класса при необходимости
        reset_third_class_units_if_empty(conn, attacking_fraction)
        reset_third_class_units_if_empty(conn, defending_fraction)

        conn.commit()

    except sqlite3.Error as e:
        print(f"Ошибка при обновлении гарнизонов: {e}")


def damage_to_infrastructure(all_damage, city_name, user_faction, conn):
    """Вычисляет урон по инфраструктуре города и обновляет данные в БД."""
    DAMAGE_PER_BUILDING = 45900

    try:
        cursor = conn.cursor()

        cursor.execute('''
            SELECT building_type, count 
            FROM buildings 
            WHERE city_name = ? AND count > 0
        ''', (city_name,))
        rows = cursor.fetchall()

        city_data = {}
        for row in rows:
            try:
                building_type, count = row[0], row[1]
            except (TypeError, IndexError):
                continue
            city_data[building_type] = count

        if not city_data:
            return

        total_buildings = sum(city_data.values())
        if total_buildings == 0:
            return

        potential_destroyed_buildings = int(all_damage // DAMAGE_PER_BUILDING)
        priority_buildings = ['Больница', 'Фабрика']

        for building in priority_buildings:
            if building in city_data and city_data[building] > 0:
                count = city_data[building]
                if potential_destroyed_buildings >= count:
                    city_data[building] = 0
                    potential_destroyed_buildings -= count

                    cursor.execute('''
                        UPDATE buildings 
                        SET count = 0 
                        WHERE city_name = ? AND building_type = ?
                    ''', (city_name, building))
                else:
                    city_data[building] -= potential_destroyed_buildings

                    cursor.execute('''
                        UPDATE buildings 
                        SET count = count - ? 
                        WHERE city_name = ? AND building_type = ?
                    ''', (potential_destroyed_buildings, city_name, building))

                    potential_destroyed_buildings = 0

                if potential_destroyed_buildings == 0:
                    break

        conn.commit()

    except Exception as e:
        print(f"Ошибка при работе с базой данных (damage_to_infrastructure): {e}")


def update_dossier_battle_stats(conn, user_faction, is_victory):
    """Обновляет статистику по боям в таблице dossier для текущей фракции пользователя."""
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT battle_victories, battle_defeats FROM dossier WHERE faction = ?", (user_faction,))
        result = cursor.fetchone()

        if result:
            if is_victory:
                cursor.execute("""
                    UPDATE dossier
                    SET battle_victories = battle_victories + 1,
                        last_data = datetime('now')
                    WHERE faction = ?
                """, (user_faction,))
            else:
                cursor.execute("""
                    UPDATE dossier
                    SET battle_defeats = battle_defeats + 1,
                        last_data = datetime('now')
                    WHERE faction = ?
                """, (user_faction,))
        else:
            if is_victory:
                cursor.execute("""
                    INSERT INTO dossier (
                        faction, battle_victories, battle_defeats, last_data
                    ) VALUES (?, 1, 0, datetime('now'))
                """, (user_faction,))
            else:
                cursor.execute("""
                    INSERT INTO dossier (
                        faction, battle_victories, battle_defeats, last_data
                    ) VALUES (?, 0, 1, datetime('now'))
                """, (user_faction,))
        conn.commit()
        print(f"[Досье] Обновлены данные для фракции '{user_faction}'")
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        print(f"[Ошибка] Не удалось обновить досье: {e}")


def reset_third_class_units_if_empty(conn, faction_name):
    """
    Сбрасывает характеристики юнитов 3 класса до значений по умолчанию,
    если в гарнизонах фракции не осталось юнитов 3 класса.
    Затем применяет сезонные бонусы.
    """
    try:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT COUNT(*) 
            FROM garrisons g
            JOIN units u ON g.unit_name = u.unit_name
            WHERE u.faction = ? AND u.unit_class = 3
        """, (faction_name,))

        third_class_count = cursor.fetchone()[0]

        if third_class_count == 0:
            print(f"[INFO] Юниты 3 класса фракции '{faction_name}' отсутствуют в гарнизонах. Сброс характеристик...")

            cursor.execute("""
                UPDATE units 
                SET 
                    attack = (SELECT attack FROM units_default WHERE units_default.unit_name = units.unit_name),
                    defense = (SELECT defense FROM units_default WHERE units_default.unit_name = units.unit_name),
                    durability = (SELECT durability FROM units_default WHERE units_default.unit_name = units.unit_name),
                    cost_money = (SELECT cost_money FROM units_default WHERE units_default.unit_name = units.unit_name),
                    cost_time = (SELECT cost_time FROM units_default WHERE units_default.unit_name = units.unit_name)
                WHERE faction = ? AND unit_class = 3
            """, (faction_name,))

            print(f"[SUCCESS] Характеристики юнитов 3 класса фракции '{faction_name}' сброшены до значений по умолчанию.")

            # Текущий сезон
            try:
                cursor.execute("SELECT current_season FROM season LIMIT 1")
                season_result = cursor.fetchone()
            except Exception:
                season_result = None

            if season_result:
                current_season = season_result[0]

                faction_effects = [
                    # 0 = Зима
                    {
                        'Север':   {'stat': 1.25, 'cost': 0.65},
                        'Эльфы':   {'stat': 0.65, 'cost': 1.25},
                        'Вампиры': {'stat': 0.97, 'cost': 1.00},
                        'Адепты':  {'stat': 0.90, 'cost': 1.17},
                        'Элины':   {'stat': 0.45, 'cost': 1.45},
                    },
                    # 1 = Весна
                    {
                        'Север':   {'stat': 0.90, 'cost': 1.17},
                        'Эльфы':   {'stat': 0.97, 'cost': 1.00},
                        'Вампиры': {'stat': 1.25, 'cost': 0.65},
                        'Адепты':  {'stat': 0.65, 'cost': 1.25},
                        'Элины':   {'stat': 0.99, 'cost': 0.90},
                    },
                    # 2 = Лето
                    {
                        'Север':   {'stat': 0.65, 'cost': 1.25},
                        'Эльфы':   {'stat': 1.25, 'cost': 0.65},
                        'Вампиры': {'stat': 0.90, 'cost': 1.17},
                        'Адепты':  {'stat': 0.97, 'cost': 1.00},
                        'Элины':   {'stat': 1.70, 'cost': 0.60},
                    },
                    # 3 = Осень
                    {
                        'Север':   {'stat': 0.97, 'cost': 1.00},
                        'Эльфы':   {'stat': 0.90, 'cost': 1.17},
                        'Вампиры': {'stat': 0.65, 'cost': 1.25},
                        'Адепты':  {'stat': 1.25, 'cost': 0.65},
                        'Элины':   {'stat': 0.90, 'cost': 1.17},
                    },
                ]

                if current_season in [0, 1, 2, 3] and faction_name in faction_effects[current_season]:
                    effects = faction_effects[current_season][faction_name]
                    stat_f = effects['stat']
                    cost_f = effects['cost']

                    if stat_f != 1.0:
                        cursor.execute("""
                            UPDATE units
                            SET
                                attack  = CAST(ROUND(attack  * ?) AS INTEGER),
                                defense = CAST(ROUND(defense * ?) AS INTEGER)
                            WHERE faction = ? AND unit_class = 3
                        """, (stat_f, stat_f, faction_name))

                    if cost_f != 1.0:
                        cursor.execute("""
                            UPDATE units
                            SET
                                cost_money = CAST(ROUND(cost_money * ?) AS INTEGER),
                                cost_time  = CAST(ROUND(cost_time  * ?) AS INTEGER)
                            WHERE faction = ? AND unit_class = 3
                        """, (cost_f, cost_f, faction_name))

                    print(f"[SUCCESS] Сезонные бонусы применены к юнитам 3 класса фракции '{faction_name}' для сезона {current_season}.")

            conn.commit()
            return True
        else:
            print(f"[INFO] У фракции '{faction_name}' остались юниты 3 класса в гарнизонах. Сброс не требуется.")
            return False

    except sqlite3.Error as e:
        print(f"[ERROR] Ошибка базы данных при сбросе характеристик юнитов 3 класса: {e}")
        try:
            conn.rollback()
        except Exception:
            pass
        return False
    except Exception as e:
        print(f"[ERROR] Неожиданная ошибка при сбросе характеристик юнитов 3 класса: {e}")
        import traceback
        traceback.print_exc()
        try:
            conn.rollback()
        except Exception:
            pass
        return False


def cleanup_equipment_after_battle(conn):
    """Очищает таблицы hero_equipment и ai_hero_equipment после боя."""
    try:
        cursor = conn.cursor()
        print("[DEBUG] Начало очистки таблиц экипировки после боя...")

        cursor.execute("SELECT DISTINCT hero_name FROM hero_equipment")
        hero_equipment_heroes = cursor.fetchall()

        for (hero_name,) in hero_equipment_heroes:
            cursor.execute("SELECT 1 FROM garrisons WHERE unit_name = ? LIMIT 1", (hero_name,))
            if cursor.fetchone() is None:
                print(f"[INFO] Герой '{hero_name}' не найден в garrisons. Удаление из hero_equipment.")
                cursor.execute("DELETE FROM hero_equipment WHERE hero_name = ?", (hero_name,))

        cursor.execute("SELECT DISTINCT hero_name FROM ai_hero_equipment")
        ai_hero_equipment_heroes = cursor.fetchall()

        for (hero_name,) in ai_hero_equipment_heroes:
            cursor.execute("SELECT 1 FROM garrisons WHERE unit_name = ? LIMIT 1", (hero_name,))
            if cursor.fetchone() is None:
                print(f"[INFO] Герой ИИ '{hero_name}' не найден в garrisons. Удаление из ai_hero_equipment.")
                cursor.execute("DELETE FROM ai_hero_equipment WHERE hero_name = ?", (hero_name,))

        conn.commit()
        print("[SUCCESS] Очистка таблиц экипировки завершена.")

    except sqlite3.Error as e:
        print(f"[ERROR] Ошибка базы данных при очистке экипировки: {e}")
        try:
            conn.rollback()
        except Exception:
            pass
    except Exception as e:
        print(f"[ERROR] Неожиданная ошибка при очистке экипировки: {e}")
        import traceback
        traceback.print_exc()
