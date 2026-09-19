import os
from kivy.graphics import PopMatrix, PushMatrix
from kivy.uix.checkbox import CheckBox
from kivy.uix.spinner import SpinnerOption
from kivy.metrics import dp

from db_lerdon_connect import *
from seasons import SeasonManager
from utils.helpers import format_number

from ui_components import show_message as show_popup_message

def load_artifacts_from_db(faction):
    """Загружает список артефактов из таблицы artifacts."""
    artifacts = []
    try:
        cursor = faction.conn.cursor()
        # Выбираем только нужные столбцы
        cursor.execute('''
        SELECT id, attack, defense, season_name, image_url, name, cost, artifact_type, is_created
        FROM artifacts
        ''')
        rows = cursor.fetchall()
        for row in rows:
            artifact = {
                "id": row[0],
                "attack": row[1] if row[1] is not None else 0,
                "defense": row[2] if row[2] is not None else 0,
                "season_name": row[3] if row[3] is not None else "",
                "image_url": row[4] if row[4] is not None else "files/pict/artifacts/default.png",
                "name": row[5] if row[5] is not None else "",
                "cost": row[6] if row[6] is not None else 0,
                "artifact_type": row[7] if row[7] is not None else -1,
                "is_created": row[8] if len(row) > 8 and row[8] is not None else 0
            }
            # Проверяем, есть ли какие-то значимые статы (attack или defense > 0)
            if artifact['attack'] != 0 or artifact['defense'] != 0:
                artifacts.append(artifact)
    except sqlite3.Error as e:
        print(f"Ошибка при загрузке артефактов: {e}")
    return artifacts

def load_hero_equipment_from_db(faction):
    """
    Загружает текущую экипировку героя.
    Теперь включает image_url и координаты pos_x, pos_y.
    Возвращает словарь, где ключ - slot_type, а значение - словарь с 'id', 'image_url', 'pos_x', 'pos_y'.
    Если координаты NULL, они будут None.
    """
    equipment = {}
    try:
        cursor = faction.conn.cursor()
        # Добавлены pos_x, pos_y в SELECT
        cursor.execute('''
            SELECT slot_type, artifact_id, image_url, pos_x, pos_y
            FROM hero_equipment
            WHERE faction_name = ?
        ''', (faction.faction,))
        rows = cursor.fetchall()
        for slot_type, artifact_id, image_url, pos_x, pos_y in rows:
            # Сохраняем всю информацию, включая координаты (даже если они None)
            equipment[slot_type] = {
                "id": artifact_id,
                "image_url": image_url,
                "pos_x": pos_x, # Может быть None
                "pos_y": pos_y  # Может быть None
            }
    except sqlite3.Error as e:
        print(f"Ошибка при загрузке экипировки героя: {e}")
    return equipment

def save_hero_equipment_to_db(faction, slot_type, artifact_id, season_manager, pos_x=None, pos_y=None):
    """
    Обновляет экипировку героя в БД, устанавливая artifact_id, image_url и координаты для заданного слота.
    """
    try:
        cursor = faction.conn.cursor()

        # Получаем image_url для артефакта
        cursor.execute("SELECT image_url FROM artifacts WHERE id = ?", (artifact_id,))
        row = cursor.fetchone()
        image_url = row[0] if row and row[0] else "files/pict/artifacts/default.png"

        print(f"[DEBUG] Подготовка к обновлению экипировки: faction={faction.faction}, slot_type={slot_type}, artifact_id={artifact_id}")

        # Обновляем запись, включая координаты
        cursor.execute('''
            UPDATE hero_equipment 
            SET artifact_id = ?, image_url = ?, pos_x = ?, pos_y = ?
            WHERE faction_name = ? AND slot_type = ?
        ''', (artifact_id, image_url, pos_x, pos_y, faction.faction, slot_type))

        rows_affected = cursor.rowcount
        print(f"[DEBUG] Затронуто строк: {rows_affected}")

        faction.conn.commit()

        # Проверяем, что запись действительно обновлена
        verify_cursor = faction.conn.cursor()
        verify_cursor.execute("SELECT artifact_id, image_url FROM hero_equipment WHERE faction_name = ? AND slot_type = ?",
                              (faction.faction, slot_type))
        result = verify_cursor.fetchone()
        if result:
            print(f"[DEBUG] Проверка после обновления: artifact_id={result[0]}, image_url={result[1]}")
        else:
            print(f"[ERROR] Запись не найдена после обновления!")

        # Применяем бонусы артефактов через переданный экземпляр SeasonManager
        if season_manager:
            season_manager.apply_artifact_bonuses(faction.conn)
            print(f"[SUCCESS] Экипировка героя обновлена: {slot_type}, artifact_id: {artifact_id}")
        else:
            print(f"[WARNING] SeasonManager не передан, бонусы не применены")

    except sqlite3.Error as e:
        print(f"[ERROR] save_hero_equipment_to_db: Ошибка при обновлении экипировки героя: {e}")
        import traceback
        traceback.print_exc()
        try:
            faction.conn.rollback()
        except:
            pass

def load_hero_image_from_db(faction):
    """
    Загружает изображение героя из таблицы garrisons, предварительно проверив faction героя через таблицу units.
    """
    try:
        cursor = faction.conn.cursor()

        # Сначала определяем faction героя через таблицу units и сравниваем с faction игрока
        cursor.execute('''
            SELECT DISTINCT g.unit_image FROM garrisons g
            LEFT JOIN units u ON g.unit_name = u.unit_name
            WHERE u.faction = ? AND u.unit_class = "3"
            LIMIT 1
        ''', (faction.faction,))  # Добавлена запятая здесь
        row = cursor.fetchone()
        print('Изображение героя:', row)
        if row and row[0]:
            return row[0]
        else:
            return "files/pict/hero/default_image.png"

    except sqlite3.Error as e:
        print(f"Ошибка при загрузке изображения героя: {e}")
        return "files/pict/hero/default_image.png"

