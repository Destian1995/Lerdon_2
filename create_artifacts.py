import os

from kivy.uix.popup import Popup
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView

from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.slider import Slider

from kivy.uix.image import Image
from kivy.graphics import Color, RoundedRectangle, Rectangle, Line

from kivy.metrics import dp, sp
from kivy.core.window import Window
import random

from ui_components import show_message

from utils.helpers import format_number


# ======================================================================
#  Цветовая палитра мастерской (тёмная RPG-тема с золотом и пурпуром)
# ======================================================================
_CLR_BG = (0.05, 0.06, 0.10, 1)          # Основной фон
_CLR_BG_CARD = (0.08, 0.09, 0.14, 1)     # Фон карточки
_CLR_BG_PANEL = (0.07, 0.08, 0.12, 1)    # Фон панели
_CLR_GOLD = (0.90, 0.75, 0.25, 1)        # Золотой акцент
_CLR_GOLD_DIM = (0.65, 0.55, 0.18, 1)    # Приглушённое золото
_CLR_PURPLE = (0.55, 0.30, 0.80, 1)      # Пурпурный акцент
_CLR_PURPLE_LIGHT = (0.65, 0.40, 0.90, 1)
_CLR_TEXT = (0.88, 0.90, 0.95, 1)         # Основной текст
_CLR_TEXT_DIM = (0.55, 0.58, 0.65, 1)    # Приглушённый текст
_CLR_GREEN = (0.30, 0.75, 0.40, 1)       # Зелёный (подтверждение)
_CLR_RED = (0.80, 0.25, 0.25, 1)         # Красный (ошибка/отмена)
_CLR_BLUE = (0.30, 0.55, 0.85, 1)        # Синий (информация)
_CLR_SELECTED = (0.90, 0.75, 0.25, 0.35) # Подсветка выбранного
_CLR_SLOT_BORDER = (0.45, 0.35, 0.65, 1) # Рамка слота


