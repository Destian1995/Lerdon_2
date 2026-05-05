# 🎨 Дизайн-система Lerdon Legends

## Цветовая палитра
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

## Темы (светлая/темная)
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

## Типографика
TYPOGRAPHY = {
    'h1': {'size': 32, 'weight': 'bold'},
    'h2': {'size': 24, 'weight': 'bold'},
    'h3': {'size': 20, 'weight': 'medium'},
    'body': {'size': 16, 'weight': 'normal'},
    'caption': {'size': 14, 'weight': 'normal'},
    'button': {'size': 16, 'weight': 'medium'}
}

## Цвета фракций
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
        'primary': (0.62, 0.22, 0.88, 1),
        'secondary': (0.40, 0.10, 0.60, 1),
        'glow': (0.80, 0.40, 1.00, 0.55),
        'hex': '#9E38E0',
    },
    'Элины': {
        'primary': (0.92, 0.70, 0.10, 1),
        'secondary': (0.70, 0.50, 0.04, 1),
        'glow': (1.00, 0.90, 0.28, 0.55),
        'hex': '#EBB31A',
    },
}

## Константы анимаций
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