def format_artifact_description(artifact):
    """
    Формирует строку описания артефакта на основе его характеристик.
    """
    stat_map = {
        'attack': 'Атака',
        'defense': 'Защита',
        'health': 'Здоровье'
    }
    stats = []
    for key, label in stat_map.items():
        value = artifact.get(key, 0)
        if value and value != 0:
            # Учитываем множитель сезона, если он не равен 1.0
            multiplier = artifact.get('season_bonus_multiplier', 1.0)
            if multiplier != 1.0:
                effective_value = value * multiplier
                # Округляем до целого, если результат целый, иначе до 1 знака после запятой
                if effective_value.is_integer():
                    effective_value = int(effective_value)
                else:
                    effective_value = round(effective_value, 1)
                stats.append(f"{label} {effective_value}%")
            else:
                stats.append(f"{label} {value}%")

    if not stats:
        return None  # Пропустить артефакт, если все характеристики нулевые

    # Формируем суффикс для времени действия бонуса
    season = artifact.get('season_name')
    if season:
        suffix = f"Сезон артефакта: {season}"
    else:
        suffix = "Всегда"

    return f"{', '.join(stats)} {suffix}"

def create_artifact_button_style(btn):
    """Создает стиль для строки артефакта."""
    with btn.canvas.before:
        Color(0.2, 0.2, 0.2, 1) # Темно-серый фон
        btn.rect = RoundedRectangle(pos=btn.pos, size=btn.size, radius=[10])
    def update_rect(instance, value):
        instance.rect.pos = instance.pos
        instance.rect.size = instance.size
    btn.bind(pos=update_rect, size=update_rect)
    return btn


def load_hero_stats_from_db(faction):
    """
    Загружает базовые характеристики героя.
    Сначала проверяет наличие героя в таблице garrisons, связанного с фракцией игрока.
    Если герой найден, загружает его характеристики из таблицы units.
    Герой определяется как юнит с unit_class = '3'.
    """
    stats = {
        "attack": 0,
        "defense": 0,
        "durability": 0, # Или health, в зависимости от вашей БД

    }

    try:
        cursor = faction.conn.cursor()

        cursor.execute('''
            SELECT DISTINCT g.unit_name 
            FROM garrisons g
            LEFT JOIN units u ON g.unit_name = u.unit_name
            WHERE u.faction = ? AND u.unit_class = "3"
            LIMIT 1
        ''', (faction.faction,))

        row = cursor.fetchone()

        if row:
            hero_unit_name = row[0]
            print(f"Найден герой в garrisons/units: {hero_unit_name} для фракции {faction.faction}")

            # 2. Загрузить характеристики найденного героя из таблицы units
            cursor.execute('''
                SELECT attack, defense, durability
                FROM units
                WHERE unit_name = ? AND faction = ? AND unit_class = "3"
                LIMIT 1
            ''', (hero_unit_name, faction.faction)) # Добавляем проверку faction для безопасности

            stats_row = cursor.fetchone()
            if stats_row:
                # Предполагаем, что столбцы идут в порядке SELECT
                stats['attack'] = stats_row[0] if stats_row[0] is not None else 0
                stats['defense'] = stats_row[1] if stats_row[1] is not None else 0
                # Предполагая, что в БД поле называется 'durability', а не 'health'
                stats['durability'] = stats_row[2] if stats_row[2] is not None else 0
                # Добавьте обработку других столбцов, если добавили их в SELECT
                print(f"Характеристики загружены: {stats}")
            else:
                print(f"Характеристики для героя {hero_unit_name} не найдены в units.")
        else:
            print(f"Герой (unit_class='3', связанный с garrisons) не найден для фракции {faction.faction}")

    except sqlite3.Error as e:
        print(f"Ошибка при загрузке характеристик героя: {e}")

    return stats


def format_hero_stats(stats_dict):
    """
    Форматирует словарь характеристик в строку для отображения.
    """
    if not stats_dict:
        return "Нет данных"

    lines = []
    if 'attack' in stats_dict:
        lines.append(f"Атака: {stats_dict['attack']}")
    if 'defense' in stats_dict:
        lines.append(f"Защита: {stats_dict['defense']}")
    if 'durability' in stats_dict:
        lines.append(f"Здоровье: {stats_dict['durability']}")
    # Добавьте другие характеристики при необходимости

    if not lines:
        return "Характеристики отсутствуют"

    return '\n'.join(lines)


# --- Основная функция открытия попапа ---
def create_gradient_background(widget, color1, color2, direction='vertical'):
    """Создает градиентный фон для виджета."""
    widget.canvas.before.clear()
    with widget.canvas.before:
        from kivy.graphics import Mesh
        PushMatrix()
        # Создаем простой вертикальный или горизонтальный градиент с помощью Mesh
        if direction == 'vertical':
            vertices = [widget.x, widget.y, 0, 0,  # x, y, u, v
                        widget.x + widget.width, widget.y, 1, 0,
                        widget.x + widget.width, widget.y + widget.height, 1, 1,
                        widget.x, widget.y + widget.height, 0, 1]
        else: # horizontal
            vertices = [widget.x, widget.y, 0, 0,
                        widget.x + widget.width, widget.y, 1, 0,
                        widget.x + widget.width, widget.y + widget.height, 1, 1,
                        widget.x, widget.y + widget.height, 0, 1]

        indices = [0, 1, 2, 3] # Треугольники
        mode = 'triangle_fan'
        # Используем Mesh для градиента (упрощенный подход)
        # Лучше использовать Shader или несколько прямоугольников с разными цветами
        # Но для простоты используем Mesh с двумя цветами
        mesh = Mesh(vertices=vertices, indices=indices, mode=mode, fmt=[('v_pos', 2, 'float'), ('v_tex', 2, 'float')])
        PopMatrix()

def style_rounded_button(button, bg_color=(0.2, 0.6, 0.8, 1), radius=dp(10), has_shadow=True):
    """Применяет стиль скругленной кнопки с тенью."""
    button.background_normal = ''
    button.background_color = (0, 0, 0, 0) # Прозрачный фон по умолчанию
    button.canvas.before.clear()
    with button.canvas.before:
        from kivy.graphics import Color, RoundedRectangle
        if has_shadow:
            # Тень (немного смещенная и затемненная копия)
            Color(0, 0, 0, 0.3) # Цвет тени
            shadow_offset = dp(2)
            RoundedRectangle(pos=(button.pos[0] + shadow_offset, button.pos[1] - shadow_offset),
                             size=button.size, radius=[radius])

        # Основной фон кнопки
        Color(*bg_color)
        button.rect = RoundedRectangle(pos=button.pos, size=button.size, radius=[radius])

    def update_button_graphics(*args):
        button.canvas.before.clear()
        with button.canvas.before:
            from kivy.graphics import Color, RoundedRectangle
            if has_shadow:
                Color(0, 0, 0, 0.3)
                shadow_offset = dp(2)
                RoundedRectangle(pos=(button.pos[0] + shadow_offset, button.pos[1] - shadow_offset),
                                 size=button.size, radius=[radius])
            Color(*bg_color)
            if hasattr(button, 'rect'):
                button.rect.pos = button.pos
                button.rect.size = button.size
            else:
                button.rect = RoundedRectangle(pos=button.pos, size=button.size, radius=[radius])

    button.bind(pos=update_button_graphics, size=update_button_graphics)

