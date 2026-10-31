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
который добавит колонки initiative, unit_type, morale,
crit_chance в units и units_default.
"""

import os
import random
import sqlite3
from db_lerdon_connect import *
import copy


# ======================================================================
#                       БАЛАНСНЫЕ КОНСТАНТЫ
# ======================================================================

BASE_LETHALITY = 18.0          # летальность: чем меньше, тем кровавее бой
COUNTER_ATTACK_RATIO = 0.75    # контрудар защитника слабее
RANDOM_MIN = 0.90              # рандом ±10%
RANDOM_MAX = 1.10
DEFAULT_CRIT_CHANCE = 5
CRIT_MULTIPLIER = 1.5
MAX_ROUNDS = 100               # антизацикливание

# Тип-модификаторы (камень-ножницы-бумага).
# Тип-модификаторы — каждая фракция бьёт 2 и проигрывает 2:
# Адепты(cavalry) > Вампиры(beast), Эльфы(infantry)
# Элины(mage)     > Вампиры(beast), Адепты(cavalry)
# Вампиры(beast)  > Север(archer),  Эльфы(infantry)
# Север(archer)   > Адепты(cavalry), Элины(mage)
# Эльфы(infantry) > Элины(mage),    Север(archer)
# Нежить(siege) сильна против всех (+ Ужас Смерти), но все бьют нежить без штрафа
TYPE_MOD = {
    "infantry": {"cavalry": 0.55, "archer": 1.45, "infantry": 1.0, "mage": 1.45, "beast": 0.55, "siege": 1.0},
    "cavalry":  {"archer": 0.55,  "mage": 0.55,   "infantry": 1.45,"cavalry": 1.0,"beast": 1.45, "siege": 1.0},
    "archer":   {"infantry": 0.55,"siege": 1.0,   "cavalry": 1.45, "archer": 1.0, "mage": 1.45, "beast": 0.55},
    "mage":     {"infantry": 0.55,"beast": 1.45,  "mage": 1.0,     "cavalry": 1.45,"archer": 0.55,"siege": 1.0},
    "beast":    {"archer": 1.45,  "mage": 0.55,   "infantry": 1.45,"cavalry": 0.55,"beast": 1.0, "siege": 1.0},
    "siege":    {"infantry": 1.25,"cavalry": 1.25, "archer": 1.25, "mage": 1.25,  "beast": 1.25, "siege": 1.0},
}


# Пиковые сезоны фракций (для бонусов способностей)
FACTION_PEAK_SEASON = {
    'Север': 0,    # Зима
    'Вампиры': 1,  # Весна
    'Эльфы': 2,    # Лето
    'Адепты': 3,   # Осень
    'Элины': 2,    # Лето
    'Нежить': 0,   # Зима — Ужас Смерти усиливается
}


def _get_season_mult(faction, conn):
    """Возвращает 2.75 если сейчас пиковый сезон фракции, иначе 1.0"""
    try:
        _sc = conn.cursor()
        _sc.execute("SELECT season_index FROM season LIMIT 1")
        _sr = _sc.fetchone()
        current = _sr[0] if _sr else -1
    except Exception:
        current = -1
    return 2.75 if FACTION_PEAK_SEASON.get(faction) == current else 1.0


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
    Дополняет units_stats полями 'Инициатива', 'Тип', 'Мораль', 'Крит'.
    Читает из таблицы units. БД не пишет.
    Если миграция не пройдена — использует дефолты по unit_class.
    """
    if not units:
        return
    try:
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(units)")
        cols = {row[1] for row in cur.fetchall()}
        has_new = {'initiative', 'unit_type', 'crit_chance'} <= cols
        has_morale = 'morale' in cols

        if has_new:
            names = list({u['unit_name'] for u in units})
            placeholders = ','.join('?' * len(names))
            morale_col = ", morale" if has_morale else ""
            cur.execute(
                f"SELECT unit_name, initiative, unit_type, crit_chance{morale_col} "
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
                _, ini, utype, crit = rec[:4]
                morale_val = rec[4] if has_morale and len(rec) > 4 else 100
                stats.setdefault('Инициатива', ini if ini is not None else _default_initiative(u_class))
                stats.setdefault('Тип', (utype or 'infantry'))
                stats.setdefault('Крит', crit if crit is not None else _default_crit(u_class))
                stats.setdefault('Мораль', morale_val if morale_val is not None else 100)
            else:
                stats.setdefault('Инициатива', _default_initiative(u_class))
                stats.setdefault('Тип', 'infantry')
                stats.setdefault('Крит', _default_crit(u_class))
                stats.setdefault('Мораль', 100)
    except Exception as e:
        print(f"[WARN] _enrich_with_db_stats: {e}. Использую дефолты по классу.")
        for u in units:
            u_class = get_unit_class(u)
            stats = u.setdefault('units_stats', {})
            stats.setdefault('Инициатива', _default_initiative(u_class))
            stats.setdefault('Тип', 'infantry')
            stats.setdefault('Крит', _default_crit(u_class))
            stats.setdefault('Мораль', 100)



def calculate_hero_stat_bonus(army):
    """Сумма сырых характеристик живых героев классов 2 и 3 для бонуса юнитам 1 класса.
    Класс 4 действует сам по себе и НЕ передаёт статы солдатам.
    Возвращает (bonus_atk, bonus_def, bonus_dur).
    Формула: у каждого юнита 1 класса атака += hero_atk, защита += hero_def + hero_dur/2.
    """
    bonus_atk = 0
    bonus_def = 0
    bonus_dur = 0
    for u in army:
        if u['unit_count'] <= 0:
            continue
        uc = get_unit_class(u)
        if uc == 2 or uc == 3:  # класс 4 исключён намеренно
            bonus_atk += _get_stat(u, 'Урон', 0)
            bonus_def += _get_stat(u, 'Защита', 0)
            bonus_dur += _get_stat(u, 'Живучесть', 0)
    return bonus_atk, bonus_def, bonus_dur


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
                 atk_hero_bonus=(0, 0, 0), def_hero_bonus=(0, 0, 0),
                 atk_fraction='', def_fraction='', event_log=None):
    """Одна стычка: симметричные пропорциональные потери."""
    if attacker['unit_count'] <= 0 or defender['unit_count'] <= 0:
        return attacker, defender

    atk_attack = calculate_unit_power(attacker, is_attacking=True)
    atk_defense = calculate_unit_power(attacker, is_attacking=False)
    def_attack = calculate_unit_power(defender, is_attacking=True)
    def_defense = calculate_unit_power(defender, is_attacking=False)

    # Мятежники: все характеристики ×0.6
    if atk_fraction == 'Мятежники' and get_unit_class(attacker) == 1:
        atk_attack *= 0.6
        atk_defense *= 0.6
    if def_fraction == 'Мятежники' and get_unit_class(defender) == 1:
        def_attack *= 0.6
        def_defense *= 0.6

    # Сохраняем базовый урон до бонусов (для Шквала Севера)
    atk_base_attack = atk_attack
    def_base_attack = def_attack

    # Бонус от героев 2+ класса: сырые характеристики прибавляются к каждому юниту 1 класса
    # Зомби нежити не получают бафф от Низара (непослушные)
    if get_unit_class(attacker) == 1 and attacker.get('unit_name') != 'Зомби':
        atk_attack += atk_hero_bonus[0]
        atk_defense += atk_hero_bonus[1] + atk_hero_bonus[2] / 2.0
    if get_unit_class(defender) == 1 and defender.get('unit_name') != 'Зомби':
        def_attack += def_hero_bonus[0]
        def_defense += def_hero_bonus[1] + def_hero_bonus[2] / 2.0

    # Север: Шквал — если итоговый урон >= 20x от базового, урон x1.7 (в свой сезон x2.975)
    shkval_mult = 1.70 * _get_season_mult('Север', conn) if atk_fraction == 'Север' or def_fraction == 'Север' else 1.70
    if atk_fraction == 'Север' and get_unit_class(attacker) == 1 and atk_base_attack > 0:
        if atk_attack / atk_base_attack >= 20.0:
            atk_attack = int(atk_attack * shkval_mult)
    if def_fraction == 'Север' and get_unit_class(defender) == 1 and def_base_attack > 0:
        if def_attack / def_base_attack >= 20.0:
            def_attack = int(def_attack * shkval_mult)

    # Адепты: Оплот — если защита увеличена в 20+ раз от базовой (артефакты героя), +35% защиты
    atk_base_defense = calculate_unit_power(attacker, is_attacking=False)
    def_base_defense = calculate_unit_power(defender, is_attacking=False)
    oplot_mult = 1.35 * _get_season_mult('Адепты', conn) if atk_fraction == 'Адепты' or def_fraction == 'Адепты' else 1.35
    if atk_fraction == 'Адепты' and get_unit_class(attacker) == 1 and atk_base_defense > 0:
        if atk_defense / atk_base_defense >= 20.0:
            atk_defense = int(atk_defense * oplot_mult)
    if def_fraction == 'Адепты' and get_unit_class(defender) == 1 and def_base_defense > 0:
        if def_defense / def_base_defense >= 20.0:
            def_defense = int(def_defense * oplot_mult)

    # Боевой дух: 2+ победы над контрпиком за последние 4 хода → +15% урон
    # Контрпики — фракции, которые сильнее тебя по типу юнита
    _COUNTER_PICKS = {
        'Адепты': ['Элины', 'Север'],
        'Элины': ['Север', 'Эльфы'],
        'Вампиры': ['Адепты', 'Элины'],
        'Север': ['Вампиры', 'Эльфы'],
        'Эльфы': ['Адепты', 'Вампиры'],
    }
    if conn:
        try:
            _mc = conn.cursor()
            _mc.execute("SELECT turn_count FROM turn LIMIT 1")
            _tr = _mc.fetchone()
            _cur_turn = _tr[0] if _tr else 0
            for _frac, _side in [(atk_fraction, 'atk'), (def_fraction, 'def')]:
                _counters = _COUNTER_PICKS.get(_frac, [])
                if not _counters:
                    continue
                _placeholders = ','.join('?' * len(_counters))
                _mc.execute(
                    f"SELECT COUNT(*) FROM faction_victories "
                    f"WHERE faction = ? AND defeated IN ({_placeholders}) AND turn > ?",
                    [_frac] + _counters + [_cur_turn - 4]
                )
                _wins = _mc.fetchone()[0]
                if _wins >= 2:
                    if _side == 'atk':
                        atk_attack *= 1.15
                    else:
                        def_attack *= 1.15
        except Exception:
            pass

    # Тип-преимущество: урон ×1.45 при атаке, защита ×1.35 при обороне против слабого типа
    atk_type = get_unit_type(attacker)
    def_type = get_unit_type(defender)
    atk_type_mod = TYPE_MOD.get(atk_type, {}).get(def_type, 1.0)
    def_type_mod = TYPE_MOD.get(def_type, {}).get(atk_type, 1.0)
    atk_attack *= atk_type_mod
    def_attack *= def_type_mod
    # Бонус к защите: если ты силён против атакующего, +35% защита
    if def_type_mod > 1.0:
        def_defense *= 1.35
    if atk_type_mod > 1.0:
        atk_defense *= 1.35

    # Контрудар слабее
    def_attack *= COUNTER_ATTACK_RATIO

    # Рандом + крит
    atk_roll = random.uniform(RANDOM_MIN, RANDOM_MAX)
    def_roll = random.uniform(RANDOM_MIN, RANDOM_MAX)
    atk_critical = random.random() * 100 < get_crit_chance(attacker)
    if atk_critical:
        atk_roll *= CRIT_MULTIPLIER
    def_critical = random.random() * 100 < get_crit_chance(defender)
    if def_critical:
        def_roll *= CRIT_MULTIPLIER
    if event_log is not None:
        event_log.append((atk_critical, def_critical))
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
    # Snapshot only the armies participating in this battle, before losses/buffs.
    from city_war import army_strength as city_battle_strength
    initial_attacker_strength = city_battle_strength(atk_army)
    initial_defender_strength = city_battle_strength(def_army)

    # === Система опыта: миграция + загрузка + бонусы ===
    try:
        _cur = conn.cursor()
        try:
            _cur.execute("ALTER TABLE garrisons ADD COLUMN experience INTEGER DEFAULT 0")
            conn.commit()
        except sqlite3.OperationalError:
            pass  # Колонка уже есть

        # Загружаем опыт для каждого юнита
        for army, city in [(atk_army, attacking_city), (def_army, defending_city)]:
            for u in army:
                _cur.execute(
                    "SELECT COALESCE(experience, 0) FROM garrisons WHERE city_name = ? AND unit_name = ?",
                    (city, u['unit_name'])
                )
                row = _cur.fetchone()
                u['experience'] = row[0] if row else 0

                # Бонус от опыта (побед): Новобранец(0), Воин(1+: +5%), Ветеран(3+: +15%), Элита(7+: +25%)
                exp = u['experience']
                if exp >= 7:
                    exp_mult = 1.25
                elif exp >= 3:
                    exp_mult = 1.15
                elif exp >= 1:
                    exp_mult = 1.05
                else:
                    exp_mult = 1.0

                if exp_mult > 1.0 and get_unit_class(u) == 1:
                    stats = u.get('units_stats', {})
                    stats['Урон'] = stats.get('Урон', 0) * exp_mult
                    stats['Защита'] = stats.get('Защита', 0) * exp_mult
    except Exception as e:
        print(f"[EXP] Ошибка загрузки опыта: {e}")

    # Стартовые значения и выделение героев вне боя.
    # heroes3 — класс 3 (вступает при потерях ≥85%).
    # heroes4 — класс 4 (вступает последним: только когда класс 3 уже вступил или отсутствует, и потери ≥85%).
    heroes3 = {'atk': None, 'def': None}
    heroes4 = {'atk': None, 'def': None}
    heroes = heroes3  # обратная совместимость для остального кода
    new_atk_army = []
    new_def_army = []

    for u in atk_army:
        uc = get_unit_class(u)
        if uc == 3 and u['unit_count'] == 1:
            heroes3['atk'] = u
            u['initial_count'] = 1
            u['killed_count'] = 0
            u['hero_engaged'] = False
            u['hero_candidate'] = True
            new_atk_army.append(u)
        elif uc == 4 and u['unit_count'] == 1:
            heroes4['atk'] = u
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
        uc = get_unit_class(u)
        if uc == 3 and u['unit_count'] == 1:
            heroes3['def'] = u
            u['initial_count'] = 1
            u['killed_count'] = 0
            u['hero_engaged'] = False
            u['hero_candidate'] = True
            new_def_army.append(u)
        elif uc == 4 and u['unit_count'] == 1:
            heroes4['def'] = u
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

    # === Фракционные пассивные способности ===
    # В "свой" сезон бонус способности работает на 175% сильнее
    def _season_mult(faction):
        return _get_season_mult(faction, conn)

    # Север: Шквал — реализуется в battle_chain (x1.7 при 20x множителе)
    # В пиковый сезон порог снижается (множитель Шквала передаётся через atk_fraction)

    # Эльфы: Природное исцеление — 10% погибших возвращаются в строй после боя
    # (в свой сезон Лето: 27.5%)
    # Реализуется после боя в _apply_elf_healing

    # Нежить: Ужас Смерти — -15% атаки у врагов (в Зиму -25%)
    # Применяется к стороне, которая сражается ПРОТИВ Нежити
    _undead_fear = 0.0
    if attacking_fraction == 'Нежить':
        _undead_fear = 0.25 if _season_mult('Нежить') > 1 else 0.15
        for u in def_army:
            stats = u.get('units_stats', {})
            stats['Урон'] = stats.get('Урон', 0) * (1 - _undead_fear)
    elif defending_fraction == 'Нежить':
        _undead_fear = 0.25 if _season_mult('Нежить') > 1 else 0.15
        for u in atk_army:
            stats = u.get('units_stats', {})
            stats['Урон'] = stats.get('Урон', 0) * (1 - _undead_fear)

    # === Бонусы от зданий города-защитника ===
    city_wall_bonus = 0.0    # +15% защита за каждую Стену
    city_smithy_bonus = 0.0  # +5% атака за каждую Кузницу (бонус защитнику)
    try:
        _cur = conn.cursor()
        _cur.execute(
            "SELECT building_type, count FROM buildings WHERE city_name = ?",
            (defending_city,)
        )
        for b_type, b_count in _cur.fetchall():
            if b_type == 'Стена':
                city_wall_bonus += b_count * 0.15
            elif b_type == 'Кузница':
                city_smithy_bonus += b_count * 0.05
    except Exception:
        pass

    # Применяем бонус Стен: усиливаем защиту всех юнитов обороны
    if city_wall_bonus > 0:
        for u in def_army:
            stats = u.get('units_stats', {})
            base_def = stats.get('Защита', 0)
            stats['Защита'] = base_def * (1 + city_wall_bonus)

    # Суперкрепость нежити: +65% защита если город is_undead
    _is_undead_capital = False
    if defending_fraction == 'Нежить':
        try:
            _uc = conn.cursor()
            _uc.execute("SELECT COALESCE(is_undead, 0) FROM cities WHERE name = ?", (defending_city,))
            _ur = _uc.fetchone()
            if _ur and _ur[0]:
                for u in def_army:
                    stats = u.get('units_stats', {})
                    stats['Защита'] = stats.get('Защита', 0) * 1.65
                print(f"[UNDEAD] Суперкрепость {defending_city}: +65% защита гарнизону")
                # Проверяем, является ли город столицей нежити
                _uc.execute("SELECT capital_city FROM undead_invasion WHERE id = 1")
                _cap = _uc.fetchone()
                if _cap and _cap[0] == defending_city:
                    _is_undead_capital = True
        except Exception:
            pass

    # Применяем бонус Кузниц: усиливаем атаку юнитов обороны
    if city_smithy_bonus > 0:
        for u in def_army:
            stats = u.get('units_stats', {})
            base_atk = stats.get('Урон', 0)
            stats['Урон'] = base_atk * (1 + city_smithy_bonus)

    # Данные для анимации
    battle_rounds = []

    # === Мораль: динамическая система ===
    # Стартовые модификаторы морали
    for _side_army, _side_fraction in [(atk_army, attacking_fraction), (def_army, defending_fraction)]:
        _has_hero = any(get_unit_class(u) >= 2 and u['unit_count'] > 0 for u in _side_army)
        for u in _side_army:
            if get_unit_class(u) >= 2:
                continue  # Герои не теряют мораль
            base_morale = _get_stat(u, 'Мораль', 100)
            # Нет героя в армии → -30
            if not _has_hero:
                base_morale -= 30
            u['_battle_morale'] = max(0, min(100, base_morale))

    def _update_morale(army, fraction):
        """Обновляет мораль каждый раунд на основе потерь."""
        total_initial = sum(u.get('initial_count', u['unit_count']) for u in army)
        total_current = sum(u['unit_count'] for u in army)
        if total_initial == 0:
            return
        loss_pct = (total_initial - total_current) / total_initial * 100

        # Проверяем, погиб ли герой
        _hero_died = any(
            get_unit_class(u) >= 2 and u.get('initial_count', 0) > 0 and u['unit_count'] <= 0
            for u in army
        )

        for u in army:
            if u['unit_count'] <= 0 or get_unit_class(u) >= 2:
                continue
            morale = u.get('_battle_morale', 100)

            # Потери стека снижают мораль: -2 за каждые 5% потерь армии
            morale_loss = int(loss_pct / 5) * 2
            morale -= morale_loss

            # Гибель героя → -40
            if _hero_died:
                morale -= 40

            u['_battle_morale'] = max(0, min(100, morale))

    def _apply_morale_effects(army):
        """Применяет эффекты морали: воодушевление, паника, бегство."""
        for u in army:
            if u['unit_count'] <= 0 or get_unit_class(u) >= 2:
                continue
            morale = u.get('_battle_morale', 100)
            stats = u.get('units_stats', {})

            # Сбрасываем предыдущий модификатор морали
            prev_mod = u.pop('_morale_atk_mod', 1.0)
            if prev_mod != 1.0 and 'Урон' in stats:
                stats['Урон'] = stats['Урон'] / prev_mod

            # Воодушевление: мораль > 80 → +10% урон
            if morale > 80:
                mod = 1.10
            # Паника: мораль < 40 → -20% урон
            elif morale < 40:
                mod = 0.80
            else:
                mod = 1.0

            if mod != 1.0 and 'Урон' in stats:
                stats['Урон'] = stats['Урон'] * mod
            u['_morale_atk_mod'] = mod

            # Бегство: мораль < 25 → 15% шанс потерять 15% стека
            if morale < 25 and random.random() < 0.15:
                fled = max(1, int(u['unit_count'] * 0.15))
                u['unit_count'] = max(0, u['unit_count'] - fled)

    # Проверяем боевой дух для сообщения игроку
    _COUNTER_PICKS_MSG = {
        'Адепты': ['Элины', 'Север'],
        'Элины': ['Север', 'Эльфы'],
        'Вампиры': ['Адепты', 'Элины'],
        'Север': ['Вампиры', 'Эльфы'],
        'Эльфы': ['Адепты', 'Вампиры'],
    }
    _spirit_factions = []
    if conn and user_faction:
        try:
            _sc = conn.cursor()
            _sc.execute("SELECT turn_count FROM turn LIMIT 1")
            _st = _sc.fetchone()
            _s_turn = _st[0] if _st else 0
            for _sf in [attacking_fraction, defending_fraction]:
                _cpicks = _COUNTER_PICKS_MSG.get(_sf, [])
                if not _cpicks:
                    continue
                _sph = ','.join('?' * len(_cpicks))
                _sc.execute(
                    f"SELECT COUNT(*) FROM faction_victories "
                    f"WHERE faction = ? AND defeated IN ({_sph}) AND turn > ?",
                    [_sf] + _cpicks + [_s_turn - 4]
                )
                if _sc.fetchone()[0] >= 2:
                    _spirit_factions.append(_sf)
        except Exception:
            pass

    # Добавляем сообщения о боевом духе
    for _spf in _spirit_factions:
        if _spf == user_faction:
            _faction_bonus_messages.append(
                f"[color=#FFD700]Боевой дух![/color] +15% урон (победы над контрпиком)"
            )
        else:
            _faction_bonus_messages.append(
                f"[color=#FF6644]Враг воодушевлён![/color] {_spf}: +15% урон"
            )

    # Боевой цикл
    round_num = 0
    while round_num < MAX_ROUNDS:
        round_num += 1
        round_criticals = {'A': 0, 'D': 0}
        round_heroes = []

        atk_alive = [u for u in atk_army if is_unit_combat_ready(u, atk_army)]
        def_alive = [u for u in def_army if is_unit_combat_ready(u, def_army)]
        if not atk_alive or not def_alive:
            break

        # Сырые бонусы от героев 2+ класса для юнитов 1 класса
        atk_hero_bonus = calculate_hero_stat_bonus(atk_army)
        def_hero_bonus = calculate_hero_stat_bonus(def_army)

        # Стены столицы нежити: +100 атаки, +850 защиты
        if _is_undead_capital:
            def_hero_bonus = (def_hero_bonus[0] + 100,
                              def_hero_bonus[1] + 850,
                              def_hero_bonus[2])

        all_combatants = [(get_initiative(u), 'A', u) for u in atk_alive] + \
                         [(get_initiative(u), 'D', u) for u in def_alive]
        # Сортировка: сначала по инициативе (убывание), затем по атаке (убывание).
        # Это обеспечивает, что при равной инициативе юниты с большей атакой
        # (например, пленные юниты другой фракции) вступают в бой первыми.
        all_combatants.sort(key=lambda t: (-t[0], -_get_stat(t[2], 'Урон', 0)))

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
            critical_events = []

            if side == 'A':
                battle_chain(unit, target, defending_city, user_faction, conn,
                             atk_hero_bonus=atk_hero_bonus, def_hero_bonus=def_hero_bonus,
                             atk_fraction=attacking_fraction, def_fraction=defending_fraction,
                             event_log=critical_events)
            else:
                battle_chain(unit, target, defending_city, user_faction, conn,
                             atk_hero_bonus=def_hero_bonus, def_hero_bonus=atk_hero_bonus,
                             atk_fraction=defending_fraction, def_fraction=attacking_fraction,
                             event_log=critical_events)
            for own_critical, enemy_critical in critical_events:
                round_criticals[side] += int(own_critical)
                round_criticals['D' if side == 'A' else 'A'] += int(enemy_critical)

        # Проверка на вступление героев при потерях ≥85%
        for side in ['atk', 'def']:
            army = atk_army if side == 'atk' else def_army
            active_units = [u for u in army if not u.get('hero_candidate', False)]
            total_initial = sum(u['initial_count'] for u in active_units)
            total_current = sum(u['unit_count'] for u in active_units)
            losses_percent = 100.0 if total_initial == 0 else (
                (total_initial - total_current) / total_initial * 100
            )

            # Класс 3: вступает при потерях ≥85%
            hero3 = heroes3[side]
            if hero3 is not None and not hero3.get('hero_engaged', False):
                if total_initial == 0 or losses_percent >= 85:
                    hero3['hero_engaged'] = True
                    round_heroes.append({'side': side, 'unit_name': hero3['unit_name']})
                    hero3['unit_count'] = 1
                    stats = hero3.get('units_stats', {})
                    if 'Урон' in stats:
                        stats['Урон'] = int(float(stats['Урон']) * 1.5)
                    if 'Защита' in stats:
                        stats['Защита'] = int(float(stats['Защита']) * 1.5)
                    print(f"[BattleHero] Герой 3 кл. '{hero3['unit_name']}' вступил в бой! +50%")

            # Класс 4: вступает ПОСЛЕДНИМ — только если класс 3 уже вступил (или отсутствует)
            # и потери также ≥85%
            hero4 = heroes4[side]
            if hero4 is not None and not hero4.get('hero_engaged', False):
                class3_done = (hero3 is None or hero3.get('hero_engaged', False)
                               or hero3.get('unit_count', 0) <= 0)
                if class3_done and (total_initial == 0 or losses_percent >= 85):
                    hero4['hero_engaged'] = True
                    round_heroes.append({'side': side, 'unit_name': hero4['unit_name']})
                    hero4['unit_count'] = 1
                    stats = hero4.get('units_stats', {})
                    if 'Урон' in stats:
                        stats['Урон'] = int(float(stats['Урон']) * 1.5)
                    if 'Защита' in stats:
                        stats['Защита'] = int(float(stats['Защита']) * 1.5)
                    print(f"[BattleHero] Герой 4 кл. '{hero4['unit_name']}' вступил в бой! +50%")

        # Динамическая мораль: обновляем и применяем эффекты
        _update_morale(atk_army, attacking_fraction)
        _update_morale(def_army, defending_fraction)
        _apply_morale_effects(atk_army)
        _apply_morale_effects(def_army)

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
            'def_max': def_max,
            'atk_crits': round_criticals['A'],
            'def_crits': round_criticals['D'],
            'heroes': round_heroes,
        })

    # Подсчёт потерь
    for u in atk_army + def_army:
        if u.get('hero_engaged', False) or u['unit_count'] > 0 or u['initial_count'] > 0:
            u['killed_count'] = u['initial_count'] - u['unit_count']
        else:
            u['killed_count'] = 0

    # Список сообщений о фракционных бонусах для отчёта
    _faction_bonus_messages = []

    # Сообщения о боевом духе (заполняется позже, после расчёта _spirit_factions)
    # — добавляются перед возвратом результата

    # Вампиры: Вампиризм — 5% убитых врагов воскресают (в свой сезон 8.75%)
    vamp_rate = 0.05 * _season_mult('Вампиры') if _season_mult('Вампиры') > 1 else 0.05
    def _apply_vampirism(vampire_army, enemy_army, faction):
        if faction != 'Вампиры':
            return
        enemy_killed = sum(u.get('killed_count', 0) for u in enemy_army if get_unit_class(u) == 1)
        if enemy_killed <= 0:
            return
        resurrected = max(1, int(enemy_killed * vamp_rate))
        for u in vampire_army:
            if get_unit_class(u) == 1 and u['unit_count'] > 0:
                u['unit_count'] += resurrected
                u['killed_count'] = max(0, u.get('killed_count', 0) - resurrected)
                u['healed_count'] = u.get('healed_count', 0) + resurrected
                if resurrected > 1:
                    _faction_bonus_messages.append(
                        f"[color=#C71A28]Вампиризм:[/color] +{resurrected} воскрешено из врагов"
                    )
                print(f"[Вампиризм] {resurrected} врагов воскрешены как юниты Вампиров")
                break

    _apply_vampirism(atk_army, def_army, attacking_fraction)
    _apply_vampirism(def_army, atk_army, defending_fraction)

    # Эльфы: Природное исцеление — 10% своих погибших возвращаются в строй (в Лето 27.5%)
    elf_heal_rate = 0.10 * _season_mult('Эльфы') if _season_mult('Эльфы') > 1 else 0.10
    def _apply_elf_healing(army, faction):
        if faction != 'Эльфы':
            return
        total_healed = 0
        for u in army:
            if get_unit_class(u) != 1:
                continue
            killed = u.get('killed_count', 0)
            if killed <= 0:
                continue
            healed = max(1, int(killed * elf_heal_rate))
            u['unit_count'] += healed
            u['healed_count'] = u.get('healed_count', 0) + healed
            u['killed_count'] -= healed
            total_healed += healed
            print(f"[Исцеление] {healed} юнитов {u['unit_name']} вернулись в строй")
        if total_healed > 1:
            _faction_bonus_messages.append(
                f"[color=#38C252]Исцеление:[/color] +{total_healed} вернулось в строй"
            )

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

    # Записываем победу фракции для системы боевого духа
    winning_faction = attacking_fraction if winner == 'attacker' else defending_fraction
    losing_faction = defending_fraction if winner == 'attacker' else attacking_fraction
    try:
        _vc = conn.cursor()
        _vc.execute("""
            CREATE TABLE IF NOT EXISTS faction_victories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                faction TEXT NOT NULL,
                defeated TEXT NOT NULL DEFAULT '',
                turn INTEGER NOT NULL
            )
        """)
        # Миграция: добавить колонку defeated если её нет
        _vc.execute("PRAGMA table_info(faction_victories)")
        _fv_cols = {r[1] for r in _vc.fetchall()}
        if 'defeated' not in _fv_cols:
            _vc.execute("ALTER TABLE faction_victories ADD COLUMN defeated TEXT NOT NULL DEFAULT ''")
        _vc.execute("SELECT turn_count FROM turn LIMIT 1")
        _vt = _vc.fetchone()
        _v_turn = _vt[0] if _vt else 1
        _vc.execute("INSERT INTO faction_victories (faction, defeated, turn) VALUES (?, ?, ?)",
                    (winning_faction, losing_faction, _v_turn))
        # Чистим старые записи (старше 5 ходов)
        _vc.execute("DELETE FROM faction_victories WHERE turn < ?", (_v_turn - 5,))
        conn.commit()
    except Exception as e:
        print(f"[MORALE] Ошибка записи победы: {e}")

    # Эльфы: Исцеление применяется ТОЛЬКО победившей стороне
    if winner == 'attacker':
        _apply_elf_healing(atk_army, attacking_fraction)
    else:
        _apply_elf_healing(def_army, defending_fraction)

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

    # results — убитая нежить даёт x0.01 к рейтингу (1000 нежити = 10 обычных)
    UNDEAD_RATING_MULT = 0.01
    total_attacking_losses = sum(u['killed_count'] for u in visible_atk_army)
    total_defending_losses = sum(u['killed_count'] for u in visible_def_army)

    # Для рейтинга: потери нежити уменьшаются (1000 нежити = 10 обычных)
    rating_atk_enemy_losses = max(1, int(total_defending_losses * UNDEAD_RATING_MULT)) if defending_fraction == 'Нежить' else total_defending_losses
    rating_def_enemy_losses = max(1, int(total_attacking_losses * UNDEAD_RATING_MULT)) if attacking_fraction == 'Нежить' else total_attacking_losses

    try:
        update_results_table(db_connection=conn, faction=attacking_fraction,
                             units_destroyed=total_attacking_losses,
                             enemy_losses=rating_atk_enemy_losses)
        update_results_table(db_connection=conn, faction=defending_fraction,
                             units_destroyed=total_defending_losses,
                             enemy_losses=rating_def_enemy_losses)
    except Exception as e:
        print(f"[ERROR] update_results_table: {e}")

    # Persistent smoke/damage for player battles and AI battles alike.
    try:
        from city_war import record_battle
        record_battle(conn, defending_city, initial_attacker_strength,
                      initial_defender_strength, defending_fraction)
        conn.commit()
    except Exception as e:
        print(f"[SMOKE] Ошибка записи: {e}")

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
            from kivy.clock import Clock as _BattleClock

            # Копируем данные для безопасной передачи в главный поток
            _atk_army_copy = copy.deepcopy(atk_army)
            _def_army_copy = copy.deepcopy(def_army)
            _battle_rounds_copy = list(battle_rounds)
            _legacy_winner = legacy_winner
            _attacking_fraction = attacking_fraction
            _defending_fraction = defending_fraction
            _user_faction = user_faction
            _defending_city = defending_city
            _attacking_city = attacking_city
            _is_user_involved = is_user_involved
            _conn = conn
            _bonus_msgs = list(_faction_bonus_messages)

            # Картинки по приоритету:
            # Нежить → всегда изображение нежити
            # Иначе: класс 3 > класс 2 > класс 4 > класс 1
            _UNDEAD_IMG = {
                'files/army/death/king_.png',
                'files/army/death/solder.png',
                'files/army/death/zombie.png',
                'files/army/death/death.png',
                'files/army/death/banshi.png',
            }

            def _pick_battle_img(army, fraction):
                if fraction == 'Нежить':
                    # Ищем картинку любого юнита нежити, предпочтительно king_
                    for u in army:
                        img = u.get('unit_image', '')
                        if img in _UNDEAD_IMG:
                            return img
                    return 'files/army/death/king_.png'
                # Приоритет: 3 > 2 > 4 > 1
                by_class = {}
                for u in army:
                    uc = get_unit_class(u)
                    img = u.get('unit_image', '')
                    if img and uc not in by_class:
                        by_class[uc] = img
                for priority in (3, 2, 4, 1):
                    if priority in by_class:
                        return by_class[priority]
                return None

            _atk_hero_img = _pick_battle_img(atk_army, _attacking_fraction)
            _def_hero_img = _pick_battle_img(def_army, _defending_fraction)

            def _show_battle_on_main_thread(dt):
                try:
                    def show_report():
                        report_data = generate_battle_report(
                            _atk_army_copy, _def_army_copy,
                            winner=_legacy_winner,
                            attacking_fraction=_attacking_fraction,
                            defending_fraction=_defending_fraction,
                            user_faction=_user_faction,
                            city=_defending_city
                        )
                        show_battle_report(report_data, is_user_involved=_is_user_involved,
                                           user_faction=_user_faction, conn=_conn,
                                           attacking_fraction=_attacking_fraction,
                                           defending_fraction=_defending_fraction,
                                           bonus_messages=_bonus_msgs,
                                           battle_rounds=_battle_rounds_copy)

                    show_battle_animation(_battle_rounds_copy, _attacking_fraction,
                                          _defending_fraction, winner, _user_faction,
                                          _attacking_city, _defending_city,
                                          callback=show_report,
                                          atk_hero_image=_atk_hero_img,
                                          def_hero_image=_def_hero_img)
                except Exception as e:
                    print(f"[ERROR] battle animation/report (main thread): {e}")

            _BattleClock.schedule_once(_show_battle_on_main_thread, 0)
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
    from battle_presentation import side_name
    winner = side_name(winner)
    attacking_result = None
    defending_result = None
    report_data = []

    def process_army(army, side, result=None):
        for unit in army:
            initial_count = unit.get('initial_count', 0)
            final_count = unit['unit_count']
            healed = unit.get('healed_count', 0)
            # losses = чистые потери (после исцеления)
            losses = max(0, initial_count - final_count)
            # total_killed = потери до исцеления
            total_killed = max(0, unit.get('killed_count', losses + healed))
            report_data.append({
                'unit_name': unit['unit_name'],
                'initial_count': initial_count,
                'final_count': final_count,
                'losses': total_killed,
                'healed': healed,
                'side': side,
                'result': result,
                'city': city,
                'unit_image': unit.get('unit_image', ''),
                'unit_class': get_unit_class(unit),
                'net_losses': max(0, total_killed - healed),
                'reinforcements': max(0, final_count - initial_count + max(0, total_killed - healed)),
                'winner': winner,
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


def show_battle_report(report_data, is_user_involved=False, user_faction=None, conn=None,
                       attacking_fraction=None, defending_fraction=None, bonus_messages=None, battle_rounds=None):
    """Present the immutable after-action data through the shared battle UI."""
    if not report_data:
        return None
    from battle_ui import BattleReport
    popup = BattleReport(report_data, user_faction, attacking_fraction, defending_fraction, bonus_messages, battle_rounds)
    if is_user_involved and user_faction and conn is not None:
        is_victory = any(item.get('result') in ('\u041f\u043e\u0431\u0435\u0434\u0430', 'VICTORY') for item in report_data)
        update_dossier_battle_stats(conn, user_faction, is_victory)
    popup.open()
    return popup


def show_battle_animation(battle_rounds, attacking_fraction, defending_fraction, winner,
                          user_faction, attacking_city, defending_city, callback=None,
                          atk_hero_image=None, def_hero_image=None):
    """Replay real rounds; skip/dismiss opens the report exactly once."""
    from battle_ui import BattleViewer
    popup = BattleViewer(battle_rounds, attacking_fraction, defending_fraction, winner,
                         user_faction, attacking_city, defending_city, callback,
                         atk_hero_image, def_hero_image)
    popup.open()
    return popup


def update_garrisons_after_battle(winner, attacking_city, defending_city,
                                  attacking_army, defending_army,
                                  attacking_fraction, defending_fraction, conn):

    """Обновляет гарнизоны после боя."""
    _faction_hex_colors = {
        'Север': '#4085EB', 'Эльфы': '#38C252', 'Вампиры': '#C71A28',
        'Адепты': '#5A5A61', 'Элины': '#F28014', 'Нежить': '#33BF99',
        'Мятежники': '#888888', 'Нейтрал': '#AAAAAA'
    }

    def _determine_unit_faction(unit, conn):
        """Определяет фракцию юнита по таблице units."""
        try:
            _c = conn.cursor()
            _c.execute("SELECT faction FROM units WHERE unit_name = ?", (unit['unit_name'],))
            _r = _c.fetchone()
            return _r[0] if _r else None
        except Exception:
            return None

    def _determine_army_owner(army, conn, fallback_fraction):
        """Определяет фракцию-владельца армии по живым юнитам.
        Если все юниты одной фракции — возвращает её.
        Иначе — fallback_fraction."""
        factions = {}
        for u in army:
            if u['unit_count'] > 0:
                uf = _determine_unit_faction(u, conn)
                if uf:
                    factions[uf] = factions.get(uf, 0) + u['unit_count']
        if not factions:
            return fallback_fraction
        if len(factions) == 1:
            return list(factions.keys())[0]
        return fallback_fraction

    try:
        cursor = conn.cursor()
        if winner == 'attacking':
            # Победила атакующая сторона
            cursor.execute("DELETE FROM garrisons WHERE city_name = ?", (defending_city,))

            for unit in attacking_army:
                if unit['unit_count'] > 0:
                    _u_exp = unit.get('experience', 0)
                    print(f"[GARRISON] Перенос '{unit['unit_name']}' (x{unit['unit_count']}, exp={_u_exp}) в {defending_city}")
                    cursor.execute("""
                        INSERT INTO garrisons (city_name, unit_name, unit_count, unit_image, experience)
                        VALUES (?, ?, ?, ?, ?)
                        ON CONFLICT(city_name, unit_name) DO UPDATE SET
                            unit_count = excluded.unit_count,
                            unit_image = excluded.unit_image,
                            experience = excluded.experience
                    """, (
                        defending_city,
                        unit['unit_name'],
                        unit['unit_count'],
                        unit.get('unit_image', ''),
                        _u_exp
                    ))
            # Город переходит к фракции юнитов атакующей армии
            _actual_owner = _determine_army_owner(attacking_army, conn, attacking_fraction)
            cursor.execute("UPDATE cities SET faction = ? WHERE name = ?", (_actual_owner, defending_city))
            # Все здания разрушаются при захвате города — отстраивать заново
            cursor.execute("DELETE FROM buildings WHERE city_name = ?", (defending_city,))
            # Обновляем цвет фракции города
            _new_color = _faction_hex_colors.get(_actual_owner, '#AAAAAA')
            cursor.execute("UPDATE cities SET color_faction = ? WHERE name = ?", (_new_color, defending_city))
            print(f"[CAPTURE] {defending_city} захвачен фракцией {_actual_owner} (атака из {attacking_city})")

        else:
            # Победила обороняющаяся сторона
            cursor.execute("DELETE FROM garrisons WHERE city_name = ?", (defending_city,))

            # Проверяем: остались ли юниты фракции города?
            _city_faction_alive = False
            # {faction: (max_class, total_power)} — класс + суммарная мощь
            _other_factions = {}
            for unit in defending_army:
                if unit['unit_count'] > 0:
                    uf = _determine_unit_faction(unit, conn)
                    if uf == defending_fraction:
                        _city_faction_alive = True
                    elif uf:
                        uc = get_unit_class(unit)
                        atk = _get_stat(unit, 'Урон', 0) * unit['unit_count']
                        dfs = _get_stat(unit, 'Защита', 0) * unit['unit_count']
                        power = atk + dfs
                        prev = _other_factions.get(uf, (0, 0))
                        _other_factions[uf] = (max(prev[0], uc), prev[1] + power)
            # Выбираем фракцию-наследника: приоритет по классу, при равном — по мощи
            _heir_faction = None
            if _other_factions:
                _heir_faction = max(_other_factions,
                                    key=lambda f: (_other_factions[f][0], _other_factions[f][1]))

            # Вставляем выживших обратно
            for unit in defending_army:
                if unit['unit_count'] > 0:
                    _u_exp = unit.get('experience', 0)
                    cursor.execute("""
                        INSERT INTO garrisons (city_name, unit_name, unit_count, unit_image, experience)
                        VALUES (?, ?, ?, ?, ?)
                        ON CONFLICT(city_name, unit_name) DO UPDATE SET
                            unit_count = excluded.unit_count,
                            unit_image = excluded.unit_image,
                            experience = excluded.experience
                    """, (
                        defending_city,
                        unit['unit_name'],
                        unit['unit_count'],
                        unit.get('unit_image', ''),
                        _u_exp
                    ))

            # Если все юниты фракции города погибли, но выжили юниты/герои другой фракции —
            # город переходит к фракции с наивысшим классом выжившего юнита
            if not _city_faction_alive and _heir_faction:
                cursor.execute("UPDATE cities SET faction = ? WHERE name = ?",
                               (_heir_faction, defending_city))
                _new_color = _faction_hex_colors.get(_heir_faction, '#AAAAAA')
                cursor.execute("UPDATE cities SET color_faction = ? WHERE name = ?",
                               (_new_color, defending_city))
                print(f"[CAPTURE] {defending_city} перешёл к {_heir_faction} (юниты города погибли, выжили чужие)")

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

        # === Обновление опыта: +1 за каждую победу (атака И защита) ===
        # 1 победа = Воин (+5%), 3 победы = Ветеран (+15%), 7 побед = Элита (+25%)
        try:
            if winner == 'attacking':
                _win_city = defending_city
                _win_army = attacking_army
                _side = 'атакующий'
            else:
                _win_city = defending_city
                _win_army = defending_army
                _side = 'защитник'

            # Начисляем опыт юнитам 1 класса победившей стороны
            _exp_count = 0
            for u in _win_army:
                if get_unit_class(u) == 1 and u['unit_count'] > 0:
                    cursor.execute("""
                        UPDATE garrisons SET experience = COALESCE(experience, 0) + 1
                        WHERE city_name = ? AND unit_name = ? AND unit_count > 0
                    """, (_win_city, u['unit_name']))
                    _exp_count += 1
                    print(f"[EXP] +1 побед '{u['unit_name']}' в {_win_city} (сторона: {_side})")
            if _exp_count == 0:
                print(f"[EXP] Нет юнитов 1 класса для начисления опыта ({_side}, {_win_city})")
            else:
                print(f"[EXP] +1 опыт {_exp_count} юнитам ({_side}) в {_win_city}")
        except Exception as e:
            print(f"[EXP] Ошибка обновления опыта: {e}")

        # Меч Короля Мёртвых: при захвате столицы нежити
        if winner == 'attacking' and defending_fraction == 'Нежить':
            try:
                # Проверяем: это столица нежити?
                _is_capital = False
                try:
                    cursor.execute("SELECT capital_city FROM undead_invasion WHERE id = 1")
                    _cap = cursor.fetchone()
                    _is_capital = _cap and _cap[0] == defending_city
                except Exception:
                    pass
                if _is_capital:
                        _sword_owner = _determine_army_owner(attacking_army, conn, attacking_fraction)
                        # Создаём артефакт
                        cursor.execute("SELECT MAX(id) FROM artifacts")
                        _max_id = cursor.fetchone()[0] or 0
                        _sword_id = _max_id + 1
                        cursor.execute("""
                            INSERT INTO artifacts (id, attack, defense, season_name, image_url, name, cost, artifact_type, is_created)
                            VALUES (?, 4000, 4000, 'Все', 'files/pict/artifacts/king_death/0m_king_death.png',
                                    'Меч Короля Мёртвых', 10000000, 0, 1)
                        """, (_sword_id,))
                        print(f"[UNDEAD SWORD] Меч Короля Мёртвых создан! ID={_sword_id}, фракция {_sword_owner}")

                        # Определяем фракцию игрока
                        cursor.execute("SELECT faction_name FROM user_faction")
                        _uf_row = cursor.fetchone()
                        _user_f = _uf_row[0] if _uf_row else None

                        if _sword_owner == _user_f:
                            # Игрок — показать попап с предложением
                            try:
                                from kivy.clock import Clock as _SwordClock
                                _SwordClock.schedule_once(
                                    lambda dt: _show_sword_offer(conn, _sword_id), 1.0)
                            except Exception:
                                pass
                        else:
                            # AI — автоматически экипировать
                            try:
                                _ai_equip_sword(conn, _sword_owner, _sword_id)
                            except Exception as _ae:
                                print(f"[UNDEAD SWORD] AI equip error: {_ae}")
            except Exception as e:
                print(f"[UNDEAD SWORD] Ошибка: {e}")

        conn.commit()

    except sqlite3.Error as e:
        print(f"Ошибка при обновлении гарнизонов: {e}")


def _show_sword_offer(conn, sword_id):
    """Попап предложения Меча Короля Мёртвых игроку."""
    from kivy.uix.popup import Popup
    from kivy.uix.boxlayout import BoxLayout
    from kivy.uix.label import Label
    from kivy.uix.button import Button
    from kivy.uix.image import Image
    from kivy.metrics import dp, sp
    from kivy.graphics import Color, RoundedRectangle
    from kivy.utils import platform

    _is_m = platform in ('android', 'ios')

    content = BoxLayout(orientation='vertical', padding=[dp(14), dp(10)], spacing=dp(8))
    with content.canvas.before:
        Color(0.06, 0.07, 0.11, 1)
        content._bg = RoundedRectangle(pos=content.pos, size=content.size, radius=[dp(12)])
    content.bind(pos=lambda i, v: setattr(i._bg, 'pos', v),
                 size=lambda i, v: setattr(i._bg, 'size', v))

    # Заголовок
    title = Label(text="[b]Трофей: Меч Короля Мёртвых[/b]", markup=True,
                  font_size=sp(17) if not _is_m else sp(15),
                  color=(0.85, 0.25, 0.25, 1),
                  size_hint_y=None, height=dp(32), halign='center')
    title.bind(size=lambda i, s: setattr(i, 'text_size', (s[0], None)))
    content.add_widget(title)

    # Изображение
    img = Image(source='files/pict/artifacts/king_death/0m_king_death.png',
                size_hint=(1, 0.4), allow_stretch=True, keep_ratio=True)
    content.add_widget(img)

    # Характеристики
    stats = Label(
        text="[color=#FF6644]Атака: +4000%[/color]\n[color=#4488FF]Защита: +4000%[/color]\n"
             "[color=#AAAAAA]Слот: Оружие[/color]\n[color=#66CC66]Трофей — бесплатно[/color]\n\n"
             "[color=#AAAAAA]Заменит текущее оружие героя[/color]",
        markup=True, font_size=sp(13) if not _is_m else sp(11),
        halign='center', valign='middle',
        size_hint_y=None, height=dp(100),
        color=(0.9, 0.9, 0.9, 1)
    )
    stats.bind(size=lambda i, s: setattr(i, 'text_size', (s[0], None)))
    content.add_widget(stats)

    from kivy.uix.widget import Widget
    content.add_widget(Widget(size_hint_y=1))

    # Кнопки
    btn_row = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(10))

    accept_btn = Button(text="Взять", bold=True,
                        font_size=sp(14) if not _is_m else sp(12),
                        background_normal='', background_color=(0, 0, 0, 0), color=(1, 1, 1, 1))
    with accept_btn.canvas.before:
        Color(0.15, 0.45, 0.2, 0.95)
        accept_btn._rr = RoundedRectangle(pos=accept_btn.pos, size=accept_btn.size, radius=[dp(8)])
    accept_btn.bind(pos=lambda i, v: setattr(i._rr, 'pos', v),
                    size=lambda i, v: setattr(i._rr, 'size', v))

    decline_btn = Button(text="Отказаться", bold=True,
                         font_size=sp(14) if not _is_m else sp(12),
                         background_normal='', background_color=(0, 0, 0, 0), color=(0.9, 0.9, 0.9, 1))
    with decline_btn.canvas.before:
        Color(0.35, 0.15, 0.15, 0.95)
        decline_btn._rr = RoundedRectangle(pos=decline_btn.pos, size=decline_btn.size, radius=[dp(8)])
    decline_btn.bind(pos=lambda i, v: setattr(i._rr, 'pos', v),
                     size=lambda i, v: setattr(i._rr, 'size', v))

    popup = Popup(title="", content=content,
                  size_hint=(0.75 if not _is_m else 0.9, 0.7 if not _is_m else 0.65),
                  pos_hint={'center_x': 0.5, 'center_y': 0.5},
                  auto_dismiss=False,
                  background_color=(0.04, 0.05, 0.09, 0.98), separator_height=0)

    def _accept(*a):
        popup.dismiss()
        try:
            cur = conn.cursor()
            # Ищем фракцию и героя 3 класса игрока
            cur.execute("SELECT faction_name FROM user_faction")
            _pf = cur.fetchone()
            if not _pf:
                return
            player_faction = _pf[0]
            cur.execute("""
                SELECT u.unit_name FROM units u
                JOIN garrisons g ON u.unit_name = g.unit_name
                WHERE u.faction = ? AND u.unit_class = 3 AND g.unit_count > 0
                LIMIT 1
            """, (player_faction,))
            _hero = cur.fetchone()
            if not _hero:
                print("[UNDEAD SWORD] Нет героя 3 класса для экипировки")
                return
            hero_name = _hero[0]
            # Удаляем старое оружие (slot_type = '0')
            cur.execute("""
                SELECT artifact_id FROM hero_equipment
                WHERE faction_name = ? AND slot_type = '0'
            """, (player_faction,))
            _old = cur.fetchone()
            if _old:
                cur.execute("DELETE FROM hero_equipment WHERE faction_name = ? AND slot_type = '0'",
                            (player_faction,))
                cur.execute("DELETE FROM artifacts WHERE id = ?", (_old[0],))
            # Получаем image_url меча
            cur.execute("SELECT image_url FROM artifacts WHERE id = ?", (sword_id,))
            _img_row = cur.fetchone()
            _sword_img = _img_row[0] if _img_row else 'files/pict/artifacts/king_death/0m_king_death.png'
            # Экипируем меч (бесплатно — трофей)
            cur.execute("""
                INSERT INTO hero_equipment (faction_name, hero_name, slot_type, artifact_id, image_url)
                VALUES (?, ?, '0', ?, ?)
            """, (player_faction, hero_name, sword_id, _sword_img))
            conn.commit()
            # Применяем бонусы через стандартную систему сезонов
            try:
                from seasons import SeasonManager
                _sm = SeasonManager(conn)
                _sm.update_season_bonuses(conn)
            except Exception as _se:
                print(f"[UNDEAD SWORD] Пересчёт через SeasonManager: {_se}")
            print(f"[UNDEAD SWORD] Меч экипирован на {hero_name} (фракция {player_faction})")
        except Exception as e:
            print(f"[UNDEAD SWORD] Ошибка экипировки: {e}")
            import traceback
            traceback.print_exc()

    accept_btn.bind(on_release=_accept)
    decline_btn.bind(on_release=lambda *a: popup.dismiss())

    btn_row.add_widget(accept_btn)
    btn_row.add_widget(decline_btn)
    content.add_widget(btn_row)

    popup.open()


def _ai_equip_sword(conn, faction, sword_id):
    """AI автоматически экипирует Меч Короля Мёртвых."""
    cur = conn.cursor()
    cur.execute("""
        SELECT u.unit_name FROM units u
        JOIN garrisons g ON u.unit_name = g.unit_name
        WHERE u.faction = ? AND u.unit_class = 3 AND g.unit_count > 0
        LIMIT 1
    """, (faction,))
    _hero = cur.fetchone()
    if not _hero:
        return
    hero_name = _hero[0]
    # Удаляем старое оружие
    cur.execute("SELECT artifact_id FROM ai_hero_equipment WHERE hero_name = ? AND slot = 0", (hero_name,))
    _old = cur.fetchone()
    if _old:
        cur.execute("DELETE FROM ai_hero_equipment WHERE hero_name = ? AND slot = 0", (hero_name,))
        cur.execute("DELETE FROM artifacts_ai WHERE id = ?", (_old[0],))
    # Создаём копию в artifacts_ai и экипируем
    cur.execute("SELECT MAX(id) FROM artifacts_ai")
    _max = cur.fetchone()[0] or 0
    _ai_id = _max + 1
    cur.execute("""
        INSERT INTO artifacts_ai (id, attack, defense, season_name, image_url, name, cost, artifact_type)
        VALUES (?, 4000, 4000, 'Все', 'files/pict/artifacts/king_death/0m_king_death.png',
                'Меч Короля Мёртвых', 10000000, 0)
    """, (_ai_id,))
    cur.execute("INSERT INTO ai_hero_equipment (hero_name, slot, artifact_id) VALUES (?, 0, ?)",
                (hero_name, _ai_id))
    conn.commit()
    # Применяем бонусы через стандартную систему
    try:
        from seasons import SeasonManager
        _sm = SeasonManager(conn)
        _sm.update_season_bonuses(conn)
    except Exception as _se:
        print(f"[UNDEAD SWORD] AI пересчёт: {_se}")
    print(f"[UNDEAD SWORD] AI {faction}: Меч экипирован на {hero_name}")


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
