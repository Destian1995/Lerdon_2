# Дизайн-система Lerdon Legends
from kivy.metrics import dp, sp
from kivy.utils import get_color_from_hex

# ─── Цветовая палитра (базовые цвета) ────────────────────────────
PRIMARY_COLORS = {
    'primary': '#2E3440',      # Темно-синий (Nord)
    'secondary': '#4C566A',    # Серый
    'accent': '#88C0D0',       # Светло-голубой
    'success': '#A3BE8C',      # Зеленый
    'warning': '#EBCB8B',      # Желтый
    'error': '#BF616A',        # Красный
    'background': '#ECEFF4',   # Светло-серый фон
    'surface': '#FFFFFF',      # Белый для карточек
}

# ─── Семантические цвета (для UI-элементов) ──────────────────────
SEMANTIC_COLORS = {
    # Фоны
    'bg_dark': '#121212',
    'bg_card': '#1E1E1E',
    'bg_input': '#2A2A2A',
    'bg_overlay': '#000000B0',

    # Текст
    'text_white': '#FFFFFF',
    'text_light': '#E0E0E0',
    'text_muted': '#AAAAAA',
    'text_disabled': '#666666',

    # Действия
    'action_primary': '#4CAF50',
    'action_danger': '#E53E3E',
    'action_info': '#2196F3',
    'action_gold': '#FFD700',

    # Статусы
    'status_war': '#FF4444',
    'status_peace': '#38A169',
    'status_neutral': '#888888',
    'status_ally': '#4085EB',

    # Границы
    'border_light': '#333333',
    'border_accent': '#BB86FC',
    'border_muted': '#444444',

    # Accent / highlight
    'highlight': '#BB86FC',
    'highlight_secondary': '#03DAC6',
}

# ─── Темы (светлая/темная) ────────────────────────────────────────
THEMES = {
    'light': {
        'bg_primary': '#ECEFF4',
        'bg_secondary': '#FFFFFF',
        'text_primary': '#2E3440',
        'text_secondary': '#4C566A',
        'border': '#D8DEE9'
    },
    'dark': {
        'bg_primary': '#2E3440',
        'bg_secondary': '#3B4252',
        'text_primary': '#ECEFF4',
        'text_secondary': '#D8DEE9',
        'border': '#4C566A'
    }
}

# ─── Типографика ──────────────────────────────────────────────────
TYPOGRAPHY = {
    'h1': {'size': 32, 'weight': 'bold'},
    'h2': {'size': 24, 'weight': 'bold'},
    'h3': {'size': 20, 'weight': 'medium'},
    'body': {'size': 16, 'weight': 'normal'},
    'caption': {'size': 14, 'weight': 'normal'},
    'small': {'size': 12, 'weight': 'normal'},
    'button': {'size': 16, 'weight': 'medium'}
}

# Готовые sp-значения для прямого использования
FONT = {
    'h1': sp(32),
    'h2': sp(24),
    'h3': sp(20),
    'body': sp(16),
    'caption': sp(14),
    'small': sp(12),
    'button': sp(16),
}

# ─── Отступы и интервалы ──────────────────────────────────────────
SPACING = {
    'xxs': dp(2),
    'xs': dp(4),
    'sm': dp(8),
    'md': dp(12),
    'lg': dp(16),
    'xl': dp(24),
    'xxl': dp(32),
}

# ─── Размеры элементов ───────────────────────────────────────────
SIZES = {
    'button_height': dp(48),
    'button_height_sm': dp(36),
    'icon_sm': dp(24),
    'icon_md': dp(36),
    'icon_lg': dp(48),
    'card_radius': dp(12),
    'button_radius': dp(24),
    'input_height': dp(44),
    'toolbar_height': dp(56),
    'tab_height': dp(48),
}

# ─── Тени ─────────────────────────────────────────────────────────
SHADOWS = {
    'sm': {'offset': (dp(1), dp(-1)), 'color': (0, 0, 0, 0.15)},
    'md': {'offset': (dp(2), dp(-2)), 'color': (0, 0, 0, 0.20)},
    'lg': {'offset': (dp(4), dp(-4)), 'color': (0, 0, 0, 0.30)},
}

# ─── Цвета фракций ───────────────────────────────────────────────
FACTION_COLORS = {
    'Север': {
        'primary': (0.25, 0.52, 0.92, 1),
        'secondary': (0.12, 0.32, 0.72, 1),
        'glow': (0.40, 0.68, 1.00, 0.55),
        'hex': '#4085EB',
    },
    'Эльфы': {
        'primary': (0.22, 0.76, 0.32, 1),
        'secondary': (0.10, 0.50, 0.20, 1),
        'glow': (0.38, 1.00, 0.52, 0.55),
        'hex': '#38C252',
    },
    'Вампиры': {
        'primary': (0.78, 0.10, 0.16, 1),
        'secondary': (0.50, 0.05, 0.10, 1),
        'glow': (1.00, 0.20, 0.30, 0.55),
        'hex': '#C71A28',
    },
    'Адепты': {
        'primary': (0.35, 0.35, 0.38, 1),
        'secondary': (0.22, 0.22, 0.25, 1),
        'glow': (0.50, 0.50, 0.55, 0.55),
        'hex': '#5A5A61',
    },
    'Элины': {
        'primary': (0.95, 0.50, 0.08, 1),
        'secondary': (0.75, 0.35, 0.04, 1),
        'glow': (1.00, 0.65, 0.20, 0.55),
        'hex': '#F28014',
    },
    'Нежить': {
        'primary': (0.20, 0.75, 0.60, 1),
        'secondary': (0.10, 0.50, 0.40, 1),
        'glow': (0.25, 0.85, 0.70, 0.55),
        'hex': '#33BF99',
    },
}

# ─── Константы анимаций ───────────────────────────────────────────
ANIMATION = {
    'fast':       0.15,
    'normal':     0.30,
    'slow':       0.55,
    'very_slow':  1.10,
    'bounce':     'out_elastic',
    'smooth':     'out_cubic',
    'ease_in':    'in_quad',
    'ease_out':   'out_quad',
    'linear':     'linear',
}


# ─── Утилиты ─────────────────────────────────────────────────────
def color(name):
    """Получить цвет из SEMANTIC_COLORS или PRIMARY_COLORS как rgba-кортеж.

    Использование: color('action_primary') -> (0.29, 0.68, 0.31, 1)
    """
    hex_val = SEMANTIC_COLORS.get(name) or PRIMARY_COLORS.get(name)
    if hex_val is None:
        raise KeyError(f"Цвет '{name}' не найден в дизайн-системе")
    return get_color_from_hex(hex_val)