class _ArtifactSpinnerOption(SpinnerOption):
    """Стилизованный элемент выпадающего списка для лавки артефактов."""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.background_normal = ''
        self.background_down = ''
        self.background_color = (0.12, 0.15, 0.28, 0.95)
        self.color = (0.9, 0.92, 1.0, 1)
        self.font_size = dp(13)
        self.halign = 'center'

        with self.canvas.before:
            from kivy.graphics import Color, RoundedRectangle
            Color(0.18, 0.22, 0.35, 0.3)
            self._sep = RoundedRectangle(pos=self.pos, size=(self.width, dp(1)), radius=[0])

        self.bind(pos=self._upd, size=self._upd)

    def _upd(self, *args):
        self._sep.pos = (self.x, self.y)
        self._sep.size = (self.width, dp(1))

    def on_press(self, *args):
        self.background_color = (0.22, 0.28, 0.50, 1)

    def on_release(self, *args):
        self.background_color = (0.12, 0.15, 0.28, 0.95)


def style_rounded_spinner(spinner, bg_color=(0.4, 0.4, 0.4, 1), text_color=(1, 1, 1, 1), radius=dp(8)):
    """Применяет стиль скругленного спиннера с кастомным dropdown."""
    spinner.option_cls = _ArtifactSpinnerOption
    spinner.background_normal = ''
    spinner.background_color = (0, 0, 0, 0)
    spinner.color = text_color
    spinner.canvas.before.clear()
    with spinner.canvas.before:
        from kivy.graphics import Color, RoundedRectangle
        Color(*bg_color)
        spinner.rect = RoundedRectangle(pos=spinner.pos, size=spinner.size, radius=[radius])

    def update_spinner_graphics(*args):
        spinner.canvas.before.clear()
        with spinner.canvas.before:
            from kivy.graphics import Color, RoundedRectangle
            Color(*bg_color)
            if hasattr(spinner, 'rect'):
                spinner.rect.pos = spinner.pos
                spinner.rect.size = spinner.size
            else:
                spinner.rect = RoundedRectangle(pos=spinner.pos, size=spinner.size, radius=[radius])

    spinner.bind(pos=update_spinner_graphics, size=update_spinner_graphics)

    # Стилизация dropdown фона
    def _style_dropdown(spinner_inst, is_open):
        if is_open and hasattr(spinner_inst, '_dropdown'):
            dd = spinner_inst._dropdown
            dd.canvas.before.clear()
            with dd.canvas.before:
                from kivy.graphics import Color, RoundedRectangle
                Color(0.08, 0.10, 0.20, 0.95)
                dd._bg = RoundedRectangle(pos=dd.pos, size=dd.size, radius=[dp(8)])
            dd.bind(
                pos=lambda i, v: setattr(i._bg, 'pos', v) if hasattr(i, '_bg') else None,
                size=lambda i, v: setattr(i._bg, 'size', v) if hasattr(i, '_bg') else None
            )

    spinner.bind(on_is_open=_style_dropdown)

# --- Основная функция сборки и построения интерфейса артефактов---