def workshop(faction, db_conn):
    """Мастерская артефактов — полноэкранный 3-шаговый визард."""

    # === Платформа ===
    from kivy.utils import platform as _platform
    is_android = _platform == 'android'

    # === Адаптивные размеры ===
    font_title = sp(17) if not is_android else sp(15)
    font_normal = sp(13) if not is_android else sp(11)
    font_small = sp(11) if not is_android else sp(9)
    font_tiny = sp(9) if not is_android else sp(7)

    padding_main = dp(10) if is_android else dp(14)
    spacing_main = dp(6) if is_android else dp(8)
    btn_height = dp(36) if is_android else dp(40)

    # Размер миниатюры артефакта в сетке
    thumb_size = dp(80) if is_android else dp(100)
    # Размер превью артефакта (крупное)
    preview_size = dp(140) if is_android else dp(180)

    # === Попап ===
    workshop_popup = Popup(
        title="",
        separator_height=0,
        size_hint=(0.96 if is_android else 0.80, 0.94 if is_android else 0.90),
        background_color=(0, 0, 0, 0),
        auto_dismiss=False
    )

    # === Общие данные ===
    current_data = {
        'icon': None,
        'name': '',
        'attack': 0,
        'defense': 0,
        'season': 'Нет',
        'slot': 'Оружие'
    }

    # === Изображения артефактов ===
    artifact_images_path = r"files/pict/artifacts/custom"
    if os.path.exists(artifact_images_path):
        image_files = sorted([
            f for f in os.listdir(artifact_images_path)
            if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp'))
        ])
    else:
        image_files = []

    selected_image = [None]
    current_index = [0]

    # ======================================================================
    #  Утилиты UI
    # ======================================================================

    def _make_rounded_bg(widget, color, radius=dp(10)):
        """Добавляет скруглённый фон виджету."""
        with widget.canvas.before:
            widget._bg_color = Color(*color)
            widget._bg_rect = RoundedRectangle(pos=widget.pos, size=widget.size, radius=[radius])
        widget.bind(
            pos=lambda w, v: setattr(w._bg_rect, 'pos', v),
            size=lambda w, v: setattr(w._bg_rect, 'size', v)
        )

    def _make_action_btn(text, color, font_sz=None, height=None):
        """Создаёт стилизованную кнопку действия."""
        b = Button(
            text=text,
            size_hint_y=None,
            height=height or btn_height,
            background_color=(0, 0, 0, 0),
            background_normal='',
            font_size=font_sz or font_normal,
            color=(1, 1, 1, 1),
            bold=True
        )
        _make_rounded_bg(b, color, dp(10))
        return b

    def _make_label(text, font_sz=None, color=None, bold=False, halign='center',
                    height=None, size_hint_y=None):
        """Создаёт стилизованный Label."""
        lbl = Label(
            text=text,
            font_size=font_sz or font_normal,
            color=color or _CLR_TEXT,
            bold=bold,
            halign=halign,
            valign='middle',
            size_hint_y=size_hint_y,
            height=height or dp(24),
            markup=True
        )
        if size_hint_y is None:
            lbl.size_hint_y = None
        lbl.bind(size=lambda inst, val: setattr(inst, 'text_size', (inst.width, None)))
        return lbl

    def _step_indicator(step_num, total=3):
        """Индикатор шагов: ● ● ○"""
        dots = ''
        for i in range(1, total + 1):
            if i == step_num:
                dots += f'[color=e6bf3a]●[/color]  '
            else:
                dots += f'[color=555555]○[/color]  '
        return dots.strip()

    # ======================================================================
    #  Переключение экранов
    # ======================================================================

    def switch_to_screen(screen_func):
        root = BoxLayout(orientation='vertical', padding=0, spacing=0)
        _make_rounded_bg(root, _CLR_BG, dp(12))
        screen_func(root)
        workshop_popup.content = root

    # ======================================================================
    #  Генерация имени артефакта
    # ======================================================================

    def generate_random_name(filename=None):
        """Генерирует случайное RPG-название артефакта по имени файла."""
        weapon_subclasses = {
            'v': ["Винтовка", "Ружьё", "Карабин"],
            'a': ["Арбалет"],
            'm': ["Меч", "Клинок", "Кинжал", "Сабля"],
            'p': ["Посох", "Скипетр", "Жезл"],
            'k': ["Копье"],
            's': ["Секира", "Топор"],
            'l': ["Лук"]
        }
        head_subclasses = {
            'k': ["Корона", "Диадема"], 'h': ["Шлем"],
            's': ["Шляпа", "Колпак"], 'v': ["Венок"],
        }
        legs_subclasses = {'s': ["Сапоги", "Ботинки"]}
        torso_subclasses = {
            'b': ["Броня", "Латы", "Кираса", "Панцирь", "Доспех"],
            'm': ["Мантия", "Плащ", "Накидка"],
            'g': ["Жилет", "Камзол", "Дублет"],
        }
        accessory_subclasses = {
            'k': ["Кольцо", "Перстень"],
            'a': ["Амулет", "Талисман", "Медальон", "Филактерия", "Оберег"],
            's': ["Серьга"],
        }
        prefixes_by_type = {
            0: ["Секира", "Меч", "Клинок", "Винтовка", "Мушкет", "Дробовик", "Арбалет",
                "Кинжал", "Скипетр", "Ружьё", "Копьё", "Посох", "Палаш", "Шпага", "Рапира"],
            1: ["Шлем", "Шляпа", "Корона", "Венец", "Наголовье", "Капюшон", "Диадема",
                "Каска", "Колпак", "Тюрбан", "Берет", "Тиара", "Венок", "Обруч"],
            2: ["Сапоги", "Обувь", "Ботинки", "Постаменты", "Поножи", "Сандалии",
                "Башмаки", "Лапти", "Наколенники", "Онучи", "Обмотки", "Чоботы", "Мокасины"],
            3: ["Броня", "Панцирь", "Кираса", "Доспех", "Мантия", "Кольчуга",
                "Латы", "Жилет", "Плащ", "Дублет", "Камзол", "Хауберк", "Ряса", "Пелерина"],
            4: ["Амулет", "Кольцо", "Серьга", "Браслет", "Талисман", "Артефакт",
                "Сердце", "Душа", "Звезда", "Камень", "Медальон", "Подвеска", "Чары", "Перстень"]
        }
        suffixes = [
            "Силы", "Защиты", "Мудрости", "Света", "Тьмы", "Мощи",
            "Вампиров", "Эльфов", "Просветления", "Судьбы", "Веры",
            "Смерти", "Багровой крови", "Мастеров", "Дракона", "Феникса",
            "Бездны", "Рассвета", "Заката", "Бури", "Огня", "Льда",
            "Ветра", "Земли", "Воды", "Грома", "Теней", "Истины", "Хаоса"
        ]
        artifact_type = 0
        prefixes = prefixes_by_type[0]

        if filename:
            try:
                clean_name = os.path.splitext(filename.strip())[0].lower().replace(' ', '_')
                if len(clean_name) >= 1 and clean_name[0].isdigit():
                    artifact_type = int(clean_name[0])
                    subclass_dict = {
                        0: weapon_subclasses, 1: head_subclasses,
                        2: legs_subclasses, 3: torso_subclasses, 4: accessory_subclasses,
                    }.get(artifact_type, {})
                    if len(clean_name) >= 2 and clean_name[1].isalpha():
                        subclass_key = clean_name[1]
                        if subclass_key in subclass_dict:
                            prefixes = subclass_dict[subclass_key]
                        else:
                            prefixes = prefixes_by_type.get(artifact_type, prefixes_by_type[0])
                    else:
                        prefixes = prefixes_by_type.get(artifact_type, prefixes_by_type[0])
                else:
                    prefixes = prefixes_by_type[0]
            except (IndexError, ValueError, AttributeError):
                prefixes = prefixes_by_type.get(artifact_type, prefixes_by_type[0])

        return f"{random.choice(prefixes)} {random.choice(suffixes)}", artifact_type

    # ======================================================================
    #  ЭКРАН 1 — Выбор иконки (сетка крупных миниатюр)
    # ======================================================================

    def screen1(layout):
        # --- Шапка ---
        header = BoxLayout(orientation='vertical', size_hint_y=None, height=dp(60),
                           padding=[padding_main, dp(8), padding_main, 0])
        _make_rounded_bg(header, _CLR_BG_PANEL, dp(10))

        step_lbl = _make_label(_step_indicator(1), font_sz=font_normal, height=dp(20))
        header.add_widget(step_lbl)

        title_lbl = _make_label("Выберите облик артефакта", font_sz=font_title,
                                color=_CLR_GOLD, bold=True, height=dp(30))
        header.add_widget(title_lbl)
        layout.add_widget(header)

        # --- Превью выбранного артефакта (крупное) ---
        preview_panel = BoxLayout(orientation='horizontal', size_hint_y=None,
                                  height=preview_size + dp(20),
                                  padding=[padding_main, dp(6)], spacing=dp(12))
        _make_rounded_bg(preview_panel, _CLR_BG_CARD, dp(10))

        # Контейнер изображения с рамкой
        img_container = FloatLayout(size_hint_x=None, width=preview_size)

        preview_img = Image(
            source="" if not image_files else os.path.join(artifact_images_path, image_files[0]),
            size_hint=(None, None),
            size=(preview_size - dp(8), preview_size - dp(8)),
            pos_hint={'center_x': 0.5, 'center_y': 0.5},
            allow_stretch=True,
            keep_ratio=True
        )
        img_container.add_widget(preview_img)

        # Золотая рамка
        with img_container.canvas.after:
            img_container._border_color = Color(*_CLR_GOLD_DIM)
            img_container._border_line = Line(
                rounded_rectangle=(0, 0, 10, 10, dp(6)),
                width=dp(1.5)
            )

        def _update_border(inst, _):
            inst._border_line.rounded_rectangle = (
                inst.x + dp(2), inst.y + dp(2),
                inst.width - dp(4), inst.height - dp(4), dp(6)
            )
        img_container.bind(pos=_update_border, size=_update_border)

        preview_panel.add_widget(img_container)

        # Информация справа от превью
        info_box = BoxLayout(orientation='vertical', spacing=dp(4),
                             padding=[0, dp(10), 0, dp(10)])

        name_lbl = _make_label("—", font_sz=font_normal, color=_CLR_GOLD,
                               bold=True, halign='left', height=dp(28))
        info_box.add_widget(name_lbl)

        type_lbl = _make_label("Тип: —", font_sz=font_small, color=_CLR_TEXT_DIM,
                               halign='left', height=dp(20))
        info_box.add_widget(type_lbl)

        counter_lbl = _make_label("", font_sz=font_tiny, color=_CLR_TEXT_DIM,
                                  halign='left', height=dp(18))
        info_box.add_widget(counter_lbl)

        # Кнопка перегенерации имени
        rename_btn = _make_action_btn("⟳ Новое имя", (0.20, 0.35, 0.55, 1),
                                      font_sz=font_small, height=dp(30))
        info_box.add_widget(rename_btn)

        # Спейсер
        info_box.add_widget(BoxLayout())

        preview_panel.add_widget(info_box)
        layout.add_widget(preview_panel)

        # --- Сетка миниатюр ---
        grid_label = _make_label("Доступные иконки:", font_sz=font_small,
                                 color=_CLR_TEXT_DIM, halign='left', height=dp(22))
        grid_label.padding = [padding_main, 0]
        layout.add_widget(grid_label)

        scroll = ScrollView(size_hint_y=1, do_scroll_x=False)
        cols = 4 if is_android else 5
        grid = GridLayout(cols=cols, spacing=dp(6), padding=[dp(6)],
                          size_hint_y=None)
        grid.bind(minimum_height=grid.setter('height'))

        _thumb_widgets = []

        def _select_thumb(idx, *_args):
            current_index[0] = idx
            _update_selection()

        def _update_selection():
            idx = current_index[0]
            if not image_files:
                return

            img_filename = image_files[idx]
            img_path = os.path.join(artifact_images_path, img_filename)
            preview_img.source = img_path
            selected_image[0] = img_filename

            auto_name, detected_type = generate_random_name(img_filename)
            current_data['name'] = auto_name
            current_data['icon'] = img_filename
            name_lbl.text = auto_name

            slot_map = {0: 'Оружие', 1: 'Голова', 2: 'Ноги', 3: 'Туловище', 4: 'Аксессуар'}
            if detected_type in slot_map:
                current_data['slot'] = slot_map[detected_type]
                type_lbl.text = f"Тип: {slot_map[detected_type]}"

            counter_lbl.text = f"{idx + 1} / {len(image_files)}"

            # Обновляем подсветку миниатюр
            for i, tw in enumerate(_thumb_widgets):
                if i == idx:
                    if hasattr(tw, '_sel_color'):
                        tw._sel_color.rgba = _CLR_SELECTED
                else:
                    if hasattr(tw, '_sel_color'):
                        tw._sel_color.rgba = (0, 0, 0, 0)

        for i, fname in enumerate(image_files):
            cell = FloatLayout(size_hint_y=None, height=thumb_size)

            # Фон с подсветкой
            with cell.canvas.before:
                cell._sel_color = Color(0, 0, 0, 0)
                cell._sel_rect = RoundedRectangle(pos=cell.pos, size=cell.size, radius=[dp(8)])
                Color(*_CLR_BG_CARD)
                cell._bg_rect = RoundedRectangle(pos=cell.pos, size=cell.size, radius=[dp(8)])

            def _bind_bg(w):
                def _upd(inst, val):
                    inst._sel_rect.pos = val
                    inst._bg_rect.pos = val
                def _upd_sz(inst, val):
                    inst._sel_rect.size = val
                    inst._bg_rect.size = val
                w.bind(pos=_upd, size=_upd_sz)
            _bind_bg(cell)

            thumb_img = Image(
                source=os.path.join(artifact_images_path, fname),
                size_hint=(None, None),
                size=(thumb_size - dp(12), thumb_size - dp(12)),
                pos_hint={'center_x': 0.5, 'center_y': 0.5},
                allow_stretch=True,
                keep_ratio=True
            )
            cell.add_widget(thumb_img)

            # Невидимая кнопка поверх для обработки нажатия
            touch_btn = Button(
                size_hint=(1, 1),
                background_color=(0, 0, 0, 0),
                background_normal='',
                on_release=lambda inst, _i=i: _select_thumb(_i)
            )
            cell.add_widget(touch_btn)

            grid.add_widget(cell)
            _thumb_widgets.append(cell)

        scroll.add_widget(grid)
        layout.add_widget(scroll)

        # --- Нижняя панель ---
        bottom = BoxLayout(orientation='horizontal', size_hint_y=None,
                           height=btn_height + dp(12), spacing=dp(8),
                           padding=[padding_main, dp(6)])
        _make_rounded_bg(bottom, _CLR_BG_PANEL, dp(10))

        close_btn = _make_action_btn("Закрыть", _CLR_RED)
        next_btn = _make_action_btn("Далее  ➜", (0.18, 0.52, 0.28, 1))

        bottom.add_widget(close_btn)
        bottom.add_widget(next_btn)
        layout.add_widget(bottom)

        # --- События ---
        def on_rename(*_):
            if selected_image[0]:
                name, dt = generate_random_name(selected_image[0])
                current_data['name'] = name
                name_lbl.text = name

        def on_next(*_):
            current_data['icon'] = selected_image[0]
            if not current_data['icon']:
                show_message("Ошибка", "Выберите иконку артефакта")
                return
            if not current_data.get('name'):
                auto_name, _ = generate_random_name(selected_image[0])
                current_data['name'] = auto_name
            switch_to_screen(screen2)

        rename_btn.bind(on_release=on_rename)
        close_btn.bind(on_release=lambda x: workshop_popup.dismiss())
        next_btn.bind(on_release=on_next)

        # Инициализация
        if image_files:
            _update_selection()

    # ======================================================================
    #  ЭКРАН 2 — Характеристики (слайдеры + превью)
    # ======================================================================

    def screen2(layout):
        _BLUEPRINT_COST = 50_000
        _faction_name = getattr(faction, 'faction', '')
        _MAX_ARTIFACT_COST = 12_000_000 if _faction_name == 'Элины' else 9_900_000
        _max_budget_for_stats = _MAX_ARTIFACT_COST - _BLUEPRINT_COST
        _budget = min(faction.money, _max_budget_for_stats)
        ardanian_tokens_available = _budget / 3200.0
        current_attack = current_data.get('attack', 0)
        current_defense = current_data.get('defense', 0)

        def calculate_tokens(attack, defense):
            ta = attack / 1.5
            td = defense / 1.0
            return ta + td, ta, td

        # --- Шапка ---
        header = BoxLayout(orientation='vertical', size_hint_y=None, height=dp(56),
                           padding=[padding_main, dp(6), padding_main, 0])
        _make_rounded_bg(header, _CLR_BG_PANEL, dp(10))
        header.add_widget(_make_label(_step_indicator(2), font_sz=font_normal, height=dp(18)))
        header.add_widget(_make_label("Настройка характеристик", font_sz=font_title,
                                      color=_CLR_GOLD, bold=True, height=dp(28)))
        layout.add_widget(header)

        # --- Мини-превью артефакта ---
        mini_preview = BoxLayout(orientation='horizontal', size_hint_y=None,
                                 height=dp(70), padding=[padding_main, dp(6)], spacing=dp(10))
        _make_rounded_bg(mini_preview, _CLR_BG_CARD, dp(8))

        _icon_path = os.path.join(artifact_images_path, current_data['icon']) if current_data['icon'] else ''
        mini_img = Image(
            source=_icon_path,
            size_hint=(None, None),
            size=(dp(54), dp(54)),
            pos_hint={'center_y': 0.5},
            allow_stretch=True, keep_ratio=True
        )
        mini_preview.add_widget(mini_img)

        mini_info = BoxLayout(orientation='vertical', spacing=dp(2))
        mini_info.add_widget(_make_label(current_data['name'], font_sz=font_normal,
                                         color=_CLR_GOLD, bold=True, halign='left', height=dp(22)))
        mini_info.add_widget(_make_label(f"Тип: {current_data['slot']}", font_sz=font_small,
                                         color=_CLR_TEXT_DIM, halign='left', height=dp(18)))
        mini_info.add_widget(_make_label(f"Бюджет: {format_number(int(_budget))} крон",
                                         font_sz=font_small, color=_CLR_BLUE,
                                         halign='left', height=dp(18)))
        mini_preview.add_widget(mini_info)
        layout.add_widget(mini_preview)

        # --- Панель баланса жетонов ---
        token_panel = BoxLayout(orientation='vertical', size_hint_y=None, height=dp(62),
                                padding=[padding_main, dp(4)], spacing=dp(2))
        _make_rounded_bg(token_panel, (0.06, 0.08, 0.14, 1), dp(8))

        balance_label = _make_label(
            f"Жетоны Ардании: {ardanian_tokens_available:.1f}",
            font_sz=font_small, color=_CLR_GREEN, bold=True, height=dp(20)
        )
        token_panel.add_widget(balance_label)

        used_label = _make_label(
            f"Использовано: 0.0",
            font_sz=font_tiny, color=_CLR_TEXT_DIM, height=dp(18)
        )
        token_panel.add_widget(used_label)

        cost_label = _make_label(
            f"Стоимость: 0 крон",
            font_sz=font_tiny, color=_CLR_TEXT, height=dp(18)
        )
        token_panel.add_widget(cost_label)
        layout.add_widget(token_panel)

        # --- Слайдер АТАКИ ---
        atk_section = BoxLayout(orientation='vertical', spacing=dp(2),
                                size_hint_y=None, height=dp(78),
                                padding=[padding_main, dp(4)])
        _make_rounded_bg(atk_section, _CLR_BG_CARD, dp(8))

        atk_header = BoxLayout(size_hint_y=None, height=dp(22), spacing=dp(4))
        atk_icon_lbl = _make_label("⚔  Атака", font_sz=font_small, color=_CLR_RED,
                                   bold=True, halign='left', height=dp(22))
        atk_icon_lbl.size_hint_x = 0.35
        atk_header.add_widget(atk_icon_lbl)

        atk_value_lbl = _make_label(f"{current_attack}", font_sz=font_normal,
                                    color=_CLR_TEXT, bold=True, height=dp(22))
        atk_value_lbl.size_hint_x = 0.25
        atk_header.add_widget(atk_value_lbl)

        atk_cost_lbl = _make_label(f"{format_number(current_attack * 2400)} крон",
                                   font_sz=font_tiny, color=_CLR_TEXT_DIM,
                                   halign='right', height=dp(22))
        atk_cost_lbl.size_hint_x = 0.40
        atk_header.add_widget(atk_cost_lbl)
        atk_section.add_widget(atk_header)

        _max_atk = max(min(int(ardanian_tokens_available * 1.5), int(_max_budget_for_stats / 2400)), 100)
        atk_slider = Slider(
            min=0, max=_max_atk, value=current_attack, step=1,
            size_hint_y=None, height=dp(38),
            cursor_size=(dp(28), dp(28)) if is_android else (dp(24), dp(24)),
            cursor_image='atlas://data/images/defaulttheme/slider_cursor'
        )
        atk_section.add_widget(atk_slider)
        layout.add_widget(atk_section)

        # --- Слайдер ЗАЩИТЫ ---
        def_section = BoxLayout(orientation='vertical', spacing=dp(2),
                                size_hint_y=None, height=dp(78),
                                padding=[padding_main, dp(4)])
        _make_rounded_bg(def_section, _CLR_BG_CARD, dp(8))

        def_header = BoxLayout(size_hint_y=None, height=dp(22), spacing=dp(4))
        def_icon_lbl = _make_label("🛡  Защита", font_sz=font_small, color=_CLR_BLUE,
                                   bold=True, halign='left', height=dp(22))
        def_icon_lbl.size_hint_x = 0.35
        def_header.add_widget(def_icon_lbl)

        def_value_lbl = _make_label(f"{current_defense}", font_sz=font_normal,
                                    color=_CLR_TEXT, bold=True, height=dp(22))
        def_value_lbl.size_hint_x = 0.25
        def_header.add_widget(def_value_lbl)

        def_cost_lbl = _make_label(f"{format_number(current_defense * 3200)} крон",
                                   font_sz=font_tiny, color=_CLR_TEXT_DIM,
                                   halign='right', height=dp(22))
        def_cost_lbl.size_hint_x = 0.40
        def_header.add_widget(def_cost_lbl)
        def_section.add_widget(def_header)

        _max_def = max(int(ardanian_tokens_available), 100)
        def_slider = Slider(
            min=0, max=_max_def, value=current_defense, step=1,
            size_hint_y=None, height=dp(38),
            cursor_size=(dp(28), dp(28)) if is_android else (dp(24), dp(24)),
            cursor_image='atlas://data/images/defaulttheme/slider_cursor'
        )
        def_section.add_widget(def_slider)
        layout.add_widget(def_section)

        # --- Выбор сезона ---
        season_panel = BoxLayout(orientation='horizontal', size_hint_y=None,
                                 height=dp(36), padding=[padding_main, dp(2)], spacing=dp(6))
        _make_rounded_bg(season_panel, _CLR_BG_CARD, dp(8))

        season_title = _make_label("Сезон:", font_sz=font_small, color=_CLR_PURPLE_LIGHT,
                                   bold=True, halign='left', height=dp(30))
        season_title.size_hint_x = 0.22
        season_panel.add_widget(season_title)

        prev_season_btn = _make_action_btn("◀", (0.25, 0.20, 0.40, 1),
                                           font_sz=font_small, height=dp(30))
        prev_season_btn.size_hint_x = 0.12
        season_panel.add_widget(prev_season_btn)

        season_lbl = _make_label(current_data['season'], font_sz=font_small,
                                 color=_CLR_TEXT, height=dp(30))
        season_lbl.size_hint_x = 0.54
        season_panel.add_widget(season_lbl)

        next_season_btn = _make_action_btn("▶", (0.25, 0.20, 0.40, 1),
                                           font_sz=font_small, height=dp(30))
        next_season_btn.size_hint_x = 0.12
        season_panel.add_widget(next_season_btn)
        layout.add_widget(season_panel)

        seasons = [
            'Нет', 'Весна', 'Лето', 'Осень', 'Зима',
            'Весна, Лето', 'Весна, Осень', 'Весна, Зима',
            'Лето, Осень', 'Лето, Зима', 'Осень, Зима',
            'Весна, Лето, Осень', 'Весна, Лето, Зима',
            'Весна, Осень, Зима', 'Лето, Осень, Зима',
            'Все'
        ]
        season_index = [seasons.index(current_data['season']) if current_data['season'] in seasons else 0]

        def on_prev_season(*_):
            season_index[0] = (season_index[0] - 1) % len(seasons)
            season_lbl.text = seasons[season_index[0]]

        def on_next_season(*_):
            season_index[0] = (season_index[0] + 1) % len(seasons)
            season_lbl.text = seasons[season_index[0]]

        prev_season_btn.bind(on_release=on_prev_season)
        next_season_btn.bind(on_release=on_next_season)

        # Спейсер
        layout.add_widget(BoxLayout(size_hint_y=1))

        # --- Навигация ---
        bottom = BoxLayout(orientation='horizontal', size_hint_y=None,
                           height=btn_height + dp(12), spacing=dp(8),
                           padding=[padding_main, dp(6)])
        _make_rounded_bg(bottom, _CLR_BG_PANEL, dp(10))

        back_btn = _make_action_btn("← Назад", _CLR_GOLD_DIM)
        next_btn = _make_action_btn("Далее  ➜", (0.18, 0.52, 0.28, 1))
        bottom.add_widget(back_btn)
        bottom.add_widget(next_btn)
        layout.add_widget(bottom)

        # --- Обновление значений ---
        def update_values(*_):
            av = int(atk_slider.value)
            dv = int(def_slider.value)
            atk_value_lbl.text = str(av)
            def_value_lbl.text = str(dv)
            atk_cost_lbl.text = f"{format_number(av * 2400)} крон"
            def_cost_lbl.text = f"{format_number(dv * 3200)} крон"

            tu, ta, td = calculate_tokens(av, dv)
            used_label.text = f"Использовано: {tu:.1f}  (⚔ {ta:.1f}  🛡 {td:.1f})"
            total_c = av * 2400 + dv * 3200
            cost_label.text = f"Стоимость: {format_number(total_c)} крон"

            if tu > ardanian_tokens_available:
                balance_label.color = _CLR_RED
                balance_label.text = f"ПРЕВЫШЕН БЮДЖЕТ!  Нужно: {tu:.1f} / {ardanian_tokens_available:.1f}"
                next_btn.disabled = True
                if hasattr(next_btn, '_bg_color'):
                    next_btn._bg_color.rgba = (0.3, 0.3, 0.3, 1)
            else:
                balance_label.color = _CLR_GREEN
                balance_label.text = f"Жетоны: {ardanian_tokens_available:.1f}  |  Осталось: {ardanian_tokens_available - tu:.1f}"
                next_btn.disabled = False
                if hasattr(next_btn, '_bg_color'):
                    next_btn._bg_color.rgba = (0.18, 0.52, 0.28, 1)

            current_data['attack'] = av
            current_data['defense'] = dv

        atk_slider.bind(value=update_values)
        def_slider.bind(value=update_values)
        update_values()

        def on_back(*_):
            current_data['attack'] = int(atk_slider.value)
            current_data['defense'] = int(def_slider.value)
            current_data['season'] = seasons[season_index[0]]
            switch_to_screen(screen1)

        def on_next(*_):
            av = int(atk_slider.value)
            dv = int(def_slider.value)
            tu, _, _ = calculate_tokens(av, dv)
            if tu > ardanian_tokens_available:
                show_message("Бюджет", "Недостаточно жетонов Ардании!")
                return
            current_data['attack'] = av
            current_data['defense'] = dv
            current_data['season'] = seasons[season_index[0]]
            switch_to_screen(screen3)

        back_btn.bind(on_release=on_back)
        next_btn.bind(on_release=on_next)

    # ======================================================================
    #  ЭКРАН 3 — Итоговый чертёж и создание
    # ======================================================================

    def screen3(layout):
        # --- Шапка ---
        header = BoxLayout(orientation='vertical', size_hint_y=None, height=dp(56),
                           padding=[padding_main, dp(6), padding_main, 0])
        _make_rounded_bg(header, _CLR_BG_PANEL, dp(10))
        header.add_widget(_make_label(_step_indicator(3), font_sz=font_normal, height=dp(18)))
        header.add_widget(_make_label("Чертёж артефакта", font_sz=font_title,
                                      color=_CLR_GOLD, bold=True, height=dp(28)))
        layout.add_widget(header)

        # --- Большая карточка артефакта ---
        card = BoxLayout(orientation='vertical', size_hint_y=None,
                         height=preview_size + dp(120),
                         padding=[padding_main, dp(8)], spacing=dp(6))
        _make_rounded_bg(card, _CLR_BG_CARD, dp(12))

        # Изображение по центру (крупное)
        img_row = BoxLayout(size_hint_y=None, height=preview_size)
        img_row.add_widget(BoxLayout())  # left spacer

        _icon_path = os.path.join(artifact_images_path, current_data['icon']) if current_data['icon'] else ''
        big_img = Image(
            source=_icon_path,
            size_hint=(None, None),
            size=(preview_size - dp(16), preview_size - dp(16)),
            pos_hint={'center_y': 0.5},
            allow_stretch=True, keep_ratio=True
        )
        img_row.add_widget(big_img)
        img_row.add_widget(BoxLayout())  # right spacer
        card.add_widget(img_row)

        # Название
        card.add_widget(_make_label(current_data['name'], font_sz=font_title,
                                    color=_CLR_GOLD, bold=True, height=dp(26)))

        # Статы
        atk_val = current_data['attack']
        def_val = current_data['defense']
        stats_text = f"⚔ Атака: [b]{atk_val}[/b]     🛡 Защита: [b]{def_val}[/b]"
        card.add_widget(_make_label(stats_text, font_sz=font_normal, color=_CLR_TEXT, height=dp(22)))

        # Сезон
        season_text = current_data['season']
        season_color = _CLR_PURPLE_LIGHT if season_text != 'Нет' else _CLR_TEXT_DIM
        card.add_widget(_make_label(f"Сезон: {season_text}", font_sz=font_small,
                                    color=season_color, height=dp(20)))

        # --- Расчет стоимости ---
        attack_bonus = current_data['attack']
        defense_bonus = current_data['defense']

        attack_cost = abs(attack_bonus) * 2400
        defense_cost = abs(defense_bonus) * 3200
        base_cost = attack_cost + defense_cost

        if current_data['season'] == 'Нет':
            seasons_bonus = []
            base_cost *= 1.12
        elif current_data['season'] == 'Все':
            seasons_bonus = ['Весна', 'Лето', 'Осень', 'Зима']
            base_cost *= 0.90
        else:
            seasons_bonus = [s.strip() for s in current_data['season'].split(',')]
            if len(seasons_bonus) == 1:
                base_cost *= 0.25
            elif len(seasons_bonus) == 2:
                consecutive_pairs = [
                    ['Весна', 'Лето'], ['Лето', 'Осень'],
                    ['Осень', 'Зима'], ['Зима', 'Весна']
                ]
                if sorted(seasons_bonus) in [sorted(p) for p in consecutive_pairs]:
                    base_cost *= 0.75
                else:
                    base_cost *= 0.55
            elif len(seasons_bonus) >= 3:
                base_cost *= 0.90

        negative_modifier = 1.0
        if attack_bonus < 0 or defense_bonus < 0:
            negative_count = sum(1 for x in [attack_bonus, defense_bonus] if x < 0)
            negative_modifier = 1 - (negative_count * 0.3)

        total_cost = base_cost * negative_modifier
        _fn3 = getattr(faction, 'faction', '')
        _max_total = 11_950_000 if _fn3 == 'Элины' else 9_850_000
        total_cost = max(20000, min(total_cost, _max_total))

        # Стоимость
        cost_row = BoxLayout(size_hint_y=None, height=dp(24))
        cost_row.add_widget(_make_label(
            f"Стоимость: [b]{format_number(int(total_cost))}[/b] крон  +  50 000 (чертёж)",
            font_sz=font_small, color=_CLR_TEXT, height=dp(24)
        ))
        card.add_widget(cost_row)

        layout.add_widget(card)

        # --- Выбор слота ---
        slot_panel = BoxLayout(orientation='horizontal', size_hint_y=None,
                               height=dp(38), padding=[padding_main, dp(2)], spacing=dp(6))
        _make_rounded_bg(slot_panel, _CLR_BG_CARD, dp(8))

        slot_title = _make_label("Слот:", font_sz=font_small, color=_CLR_SLOT_BORDER,
                                 bold=True, halign='left', height=dp(32))
        slot_title.size_hint_x = 0.18
        slot_panel.add_widget(slot_title)

        prev_slot_btn = _make_action_btn("◀", (0.25, 0.20, 0.40, 1),
                                         font_sz=font_small, height=dp(30))
        prev_slot_btn.size_hint_x = 0.12
        slot_panel.add_widget(prev_slot_btn)

        slots = ['Оружие', 'Голова', 'Ноги', 'Туловище', 'Аксессуар']
        slot_index = [slots.index(current_data['slot']) if current_data['slot'] in slots else 0]

        slot_lbl = _make_label(slots[slot_index[0]], font_sz=font_normal,
                               color=_CLR_TEXT, bold=True, height=dp(32))
        slot_lbl.size_hint_x = 0.58
        slot_panel.add_widget(slot_lbl)

        next_slot_btn = _make_action_btn("▶", (0.25, 0.20, 0.40, 1),
                                         font_sz=font_small, height=dp(30))
        next_slot_btn.size_hint_x = 0.12
        slot_panel.add_widget(next_slot_btn)
        layout.add_widget(slot_panel)

        def on_prev_slot(*_):
            slot_index[0] = (slot_index[0] - 1) % len(slots)
            slot_lbl.text = slots[slot_index[0]]

        def on_next_slot(*_):
            slot_index[0] = (slot_index[0] + 1) % len(slots)
            slot_lbl.text = slots[slot_index[0]]

        prev_slot_btn.bind(on_release=on_prev_slot)
        next_slot_btn.bind(on_release=on_next_slot)

        # Спейсер
        layout.add_widget(BoxLayout(size_hint_y=1))

        # --- Кнопка создания ---
        create_btn = _make_action_btn("✦  Создать чертёж  ✦", _CLR_PURPLE,
                                      font_sz=font_title, height=dp(44))
        create_btn.padding = [padding_main, 0]
        layout.add_widget(create_btn)

        # --- Навигация ---
        bottom = BoxLayout(orientation='horizontal', size_hint_y=None,
                           height=btn_height + dp(12), spacing=dp(8),
                           padding=[padding_main, dp(6)])
        _make_rounded_bg(bottom, _CLR_BG_PANEL, dp(10))

        back_btn = _make_action_btn("← Назад", _CLR_GOLD_DIM)
        close_btn = _make_action_btn("Закрыть", _CLR_RED)
        bottom.add_widget(back_btn)
        bottom.add_widget(close_btn)
        layout.add_widget(bottom)

        # --- События ---
        def on_back(*_):
            current_data['slot'] = slots[slot_index[0]]
            switch_to_screen(screen2)

        def on_create(*_):
            current_data['slot'] = slots[slot_index[0]]

            if current_data['attack'] == 0 and current_data['defense'] == 0:
                show_message("Ошибка",
                             "Артефакт должен иметь хотя бы одну характеристику!\n"
                             "Установите Атаку или Защиту больше 0.")
                return

            _fn = getattr(faction, 'faction', '')
            _max_cost = 12_000_000 if _fn == 'Элины' else 9_900_000
            _full_cost = total_cost + 50_000
            if _full_cost > _max_cost:
                show_message("Ошибка",
                             f"Общая стоимость ({format_number(int(_full_cost))} крон)\n"
                             f"превышает лимит {format_number(_max_cost)} крон.")
                return

            if faction.money < 50000:
                show_message("Ошибка", "Недостаточно средств для чертежа (50 000 крон)")
                return

            faction.money -= 50000

            artifact_name = current_data['name'] or generate_random_name()[0]
            image_path = os.path.join(artifact_images_path, current_data['icon'])
            artifact_type_map = {
                'Оружие': 0, 'Голова': 1, 'Ноги': 2,
                'Туловище': 3, 'Аксессуар': 4
            }

            try:
                cursor = db_conn.cursor()
                cursor.execute("SELECT MAX(id) FROM artifacts")
                result = cursor.fetchone()
                new_id = (result[0] or 0) + 1

                cursor.execute('''
                    INSERT INTO artifacts (id, attack, defense, season_name, image_url, name, cost, artifact_type, is_created)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    new_id,
                    attack_bonus,
                    defense_bonus,
                    ', '.join(seasons_bonus),
                    image_path,
                    artifact_name,
                    int(total_cost),
                    artifact_type_map[current_data['slot']],
                    1
                ))
                db_conn.commit()
                show_message("Успех", f"Артефакт «{artifact_name}» создан и добавлен в лавку!")
                workshop_popup.dismiss()
            except Exception as e:
                show_message("Ошибка", f"Не удалось создать артефакт: {e}")

        back_btn.bind(on_release=on_back)
        close_btn.bind(on_release=lambda x: workshop_popup.dismiss())
        create_btn.bind(on_release=on_create)

    # === Запуск ===
    switch_to_screen(screen1)
    workshop_popup.open()
