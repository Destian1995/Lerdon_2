"""Общие утилиты проекта Lerdon Legends."""

import math


def format_number(number):
    """Форматирует число с добавлением приставок. Всегда округляет вниз (floor)."""
    if not isinstance(number, (int, float)):
        return str(number)
    if number == 0:
        return "0"

    absolute = abs(number)
    sign = -1 if number < 0 else 1

    suffixes = [
        (1e36, "андец."),
        (1e33, "децил."),
        (1e30, "нонил."),
        (1e27, "октил."),
        (1e24, "септил."),
        (1e21, "секст."),
        (1e18, "квинт."),
        (1e15, "квадр."),
        (1e12, "трлн."),
        (1e9,  "млрд."),
        (1e6,  "млн."),
        (1e3,  "тыс."),
    ]

    for threshold, suffix in suffixes:
        if absolute >= threshold:
            value = sign * absolute / threshold
            # Округляем вниз до 1 знака после запятой
            floored = math.floor(abs(value) * 10) / 10
            if value < 0:
                floored = -floored
            return f"{floored:.1f} {suffix}"

    # Для чисел < 1000 — целое число (без дробной части)
    return f"{int(number)}"


def plural(n, one, few, many):
    """Склонение слова по числу: plural(1,'город','города','городов') -> 'город'"""
    n = abs(int(n))
    if 11 <= n % 100 <= 19:
        return many
    r = n % 10
    if r == 1:
        return one
    if 2 <= r <= 4:
        return few
    return many


def city_word(n):
    """Возвращает '1 город', '3 города', '5 городов' и т.д."""
    return f"{n} {plural(n, 'город', 'города', 'городов')}"


def warrior_word(n):
    """Возвращает '1 воин', '3 воина', '100 воинов' и т.д."""
    return f"{format_number(n)} {plural(n, 'воин', 'воина', 'воинов')}"


def parse_formatted_number(formatted_str):
    """Преобразует отформатированную строку с приставкой обратно в число."""
    multipliers = {
        'андец': 1e36,
        'децил': 1e33,
        'нонил': 1e30,
        'октил': 1e27,
        'септил': 1e24,
        'секст': 1e21,
        'квинт': 1e18,
        'квадр': 1e15,
        'трлн': 1e12,
        'млрд': 1e9,
        'млн': 1e6,
        'тыс': 1e3,
    }

    try:
        cleaned = formatted_str.replace(',', '.').strip()
        parts = cleaned.split()
        number_part = parts[0]
        suffix = parts[1].rstrip('.').lower() if len(parts) > 1 else ''

        base_value = float(number_part)

        for key in multipliers:
            if suffix.startswith(key.lower()):
                return base_value * multipliers[key]

        return base_value

    except (ValueError, IndexError, AttributeError):
        return float('nan')
