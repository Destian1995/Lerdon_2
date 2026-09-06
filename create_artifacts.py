import os

from kivy.uix.popup import Popup
from kivy.uix.boxlayout import BoxLayout

from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.slider import Slider

from kivy.uix.image import Image
from kivy.graphics import Color, RoundedRectangle

from kivy.metrics import dp, sp
from kivy.core.window import Window
import random

from ui_components import show_message

from utils.helpers import format_number


def workshop(faction, db_conn):
    # === Определение устройства ===
    is_android = hasattr(Window, 'keyboard')

    # === Адаптивные размеры ===
    font_title = sp(16) if not is_android else sp(14)
    font_normal = sp(12) if not is_android else sp(10)
    font_small = sp(10) if not is_android else sp(8)

    padding_main = dp(8) if is_android else dp(12)
    spacing_main = dp(4) if is_android else dp(6)
    btn_height = dp(30) if is_android else dp(35)
    input_height = dp(25) if is_android else dp(30)
    label_height = dp(20) if is_android else dp(25)

    # === Создание всплывающего окна ===
    workshop_popup = Popup(
        title="Мастерская артефактов",
        size_hint=(0.98, 0.95),
        title_size=font_title,
        title_align='center',
        title_color=(0.9, 0.9, 0.9, 1),
        background_color=(0.08, 0.08, 0.08, 0.98),  # Темнее
        separator_color=(0.3, 0.3, 0.3, 1),
        auto_dismiss=False
    )

    # === Данные между экранами ===
    current_data = {
        'icon': None,
        'name': '',
        'attack': 0,
        'defense': 0,
        'season': 'Нет',
        'slot': 'Оружие'  # По умолчанию
    }

    # === Список изображений ===
    artifact_images_path = r"files/pict/artifacts/custom"
    if os.path.exists(artifact_images_path):
        image_files = [f for f in os.listdir(artifact_images_path) if
                       f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp'))]
    else:
        image_files = []

    selected_image = [None]
    current_index = [0]

    # === Функция переключения экрана ===
    def switch_to_screen(screen_func):
        layout = BoxLayout(orientation='vertical', padding=padding_main, spacing=spacing_main)
        screen_func(layout)
        workshop_popup.content = layout

    # === Функция генерации случайного названия ===
    def generate_random_name(filename=None):
        """
        Генерирует случайное название артефакта на основе типа и подкласса,
        определённых по первым символам имени файла.

        Формат имени файла: {type}{subclass}...
        Примеры: '0v_sniper.png' (огнестрел), '1c_royal.jpg' (корона), '3p_knight.png' (латы)

        :param filename: имя файла (например, '0vап.png', '3r_mage.jpg') или None
        :return: tuple (название_артефакта, тип_артефакта)
        """
        # === ПОДКЛАССЫ ДЛЯ ОРУЖИЯ (тип 0) ===
        weapon_subclasses = {
            'v': ["Винтовка", "Ружьё", "Карабин"],
            'a': ["Арбалет"],
            'm': ["Меч", "Клинок", "Кинжал", "Сабля"],
            'p': ["Посох", "Скипетр", "Жезл"],
            'k': ["Копье"],
            's': ["Секира", "Топор"],
            'l': ["Лук"]
        }

        # === ПОДКЛАССЫ ДЛЯ ГОЛОВЫ (тип 1) ===
        head_subclasses = {
            'k': ["Корона", "Диадема"],
            'h': ["Шлем"],
            's': ["Шляпа", "Колпак"],
            'v': ["Венок"],
        }

        # === ПОДКЛАССЫ ДЛЯ НОГ (тип 2) ===
        legs_subclasses = {
            's': ["Сапоги", "Ботинки"],
        }

        # === ПОДКЛАССЫ ДЛЯ ТУЛОВИЩА (тип 3) ===
        torso_subclasses = {
            'b': ["Броня", "Латы", "Кираса", "Панцирь", "Доспех"],
            'm': ["Мантия", "Плащ", "Накидка"],
            'g': ["Жилет", "Камзол", "Дублет"],
        }

        # === ПОДКЛАССЫ ДЛЯ АКСЕССУАРОВ (тип 4) ===
        accessory_subclasses = {
            'k': ["Кольцо", "Перстень"],
            'a': ["Амулет", "Талисман", "Медальон", "Филактерия", "Оберег"],
            's': ["Серьга"],
        }

        # === ОБЩИЕ СПИСКИ ПО ТИПАМ (fallback, если подкласс не указан) ===
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

        # === Общие суффиксы для всех типов ===
        suffixes = [
            "Силы", "Защиты", "Мудрости", "Света", "Тьмы", "Мощи",
            "Вампиров", "Эльфов", "Просветления", "Судьбы", "Веры",
            "Смерти", "Багровой крови", "Мастеров", "Дракона", "Феникса",
            "Бездны", "Рассвета", "Заката", "Бури", "Огня", "Льда",
            "Ветра", "Земли", "Воды", "Грома", "Теней", "Истины", "Хаоса"
        ]

        # === По умолчанию — тип 0 (оружие) ===
        artifact_type = 0

        if filename:
            try:
                # Убираем расширение и приводим к нижнему регистру
                clean_name = os.path.splitext(filename.strip())[0].lower().replace(' ', '_')

                if len(clean_name) >= 1 and clean_name[0].isdigit():
                    # Первый символ — тип артефакта (0-4)
                    artifact_type = int(clean_name[0])

                    # === ПРОВЕРКА ПОДКЛАССА (вторая буква) ===
                    if len(clean_name) >= 2 and clean_name[1].isalpha():
                        subclass_key = clean_name[1]  # 'v', 'm', 'c', 'b', 'r' и т.д.

                        # Выбираем словарь подклассов по типу артефакта
                        subclass_dict = {
                            0: weapon_subclasses,
                            1: head_subclasses,
                            2: legs_subclasses,
                            3: torso_subclasses,
                            4: accessory_subclasses,
                        }.get(artifact_type, {})

                        # Если подкласс найден — используем специализированный список
                        if subclass_key in subclass_dict:
                            prefixes = subclass_dict[subclass_key]
                            print(f"[DEBUG] Тип {artifact_type}, подкласс '{subclass_key}' → {prefixes[:3]}...")
                        else:
                            # Подкласс не найден — берём общий список по типу
                            prefixes = prefixes_by_type.get(artifact_type, prefixes_by_type[0])
                            print(
                                f"[DEBUG] Подкласс '{subclass_key}' не найден для типа {artifact_type}, используем общий список")
                    else:
                        # Нет второй буквы — берём общий список по типу
                        prefixes = prefixes_by_type.get(artifact_type, prefixes_by_type[0])
                else:
                    # Не начинается с цифры — fallback на оружие
                    prefixes = prefixes_by_type[0]

            except (IndexError, ValueError, AttributeError) as e:
                print(f"[WARNING] Не удалось определить подкласс для '{filename}': {e}")
                prefixes = prefixes_by_type.get(artifact_type, prefixes_by_type[0])
        else:
            # filename=None — берём общий список оружия
            prefixes = prefixes_by_type[0]

        # === Генерация названия ===
        prefix = random.choice(prefixes)
        suffix = random.choice(suffixes)

        # Возвращаем название и тип артефакта (для автоустановки слота)
        return f"{prefix} {suffix}", artifact_type

    # === Экран 1: Выбор иконки и названия ===
    def screen1(layout):
        # Заголовок
        title = Label(
            text="Выберите иконку артефакта",
            font_size=font_normal,
            color=(0.85, 0.90, 1.0, 1),
            size_hint_y=None,
            height=label_height,
            halign='center',
            valign='middle',
            bold=True
        )
        title.bind(size=lambda inst, val: setattr(inst, 'text_size', (inst.width, inst.height)))
        layout.add_widget(title)

        # Кнопки навигации иконки
        nav_layout = BoxLayout(size_hint_y=None, height=dp(28), spacing=dp(4))
        def _nav_btn(txt):
            b = Button(
                text=txt, size_hint_x=0.3,
                font_size=font_small, color=(1, 1, 1, 1),
                background_color=(0, 0, 0, 0),
                size_hint_y=None, height=dp(28)
            )
            with b.canvas.before:
                b._bc = Color(0.18, 0.28, 0.45, 1)
                b._br = RoundedRectangle(pos=b.pos, size=b.size, radius=[dp(8)])
            b.bind(pos=lambda i, v: setattr(i._br, 'pos', v),
                   size=lambda i, v: setattr(i._br, 'size', v))
            return b

        prev_btn = _nav_btn("<")
        next_btn = _nav_btn(">")
        nav_layout.add_widget(prev_btn)
        nav_layout.add_widget(next_btn)
        layout.add_widget(nav_layout)

        # Отображение текущей иконки
        current_icon_display = Image(
            source="" if not image_files else os.path.join(artifact_images_path, image_files[0]),
            size_hint_y=None,
            height=dp(60) if is_android else dp(72),
            allow_stretch=True,
            keep_ratio=True
        )
        layout.add_widget(current_icon_display)

        # Метка с текущим названием артефакта (только для чтения)
        name_display_label = Label(
            text="—",
            font_size=font_small,
            color=(0.75, 0.95, 0.85, 1),
            size_hint_y=None,
            height=label_height,
            halign='center',
            valign='middle',
            bold=True
        )
        name_display_label.bind(size=lambda inst, val: setattr(inst, 'text_size', (inst.width, inst.height)))
        layout.add_widget(name_display_label)

        def update_current_icon():
            if not image_files:
                current_icon_display.source = ""
                selected_image[0] = None
                name_display_label.text = "—"
                current_data['name'] = ''
                return
            idx = current_index[0] % len(image_files)
            img_filename = image_files[idx]
            img_path = os.path.join(artifact_images_path, img_filename)
            current_icon_display.source = img_path
            selected_image[0] = img_filename

            # === Автоопределение типа артефакта и установка слота ===
            try:
                first_char = img_filename.strip().lower()[0]
                if first_char.isdigit():
                    artifact_type = int(first_char)
                    slot_map = {0: 'Оружие', 1: 'Голова', 2: 'Ноги', 3: 'Туловище', 4: 'Аксессуар'}
                    if artifact_type in slot_map:
                        current_data['slot'] = slot_map[artifact_type]
            except (IndexError, ValueError):
                pass

            # Автоматически генерируем название при смене иконки
            auto_name, detected_type = generate_random_name(img_filename)
            current_data['name'] = auto_name
            name_display_label.text = auto_name
            slot_map = {0: 'Оружие', 1: 'Голова', 2: 'Ноги', 3: 'Туловище', 4: 'Аксессуар'}
            if detected_type in slot_map:
                current_data['slot'] = slot_map[detected_type]

        def on_prev(instance):
            current_index[0] -= 1
            update_current_icon()

        def on_next(instance):
            current_index[0] += 1
            update_current_icon()

        prev_btn.bind(on_release=on_prev)
        next_btn.bind(on_release=on_next)
        update_current_icon()

        # Кнопка случайного названия (единственный способ задать имя)
        random_name_btn = Button(
            text="Сгенерировать название",
            size_hint_y=None,
            height=btn_height,
            background_color=(0, 0, 0, 0),
            font_size=font_normal,
            color=(1, 1, 1, 1),
            bold=True,
            size_hint_x=1
        )
        with random_name_btn.canvas.before:
            random_name_btn._bc = Color(0.18, 0.45, 0.55, 1)
            random_name_btn._br = RoundedRectangle(
                pos=random_name_btn.pos, size=random_name_btn.size, radius=[dp(10)]
            )
        random_name_btn.bind(
            pos=lambda i, v: setattr(i._br, 'pos', v),
            size=lambda i, v: setattr(i._br, 'size', v)
        )
        layout.add_widget(random_name_btn)

        # Кнопки навигации внизу
        btn_box = BoxLayout(orientation='horizontal', spacing=dp(4), size_hint=(1, None), height=btn_height)

        def _action_btn(txt, color):
            b = Button(
                text=txt, size_hint=(0.5, 1),
                background_color=(0, 0, 0, 0),
                font_size=font_normal, color=(1, 1, 1, 1), bold=True
            )
            with b.canvas.before:
                b._bc = Color(*color)
                b._br = RoundedRectangle(pos=b.pos, size=b.size, radius=[dp(10)])
            b.bind(pos=lambda i, v: setattr(i._br, 'pos', v),
                   size=lambda i, v: setattr(i._br, 'size', v))
            return b

        close_btn = _action_btn("Закрыть", (0.65, 0.18, 0.18, 1))
        next_scr_btn = _action_btn("Далее", (0.18, 0.55, 0.22, 1))
        btn_box.add_widget(close_btn)
        btn_box.add_widget(next_scr_btn)
        layout.add_widget(btn_box)

        # Привязка событий
        def on_next_screen(instance):
            current_data['icon'] = selected_image[0]
            if not current_data['icon']:
                show_message("Ошибка", "Пожалуйста, выберите иконку")
                return
            # Если название ещё не сгенерировано — генерируем автоматически
            if not current_data.get('name'):
                auto_name, _ = generate_random_name(selected_image[0])
                current_data['name'] = auto_name
            switch_to_screen(screen2)

        def on_random_name(instance):
            name, detected_type = generate_random_name(selected_image[0])
            current_data['name'] = name
            name_display_label.text = name
            slot_map = {0: 'Оружие', 1: 'Голова', 2: 'Ноги', 3: 'Туловище', 4: 'Аксессуар'}
            if detected_type in slot_map:
                current_data['slot'] = slot_map[detected_type]

        close_btn.bind(on_release=lambda x: workshop_popup.dismiss())
        next_scr_btn.bind(on_release=on_next_screen)
        random_name_btn.bind(on_release=on_random_name)

    # === Экран 2: Выбор характеристик через слайдеры с системой жетонов Ардании ===
    def screen2(layout):

        # === Система жетонов Ардании ===
        ardanian_tokens_available = faction.money / 2000.0
        current_attack = current_data.get('attack', 0)
        current_defense = current_data.get('defense', 0)

        def calculate_tokens(attack, defense):
            tokens_attack = attack * 0.25
            tokens_defense = defense * 0.5
            return tokens_attack + tokens_defense, tokens_attack, tokens_defense

        tokens_used, tokens_attack, tokens_defense = calculate_tokens(current_attack, current_defense)

        # === Отображение баланса жетонов ===
        tokens_info = BoxLayout(orientation='vertical', size_hint_y=None, height=dp(75))

        balance_label = Label(
            text=f"Доступно жетонов Ардании: {ardanian_tokens_available:.1f}",
            font_size=font_small,
            color=(0.7, 0.9, 0.7, 1) if tokens_used <= ardanian_tokens_available else (0.9, 0.3, 0.3, 1),
            size_hint_y=None,
            height=label_height * 1.3,
            halign='center',
            valign='middle',
            bold=True
        )
        balance_label.bind(size=lambda inst, val: setattr(inst, 'text_size', (inst.width * 0.95, None)))
        tokens_info.add_widget(balance_label)

        used_label = Label(
            text=f"Использовано: {tokens_used:.1f} (Атака: {tokens_attack:.1f}, Защита: {tokens_defense:.1f})",
            font_size=font_small,
            color=(0.9, 0.9, 0.5, 1),
            size_hint_y=None,
            height=label_height,
            halign='center',
            valign='middle'
        )
        used_label.bind(size=lambda inst, val: setattr(inst, 'text_size', (inst.width * 0.95, None)))
        tokens_info.add_widget(used_label)

        cost_label = Label(
            text=f"Стоимость: {format_number(int((current_attack * 600) + (current_defense * 800)))} крон",
            font_size=font_small,
            color=(0.9, 0.9, 0.9, 1),
            size_hint_y=None,
            height=label_height,
            halign='center',
            valign='middle'
        )
        cost_label.bind(size=lambda inst, val: setattr(inst, 'text_size', (inst.width * 0.95, None)))
        tokens_info.add_widget(cost_label)

        layout.add_widget(tokens_info)

        # === Слайдер АТАКИ ===
        attack_section = BoxLayout(orientation='vertical', spacing=dp(2), size_hint_y=None, height=dp(85))

        attack_header = BoxLayout(orientation='horizontal', size_hint_y=None, height=label_height)
        attack_title = Label(
            text="Атака:",
            font_size=font_small,
            color=(0.9, 0.9, 0.9, 1),
            size_hint_x=0.25,
            halign='left',
            valign='middle'
        )
        attack_title.bind(size=lambda inst, val: setattr(inst, 'text_size', (inst.width, inst.height)))
        attack_header.add_widget(attack_title)

        attack_value_label = Label(
            text=f"{current_attack}%",
            font_size=font_small,
            color=(0.7, 0.9, 0.7, 1),
            size_hint_x=0.2,
            halign='center',
            valign='middle',
            bold=True
        )
        attack_value_label.bind(size=lambda inst, val: setattr(inst, 'text_size', (inst.width, inst.height)))
        attack_header.add_widget(attack_value_label)

        attack_cost_label = Label(
            text=f"{int(current_attack * 600)} крон",
            font_size=font_small,
            color=(0.7, 0.9, 0.7, 1),
            size_hint_x=0.55,
            halign='right',
            valign='middle'
        )
        attack_cost_label.bind(size=lambda inst, val: setattr(inst, 'text_size', (inst.width, inst.height)))
        attack_header.add_widget(attack_cost_label)

        attack_section.add_widget(attack_header)

        # Динамический максимум без искусственных ограничений
        max_attack_possible = max(int(ardanian_tokens_available / 0.25 * 1.5), 200)
        attack_slider = Slider(
            min=0,
            max=max_attack_possible,
            value=current_attack,
            step=1,
            size_hint_y=None,
            height=dp(35),
            background_width=dp(3),
            cursor_size=(dp(30), dp(30)) if is_android else (dp(25), dp(25)),
            cursor_image='atlas://data/images/defaulttheme/slider_cursor'
        )
        attack_section.add_widget(attack_slider)
        layout.add_widget(attack_section)

        # === Слайдер ЗАЩИТЫ ===
        defense_section = BoxLayout(orientation='vertical', spacing=dp(2), size_hint_y=None, height=dp(85))

        defense_header = BoxLayout(orientation='horizontal', size_hint_y=None, height=label_height)
        defense_title = Label(
            text="Защита:",
            font_size=font_small,
            color=(0.9, 0.9, 0.9, 1),
            size_hint_x=0.25,
            halign='left',
            valign='middle'
        )
        defense_title.bind(size=lambda inst, val: setattr(inst, 'text_size', (inst.width, inst.height)))
        defense_header.add_widget(defense_title)

        defense_value_label = Label(
            text=f"{current_defense}%",
            font_size=font_small,
            color=(0.7, 0.9, 0.7, 1),
            size_hint_x=0.2,
            halign='center',
            valign='middle',
            bold=True
        )
        defense_value_label.bind(size=lambda inst, val: setattr(inst, 'text_size', (inst.width, inst.height)))
        defense_header.add_widget(defense_value_label)

        defense_cost_label = Label(
            text=f"{int(current_defense * 800)} крон",
            font_size=font_small,
            color=(0.7, 0.9, 0.7, 1),
            size_hint_x=0.55,
            halign='right',
            valign='middle'
        )
        defense_cost_label.bind(size=lambda inst, val: setattr(inst, 'text_size', (inst.width, inst.height)))
        defense_header.add_widget(defense_cost_label)

        defense_section.add_widget(defense_header)

        max_defense_possible = max(int(ardanian_tokens_available / 0.5 * 1.5), 200)
        defense_slider = Slider(
            min=0,
            max=max_defense_possible,
            value=current_defense,
            step=1,
            size_hint_y=None,
            height=dp(35),
            background_width=dp(3),
            cursor_size=(dp(30), dp(30)) if is_android else (dp(25), dp(25)),
            cursor_image='atlas://data/images/defaulttheme/slider_cursor'
        )
        defense_section.add_widget(defense_slider)
        layout.add_widget(defense_section)

        prev_season_btn = Button(
            text="<",
            size_hint_x=0.2,
            font_size=font_small,
            background_color=(0.2, 0.2, 0.2, 1),
            background_normal='',
            size_hint_y=None,
            height=dp(25)
        )
        current_season_label = Label(
            text=current_data['season'],
            font_size=font_small,
            color=(0.9, 0.9, 0.9, 1),
            halign='center',
            valign='middle',
            size_hint_x=0.6
        )
        current_season_label.bind(size=lambda inst, val: setattr(inst, 'text_size', (inst.width, inst.height)))
        next_season_btn = Button(
            text=">",
            size_hint_x=0.2,
            font_size=font_small,
            background_color=(0.2, 0.2, 0.2, 1),
            background_normal='',
            size_hint_y=None,
            height=dp(25)
        )

        seasons = [
            'Нет', 'Весна', 'Лето', 'Осень', 'Зима',
            'Весна, Лето', 'Весна, Осень', 'Весна, Зима',
            'Лето, Осень', 'Лето, Зима', 'Осень, Зима',
            'Весна, Лето, Осень', 'Весна, Лето, Зима',
            'Весна, Осень, Зима', 'Лето, Осень, Зима',
            'Все'
        ]
        season_index = [seasons.index(current_data['season']) if current_data['season'] in seasons else 0]

        def update_season_label():
            current_season_label.text = seasons[season_index[0]]

        def on_prev_season(instance):
            season_index[0] = (season_index[0] - 1) % len(seasons)
            update_season_label()

        def on_next_season(instance):
            season_index[0] = (season_index[0] + 1) % len(seasons)
            update_season_label()

        prev_season_btn.bind(on_release=on_prev_season)
        next_season_btn.bind(on_release=on_next_season)

        # === Кнопки навигации (СОЗДАЁМ ДО вызова update_values!) ===
        btn_box = BoxLayout(orientation='horizontal', spacing=dp(4), size_hint=(1, None), height=btn_height)

        def _s2_btn(txt, clr):
            b = Button(
                text=txt, size_hint=(0.5, 1),
                background_color=(0, 0, 0, 0),
                font_size=font_normal, color=(1, 1, 1, 1), bold=True
            )
            with b.canvas.before:
                b._bc = Color(*clr)
                b._br = RoundedRectangle(pos=b.pos, size=b.size, radius=[dp(10)])
            b.bind(pos=lambda i, v: setattr(i._br, 'pos', v),
                   size=lambda i, v: setattr(i._br, 'size', v))
            return b

        back_btn = _s2_btn("Назад", (0.50, 0.42, 0.10, 1))
        next_scr_btn = _s2_btn("Далее", (0.18, 0.55, 0.22, 1))
        btn_box.add_widget(back_btn)
        btn_box.add_widget(next_scr_btn)
        layout.add_widget(btn_box)

        # === Функция обновления значений (теперь имеет доступ к next_scr_btn) ===
        def update_values(*args):
            attack_val = int(attack_slider.value)
            defense_val = int(defense_slider.value)

            # Обновляем отображение
            attack_value_label.text = f"{attack_val}%"
            defense_value_label.text = f"{defense_val}%"
            attack_cost_label.text = f"{int(attack_val * 600)} крон"
            defense_cost_label.text = f"{int(defense_val * 800)} крон"

            # Расчет жетонов
            tokens_used, tokens_a, tokens_d = calculate_tokens(attack_val, defense_val)
            used_label.text = f"Использовано: {tokens_used:.1f} (Атака: {tokens_a:.1f}, Защита: {tokens_d:.1f})"

            # Расчет стоимости
            total_cost = (attack_val * 600) + (defense_val * 800)
            cost_label.text = f"Стоимость: {format_number(int(total_cost))} крон"

            # Валидация бюджета
            if tokens_used > ardanian_tokens_available:
                balance_label.color = (0.95, 0.3, 0.3, 1)
                balance_label.text = f"БЮДЖЕТ ПРЕВЫШЕН! Доступно: {ardanian_tokens_available:.1f}, Нужно: {tokens_used:.1f}"
                next_scr_btn.disabled = True
                if hasattr(next_scr_btn, '_bc'):
                    next_scr_btn._bc.rgba = (0.35, 0.35, 0.35, 1)
            else:
                balance_label.color = (0.6, 0.95, 0.6, 1)
                balance_label.text = f"Доступно жетонов: {ardanian_tokens_available:.1f} | Использовано: {tokens_used:.1f}"
                next_scr_btn.disabled = False
                if hasattr(next_scr_btn, '_bc'):
                    next_scr_btn._bc.rgba = (0.18, 0.55, 0.22, 1)

            # Сохраняем текущие значения
            current_data['attack'] = attack_val
            current_data['defense'] = defense_val

        # Привязка обновления к слайдерам
        attack_slider.bind(value=update_values)
        defense_slider.bind(value=update_values)

        # Инициализация значений (вызываем ПОСЛЕ создания всех виджетов)
        update_values()

        # === Привязка событий кнопок ===
        def on_back(instance):
            current_data['attack'] = int(attack_slider.value)
            current_data['defense'] = int(defense_slider.value)
            current_data['season'] = seasons[season_index[0]]
            switch_to_screen(screen1)

        def on_next_screen(instance):
            attack_val = int(attack_slider.value)
            defense_val = int(defense_slider.value)
            tokens_used, _, _ = calculate_tokens(attack_val, defense_val)

            if tokens_used > ardanian_tokens_available:
                show_message("Ошибка бюджета",
                             f"Недостаточно жетонов Ардании!\n"
                             f"Доступно: {ardanian_tokens_available:.1f}\n"
                             f"Требуется: {tokens_used:.1f}\n\n"
                             f"Уменьшите параметры артефакта.")
                return

            current_data['attack'] = attack_val
            current_data['defense'] = defense_val
            current_data['season'] = seasons[season_index[0]]
            switch_to_screen(screen3)

        back_btn.bind(on_release=on_back)
        next_scr_btn.bind(on_release=on_next_screen)

    # === Экран 3: Выбор слота и создание ===
    def screen3(layout):
        # Заголовок
        title = Label(
            text="Выберите слот и создайте чертеж артефакта",
            font_size=font_normal,
            color=(0.9, 0.9, 0.9, 1),
            size_hint_y=None,
            height=label_height,
            halign='center',
            valign='middle'
        )
        title.bind(size=lambda inst, val: setattr(inst, 'text_size', (inst.width, inst.height)))
        layout.add_widget(title)

        # Слот — теперь кнопки
        slot_label = Label(
            text="Слот артефакта:",
            font_size=font_small,
            color=(0.9, 0.9, 0.9, 1),
            size_hint_y=None,
            height=label_height,
            halign='left',
            valign='middle'
        )
        slot_label.bind(size=lambda inst, val: setattr(inst, 'text_size', (inst.width, inst.height)))
        layout.add_widget(slot_label)

        # Кнопки для выбора слота
        slot_layout = BoxLayout(orientation='horizontal', spacing=dp(3), size_hint_y=None, height=dp(25))
        prev_slot_btn = Button(
            text="<",
            size_hint_x=0.2,
            font_size=font_small,
            background_color=(0.2, 0.2, 0.2, 1),
            background_normal='',
            size_hint_y=None,
            height=dp(25)
        )
        current_slot_label = Label(
            text=current_data['slot'],
            font_size=font_small,
            color=(0.9, 0.9, 0.9, 1),
            halign='center',
            valign='middle',
            size_hint_x=0.6
        )
        current_slot_label.bind(size=lambda inst, val: setattr(inst, 'text_size', (inst.width, inst.height)))
        next_slot_btn = Button(
            text=">",
            size_hint_x=0.2,
            font_size=font_small,
            background_color=(0.2, 0.2, 0.2, 1),
            background_normal='',
            size_hint_y=None,
            height=dp(25)
        )
        slot_layout.add_widget(prev_slot_btn)
        slot_layout.add_widget(current_slot_label)
        slot_layout.add_widget(next_slot_btn)
        layout.add_widget(slot_layout)

        # Список слотов
        slots = ['Оружие', 'Голова', 'Ноги', 'Туловище', 'Аксессуар']
        slot_index = [0]
        # === Сначала объявляем функции ===
        def update_slot_label():
            current_slot_label.text = slots[slot_index[0]]

        def on_prev_slot(instance):
            slot_index[0] = (slot_index[0] - 1) % len(slots)
            update_slot_label()

        def on_next_slot(instance):
            slot_index[0] = (slot_index[0] + 1) % len(slots)
            update_slot_label()

        # === Привязка кнопок ===
        prev_slot_btn.bind(on_release=on_prev_slot)
        next_slot_btn.bind(on_release=on_next_slot)

        # === Только теперь синхронизируем и обновляем отображение ===
        slot_index[0] = slots.index(current_data['slot']) if current_data['slot'] in slots else 0
        update_slot_label()  # ✅ Теперь функция уже определена
        prev_slot_btn.bind(on_release=on_prev_slot)
        next_slot_btn.bind(on_release=on_next_slot)

        # === Отображение итогового артефакта ===
        artifact_title = Label(
            text="Итоговый артефакт:",
            font_size=font_normal,
            color=(0.9, 0.9, 0.9, 1),
            size_hint_y=None,
            height=label_height,
            halign='center',
            valign='middle'
        )
        artifact_title.bind(size=lambda inst, val: setattr(inst, 'text_size', (inst.width, inst.height)))
        layout.add_widget(artifact_title)

        artifact_display = BoxLayout(orientation='horizontal', spacing=dp(5), size_hint_y=None, height=dp(45))

        # Подгружаем иконку правильно — с полным путем
        full_icon_path = os.path.join(artifact_images_path, current_data['icon']) if current_data['icon'] else ''
        artifact_image = Image(
            source=full_icon_path,
            size_hint_x=None,
            width=dp(35),
            allow_stretch=True,
            keep_ratio=True
        )
        artifact_display.add_widget(artifact_image)

        artifact_info = BoxLayout(orientation='vertical', spacing=dp(1))
        artifact_name_label = Label(
            text=current_data['name'] if current_data['name'] else "Название не задано",
            font_size=font_small,
            color=(0.9, 0.9, 0.9, 1),
            halign='left',
            valign='middle',
            size_hint_y=None,
            height=dp(18)
        )
        artifact_name_label.bind(size=lambda inst, val: setattr(inst, 'text_size', (inst.width, inst.height)))
        artifact_info.add_widget(artifact_name_label)

        # Расчет стоимости
        attack_bonus = current_data['attack']
        defense_bonus = current_data['defense']

        # Преобразуем строку сезонов в список
        if current_data['season'] == 'Нет':
            seasons_bonus = []
        elif current_data['season'] == 'Все':
            seasons_bonus = ['Весна', 'Лето', 'Осень', 'Зима']
        else:
            seasons_bonus = [s.strip() for s in current_data['season'].split(',')]

        # Логика расчета стоимости
        # === Расчет стоимости БЕЗ случайных множителей ===
        attack_bonus = current_data['attack']
        defense_bonus = current_data['defense']

        # Фиксированные коэффициенты как требуется
        attack_cost = abs(attack_bonus) * 0.6 * 1000  # 600 крон за 1%
        defense_cost = abs(defense_bonus) * 0.8 * 1000  # 800 крон за 1%
        base_cost = attack_cost + defense_cost

        # Сезонные модификаторы (без изменений)
        if current_data['season'] == 'Нет':
            base_cost *= 1.12  # Нет влияния сезонов + 12%
        elif current_data['season'] == 'Все':
            season_discount = 0.10
            base_cost *= (1 - season_discount)
        else:
            seasons_bonus = [s.strip() for s in current_data['season'].split(',')]
            if len(seasons_bonus) == 1:
                season_discount = 0.75
            elif len(seasons_bonus) == 2:
                consecutive_pairs = [
                    ['Весна', 'Лето'],
                    ['Лето', 'Осень'],
                    ['Осень', 'Зима'],
                    ['Зима', 'Весна']
                ]
                if sorted(seasons_bonus) in [sorted(p) for p in consecutive_pairs]:
                    season_discount = 0.25
                else:
                    season_discount = 0.45
            elif len(seasons_bonus) >= 3:
                season_discount = 0.10
            else:
                season_discount = 0

            base_cost *= (1 - season_discount)

        # Модификатор негативных значений
        negative_modifier = 1.0
        if attack_bonus < 0 or defense_bonus < 0:
            negative_count = sum(1 for x in [attack_bonus, defense_bonus] if x < 0)
            negative_modifier = 1 - (negative_count * 0.3)

        total_cost = base_cost * negative_modifier
        min_cost = 5000
        total_cost = max(min_cost, total_cost)

        artifact_cost_label = Label(
            text=f"Стоимость: {format_number(int(total_cost))} крон",
            font_size=font_small,
            color=(0.9, 0.9, 0.9, 1),
            halign='left',
            valign='middle',
            size_hint_y=None,
            height=dp(18)
        )
        artifact_cost_label.bind(size=lambda inst, val: setattr(inst, 'text_size', (inst.width, inst.height)))
        artifact_info.add_widget(artifact_cost_label)

        artifact_display.add_widget(artifact_info)
        layout.add_widget(artifact_display)

        # Кнопка создания
        create_btn = Button(
            text="Создать чертеж артефакта",
            size_hint_y=None,
            height=btn_height * 0.9,
            background_normal='',
            background_color=(0.6, 0.2, 0.6, 1),
            font_size=font_normal,
            bold=True,
            size_hint_x=1
        )
        layout.add_widget(create_btn)

        # Кнопки навигации — добавим кнопку "Назад"
        btn_box = BoxLayout(orientation='horizontal', spacing=dp(3), size_hint=(1, None), height=btn_height)
        back_btn = Button(
            text="Назад",
            size_hint=(0.5, 1),
            background_normal='',
            background_color=(0.6, 0.6, 0.2, 1),
            font_size=font_normal,
            color=(1, 1, 1, 1)
        )
        close_btn = Button(
            text="Закрыть",
            size_hint=(0.5, 1),
            background_normal='',
            background_color=(0.7, 0.2, 0.2, 1),
            font_size=font_normal,
            color=(1, 1, 1, 1)
        )
        btn_box.add_widget(back_btn)
        btn_box.add_widget(close_btn)
        layout.add_widget(btn_box)

        # Привязка событий
        def on_back(instance):
            current_data['slot'] = slots[slot_index[0]]  # Сохраняем слот перед возвратом
            switch_to_screen(screen2)

        def on_close(instance):
            workshop_popup.dismiss()

        def on_create(instance):
            current_data['slot'] = slots[slot_index[0]]  # Обновляем слот перед созданием

            # === НОВАЯ ПРОВЕРКА: нельзя создать артефакт с 0% атаки и 0% защиты ===
            if current_data['attack'] == 0 and current_data['defense'] == 0:
                show_message("Ошибка",
                             "Артефакт должен иметь хотя бы одну характеристику!\n"
                             "Установите значение Атаки или Защиты больше 0%.")
                return
            current_data['slot'] = slots[slot_index[0]]  # Обновляем слот перед созданием
            if total_cost > 200000000:
                show_message("Ошибка",
                             "Стоимость производства артефакта превышает 20 млн. крон. \nПожалуйста, уменьшите параметры артефакта.")
                return

            if faction.money < 50000:
                show_message("Ошибка", "Недостаточно средств для создания чертежа артефакта (требуется 50 тыс. крон)")
                return

            faction.money -= 50000
            money_label = Label(
                text=f"Баланс: {format_number(faction.money)}",
                font_size=font_small,
                color=(0.9, 0.9, 0.9, 1),
                halign='left',
                valign='middle',
                size_hint_y=None,
                height=label_height
            )
            money_label.bind(size=lambda inst, val: setattr(inst, 'text_size', (inst.width, inst.height)))

            artifact_name = current_data['name']
            if not artifact_name:
                artifact_name = generate_random_name()

            image_path = os.path.join(artifact_images_path, current_data['icon'])

            artifact_type_map = {
                'Оружие': 0,
                'Голова': 1,
                'Ноги': 2,
                'Туловище': 3,
                'Аксессуар': 4
            }

            # Добавляем в базу
            try:
                cursor = db_conn.cursor()
                cursor.execute("SELECT MAX(id) FROM artifacts")
                result = cursor.fetchone()
                current_max_id = result[0]

                if current_max_id is None:
                    new_artifact_id = 1
                else:
                    new_artifact_id = current_max_id + 1

                cursor.execute('''
                    INSERT INTO artifacts (id, attack, defense, season_name, image_url, name, cost, artifact_type, is_created)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    new_artifact_id,
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
                show_message("Успех", f"Артефакт '{artifact_name}' (ID: {new_artifact_id}) добавлен в лавку!")
                workshop_popup.dismiss()
            except Exception as e:
                show_message("Ошибка", f"Не удалось добавить артефакт в базу данных: {str(e)}")

        back_btn.bind(on_release=on_back)
        close_btn.bind(on_release=on_close)
        create_btn.bind(on_release=on_create)

    # === Открываем первый экран ===
    switch_to_screen(screen1)
    workshop_popup.open()
