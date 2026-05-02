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