def open_artifacts_popup(faction, season_manager):
    """
    Открывает Popup с артефактами и экипировкой героя.
    :param season_manager:
    :param faction: Экземпляр класса Faction
    """
    from kivy.metrics import dp
    from kivy.utils import platform
    is_android = platform == 'android'

    # --- Размеры, адаптированные под платформу ---
    if is_android:
        artifact_row_height = dp(74)
        button_width = dp(72)
        button_height = dp(44)
        font_size_large = '14sp'
        font_size_medium = '12sp'
        font_size_small = '11sp'
        filter_height = dp(96)
        filter_spacing = dp(3)
        slot_size = (dp(52), dp(52))
        name_label_height = dp(14)
        offset = dp(8)
        padding_val = dp(4)
        spacing_val = dp(4)
        hero_img_size_val = dp(160)
    else:
        artifact_row_height = dp(88)
        button_width = dp(88)
        button_height = dp(54)
        font_size_large = '16sp'
        font_size_medium = '14sp'
        font_size_small = '13sp'
        filter_height = dp(110)
        filter_spacing = dp(4)
        slot_size = (dp(80), dp(80))
        name_label_height = dp(18)
        offset = dp(16)
        padding_val = dp(6)
        spacing_val = dp(6)
        hero_img_size_val = dp(180)

    # --- RPG цвета ---
    COLOR_BG = (0.06, 0.07, 0.12, 1)
    COLOR_PANEL_BG = (0.08, 0.09, 0.15, 1)
    COLOR_CARD_BG = (0.10, 0.12, 0.20, 1)
    COLOR_GOLD = (1, 0.84, 0.0, 1)
    COLOR_GOLD_TEXT = (1, 0.9, 0.4, 1)
    COLOR_PURPLE = (0.65, 0.35, 1.0, 1)
    COLOR_PURPLE_DIM = (0.50, 0.22, 0.80, 0.75)
    COLOR_TEXT = (0.92, 0.92, 0.92, 1)
    COLOR_SLOT_EMPTY = (0.25, 0.25, 0.35, 1)
    COLOR_SLOT_BORDER = (0.5, 0.4, 0.7, 1)
    COLOR_BUY_BTN = (0.15, 0.55, 0.25, 1)

    # Рамки редкости по стоимости
    def rarity_border_color(cost):
        if cost >= 50000:
            return (1.0, 0.84, 0.0, 1)       # gold / legendary
        elif cost >= 20000:
            return (0.65, 0.35, 1.0, 1)       # purple / expensive
        elif cost >= 5000:
            return (0.3, 0.55, 1.0, 1)        # blue / medium
        else:
            return (0.5, 0.5, 0.55, 1)        # grey / cheap

    # Названия слотов
    slot_names_map = {
        '0': 'Оружие',
        '1': 'Голова',
        '2': 'Сапоги',
        '3': 'Туловище',
        '4': 'Аксессуар'
    }
    slot_icons_map = {
        '0': '',
        '1': '',
        '2': '',
        '3': '',
        '4': '',
    }

    # --- Загрузка данных ---

    # RPG rarity color by cost
    def _rarity_color(cost):
        if cost >= 50000: return (0.85, 0.70, 0.20, 1)   # gold
        if cost >= 20000: return (0.60, 0.35, 0.85, 1)   # purple
        if cost >= 5000:  return (0.30, 0.55, 0.85, 1)   # blue
        return (0.40, 0.40, 0.45, 1)                      # grey

    artifacts_list = load_artifacts_from_db(faction)
    hero_equipment = load_hero_equipment_from_db(faction)
    hero_image_path = load_hero_image_from_db(faction)

    # --- Корневой layout ---
    popup_layout = BoxLayout(orientation='horizontal', padding=padding_val, spacing=spacing_val)
    with popup_layout.canvas.before:
        Color(*COLOR_BG)
        popup_layout._bg = Rectangle(pos=popup_layout.pos, size=popup_layout.size)
    popup_layout.bind(pos=lambda i, v: setattr(i._bg, 'pos', v),
                      size=lambda i, v: setattr(i._bg, 'size', v))

    # ==================================================================
    #  ЛЕВАЯ ПАНЕЛЬ: фильтры + список артефактов
    # ==================================================================
    left_panel = BoxLayout(orientation='vertical', size_hint=(0.52, 1), spacing=dp(2))

    # --- Фильтры ---
    filters_container = BoxLayout(orientation='vertical', size_hint_y=None,
                                  height=filter_height, spacing=filter_spacing,
                                  padding=(dp(4), dp(2)))
    with filters_container.canvas.before:
        Color(0.09, 0.10, 0.17, 1)
        filters_container._bg = RoundedRectangle(pos=filters_container.pos,
                                                  size=filters_container.size,
                                                  radius=[dp(6)])
    filters_container.bind(pos=lambda i, v: setattr(i._bg, 'pos', v),
                           size=lambda i, v: setattr(i._bg, 'size', v))

    filter_states = {
        'artifact_type': 'all',
        'cost_sort': 'all',
        'show_created_only': False
    }

    # --- Деньги (лейбл вверху левой панели) ---
    money_info_label = Label(
        text="",
        size_hint_y=None,
        height=dp(28) if is_android else dp(34),
        halign='right',
        valign='middle',
        font_size=font_size_large,
        bold=True,
        color=COLOR_GOLD,
        markup=True
    )
    money_info_label.bind(size=money_info_label.setter('text_size'))

    def update_money_display():
        try:
            current_money = faction.resources.get('Кроны', 0)
            money_info_label.text = f"[b]Кроны: {format_number(current_money)}[/b]"
        except Exception as e:
            print(f"[ERROR] Ошибка при обновлении отображения крон: {e}")
            money_info_label.text = "Кроны: ошибка"

    # ---- Предварительно создаём ВСЕ карточки артефактов (show/hide вместо recreate) ----
    all_artifact_widgets = []  # список (artifact_dict, widget)

    def _build_artifact_card(artifact):
        """Создаёт виджет-карточку для одного артефакта. Вызывается один раз."""
        description = format_artifact_description(artifact)
        if not description:
            return None

        cost = artifact.get('cost', 0)
        border_col = rarity_border_color(cost)

        # Внешний контейнер с цветной рамкой редкости
        outer = BoxLayout(orientation='horizontal', size_hint_y=None,
                          height=artifact_row_height,
                          padding=(dp(3), dp(2)), spacing=dp(4))
        with outer.canvas.before:
            Color(*border_col)
            outer._border_rect = RoundedRectangle(pos=outer.pos, size=outer.size,
                                                   radius=[dp(8)])
        with outer.canvas.before:
            Color(*COLOR_CARD_BG)
            outer._bg_rect = RoundedRectangle(
                pos=(outer.x + dp(2), outer.y + dp(2)),
                size=(outer.width - dp(4), outer.height - dp(4)),
                radius=[dp(6)])

        def _upd_outer(inst, val):
            inst._border_rect.pos = inst.pos
            inst._border_rect.size = inst.size
            inst._bg_rect.pos = (inst.x + dp(2), inst.y + dp(2))
            inst._bg_rect.size = (inst.width - dp(4), inst.height - dp(4))
        outer.bind(pos=_upd_outer, size=_upd_outer)

        # Левая часть: название + статы
        info_box = BoxLayout(orientation='vertical', size_hint_x=0.72, padding=(dp(2), 0))
        name_lbl = Label(text=artifact['name'], halign='left', valign='middle',
                         font_size=font_size_large, bold=True,
                         size_hint_y=None, height=dp(20) if is_android else dp(24),
                         color=COLOR_GOLD_TEXT, markup=False)
        name_lbl.bind(size=name_lbl.setter('text_size'))
        stats_lbl = Label(text=description, halign='left', valign='top',
                          font_size=font_size_medium, bold=True,
                          color=COLOR_TEXT, size_hint_y=None,
                          height=dp(38) if is_android else dp(48))
        stats_lbl.bind(size=stats_lbl.setter('text_size'))
        info_box.add_widget(name_lbl)
        info_box.add_widget(stats_lbl)

        # Правая часть: кнопка купить
        formatted_cost = format_number(cost)
        buy_btn = Button(
            text=f"Купить\n({formatted_cost})",
            size_hint=(None, None),
            width=button_width,
            height=button_height,
            font_size=font_size_small,
            bold=True,
            halign='center'
        )
        style_rounded_button(buy_btn, bg_color=COLOR_BUY_BTN,
                             radius=dp(6), has_shadow=True)
        buy_btn.bind(on_release=make_buy_handler(artifact))

        btn_wrapper = BoxLayout(size_hint_x=None, width=button_width,
                                padding=(0, dp(8), 0, dp(8)))
        btn_wrapper.add_widget(buy_btn)

        outer.add_widget(info_box)
        outer.add_widget(btn_wrapper)
        return outer

    # --- Обработчик покупки (объявляем до создания карточек) ---
    def make_buy_handler(art_data):
        def on_buy(instance):
            current_fraction_instance = faction

            try:
                check_cursor = current_fraction_instance.conn.cursor()
                check_cursor.execute(
                    "SELECT COUNT(*) FROM hero_equipment WHERE faction_name = ?",
                    (current_fraction_instance.faction,)
                )
                hero_count = check_cursor.fetchone()[0]
                if hero_count == 0:
                    print("[INFO] Попытка покупки артефакта без нанятого героя.")
                    show_popup_message("Ошибка", "Герой еще не нанят, покупать артефакт некому!")
                    return
            except sqlite3.Error as e:
                print(f"[ERROR] Ошибка при проверке наличия героя: {e}")
                show_popup_message("Ошибка", "Ошибка проверки данных героя.")
                return

            artifact_type_to_slot = {0: '0', 1: '1', 2: '2', 3: '3', 4: '4'}
            slot_type = artifact_type_to_slot.get(art_data['artifact_type'])

            if slot_type is None:
                print(f"[ERROR] Неизвестный тип артефакта: {art_data['artifact_type']}")
                show_popup_message("Ошибка", "Невозможно экипировать этот артефакт.")
                return

            artifact_entry = hero_equipment.get(slot_type)
            current_artifact_id_in_slot = None
            if isinstance(artifact_entry, dict):
                current_artifact_id_in_slot = artifact_entry.get('id')

            def deduct_coins_local(fraction_obj, amount):
                try:
                    current_money = getattr(fraction_obj, 'money', 0)
                    if current_money >= amount:
                        new_amount = current_money - amount
                        fraction_obj.update_resource_now('Кроны', new_amount)
                        update_money_display()
                        return True
                    else:
                        print(f"[INFO] [deduct_coins_local] Недостаточно крон. Нужно: {amount}, Есть: {current_money}")
                        return False
                except Exception as e:
                    print(f"[ERROR] [deduct_coins_local] Ошибка при списании: {e}")
                    import traceback
                    traceback.print_exc()
                    return False

            def add_coins_local(fraction_obj, amount):
                try:
                    current_money = getattr(fraction_obj, 'money', 0)
                    new_amount = current_money + amount
                    fraction_obj.update_resource_now('Кроны', new_amount)
                    update_money_display()
                    return True
                except Exception as e:
                    print(f"[ERROR] [add_coins_local] Ошибка при начислении: {e}")
                    import traceback
                    traceback.print_exc()
                    return False

            try:
                artifact_cost = art_data['cost']

                if current_artifact_id_in_slot is None:
                    if deduct_coins_local(current_fraction_instance, artifact_cost):
                        hero_equipment[slot_type] = {
                            "id": art_data['id'],
                            "image_url": art_data.get('image_url'),
                            "pos_x": None,
                            "pos_y": None
                        }
                        update_equipment_slot_visual(slot_type, hero_equipment[slot_type])
                        save_hero_equipment_to_db(current_fraction_instance, slot_type, art_data['id'], season_manager, None, None)
                        print(f"[SUCCESS] Артефакт {art_data['name']} куплен и экипирован в слот {slot_type}.")
                        show_popup_message("Успех", f"Артефакт {art_data['name']} куплен!")
                        update_hero_stats_display()
                    else:
                        print("[INFO] Недостаточно монет для покупки.")
                        show_popup_message("Ошибка", "Недостаточно Крон!")
                else:
                    old_artifact_data = None
                    try:
                        cursor = current_fraction_instance.conn.cursor()
                        cursor.execute("SELECT name, cost FROM artifacts WHERE id = ?", (current_artifact_id_in_slot,))
                        old_artifact_row = cursor.fetchone()
                        if old_artifact_row:
                            old_artifact_data = {
                                "id": current_artifact_id_in_slot,
                                "name": old_artifact_row['name'],
                                "cost": old_artifact_row['cost']
                            }
                    except sqlite3.Error as e:
                        print(f"[ERROR] Ошибка при получении данных старого артефакта: {e}")
                        show_popup_message("Ошибка", "Ошибка при проверке старого артефакта.")
                        return

                    if not old_artifact_data:
                        print(f"[WARNING] Данные старого артефакта (ID: {current_artifact_id_in_slot}) не найдены. Заменяем без возврата.")
                        old_artifact_cost = 0
                    else:
                        old_artifact_cost = old_artifact_data.get('cost', 0)

                    sell_price = int(old_artifact_cost * 0.65)
                    net_cost = artifact_cost - sell_price

                    def confirm_replace(instance):
                        confirm_popup.dismiss()
                        if net_cost > 0:
                            if not deduct_coins_local(current_fraction_instance, net_cost):
                                print("[INFO] Недостаточно монет для замены.")
                                show_popup_message("Ошибка", "Недостаточно Крон для замены!")
                                return
                        elif net_cost < 0:
                            refund_amount = abs(net_cost)
                            add_coins_local(current_fraction_instance, refund_amount)

                        save_hero_equipment_to_db(current_fraction_instance, slot_type, art_data['id'], season_manager, None, None)
                        hero_equipment[slot_type] = {
                            "id": art_data['id'],
                            "image_url": art_data.get('image_url'),
                            "pos_x": None,
                            "pos_y": None
                        }
                        update_equipment_slot_visual(slot_type, hero_equipment[slot_type])
                        print(f"[SUCCESS] Артефакт {art_data['name']} куплен и экипирован в слот {slot_type} (старый заменен).")
                        show_popup_message("Успех", f"Артефакт {art_data['name']} куплен! Старый артефакт продан.")
                        update_hero_stats_display()

                    def cancel_replace(instance):
                        confirm_popup.dismiss()
                        print("[INFO] Замена артефакта отменена пользователем.")

                    # Popup подтверждения замены (RPG-стиль)
                    content = BoxLayout(orientation='vertical', padding=dp(8), spacing=dp(6))
                    with content.canvas.before:
                        Color(*COLOR_BG)
                        content._bg = Rectangle(pos=content.pos, size=content.size)
                    content.bind(pos=lambda i, v: setattr(i._bg, 'pos', v),
                                 size=lambda i, v: setattr(i._bg, 'size', v))

                    old_art_name = old_artifact_data.get('name', 'Неизвестный артефакт') if old_artifact_data else 'Неизвестный артефакт'
                    message = (f"Заменить артефакт '{old_art_name}'\n"
                               f"на '{art_data['name']}'?\n"
                               f"Цена нового: {format_number(artifact_cost)}\n"
                               f"Вы получите за старый: {format_number(sell_price)}\n"
                               f"К оплате: {format_number(net_cost)}")
                    message_label = Label(text=message, text_size=(None, None), halign='center',
                                          font_size=font_size_small if is_android else '15sp',
                                          color=COLOR_TEXT)
                    message_label.bind(
                        size=lambda instance, value: setattr(instance, 'text_size', (value[0] * 0.9, None)))
                    content.add_widget(message_label)

                    btn_layout = BoxLayout(size_hint_y=None,
                                           height=dp(40) if is_android else dp(48),
                                           spacing=dp(8))
                    btn_yes = Button(text="Да", font_size=font_size_small if is_android else '15sp', bold=True)
                    style_rounded_button(btn_yes, bg_color=(0.2, 0.6, 0.3, 1), radius=dp(6), has_shadow=True)
                    btn_no = Button(text="Нет", font_size=font_size_small if is_android else '15sp', bold=True)
                    style_rounded_button(btn_no, bg_color=(0.6, 0.2, 0.2, 1), radius=dp(6), has_shadow=True)
                    btn_yes.bind(on_release=confirm_replace)
                    btn_no.bind(on_release=cancel_replace)
                    btn_layout.add_widget(btn_yes)
                    btn_layout.add_widget(btn_no)
                    content.add_widget(btn_layout)

                    confirm_popup = Popup(title="Подтверждение замены",
                                          content=content,
                                          size_hint=(0.88 if is_android else 0.7, 0.6 if is_android else 0.5),
                                          auto_dismiss=False,
                                          background_color=COLOR_BG,
                                          separator_color=COLOR_PURPLE_DIM,
                                          title_color=COLOR_GOLD)
                    confirm_popup.open()

            except Exception as e:
                error_msg = f"Произошла ошибка при покупке артефакта: {e}"
                print(f"[ERROR] {error_msg}")
                import traceback
                traceback.print_exc()
                show_popup_message("Ошибка", error_msg)

        return on_buy

    # --- Создаём карточки артефактов один раз ---
    for artifact in artifacts_list:
        card = _build_artifact_card(artifact)
        if card is not None:
            all_artifact_widgets.append((artifact, card))

    # --- Функция фильтрации: show/hide виджетов вместо пересоздания ---
    artifacts_list_layout = BoxLayout(orientation='vertical', size_hint_y=None,
                                      spacing=dp(3) if is_android else dp(4))
    artifacts_list_layout.bind(minimum_height=artifacts_list_layout.setter('height'))

    def update_artifact_list(*args):
        # Собираем отфильтрованный список
        visible = []
        for artifact, card_widget in all_artifact_widgets:
            created_ok = True
            if filter_states['show_created_only']:
                is_created = artifact.get('is_created', 0)
                created_ok = (is_created == 1 or is_created is True)
            type_ok = True
            if filter_states['artifact_type'] != 'all':
                type_ok = artifact.get('artifact_type') == filter_states['artifact_type']
            if created_ok and type_ok:
                visible.append((artifact, card_widget))

        if filter_states['cost_sort'] == 'asc':
            visible.sort(key=lambda pair: pair[0].get('cost', 0))
        elif filter_states['cost_sort'] == 'desc':
            visible.sort(key=lambda pair: pair[0].get('cost', 0), reverse=True)

        # Удаляем все, затем добавляем только видимые (быстрее, чем show/hide через opacity)
        artifacts_list_layout.clear_widgets()
        for _art, cw in visible:
            artifacts_list_layout.add_widget(cw)

    # --- Тип-фильтр ---
    type_filter_layout = BoxLayout(orientation='horizontal', size_hint_y=None,
                                   height=dp(28) if is_android else dp(32))
    type_lbl = Label(text="Тип:", size_hint_x=None,
                     width=dp(40) if is_android else dp(50), halign='left',
                     font_size=font_size_small, color=COLOR_GOLD_TEXT)
    type_lbl.bind(size=type_lbl.setter('text_size'))
    type_filter_layout.add_widget(type_lbl)
    type_spinner = Spinner(
        text='Все',
        values=('Все', 'Оружие', 'Сапоги', 'Туловище', 'Голова', 'Аксессуар'),
        size_hint=(1, None),
        height=dp(28) if is_android else dp(32),
        font_size=font_size_small
    )
    style_rounded_spinner(type_spinner, bg_color=(0.18, 0.22, 0.38, 1),
                          text_color=(1, 1, 1, 1), radius=dp(5))

    def on_type_spinner_select(spinner, text):
        mapping = {
            'Все': 'all', 'Оружие': 0, 'Голова': 1,
            'Сапоги': 2, 'Туловище': 3, 'Аксессуар': 4
        }
        filter_states['artifact_type'] = mapping.get(text, 'all')
        update_artifact_list()

    type_spinner.bind(text=on_type_spinner_select)
    type_filter_layout.add_widget(type_spinner)
    filters_container.add_widget(type_filter_layout)

    # --- Фильтр "Только созданные" ---
    created_filter_layout = BoxLayout(orientation='horizontal', size_hint_y=None,
                                      height=dp(26) if is_android else dp(30),
                                      spacing=dp(4))
    created_checkbox = CheckBox(
        size_hint=(None, None),
        size=(dp(22) if is_android else dp(26), dp(22) if is_android else dp(26)),
        active=False, color=(1, 1, 1, 1)
    )
    created_label = Label(
        text="Только созданные", size_hint_x=None,
        width=dp(115) if is_android else dp(140),
        halign='left', font_size=font_size_small, color=COLOR_TEXT
    )
    created_label.bind(size=created_label.setter('text_size'))
    created_filter_layout.add_widget(created_checkbox)
    created_filter_layout.add_widget(created_label)
    created_filter_layout.add_widget(Widget())
    filters_container.add_widget(created_filter_layout)

    def on_created_filter_toggle(instance, value):
        filter_states['show_created_only'] = value
        update_artifact_list()
    created_checkbox.bind(active=on_created_filter_toggle)

    # --- Цена-фильтр ---
    cost_filter_layout = BoxLayout(orientation='horizontal', size_hint_y=None,
                                   height=dp(28) if is_android else dp(32))
    cost_lbl = Label(text="Цена:", size_hint_x=None,
                     width=dp(40) if is_android else dp(50), halign='left',
                     font_size=font_size_small, color=COLOR_GOLD_TEXT)
    cost_lbl.bind(size=cost_lbl.setter('text_size'))
    cost_filter_layout.add_widget(cost_lbl)
    cost_spinner = Spinner(
        text='Все',
        values=('Все', 'Сначала дешевые', 'Сначала дорогие'),
        size_hint=(1, None),
        height=dp(28) if is_android else dp(32),
        font_size=font_size_small
    )
    style_rounded_spinner(cost_spinner, bg_color=(0.18, 0.22, 0.38, 1),
                          text_color=(1, 1, 1, 1), radius=dp(5))

    def on_cost_spinner_select(spinner, text):
        mapping = {'Все': 'all', 'Сначала дешевые': 'asc', 'Сначала дорогие': 'desc'}
        filter_states['cost_sort'] = mapping.get(text, 'all')
        update_artifact_list()
    cost_spinner.bind(text=on_cost_spinner_select)
    cost_filter_layout.add_widget(cost_spinner)
    filters_container.add_widget(cost_filter_layout)

    # --- Характеристики героя (столбик вверху-слева правой панели) ---
    _hero_stats_lbl = Label(
        text="[color=aaaaaa]Герой не нанят[/color]",
        halign='left', valign='top',
        font_size=font_size_small if is_android else '12sp',
        color=COLOR_TEXT, markup=True,
        size_hint=(None, None),
        height=dp(60) if is_android else dp(72),
        width=dp(140) if is_android else dp(160),
    )
    _hero_stats_lbl.bind(size=_hero_stats_lbl.setter('text_size'))
    hero_stats_container = _hero_stats_lbl
    hero_stats_widget = _hero_stats_lbl

    # --- Собираем левую панель ---
    left_panel.add_widget(money_info_label)
    left_panel.add_widget(filters_container)

    # Заголовок списка
    art_header = Label(
        text="[b]Артефакты[/b]", markup=True,
        size_hint_y=None,
        height=dp(28) if is_android else dp(36),
        font_size=font_size_large if is_android else '18sp',
        color=COLOR_PURPLE, halign='center', valign='middle'
    )
    art_header.bind(size=art_header.setter('text_size'))
    left_panel.add_widget(art_header)

    scroll_view = ScrollView(do_scroll_x=False, bar_width=dp(6),
                              bar_color=(*COLOR_PURPLE[:3], 0.5),
                              bar_inactive_color=(0.3, 0.3, 0.4, 0.3))
    scroll_view.add_widget(artifacts_list_layout)
    left_panel.add_widget(scroll_view)

    # ==================================================================
    #  ПРАВАЯ ПАНЕЛЬ: герой + слоты + статы
    # ==================================================================
    right_panel = FloatLayout(size_hint=(0.48, 1))
    with right_panel.canvas.before:
        Color(*COLOR_PANEL_BG)
        right_panel._bg = RoundedRectangle(pos=right_panel.pos, size=right_panel.size,
                                            radius=[dp(8)])
    right_panel.bind(
        pos=lambda i, v: setattr(i._bg, 'pos', v),
        size=lambda i, v: setattr(i._bg, 'size', v))

    hero_image_widget = None
    equipment_slots = {}
    slot_name_labels = {}

    def apply_slot_style(slot_widget, slot_type_key=''):
        """Стиль пустого слота с рамкой и иконкой."""
        slot_widget.background_normal = ''
        slot_widget.background_color = (0, 0, 0, 0)
        slot_widget.canvas.before.clear()
        with slot_widget.canvas.before:
            # Рамка
            Color(*COLOR_SLOT_BORDER)
            slot_widget._border_rect = RoundedRectangle(
                pos=slot_widget.pos, size=slot_widget.size,
                radius=[dp(6)])
            # Заливка
            Color(*COLOR_SLOT_EMPTY)
            slot_widget._fill_rect = RoundedRectangle(
                pos=(slot_widget.x + dp(2), slot_widget.y + dp(2)),
                size=(slot_widget.width - dp(4), slot_widget.height - dp(4)),
                radius=[dp(5)])

        def _upd_slot(inst, val):
            if hasattr(inst, '_border_rect'):
                inst._border_rect.pos = inst.pos
                inst._border_rect.size = inst.size
            if hasattr(inst, '_fill_rect'):
                inst._fill_rect.pos = (inst.x + dp(2), inst.y + dp(2))
                inst._fill_rect.size = (inst.width - dp(4), inst.height - dp(4))
        slot_widget.unbind(pos=_upd_slot, size=_upd_slot)
        slot_widget.bind(pos=_upd_slot, size=_upd_slot)

    hero_image_size = (hero_img_size_val, hero_img_size_val)

    if hero_image_path and os.path.exists(hero_image_path):
        try:
            hero_image_widget = Image(
                source=hero_image_path,
                size_hint=(None, None),
                size=hero_image_size
            )
            hero_image_widget.pos_hint = {'center_x': 0.5, 'center_y': 0.55}
            right_panel.add_widget(hero_image_widget)

            slot_types = ['0', '1', '2', '3', '4']
            for st in slot_types:
                slot_widget = Button(
                    size_hint=(None, None),
                    size=slot_size,
                    background_normal='',
                    background_down='',
                    background_color=(1, 1, 1, 1),
                    text=slot_icons_map.get(st, ''),
                    font_size=font_size_large if is_android else '16sp',
                    color=(0.7, 0.7, 0.8, 0.6)
                )
                apply_slot_style(slot_widget, st)
                right_panel.add_widget(slot_widget)
                equipment_slots[st] = slot_widget

                name_label = Label(
                    text=slot_names_map.get(st, ''),
                    size_hint=(None, None),
                    size=(slot_size[0] + dp(10), name_label_height),
                    font_size=font_size_small if is_android else '12sp',
                    halign='center', valign='middle',
                    color=(0.7, 0.65, 0.9, 0.8),
                    bold=True
                )
                name_label.bind(size=name_label.setter('text_size'))
                slot_name_labels[st] = name_label

            def initialize_equipment_visual(dt):
                update_all_equipment_slots()
            Clock.schedule_once(initialize_equipment_visual, 0.2)

        except Exception as e:
            print(f"Ошибка загрузки изображения героя {hero_image_path}: {e}")
            import traceback
            traceback.print_exc()
            hero_image_widget = None
            hero_placeholder = Label(
                text="[b]Ошибка загрузки\nизображения[/b]", markup=True,
                halign='center', valign='middle',
                font_size=font_size_medium, color=COLOR_TEXT
            )
            hero_placeholder.pos_hint = {'center_x': 0.5, 'center_y': 0.55}
            right_panel.add_widget(hero_placeholder)
    else:
        no_hero_label = Label(
            text="[b]Герой не нанят[/b]\nНаймите героя\nдля доступа к экипировке",
            markup=True, halign='center', valign='middle',
            font_size=font_size_medium, color=COLOR_TEXT
        )
        no_hero_label.pos_hint = {'center_x': 0.5, 'center_y': 0.55}
        right_panel.add_widget(no_hero_label)
        hero_image_widget = None

    # Добавляем контейнер характеристик в правую панель
    right_panel.add_widget(hero_stats_container)

    # --- Позиционирование слотов вокруг героя ---
    def position_slots(dt):
        if not hero_image_widget:
            return
        if not right_panel or right_panel.width == 0:
            Clock.schedule_once(position_slots, 0.1)
            return

        panel_x = right_panel.x
        panel_y = right_panel.y
        panel_width = right_panel.width
        panel_height = right_panel.height

        center_x = panel_x + panel_width / 2
        center_y = panel_y + panel_height * 0.55

        hero_width, hero_height = hero_image_size
        slot_w, slot_h = slot_size
        half_hero_w = hero_width / 2
        half_hero_h = hero_height / 2

        slot_positions = {
            '0': (center_x - half_hero_w - slot_w - offset, center_y - slot_h / 2),
            '3': (center_x + half_hero_w + offset, center_y - slot_h / 2),
            '1': (center_x - slot_w / 2, center_y + half_hero_h + offset),
            '2': (center_x - slot_w / 2, center_y - half_hero_h - slot_h - offset),
            '4': (center_x + half_hero_w + offset, center_y + half_hero_h + offset),
        }

        # Позиционируем характеристики героя вверху-слева правой панели
        hero_stats_container.pos = (
            panel_x + dp(8),
            panel_y + panel_height - hero_stats_container.height - dp(8)
        )

        for slot_type, pos in slot_positions.items():
            if slot_type in slot_name_labels:
                nlbl = slot_name_labels[slot_type]
                nlbl.pos = (pos[0] - dp(5), pos[1] - (dp(16) if is_android else dp(20)))
                if nlbl.parent is None:
                    right_panel.add_widget(nlbl)
            if slot_type in equipment_slots:
                widget = equipment_slots[slot_type]
                widget.pos = pos

                artifact_entry = hero_equipment.get(slot_type)
                if isinstance(artifact_entry, dict) and artifact_entry.get('id'):
                    pos_x, pos_y = pos
                    hero_equipment[slot_type]['pos_x'] = pos_x
                    hero_equipment[slot_type]['pos_y'] = pos_y
                    save_hero_equipment_to_db(faction, slot_type, artifact_entry['id'], season_manager, pos_x, pos_y)

    # --- Обновление визуала слота ---
    def update_equipment_slot_visual(slot_type, artifact_data):
        slot_widget = equipment_slots.get(slot_type)
        name_label = slot_name_labels.get(slot_type)

        if not slot_widget:
            print(f"[WARNING] Слот типа {slot_type} не найден для обновления.")
            return

        if artifact_data and artifact_data.get('id'):
            full_artifact_data = artifact_data
            if 'name' not in artifact_data:
                artifact_id = artifact_data.get('id') or artifact_data.get('artifact_id')
                if artifact_id:
                    full_artifact_data = next((a for a in artifacts_list if a['id'] == artifact_id), None)

            image_url = full_artifact_data.get('image_url') if full_artifact_data else None
            artifact_name = full_artifact_data.get('name') if full_artifact_data else 'Без названия'

            if image_url:
                slot_widget.text = ''
                slot_widget.background_normal = image_url
                slot_widget.background_down = image_url
                slot_widget.background_color = (1, 1, 1, 1)
            else:
                slot_widget.background_normal = ''
                slot_widget.background_down = ''
                slot_widget.background_color = (0.4, 0.4, 0.4, 1)

            if name_label:
                name_label.text_size = (name_label.width, None)
                display_name = artifact_name[:13] + ".." if len(artifact_name) > 13 and is_android else artifact_name
                name_label.text = display_name
                name_label.color = COLOR_GOLD_TEXT
        else:
            slot_widget.text = slot_icons_map.get(slot_type, '')
            slot_widget.background_normal = ''
            slot_widget.background_down = ''
            slot_widget.background_color = (0, 0, 0, 0)
            apply_slot_style(slot_widget, slot_type)

            if name_label:
                name_label.text = slot_names_map.get(slot_type, '')
                name_label.color = (0.7, 0.65, 0.9, 0.8)

    def update_all_equipment_slots():
        for slot_type_key in ['0', '1', '2', '3', '4']:
            artifact_entry = hero_equipment.get(slot_type_key)
            if isinstance(artifact_entry, dict) and artifact_entry.get('id'):
                artifact_id = artifact_entry['id']
                full_artifact_data = next((a for a in artifacts_list if a['id'] == artifact_id), None)
                if full_artifact_data:
                    update_equipment_slot_visual(slot_type_key, full_artifact_data)
                else:
                    print(f"[WARNING] Артефакт ID {artifact_id} для слота {slot_type_key} не найден в artifacts_list.")
                    update_equipment_slot_visual(slot_type_key, artifact_entry)
            else:
                update_equipment_slot_visual(slot_type_key, None)

    def update_hero_stats_display():
        if hero_stats_widget:
            try:
                hero_stats_data = load_hero_stats_from_db(faction)
                atk = hero_stats_data.get('attack', 0)
                dfn = hero_stats_data.get('defense', 0)
                hp = hero_stats_data.get('durability', 0)
                hero_stats_widget.text = (
                    f"[color=ff7777][b]Атака:[/b][/color] {atk}\n"
                    f"[color=7799ff][b]Защита:[/b][/color] {dfn}\n"
                    f"[color=77ee77][b]Здоровье:[/b][/color] {hp}"
                )
            except Exception as e:
                print(f"Ошибка обновления характеристик героя: {e}")
                import traceback
                traceback.print_exc()
                hero_stats_widget.text = "Ошибка загрузки"

    # ==================================================================
    #  Сборка и открытие Popup
    # ==================================================================
    popup_layout.add_widget(left_panel)
    popup_layout.add_widget(right_panel)

    artifacts_popup = Popup(
        title="Лавка артефактов",
        content=popup_layout,
        size_hint=(0.95, 0.95),
        title_align='center',
        background_color=COLOR_BG,
        separator_color=COLOR_PURPLE_DIM,
        title_color=COLOR_GOLD,
        title_size=font_size_large if is_android else '20sp'
    )

    # Обновляем данные при открытии (без Clock.schedule_interval!)
    update_money_display()
    update_artifact_list()
    Clock.schedule_once(lambda dt: update_hero_stats_display(), 0)

    if hero_image_widget:
        artifacts_popup.bind(on_open=lambda *args: Clock.schedule_once(position_slots, 0.1))

    artifacts_popup.open()


# --- Конец open_artifacts_popup ---









