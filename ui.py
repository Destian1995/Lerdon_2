from db_lerdon_connect import *

from fight import fight


def format_number(number):
    """Форматирует число с добавлением приставок (тыс., млн., млрд., трлн., квадр., квинт., секст., септил., октил., нонил., децил., андец.)"""
    if not isinstance(number, (int, float)):
        return str(number)
    if number == 0:
        return "0"

    absolute = abs(number)
    sign = -1 if number < 0 else 1

    if absolute >= 1_000_000_000:  # 1e9
        return f"{sign * absolute / 1e9:.1f} млрд."
    elif absolute >= 1_000_000:  # 1e6
        return f"{sign * absolute / 1e6:.1f} млн."
    elif absolute >= 1_000:  # 1e3
        return f"{sign * absolute / 1e3:.1f} тыс."
    else:
        return f"{number}"


def _show_dark_error_popup(title, message):
    """Стилизованный попап ошибки в тёмной теме, единый с дизайном ui.py."""
    content = BoxLayout(orientation='vertical', padding=dp(14), spacing=dp(10))

    lbl = Label(
        text=message,
        font_size=sp(14), color=(1, 1, 1, 1),
        halign='center', valign='middle'
    )
    lbl.bind(size=lbl.setter('text_size'))

    btn = Button(
        text='Закрыть', size_hint_y=None, height=dp(42),
        background_color=(0, 0, 0, 0), color=(1, 1, 1, 1),
        font_size=sp(14), bold=True
    )
    with btn.canvas.before:
        btn._bc = Color(0.65, 0.18, 0.18, 1)
        btn._br = RoundedRectangle(pos=btn.pos, size=btn.size, radius=[dp(10)])
    btn.bind(pos=lambda i, v: setattr(i._br, 'pos', v),
             size=lambda i, v: setattr(i._br, 'size', v))

    content.add_widget(lbl)
    content.add_widget(btn)

    popup = Popup(
        title=title, content=content,
        size_hint=(0.72, 0.32),
        background_color=(0.07, 0.08, 0.13, 1),
        separator_color=(0.78, 0.18, 0.18, 0.85),
        title_color=(1, 0.55, 0.55, 1),
        title_size=sp(16), title_align='center',
        auto_dismiss=False
    )
    btn.bind(on_release=popup.dismiss)
    popup.open()


class FortressInfoPopup(Popup):
    def __init__(self, ai_fraction, city_coords, player_fraction, conn, **kwargs):
        super(FortressInfoPopup, self).__init__(**kwargs)

        # Создаем подключение к БД
        self.send_group_button = None
        self.conn = conn
        self.cursor = self.conn.cursor()
        self.conn.execute("PRAGMA journal_mode=WAL;")
        self.conn.execute("PRAGMA synchronous=NORMAL;")
        self.ai_fraction = ai_fraction
        self.city_name = ''
        self.city_coords = list(city_coords)
        self.size_hint = (0.8, 0.8)
        self.player_fraction = player_fraction
        self.file_path2 = None
        self.file_path1 = None
        self.city_coords = city_coords  # Это кортеж (x, y)
        self.current_popup = None  # Ссылка на текущее всплывающее окно
        self.selected_group = []  # Группа для ввода войск
        self.selected_units_set = set()  # Множество для отслеживания добавленных юнитов
        self.current_troops_data = []
        self.table_widgets = {}
        # Преобразуем координаты в строку для сравнения с БД
        coords_str = f"[{self.city_coords[0]}, {self.city_coords[1]}]"
        # Получаем информацию о городе из таблицы cities
        self.cursor.execute("""
            SELECT name FROM cities 
            WHERE coordinates = ?
        """, (coords_str,))

        city_data = self.cursor.fetchone()
        if city_data:
            self.city_name = city_data[0]
        else:
            print(f"Город с координатами {self.city_coords} не найден в базе данных")
            return

        self.title = f"Информация о поселении {self.city_name}"
        self.create_ui()

    def create_ui(self):
        """
        Переработанный UI окна города — тёмная тема, карточки, фракционные акценты.
        """
        from kivy.core.window import Window
        from kivy.animation import Animation as _Anim

        is_android = platform == 'android'
        sp_base = 13 if is_android else 12
        btn_h = dp(44) if is_android else dp(38)
        pad = dp(10)
        spc = dp(8)

        # ── Фракционные цвета ────────────────────────────────────────
        _FC = {
            'Север':   (0.25, 0.52, 0.92, 1),
            'Эльфы':   (0.22, 0.76, 0.32, 1),
            'Вампиры': (0.78, 0.10, 0.16, 1),
            'Адепты':  (0.62, 0.22, 0.88, 1),
            'Элины':   (0.92, 0.70, 0.10, 1),
        }
        acc = _FC.get(self.player_fraction, (0.25, 0.52, 0.92, 1))

        def _make_btn(text, color, on_rel=None):
            """Стилизованная кнопка с фоном и hover-анимацией."""
            btn = Button(
                text=text, size_hint_y=None, height=btn_h,
                background_color=(0, 0, 0, 0), color=(1, 1, 1, 1),
                font_size=sp(sp_base), bold=True
            )
            darker = (color[0] * 0.7, color[1] * 0.7, color[2] * 0.7, 1)
            with btn.canvas.before:
                btn._bg_clr = Color(*color)
                btn._bg_rr = RoundedRectangle(pos=btn.pos, size=btn.size, radius=[dp(12)])
            btn.bind(
                pos=lambda i, v: setattr(i._bg_rr, 'pos', v),
                size=lambda i, v: setattr(i._bg_rr, 'size', v),
            )

            def _down(touch):
                if btn.collide_point(*touch.pos):
                    btn._bg_clr.rgba = darker
                return Button.on_touch_down(btn, touch)

            def _up(touch):
                btn._bg_clr.rgba = color
                return Button.on_touch_up(btn, touch)

            btn.on_touch_down = _down
            btn.on_touch_up = _up
            if on_rel:
                btn.bind(on_release=on_rel)
            return btn

        def _section_header(title, icon_char=''):
            """Заголовок секции с акцентной полосой."""
            row = BoxLayout(size_hint_y=None, height=dp(34), spacing=dp(6))
            # Акцентная вертикальная полоса
            bar = Widget(size_hint=(None, 1), width=dp(4))
            with bar.canvas:
                Color(*acc)
                bar._r = RoundedRectangle(pos=bar.pos, size=bar.size, radius=[dp(2)])
            bar.bind(pos=lambda i, v: setattr(i._r, 'pos', v),
                     size=lambda i, v: setattr(i._r, 'size', v))
            lbl = Label(
                text=f'[b]{title}[/b]', markup=True,
                font_size=sp(sp_base + 2), color=(0.95, 0.95, 0.95, 1),
                halign='left', valign='middle'
            )
            lbl.bind(size=lambda i, s: setattr(i, 'text_size', (s[0], None)))
            row.add_widget(bar)
            row.add_widget(lbl)
            return row

        # ── Root layout ───────────────────────────────────────────────
        root = BoxLayout(orientation='vertical', padding=pad, spacing=spc)

        # Тёмный фон
        with root.canvas.before:
            Color(0.07, 0.07, 0.11, 1)
            root._bg = RoundedRectangle(pos=root.pos, size=root.size, radius=[dp(10)])
        root.bind(pos=lambda i, v: setattr(i._bg, 'pos', v),
                  size=lambda i, v: setattr(i._bg, 'size', v))

        # ── Две колонки ───────────────────────────────────────────────
        cols = GridLayout(cols=2, spacing=spc, size_hint_y=0.78)

        # Левая: Гарнизон
        left = BoxLayout(orientation='vertical', spacing=spc)
        left.add_widget(_section_header('Гарнизон'))
        self.attacking_units_list = ScrollView(size_hint=(1, 1))
        self.attacking_units_box = BoxLayout(
            orientation='vertical', size_hint_y=None, spacing=dp(6), padding=[0, dp(4)]
        )
        self.attacking_units_box.bind(minimum_height=self.attacking_units_box.setter('height'))
        self.attacking_units_list.add_widget(self.attacking_units_box)
        left.add_widget(self.attacking_units_list)
        cols.add_widget(left)

        # Правая: Здания
        right = BoxLayout(orientation='vertical', spacing=spc)
        right.add_widget(_section_header('Здания'))
        self.buildings_list = ScrollView(size_hint=(1, 1))
        self.buildings_box = BoxLayout(
            orientation='vertical', size_hint_y=None, spacing=dp(6), padding=[0, dp(4)]
        )
        self.buildings_box.bind(minimum_height=self.buildings_box.setter('height'))
        self.buildings_list.add_widget(self.buildings_box)
        right.add_widget(self.buildings_list)
        cols.add_widget(right)

        root.add_widget(cols)

        # ── Разделитель ───────────────────────────────────────────────
        sep = Widget(size_hint_y=None, height=dp(1))
        with sep.canvas:
            Color(*acc[:3], 0.35)
            sep._r = RoundedRectangle(pos=sep.pos, size=sep.size)
        sep.bind(pos=lambda i, v: setattr(i._r, 'pos', v),
                 size=lambda i, v: setattr(i._r, 'size', v))
        root.add_widget(sep)

        # ── Кнопки действий ───────────────────────────────────────────
        btn_row = BoxLayout(size_hint_y=None, height=btn_h, spacing=spc)
        btn_row.add_widget(_make_btn(
            'Ввести войска', (0.18, 0.62, 0.22, 1),
            on_rel=lambda btn: self.load_troops_by_type("Любые", None)
        ))
        btn_row.add_widget(_make_btn(
            'Разместить армию', (0.16, 0.46, 0.82, 1),
            on_rel=self.place_army
        ))
        root.add_widget(btn_row)

        root.add_widget(_make_btn(
            'Закрыть', (0.62, 0.14, 0.14, 1),
            on_rel=self.dismiss
        ))

        self.content = root
        self.garrison_widgets = {}

        # Анимация появления
        root.opacity = 0
        from kivy.clock import Clock as _Clk
        _Clk.schedule_once(
            lambda dt: _Anim(opacity=1, duration=0.30, t='out_cubic').start(root), 0.05
        )

        self.get_garrison()
        self.load_buildings()

    def load_buildings(self):
        """Загружает здания в интерфейс — стилизованные карточки."""
        self.buildings_box.clear_widgets()
        buildings = self.get_buildings()

        if not buildings:
            lbl = Label(
                text='[color=#FF6666]Зданий нет[/color]', markup=True,
                size_hint_y=None, height=dp(40), font_size=sp(13),
                halign='center', valign='middle'
            )
            lbl.bind(size=lbl.setter('text_size'))
            self.buildings_box.add_widget(lbl)
            return

        # Иконки для типов зданий (если файлы есть — иначе просто буква)
        BUILDING_COLORS = {
            'Ферма':       (0.25, 0.70, 0.28, 1),
            'Казарма':     (0.75, 0.22, 0.22, 1),
            'Рынок':       (0.85, 0.65, 0.10, 1),
            'Стена':       (0.45, 0.45, 0.55, 1),
            'Библиотека':  (0.35, 0.30, 0.75, 1),
            'Кузница':     (0.60, 0.38, 0.12, 1),
            'Вышка':       (0.20, 0.55, 0.75, 1),
            'Больница':    (0.80, 0.22, 0.35, 1),
            'Фабрика':     (0.50, 0.50, 0.12, 1),
        }

        for building_str in buildings:
            # Разбираем строку "Тип: N"
            parts = building_str.split(':', 1)
            b_name = parts[0].strip()
            b_count = parts[1].strip() if len(parts) > 1 else '?'

            card = BoxLayout(
                orientation='horizontal', size_hint_y=None, height=dp(38),
                spacing=dp(6), padding=[dp(6), dp(3), dp(6), dp(3)]
            )
            # Фон карточки
            card_color = BUILDING_COLORS.get(b_name, (0.22, 0.25, 0.32, 1))
            darker = (card_color[0] * 0.55, card_color[1] * 0.55, card_color[2] * 0.55, 1)
            with card.canvas.before:
                Color(*darker)
                card._bg = RoundedRectangle(pos=card.pos, size=card.size, radius=[dp(8)])
            card.bind(pos=lambda i, v: setattr(i._bg, 'pos', v),
                      size=lambda i, v: setattr(i._bg, 'size', v))

            # Цветная метка-тип слева
            badge = Label(
                text=b_name[0], font_size=sp(13), bold=True,
                size_hint=(None, None), size=(dp(28), dp(28)),
                color=(1, 1, 1, 1)
            )
            with badge.canvas.before:
                Color(*card_color)
                badge._r = RoundedRectangle(pos=badge.pos, size=badge.size, radius=[dp(6)])
            badge.bind(pos=lambda i, v: setattr(i._r, 'pos', v),
                       size=lambda i, v: setattr(i._r, 'size', v))
            card.add_widget(badge)

            # Название здания
            name_lbl = Label(
                text=b_name, font_size=sp(12), color=(0.92, 0.92, 0.92, 1),
                halign='left', valign='middle'
            )
            name_lbl.bind(size=lambda i, s: setattr(i, 'text_size', (s[0], None)))
            card.add_widget(name_lbl)

            # Количество — справа
            count_lbl = Label(
                text=f'[b]{b_count}[/b]', markup=True,
                font_size=sp(13), color=(0.95, 0.85, 0.35, 1),
                size_hint=(None, 1), width=dp(40), halign='right', valign='middle'
            )
            count_lbl.bind(size=lambda i, s: setattr(i, 'text_size', (s[0], None)))
            card.add_widget(count_lbl)

            self.buildings_box.add_widget(card)


    def get_buildings(self):
        """Получает количество зданий в указанном городе из таблицы buildings."""
        cursor = self.conn.cursor()
        try:
            # Выполняем запрос к базе данных
            cursor.execute("""
                SELECT building_type, count 
                FROM buildings 
                WHERE city_name = ? AND faction = ?
            """, (self.city_name, self.ai_fraction))

            buildings_data = cursor.fetchall()

            # Формируем список с информацией о зданиях
            buildings = [f"{building_type}: {format_number(count)}" for building_type, count in buildings_data]

            # Если зданий нет, возвращаем пустой список
            return buildings if buildings else []

        except Exception as e:
            print(f"Ошибка при получении данных о зданиях: {e}")
            return []

    def load_troops_by_type(self, troop_type, previous_popup):
        """
        Загружает войска из гарнизонов в зависимости от выбранного типа.
        :param troop_type: Тип войск ("Defensive", "Offensive", "Any").
        :param previous_popup: Предыдущее всплывающее окно для закрытия.
        """
        try:
            # Закрываем предыдущее окно
            if previous_popup is not None:
                previous_popup.dismiss()
            cursor = self.conn.cursor()
            # Шаг 1: Получаем все юниты из таблицы garrisons
            cursor.execute("""
                SELECT city_name, unit_name, unit_count, unit_image 
                FROM garrisons
            """)
            all_troops = cursor.fetchall()

            if not all_troops:
                # Если войск нет, показываем сообщение
                _show_dark_error_popup("Нет войск", "Нет доступных войск.")
                return

            # Шаг 2: Фильтруем юниты по типу (атакующие, защитные, любые) и фракции
            filtered_troops = []
            for city_name, unit_name, unit_count, unit_image in all_troops:
                # Получаем характеристики юнита из таблицы units
                cursor.execute("""
                    SELECT attack, defense, durability, faction 
                    FROM units 
                    WHERE unit_name = ?
                """, (unit_name,))
                unit_stats = cursor.fetchone()

                if not unit_stats:
                    print(f"Характеристики для юнита '{unit_name}' не найдены.")
                    continue

                attack, defense, durability, unit_faction = unit_stats

                # Проверяем принадлежность юнита к фракции игрока
                if unit_faction != self.player_fraction:
                    continue  # Пропускаем юниты других фракций

                # Определяем тип юнита
                if troop_type == "Защитных":
                    if defense > attack and defense > durability:
                        filtered_troops.append((city_name, unit_name, unit_count, unit_image))
                elif troop_type == "Атакующих":
                    if attack > defense and attack > durability:
                        filtered_troops.append((city_name, unit_name, unit_count, unit_image))
                else:  # "Any"
                    filtered_troops.append((city_name, unit_name, unit_count, unit_image))

            if not filtered_troops:
                # Если подходящих войск нет, показываем сообщение
                _show_dark_error_popup("Нет войск", f"Нет доступных {troop_type} войск вашей фракции.")
                return

            # Открываем окно с выбором войск
            self.show_troops_selection(filtered_troops)

        except Exception as e:
            print(f"Ошибка при загрузке войск: {e}")

    def show_troops_selection(self, troops_data):
        """
        Отображает окно с выбором войск.
        :param troops_data: Список войск, полученный из базы данных.
        """
        self.current_troops_data = troops_data
        popup = Popup(
            title="Выберите войска для перемещения",
            size_hint=(0.9, 0.9),
            background_color=(0.07, 0.08, 0.13, 1),
            separator_color=(0.25, 0.52, 0.92, 0.5),
            title_color=(1, 1, 1, 1),
            title_size=sp(18),
            title_align='center'
        )
        self.current_popup = popup  # Сохраняем ссылку на текущее окно

        main_layout = BoxLayout(orientation='vertical', padding=dp(10), spacing=dp(10))
        with main_layout.canvas.before:
            main_layout._bgc = Color(0.07, 0.08, 0.13, 1)
            main_layout._bgr = Rectangle(pos=main_layout.pos, size=main_layout.size)
        main_layout.bind(pos=lambda i, v: setattr(i._bgr, 'pos', v),
                         size=lambda i, v: setattr(i._bgr, 'size', v))

        # Создаем таблицу для отображения войск
        self.table_layout = GridLayout(cols=5, spacing=dp(10), size_hint_y=None)
        self.table_layout.bind(minimum_height=self.table_layout.setter('height'))

        headers = ["Город", "Юнит", "Количество", "Изображение", "Действие"]
        for header in headers:
            label = Label(
                text=header,
                font_size=sp(18),
                bold=True,
                size_hint_y=None,
                height=dp(60),
                color=(0.55, 0.75, 1.0, 1)
            )
            self.table_layout.add_widget(label)

        for city_name, unit_name, unit_count, unit_image in troops_data:
            city_lbl = Label(text=city_name, font_size=sp(15), size_hint_y=None, height=dp(90), color=(0.96, 0.96, 0.96, 1))
            unit_lbl = Label(text=unit_name, font_size=sp(15), size_hint_y=None, height=dp(90), color=(0.96, 0.96, 0.96, 1))
            count_lbl = Label(text=str(unit_count), font_size=sp(15), size_hint_y=None, height=dp(90), color=(0.65, 0.70, 0.80, 1))

            img_box = BoxLayout(size_hint_y=None, height=dp(60))
            with img_box.canvas.before:
                img_box._bgc = Color(0.10, 0.13, 0.20, 1)
                img_box._bgr = RoundedRectangle(pos=img_box.pos, size=img_box.size, radius=[dp(10)])
            img_box.bind(pos=lambda i, v: setattr(i._bgr, 'pos', v),
                         size=lambda i, v: setattr(i._bgr, 'size', v))
            img_box.add_widget(Image(source=unit_image, size=(dp(80), dp(80)), size_hint=(None, None)))

            btn_add = Button(
                text="Добавить",
                font_size=sp(16),
                bold=True,
                size_hint_y=None,
                height=dp(80),
                background_color=(0, 0, 0, 0),
                color=(1, 1, 1, 1)
            )
            with btn_add.canvas.before:
                btn_add._bc = Color(0.18, 0.62, 0.22, 1)
                btn_add._br = RoundedRectangle(pos=btn_add.pos, size=btn_add.size, radius=[dp(12)])
            btn_add.bind(pos=lambda i, v: setattr(i._br, 'pos', v),
                         size=lambda i, v: setattr(i._br, 'size', v))
            btn_add.bind(
                on_release=lambda btn, data=(city_name, unit_name, unit_count, unit_image):
                self.create_troop_group(data, btn, city_lbl, unit_lbl, count_lbl, img_box, btn_add)
            )

            for w in (city_lbl, unit_lbl, count_lbl, img_box, btn_add):
                self.table_layout.add_widget(w)

            unique_id = f"{city_name}_{unit_name}"
            self.table_widgets[unique_id] = {
                "city_label": city_lbl,
                "unit_label": unit_lbl,
                "count_label": count_lbl,
                "image_container": img_box,
                "action_button": btn_add
            }

        scroll_view = ScrollView(size_hint=(1, 1))
        scroll_view.add_widget(self.table_layout)
        main_layout.add_widget(scroll_view)

        # Кнопка «Создать группу» — синяя
        btn_add_all = Button(
            text="Создать группу (1-3 класс)",
            size_hint=(1, None),
            height=dp(44),
            font_size=sp(16),
            bold=True,
            background_color=(0, 0, 0, 0),
            color=(1, 1, 1, 1)
        )
        with btn_add_all.canvas.before:
            btn_add_all._bc = Color(0.16, 0.46, 0.82, 1)
            btn_add_all._br = RoundedRectangle(pos=btn_add_all.pos, size=btn_add_all.size, radius=[dp(12)])
        btn_add_all.bind(pos=lambda i, v: setattr(i._br, 'pos', v),
                         size=lambda i, v: setattr(i._br, 'size', v))

        def add_all(btn):
            # Создаем копию списка для итерации, так как мы будем его модифицировать
            troops_to_process = list(self.current_troops_data)

            for city, unit, count, img in troops_to_process:
                # Проверяем класс юнита перед добавлением
                cursor = self.conn.cursor()
                cursor.execute("""
                    SELECT unit_class FROM units WHERE unit_name = ?
                """, (unit,))
                unit_class_result = cursor.fetchone()

                if unit_class_result:
                    unit_class = unit_class_result[0]
                    # Добавляем только юнитов классов 1, 2 и 3
                    if str(unit_class) in ['1', '2', '3']:
                        self.selected_group.append({
                            "city_name": city,
                            "unit_name": unit,
                            "unit_count": count,
                            "unit_image": img
                        })
                        self.selected_units_set.add((city, unit))

                        uid = f"{city}_{unit}"
                        if uid in self.table_widgets:
                            widgets = self.table_widgets.pop(uid)
                            for key in ("city_label", "unit_label", "count_label", "image_container", "action_button"):
                                self.table_layout.remove_widget(widgets[key])

                        # Удаляем из текущих данных
                        self.current_troops_data = [
                            d for d in self.current_troops_data
                            if not (d[0] == city and d[1] == unit)
                        ]

            # Если были добавлены юниты, активируем кнопку отправки
            if self.selected_group:
                self.send_group_button.disabled = False

        btn_add_all.bind(on_release=add_all)

        # Добавляем «Добавить всех» над кнопками отправки/закрытия
        main_layout.add_widget(btn_add_all)
        # Небольшой отступ
        main_layout.add_widget(Widget(size_hint_y=None, height=dp(10)))

        # Кнопки «Отправить группу в город» и «Закрыть»
        self.send_group_button = Button(
            text="Отправить группу в город",
            size_hint=(0.5, None),
            height=dp(44),
            font_size=sp(16),
            bold=True,
            background_color=(0, 0, 0, 0),
            color=(1, 1, 1, 1),
            disabled=True
        )
        with self.send_group_button.canvas.before:
            self.send_group_button._bc = Color(0.18, 0.62, 0.22, 1)
            self.send_group_button._br = RoundedRectangle(pos=self.send_group_button.pos, size=self.send_group_button.size, radius=[dp(12)])
        self.send_group_button.bind(pos=lambda i, v: setattr(i._br, 'pos', v),
                                    size=lambda i, v: setattr(i._br, 'size', v))

        close_button = Button(
            text="Закрыть",
            size_hint=(0.5, None),
            height=dp(44),
            font_size=sp(16),
            bold=True,
            background_color=(0, 0, 0, 0),
            color=(1, 1, 1, 1)
        )
        with close_button.canvas.before:
            close_button._bc = Color(0.55, 0.14, 0.14, 1)
            close_button._br = RoundedRectangle(pos=close_button.pos, size=close_button.size, radius=[dp(12)])
        close_button.bind(pos=lambda i, v: setattr(i._br, 'pos', v),
                          size=lambda i, v: setattr(i._br, 'size', v))

        self.send_group_button.bind(on_release=self.move_selected_group_to_city)
        close_button.bind(on_release=popup.dismiss)

        buttons_layout = BoxLayout(
            orientation='horizontal',
            size_hint_y=None,
            height=dp(90),
            spacing=dp(10)
        )
        buttons_layout.add_widget(self.send_group_button)
        buttons_layout.add_widget(close_button)

        main_layout.add_widget(buttons_layout)

        popup.content = main_layout
        popup.open()

    def create_troop_group(self, troop_data, button, city_label, unit_label, count_label, image_container,
                           action_button):
        """
        Создает окно для добавления юнитов в группу с использованием слайдера для выбора количества.
        :param troop_data: Данные о юните (город, название, количество, изображение).
        :param button: Кнопка "Добавить", которую нужно обновить.
        :param city_label: Метка города.
        :param unit_label: Метка названия юнита.
        :param count_label: Метка количества юнитов.
        :param image_container: Контейнер изображения.
        :param action_button: Кнопка действия.
        """
        city_name, unit_name, unit_count, unit_image = troop_data

        # Если юнит только один, добавляем его сразу без окна выбора
        if unit_count == 1:
            # 1) Добавляем в группу
            self.selected_group.append({
                "city_name": city_name,
                "unit_name": unit_name,
                "unit_count": 1,
                "unit_image": unit_image
            })

            # Блокируем повторное добавление
            self.selected_units_set.add((city_name, unit_name))

            # 2) Удаляем из текущего списка данных
            self.current_troops_data = [
                d for d in self.current_troops_data
                if not (d[0] == city_name and d[1] == unit_name)
            ]

            # 3) Убираем виджеты строки
            unique_id = f"{city_name}_{unit_name}"
            if unique_id in self.table_widgets:
                widgets = self.table_widgets.pop(unique_id)
                layout = widgets["city_label"].parent
                for key in ("city_label", "unit_label", "count_label", "image_container", "action_button"):
                    layout.remove_widget(widgets[key])

            # 4) Пересоздаём само окно «Выберите войска…» с уже обновлённым списком
            self.current_popup.dismiss()
            self.show_troops_selection(self.current_troops_data)

            # 5) Активируем кнопку «Отправить»
            self.send_group_button.disabled = False
            return

        # Если юнитов больше 1, показываем окно выбора
        # Создаем всплывающее окно
        popup = Popup(
            title=f"Добавление {unit_name} в группу",
            size_hint=(0.8, 0.7),
            background_color=(0.07, 0.08, 0.13, 1),
            separator_color=(0.25, 0.52, 0.92, 0.5),
            title_color=(1, 1, 1, 1),
            title_size=sp(18),
            title_align='center'
        )
        layout = BoxLayout(orientation='vertical', padding=dp(10), spacing=dp(10))
        with layout.canvas.before:
            layout._bgc = Color(0.07, 0.08, 0.13, 1)
            layout._bgr = Rectangle(pos=layout.pos, size=layout.size)
        layout.bind(pos=lambda i, v: setattr(i._bgr, 'pos', v),
                    size=lambda i, v: setattr(i._bgr, 'size', v))

        # Контейнер для изображения и количества
        top_section = BoxLayout(orientation='vertical', size_hint_y=None, height=dp(120), spacing=dp(10))

        # Метка количества
        selected_count_label = Label(
            text="Выбрано: 0",
            font_size=sp(18),
            color=(0.96, 0.96, 0.96, 1),
            size_hint_y=None,
            height=dp(30)
        )

        # Добавляем изображение и метку количества в вертикальный контейнер
        top_section.add_widget(selected_count_label)
        layout.add_widget(top_section)

        # Слайдер для выбора количества
        slider_layout = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(70), spacing=dp(10))
        slider = Slider(min=0, max=unit_count, value=0, step=1)

        # Обновляем метки при изменении значения слайдера
        def update_labels(instance, value):
            selected_count_label.text = f"Выбрано: {int(value)}"

        slider.bind(value=update_labels)
        slider_layout.add_widget(slider)
        layout.add_widget(slider_layout)

        # Метка для ошибок
        error_label = Label(
            text="",
            color=(1, 0, 0, 1),  # Красный цвет текста
            size_hint_y=None,
            height=dp(30)
        )
        layout.add_widget(error_label)

        # Кнопки подтверждения и отмены
        button_layout = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(60), spacing=dp(10))
        confirm_button = Button(
            text="Подтвердить",
            font_size=sp(16),
            bold=True,
            background_color=(0, 0, 0, 0),
            color=(1, 1, 1, 1)
        )
        with confirm_button.canvas.before:
            confirm_button._bc = Color(0.18, 0.62, 0.22, 1)
            confirm_button._br = RoundedRectangle(pos=confirm_button.pos, size=confirm_button.size, radius=[dp(12)])
        confirm_button.bind(pos=lambda i, v: setattr(i._br, 'pos', v),
                            size=lambda i, v: setattr(i._br, 'size', v))

        cancel_button = Button(
            text="Отмена",
            font_size=sp(16),
            bold=True,
            background_color=(0, 0, 0, 0),
            color=(1, 1, 1, 1)
        )
        with cancel_button.canvas.before:
            cancel_button._bc = Color(0.55, 0.14, 0.14, 1)
            cancel_button._br = RoundedRectangle(pos=cancel_button.pos, size=cancel_button.size, radius=[dp(12)])
        cancel_button.bind(pos=lambda i, v: setattr(i._br, 'pos', v),
                           size=lambda i, v: setattr(i._br, 'size', v))

        def confirm_action(btn):
            selected = int(slider.value)
            if 0 < selected <= unit_count:
                # 1) Добавляем в группу
                # Используем кортеж (город, юнит, число)
                self.selected_group.append({
                    "city_name": city_name,
                    "unit_name": unit_name,
                    "unit_count": selected,
                    "unit_image": unit_image
                })

                # Можно ещё блокировать повторное добавление одного и того же юнита:
                self.selected_units_set.add((city_name, unit_name))

                # 2) Удаляем из текущего списка данных, чтобы при пересоздании окна строка не вернулась
                self.current_troops_data = [
                    d for d in self.current_troops_data
                    if not (d[0] == city_name and d[1] == unit_name)
                ]

                # 3) Убираем виджеты строки сразу, если хотите
                unique_id = f"{city_name}_{unit_name}"
                if unique_id in self.table_widgets:
                    widgets = self.table_widgets.pop(unique_id)
                    layout = widgets["city_label"].parent
                    for key in ("city_label", "unit_label", "count_label", "image_container", "action_button"):
                        layout.remove_widget(widgets[key])

                popup.dismiss()
                # 4) Пересоздаём само окно «Выберите войска…» с уже обновлённым списком
                self.current_popup.dismiss()
                self.show_troops_selection(self.current_troops_data)

                # 5) Активируем кнопку «Отправить»
                self.send_group_button.disabled = False

            else:
                error_label.text = "Ошибка: некорректное количество."

        confirm_button.bind(on_release=confirm_action)
        cancel_button.bind(on_release=popup.dismiss)
        button_layout.add_widget(confirm_button)
        button_layout.add_widget(cancel_button)
        layout.add_widget(button_layout)

        popup.content = layout
        popup.open()

    def get_army_consumption_and_limit(self):
        """
        Получает текущее потребление армии и лимит из таблицы resources.
        :return: кортеж (текущее_потребление, лимит_армии)
        """
        try:
            cursor = self.conn.cursor()

            # Получаем лимит армии
            cursor.execute("""
                SELECT amount FROM resources
                WHERE faction = ? AND resource_type = ?
            """, (self.player_fraction, "Лимит Армии"))
            limit_result = cursor.fetchone()
            army_limit = limit_result[0] if limit_result else 0

            # Получаем текущее потребление
            cursor.execute("""
                SELECT amount FROM resources
                WHERE faction = ? AND resource_type = ?
            """, (self.player_fraction, "Потребление"))
            consumption_result = cursor.fetchone()
            current_consumption = consumption_result[0] if consumption_result else 0

            return current_consumption, army_limit

        except sqlite3.Error as e:
            print(f"Ошибка при получении данных о потреблении: {e}")
            return 0, 0

    def recalculate_and_update_army_consumption(self):
        """
        Пересчитывает текущее потребление армии и лимит армии для фракции игрока
        и немедленно обновляет записи в таблице resources.
        """
        try:
            cursor = self.conn.cursor()

            # 1. Пересчёт потребления: сумма потребления ВСЕХ юнитов в гарнизонах фракции игрока
            cursor.execute("""
                SELECT g.unit_name, g.unit_count, u.consumption
                FROM garrisons g
                JOIN units u ON g.unit_name = u.unit_name
                WHERE u.faction = ?
            """, (self.player_fraction,))
            rows = cursor.fetchall()

            total_consumption = 0
            for row in rows:
                unit_name, unit_count, consumption = row
                total_consumption += consumption * unit_count

            # 2. Пересчёт лимита армии: 4000 + 1000 * количество городов фракции
            cursor.execute("""
                SELECT COUNT(*) FROM cities WHERE faction = ?
            """, (self.player_fraction,))
            city_count_row = cursor.fetchone()
            city_count = city_count_row[0] if city_count_row else 0
            army_limit = 4000 + 1000 * city_count

            # 3. Обновление записи "Потребление" (создаём если не существует)
            cursor.execute("""
                UPDATE resources 
                SET amount = ? 
                WHERE faction = ? AND resource_type = ?
            """, (total_consumption, self.player_fraction, "Потребление"))

            if cursor.rowcount == 0:  # Запись не найдена — создаём новую
                cursor.execute("""
                    INSERT INTO resources (faction, resource_type, amount)
                    VALUES (?, ?, ?)
                """, (self.player_fraction, "Потребление", total_consumption))

            # 4. Обновление записи "Лимит Армии" (создаём если не существует)
            cursor.execute("""
                UPDATE resources 
                SET amount = ? 
                WHERE faction = ? AND resource_type = ?
            """, (army_limit, self.player_fraction, "Лимит Армии"))

            if cursor.rowcount == 0:  # Запись не найдена — создаём новую
                cursor.execute("""
                    INSERT INTO resources (faction, resource_type, amount)
                    VALUES (?, ?, ?)
                """, (self.player_fraction, "Лимит Армии", army_limit))

            self.conn.commit()
            print(f"[DEBUG] Потребление обновлено: {total_consumption}, Лимит армии: {army_limit}")

        except sqlite3.Error as e:
            print(f"Ошибка при пересчёте потребления: {e}")
            self.conn.rollback()

    def update_troops_table(self):
        """
        Обновляет таблицу доступных войск без пересоздания всего popup'а.
        """
        # Очищаем текущую таблицу
        self.attacking_units_box.clear_widgets()

        # Перезапрашиваем данные из БД
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT city_name, unit_name, unit_count, unit_image 
            FROM garrisons
        """)
        all_troops = cursor.fetchall()

        if not all_troops:
            label = Label(text="Нет доступных войск", size_hint_y=None, height=60)
            self.attacking_units_box.add_widget(label)
            return

        # Повторно строим таблицу
        for city_name, unit_name, unit_count, unit_image in all_troops:
            city_label = Label(text=city_name, font_size='18sp', size_hint_y=None, height=90)
            unit_label = Label(text=unit_name, font_size='18sp', size_hint_y=None, height=90)
            count_label = Label(text=str(unit_count), font_size='18sp', size_hint_y=None, height=90)

            image_container = BoxLayout(size_hint_y=None, height=60)
            unit_image_widget = Image(source=unit_image, size_hint=(None, None), size=(80, 80))
            image_container.add_widget(unit_image_widget)

            action_button = Button(
                text="Добавить",
                font_size='18sp',
                size_hint_y=None,
                height=80,
                background_color=(0.6, 0.8, 0.6, 1)
            )

            # Привязка к create_troop_group с передачей всех виджетов
            action_button.bind(on_release=lambda btn, data=(city_name, unit_name, unit_count, unit_image):
            self.create_troop_group(data, btn, city_label, unit_label, count_label, image_container, action_button))

            # Добавляем в layout
            self.attacking_units_box.add_widget(city_label)
            self.attacking_units_box.add_widget(unit_label)
            self.attacking_units_box.add_widget(count_label)
            self.attacking_units_box.add_widget(image_container)
            self.attacking_units_box.add_widget(action_button)

    def update_garrison(self):
        """
        Обновляет данные о гарнизоне на интерфейсе с сохранением стиля,
        учитывая класс юнита для отображения количества или специализации.
        """
        try:
            # Очищаем текущие виджеты гарнизона
            self.attacking_units_box.clear_widgets()

            # Получаем актуальные данные о гарнизоне из базы данных
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT unit_name, unit_count, unit_image 
                FROM garrisons 
                WHERE city_name = ?
            """, (self.city_name,))
            garrison_data = cursor.fetchall()

            if not garrison_data:
                # Если гарнизон пуст, добавляем сообщение
                label = Label(
                    text="Гарнизон пуст",
                    size_hint_y=None,
                    height=60,
                    font_size='18sp',
                    color=(1, 0, 0, 1),  # Ярко-красный текст
                    halign='center',
                    valign='middle'
                )
                label.bind(size=label.setter('text_size'))
                self.attacking_units_box.add_widget(label)
                return

            # Добавляем новые виджеты для каждого юнита в гарнизоне
            for unit_name, unit_count, unit_image in garrison_data:
                # --- НОВАЯ ЛОГИКА: Получение класса, характеристик и определение специализации ---
                specialization_icon_path = None  # Путь к иконке специализации
                try:
                    # 1. Получаем класс юнита
                    cursor.execute("""
                        SELECT unit_class, attack, defense
                        FROM units
                        WHERE unit_name = ?
                    """, (unit_name,))
                    unit_info = cursor.fetchone()

                    if unit_info:
                        unit_class, attack, defense = unit_info[0], unit_info[1], unit_info[2]

                        # 2. Логика отображения в зависимости от класса
                        if unit_class == "1":
                            # Класс 1: отображаем количество
                            unit_text = f"{unit_name}\nКоличество: {format_number(unit_count)}"
                        elif unit_class == "4":
                            # Класс 4: отображаем только имя
                            unit_text = f"{unit_name}"
                        elif unit_class in ("2", "3"):  # Класс 2 или 3: отображаем имя и иконку специализации
                            # 3. Определяем специализацию
                            try:
                                # Обработка случаев, когда один из параметров равен 0
                                if defense == 0:
                                    if attack > 0:
                                        specialization_icon_path = r"files/pict/hero_type/sword.png"
                                    # Если оба 0, остается None
                                elif attack == 0:
                                    if defense > 0:
                                        specialization_icon_path = r"files/pict/hero_type/shield.png"
                                    # Если оба 0, остается None
                                else:
                                    # Основная логика определения специализации
                                    attack_to_defense_ratio = attack / defense
                                    defense_to_attack_ratio = defense / attack
                                    if attack_to_defense_ratio >= 2.0:
                                        specialization_icon_path = r"files/pict/hero_type/sword.png"
                                    elif defense_to_attack_ratio >= 2.0:
                                        specialization_icon_path = r"files/pict/hero_type/shield.png"
                                    else:
                                        specialization_icon_path = r"files/pict/hero_type/sword-shield.png"
                            except Exception as spec_error:
                                print(f"Ошибка при определении специализации для '{unit_name}': {spec_error}")
                                # Оставляем specialization_icon_path как None в случае ошибки вычисления
                            # Формируем текст с названием
                            unit_text = f"{unit_name}"
                        else:
                            # Для других классов (например, если в будущем появятся 5+)
                            unit_text = f"{unit_name}\n(Класс {unit_class})"
                    else:
                        print(f"Информация для юнита '{unit_name}' не найдена в таблице units.")
                        unit_text = f"{unit_name}\n(Не найден в units)"
                except sqlite3.Error as e:
                    print(f"Ошибка БД при получении данных юнита '{unit_name}': {e}")
                    unit_text = f"{unit_name}\n(Ошибка БД)"
                except Exception as e:
                    print(f"Неожиданная ошибка при обработке юнита '{unit_name}': {e}")
                    unit_text = f"{unit_name}\n(Ошибка обработки)"

                # Создаем макет для одного юнита
                unit_layout = BoxLayout(orientation='horizontal', size_hint_y=None, height=150, spacing=10)

                # Изображение юнита - проверяем существование файла
                unit_image_source = unit_image
                if unit_image_source and not os.path.exists(unit_image_source):
                    print(f"Файл изображения не найден: {unit_image_source}")
                    unit_image_source = "files/pict/placeholder.png"

                unit_image_widget = Image(
                    source=unit_image_source,
                    size_hint=(None, None),
                    size=(150, 150)  # Увеличенное изображение
                )
                unit_layout.add_widget(unit_image_widget)

                # Справа — контейнер с текстом и специализацией
                right_container = BoxLayout(orientation='horizontal', size_hint=(1, 1), padding=5, spacing=10)

                # Текст с названием юнита
                text_label = Label(
                    text=unit_text,
                    font_size='17sp',
                    color=(1, 1, 1, 1),
                    halign='left',
                    valign='middle'
                )
                text_label.bind(size=text_label.setter('text_size'))
                right_container.add_widget(text_label)

                # Иконка специализации (только для классов 2 и 3)
                if unit_class in ("2", "3") and specialization_icon_path:
                    if os.path.exists(specialization_icon_path):
                        icon_image = Image(
                            source=specialization_icon_path,
                            size_hint=(None, None),
                            size=(120, 120),
                            pos_hint={'center_y': 0.5}
                        )
                        right_container.add_widget(icon_image)
                    else:
                        print(f"Файл иконки специализации не найден: {specialization_icon_path}")

                # Добавляем правый контейнер
                unit_layout.add_widget(right_container)

                # Добавляем макет юнита в контейнер
                self.attacking_units_box.add_widget(unit_layout)

        except Exception as e:
            print(f"Ошибка при обновлении гарнизона: {e}")

    def get_garrison(self):
        """Получает гарнизон города из таблицы garrisons и отображает его с учетом класса и специализации юнитов."""
        try:
            # Запрос к базе данных для получения гарнизона
            self.cursor.execute("""
                SELECT unit_name, unit_count, unit_image 
                FROM garrisons 
                WHERE city_name = ?
            """, (self.city_name,))
            garrison_data = self.cursor.fetchall()

            # Очищаем контейнер с предыдущими данными
            self.attacking_units_box.clear_widgets()

            if not garrison_data:
                print(f"Гарнизон для города {self.city_name} пуст.")
                lbl = Label(
                    text='[color=#FF8888]Гарнизон пуст[/color]', markup=True,
                    size_hint_y=None, height=dp(40), font_size=sp(13),
                    halign='center', valign='middle'
                )
                lbl.bind(size=lbl.setter('text_size'))
                self.attacking_units_box.add_widget(lbl)
                return

            # Цвета по классу юнита
            CLASS_COLORS = {
                '1': (0.22, 0.28, 0.38, 1),   # Серо-синий
                '2': (0.28, 0.22, 0.38, 1),   # Серо-фиолетовый
                '3': (0.38, 0.26, 0.12, 1),   # Золотистый
                '4': (0.38, 0.10, 0.10, 1),   # Тёмно-красный (легенда)
            }

            for unit_name, unit_count, unit_image in garrison_data:
                unit_class = '1'
                specialization_icon_path = None
                try:
                    self.cursor.execute(
                        "SELECT unit_class, attack, defense FROM units WHERE unit_name = ?",
                        (unit_name,)
                    )
                    unit_info = self.cursor.fetchone()
                    if unit_info:
                        unit_class = str(unit_info[0])
                        attack, defense = unit_info[1], unit_info[2]
                        if unit_class in ('2', '3'):
                            try:
                                if defense == 0 and attack > 0:
                                    specialization_icon_path = "files/pict/hero_type/sword.png"
                                elif attack == 0 and defense > 0:
                                    specialization_icon_path = "files/pict/hero_type/shield.png"
                                else:
                                    r = attack / defense if defense > 0 else 99
                                    if r >= 2.0:
                                        specialization_icon_path = "files/pict/hero_type/sword.png"
                                    elif 1 / r >= 2.0:
                                        specialization_icon_path = "files/pict/hero_type/shield.png"
                                    else:
                                        specialization_icon_path = "files/pict/hero_type/sword-shield.png"
                            except Exception:
                                pass
                except Exception as e:
                    print(f"[WARN] get_garrison unit info: {e}")

                # ── Карточка юнита ──────────────────────────────────────
                card_h = dp(72) if unit_class == '1' else dp(90)
                card = BoxLayout(
                    orientation='horizontal', size_hint_y=None, height=card_h,
                    spacing=dp(8), padding=[dp(6), dp(4), dp(6), dp(4)]
                )
                card_bg = CLASS_COLORS.get(unit_class, (0.20, 0.22, 0.30, 1))
                with card.canvas.before:
                    Color(*card_bg)
                    card._bg = RoundedRectangle(pos=card.pos, size=card.size, radius=[dp(10)])
                card.bind(pos=lambda i, v: setattr(i._bg, 'pos', v),
                          size=lambda i, v: setattr(i._bg, 'size', v))

                # Изображение юнита
                img_src = unit_image if unit_image and os.path.exists(unit_image) else ''
                img_size = dp(72) if unit_class == '1' else dp(82)
                unit_img = Image(
                    source=img_src, size_hint=(None, None),
                    size=(img_size, img_size),
                    allow_stretch=True, keep_ratio=True, mipmap=True
                )
                card.add_widget(unit_img)

                # Текстовая часть
                info = BoxLayout(orientation='vertical', spacing=dp(2))

                # Название
                class_labels = {'1': '', '2': '  [Герой]', '3': '  [Чемпион]', '4': '  [Легенда]'}
                cls_tag = class_labels.get(unit_class, '')
                name_lbl = Label(
                    text=f'[b]{unit_name}[/b][color=#AAAAAA]{cls_tag}[/color]',
                    markup=True, font_size=sp(12), color=(0.95, 0.95, 0.95, 1),
                    halign='left', valign='middle', size_hint_y=None, height=dp(22)
                )
                name_lbl.bind(size=lambda i, s: setattr(i, 'text_size', (s[0], None)))
                info.add_widget(name_lbl)

                # Количество (только для класса 1)
                if unit_class == '1':
                    cnt_lbl = Label(
                        text=f'[color=#FFD700]{format_number(unit_count)}[/color] бойцов',
                        markup=True, font_size=sp(11), color=(0.80, 0.80, 0.80, 1),
                        halign='left', valign='middle', size_hint_y=None, height=dp(18)
                    )
                    cnt_lbl.bind(size=lambda i, s: setattr(i, 'text_size', (s[0], None)))
                    info.add_widget(cnt_lbl)

                card.add_widget(info)

                # Иконка специализации для героев
                if unit_class in ('2', '3') and specialization_icon_path:
                    if os.path.exists(specialization_icon_path):
                        card.add_widget(Image(
                            source=specialization_icon_path,
                            size_hint=(None, None), size=(dp(40), dp(40)),
                            pos_hint={'center_y': 0.5},
                            allow_stretch=True, keep_ratio=True
                        ))

                self.attacking_units_box.add_widget(card)

        except Exception as e:
            print(f"Ошибка при получении гарнизона: {e}")
            import traceback
            traceback.print_exc()
            error_label = Label(
                text="Ошибка загрузки гарнизона",
                size_hint_y=None,
                height=60,
                font_size='18sp',
                color=(1, 0, 0, 1),
                halign='center',
                valign='middle'
            )
            error_label.bind(size=error_label.setter('text_size'))
            self.attacking_units_box.add_widget(error_label)

    def show_warning_popup(self):
        popup = Popup(
            title="Внимание!",
            size_hint=(0.55, 0.25),
            background_color=(0.07, 0.08, 0.13, 1),
            separator_color=(0.25, 0.52, 0.92, 0.5),
            title_color=(1, 1, 1, 1),
            title_size=sp(18),
            title_align='center'
        )

        layout = BoxLayout(orientation='vertical', padding=dp(12), spacing=dp(10))
        with layout.canvas.before:
            layout._bgc = Color(0.07, 0.08, 0.13, 1)
            layout._bgr = Rectangle(pos=layout.pos, size=layout.size)
        layout.bind(pos=lambda i, v: setattr(i._bgr, 'pos', v),
                    size=lambda i, v: setattr(i._bgr, 'size', v))

        label = Label(
            text="Для размещения юнитов сначала надо нанять!",
            color=(0.96, 0.96, 0.96, 1),
            font_size=sp(15),
            halign='center',
            valign='middle'
        )
        label.bind(size=lambda i, s: setattr(i, 'text_size', s))

        btn = Button(
            text="OK",
            font_size=sp(16),
            bold=True,
            background_color=(0, 0, 0, 0),
            color=(1, 1, 1, 1),
            size_hint=(1, None),
            height=dp(44)
        )
        with btn.canvas.before:
            btn._bc = Color(0.16, 0.46, 0.82, 1)
            btn._br = RoundedRectangle(pos=btn.pos, size=btn.size, radius=[dp(12)])
        btn.bind(pos=lambda i, v: setattr(i._br, 'pos', v),
                 size=lambda i, v: setattr(i._br, 'size', v))

        popup.content = layout
        btn.bind(on_release=popup.dismiss)

        layout.add_widget(label)
        layout.add_widget(btn)

        popup.open()

    def place_army(self, instance):
        try:
            if self.current_popup:
                self.current_popup.dismiss()
                self.current_popup = None

            cursor = self.conn.cursor()
            current_city_owner = self.get_city_owner(self.city_name)
            current_player_kingdom = self.player_fraction

            if current_city_owner != current_player_kingdom:
                show_popup_message("Ошибка", "Вы не можете размещать войска в чужом городе.")
                return

            cursor.execute("""
                SELECT unit_type, quantity, total_attack, total_defense, total_durability, unit_class, unit_image 
                FROM armies
            """)
            army_data = cursor.fetchall()

            if not army_data:
                print("Нет доступных юнитов для размещения.")
                self.show_warning_popup()
                return

            # Создаем всплывающее окно
            popup = Popup(
                title="Разместить армию",
                size_hint=(0.95, 0.92),
                background_color=(0.07, 0.08, 0.13, 1),
                separator_color=(0.25, 0.52, 0.92, 0.5),
                title_color=(1, 1, 1, 1),
                title_size=sp(18),
                title_align='center'
            )
            self.current_popup = popup

            screen_width, _ = Window.size
            scale_factor = screen_width / 360

            font_size = min(max(int(9 * scale_factor), 14), 18)
            image_size = int(80 * scale_factor)

            main_layout = BoxLayout(orientation='vertical', padding=dp(10), spacing=dp(10))
            with main_layout.canvas.before:
                main_layout._bgc = Color(0.07, 0.08, 0.13, 1)
                main_layout._bgr = Rectangle(pos=main_layout.pos, size=main_layout.size)
            main_layout.bind(pos=lambda i, v: setattr(i._bgr, 'pos', v),
                             size=lambda i, v: setattr(i._bgr, 'size', v))

            # ScrollView с карточками
            scroll_view = ScrollView(size_hint=(1, 1))
            card_layout = BoxLayout(orientation='vertical', spacing=dp(10), size_hint_y=None)
            card_layout.bind(minimum_height=card_layout.setter('height'))

            def create_card(unit):
                unit_type, quantity, attack, defense, durability, unit_class, unit_image = unit

                # Создаем unit_data в виде словаря, как в оригинальном коде
                unit_data = {
                    "unit_type": unit_type,
                    "quantity": quantity,
                    "stats": {
                        "Атака": attack,
                        "Защита": defense,
                        "Живучесть": durability,
                        "Класс": unit_class
                    },
                    "unit_image": unit_image
                }

                card = BoxLayout(
                    orientation='horizontal',
                    spacing=dp(10),
                    size_hint_y=None,
                    height=int(120 * scale_factor),
                    padding=dp(10)
                )

                # Фон карточки — тёмная карточка с RoundedRectangle
                with card.canvas.before:
                    card._bgc = Color(0.10, 0.13, 0.20, 1)
                    card._bgr = RoundedRectangle(pos=card.pos, size=card.size, radius=[dp(10)])
                card.bind(pos=lambda i, v: setattr(i._bgr, 'pos', v),
                          size=lambda i, v: setattr(i._bgr, 'size', v))

                # Изображение
                image = Image(
                    source=unit_image,
                    size_hint=(None, None),
                    size=(image_size, image_size)
                )

                # Информация
                info_layout = BoxLayout(orientation='vertical', spacing=dp(5))
                name_label = Label(
                    text=unit_type,
                    font_size=sp(font_size + 2),
                    bold=True,
                    color=(0.96, 0.96, 0.96, 1),
                    size_hint_y=None,
                    height=int(30 * scale_factor)
                )

                stats_label = Label(
                    text=f"Атака: {str(format_number(attack))}\nЗащита: {str(format_number(defense))}\nЖивучесть: {str(format_number(durability))}\nКласс: {unit_class}",
                    font_size=sp(font_size - 1),
                    color=(0.65, 0.70, 0.80, 1),
                    size_hint_y=None,
                    height=int(60 * scale_factor),
                    valign='middle'
                )
                stats_label.bind(size=lambda instance, value: setattr(instance, 'text_size', value))

                quantity_label = Label(
                    text=f"Доступно: {str(format_number(quantity))}",
                    font_size=sp(font_size - 1),
                    color=(0.65, 0.70, 0.80, 1)
                )

                info_layout.add_widget(name_label)
                info_layout.add_widget(stats_label)
                info_layout.add_widget(quantity_label)

                # Кнопка «Добавить» — зелёная
                btn = Button(
                    text="Добавить",
                    font_size=sp(font_size),
                    bold=True,
                    size_hint=(None, None),
                    size=(int(50 * scale_factor), int(50 * scale_factor)),
                    background_color=(0, 0, 0, 0),
                    color=(1, 1, 1, 1)
                )
                with btn.canvas.before:
                    btn._bc = Color(0.18, 0.62, 0.22, 1)
                    btn._br = RoundedRectangle(pos=btn.pos, size=btn.size, radius=[dp(12)])
                btn.bind(pos=lambda i, v: setattr(i._br, 'pos', v),
                         size=lambda i, v: setattr(i._br, 'size', v))
                btn.bind(on_release=lambda btn, data=unit_data: self.add_to_garrison_with_slider(data, btn))

                card.add_widget(image)
                card.add_widget(info_layout)
                card.add_widget(btn)

                return card

            # Добавляем карточки
            for unit in army_data:
                card_layout.add_widget(create_card(unit))

            scroll_view.add_widget(card_layout)
            main_layout.add_widget(scroll_view)

            # Кнопка закрытия — красная
            close_btn = Button(
                text="Закрыть",
                font_size=sp(font_size + 1),
                bold=True,
                size_hint=(1, None),
                height=dp(44),
                background_color=(0, 0, 0, 0),
                color=(1, 1, 1, 1)
            )
            with close_btn.canvas.before:
                close_btn._bc = Color(0.55, 0.14, 0.14, 1)
                close_btn._br = RoundedRectangle(pos=close_btn.pos, size=close_btn.size, radius=[dp(12)])
            close_btn.bind(pos=lambda i, v: setattr(i._br, 'pos', v),
                           size=lambda i, v: setattr(i._br, 'size', v))
            close_btn.bind(on_release=popup.dismiss)
            main_layout.add_widget(close_btn)

            popup.content = main_layout
            popup.open()

        except sqlite3.Error as e:
            show_popup_message("Ошибка", f"Произошла ошибка при работе с базой данных (place_army): {e}")
        except Exception as e:
            show_popup_message("Ошибка", f"Произошла ошибка: {e}")

    def add_to_garrison_with_slider(self, unit_data, name_label):
        """
        Открывает адаптивное всплывающее окно с ползунком для выбора количества войск
        или немедленно размещает, если доступен только 1 юнит.
        """
        from kivy.metrics import dp, sp
        unit_type = unit_data["unit_type"]
        available_count = unit_data["quantity"]

        if available_count == 1:
            # Немедленно размещаем 1 юнит без открытия popup
            self.transfer_army_to_garrison(unit_data, 1)
            return

        # Определение платформы
        is_mobile = platform == 'android' or platform == 'ios'

        # Расчёт ширины окна (95% ширины экрана без ограничения)
        window_width = Window.width * 0.95 if is_mobile else Window.width * 0.7

        # Высота окна с коррекцией для Android
        window_height = Window.height * 0.75 if is_mobile else Window.height * 0.4
        if is_mobile:
            window_height *= 0.9  # Компенсация высоты для Android

        # Создание Popup
        popup = Popup(
            title=f"Размещение {unit_type}",
            size_hint=(None, None),
            width=window_width,
            height=window_height,
            title_size=sp(20) if is_mobile else sp(18),
            background_color=(0.07, 0.08, 0.13, 1),
            separator_color=(0.25, 0.52, 0.92, 0.5),
            title_color=(1, 1, 1, 1),
            title_align='center'
        )

        # Основной контейнер с адаптированными отступами
        layout = BoxLayout(
            orientation='vertical',
            padding=[dp(20), dp(15)],
            spacing=dp(20)
        )
        with layout.canvas.before:
            layout._bgc = Color(0.07, 0.08, 0.13, 1)
            layout._bgr = Rectangle(pos=layout.pos, size=layout.size)
        layout.bind(pos=lambda i, v: setattr(i._bgr, 'pos', v),
                    size=lambda i, v: setattr(i._bgr, 'size', v))

        # === Получаем данные о потреблении ===
        current_consumption, army_limit = self.get_army_consumption_and_limit()

        # Получаем потребление одного юнита
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT consumption FROM units
                WHERE unit_name = ?
            """, (unit_type,))
            consumption_result = cursor.fetchone()
            unit_consumption = consumption_result[0] if consumption_result else 0
        except sqlite3.Error as e:
            print(f"Ошибка при получении потребления юнита: {e}")
            unit_consumption = 0

        # === Информация о потреблении — секция с тёмным фоном ===
        consumption_info = BoxLayout(
            orientation='vertical',
            size_hint_y=None,
            height=dp(100),
            spacing=dp(5),
            padding=[dp(8), dp(6)]
        )
        with consumption_info.canvas.before:
            consumption_info._bgc = Color(0.10, 0.13, 0.20, 1)
            consumption_info._bgr = RoundedRectangle(pos=consumption_info.pos, size=consumption_info.size, radius=[dp(10)])
        consumption_info.bind(pos=lambda i, v: setattr(i._bgr, 'pos', v),
                              size=lambda i, v: setattr(i._bgr, 'size', v))

        # Потребление (динамически обновляется, форматируем до 1 знака)
        new_consumption_label = Label(
            text=f"Потребление: {current_consumption:.1f}",
            font_size=sp(18),
            color=(0.3, 0.7, 0.3, 1),  # Зелёный по умолчанию
            bold=True,
            size_hint_y=None,
            height=dp(40),
            halign='left',
            valign='middle'
        )
        new_consumption_label.bind(size=new_consumption_label.setter('text_size'))
        consumption_info.add_widget(new_consumption_label)

        layout.add_widget(consumption_info)

        # === Ползунок с меткой ===
        slider_container = BoxLayout(
            orientation='horizontal',
            size_hint_y=None,
            height=dp(80) if is_mobile else dp(60),
            spacing=dp(15)
        )

        slider_label = Label(
            text="Количество: 0",
            font_size=sp(18) if is_mobile else sp(16),
            size_hint_x=0.4,
            color=(0.96, 0.96, 0.96, 1),
            halign='right',
            valign='middle'
        )
        slider_label.bind(size=slider_label.setter('text_size'))

        slider = Slider(
            min=0,
            max=available_count,
            value=0,
            step=1,
            size_hint_x=0.6,
            background_width=dp(40) if is_mobile else dp(30)
        )

        def update_slider_label_and_consumption(instance, value):
            """Обновляет метки при изменении значения слайдера"""
            selected_count = int(value)
            slider_label.text = f"Количество: {selected_count}"

            # Рассчитываем Потребление (без округления для точной проверки)
            new_consumption = current_consumption + (unit_consumption * selected_count)

            # Форматируем для отображения с 1 знаком после запятой
            formatted_consumption = f"{new_consumption:.1f}"

            # Обновляем цвет в зависимости от превышения лимита
            if new_consumption > army_limit:
                new_consumption_label.color = (1, 0, 0, 1)  # Красный
                new_consumption_label.text = f"Потребление: {formatted_consumption} (ПРЕВЫШЕНИЕ!)"
            else:
                new_consumption_label.color = (0.3, 0.7, 0.3, 1)  # Зелёный
                new_consumption_label.text = f"Потребление: {formatted_consumption}"

        slider.bind(value=update_slider_label_and_consumption)
        slider_container.add_widget(slider_label)
        slider_container.add_widget(slider)
        layout.add_widget(slider_container)

        # === Кнопки подтверждения ===
        button_layout = BoxLayout(
            orientation='horizontal',
            size_hint_y=None,
            height=dp(100) if is_mobile else dp(70),
            spacing=dp(25)
        )

        confirm_button = Button(
            text="Подтвердить",
            font_size=sp(20) if is_mobile else sp(16),
            bold=True,
            background_color=(0, 0, 0, 0),
            color=(1, 1, 1, 1),
            size_hint_x=0.5
        )
        with confirm_button.canvas.before:
            confirm_button._bc = Color(0.18, 0.62, 0.22, 1)
            confirm_button._br = RoundedRectangle(pos=confirm_button.pos, size=confirm_button.size, radius=[dp(12)])
        confirm_button.bind(pos=lambda i, v: setattr(i._br, 'pos', v),
                            size=lambda i, v: setattr(i._br, 'size', v))

        cancel_button = Button(
            text="Отмена",
            font_size=sp(20) if is_mobile else sp(16),
            bold=True,
            background_color=(0, 0, 0, 0),
            color=(1, 1, 1, 1),
            size_hint_x=0.5
        )
        with cancel_button.canvas.before:
            cancel_button._bc = Color(0.55, 0.14, 0.14, 1)
            cancel_button._br = RoundedRectangle(pos=cancel_button.pos, size=cancel_button.size, radius=[dp(12)])
        cancel_button.bind(pos=lambda i, v: setattr(i._br, 'pos', v),
                           size=lambda i, v: setattr(i._br, 'size', v))

        def confirm_action(btn):
            try:
                selected_count = int(slider.value)
                if 0 < selected_count <= available_count:
                    # Проверяем превышение лимита (используем точные значения!)
                    new_consumption = current_consumption + (unit_consumption * selected_count)
                    if new_consumption > army_limit:
                        show_popup_message(
                            "Превышение лимита",
                            f"Потребление ({new_consumption:.1f}) превысит лимит армии ({army_limit:.1f})."
                        )
                        return

                    self.transfer_army_to_garrison(unit_data, selected_count)
                    popup.dismiss()
                else:
                    show_popup_message("Ошибка", f"Выберите количество от 1 до {available_count}")
            except ValueError:
                show_popup_message("Ошибка", "Введите корректное число")

        confirm_button.bind(on_release=confirm_action)
        cancel_button.bind(on_release=lambda btn: popup.dismiss())
        button_layout.add_widget(confirm_button)
        button_layout.add_widget(cancel_button)
        layout.add_widget(button_layout)

        # === Адаптация размера окна при изменении размера экрана ===
        def adapt_popup_size(*args):
            if is_mobile:
                popup.width = Window.width * 0.95
                popup.height = Window.height * 0.6 * 0.9
            else:
                popup.width = Window.width * 0.7
                popup.height = Window.height * 0.4

        Window.bind(on_resize=adapt_popup_size)
        popup.bind(on_dismiss=lambda _: Window.unbind(on_resize=adapt_popup_size))
        popup.content = layout
        popup.open()

    def get_city_owner(self, city_name):
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT faction FROM cities 
                WHERE name = ?
            """, (city_name,))
            result = cursor.fetchone()
            if not result:
                print(f"Город '{city_name}' не найден в таблице cities.")
                return None

            return result[0]
        except sqlite3.Error as e:
            print(f"Ошибка при получении владельца города: {e}")
            return None

    def has_road_between_cities(self, city1_name, city2_name):
        """Проверяет, есть ли дорога между двумя городами."""
        try:
            cursor = self.conn.cursor()
            # Получаем id городов
            cursor.execute("SELECT id FROM cities WHERE name = ?", (city1_name,))
            city1_id = cursor.fetchone()
            cursor.execute("SELECT id FROM cities WHERE name = ?", (city2_name,))
            city2_id = cursor.fetchone()
            if not city1_id or not city2_id:
                return False
            city1_id, city2_id = city1_id[0], city2_id[0]
            # Проверяем наличие дороги
            cursor.execute("""
                SELECT 1 FROM roads 
                WHERE (city1 = ? AND city2 = ?) OR (city1 = ? AND city2 = ?)
            """, (city1_id, city2_id, city2_id, city1_id))
            return cursor.fetchone() is not None
        except sqlite3.Error as e:
            print(f"Ошибка при проверке дороги: {e}")
            return False

    def has_own_territory_path(self, source_city, destination_city, faction):
        """Проверяет наличие пути по дорогам внутри собственной территории."""
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT id FROM cities WHERE name = ?", (source_city,))
            source_row = cursor.fetchone()
            cursor.execute("SELECT id FROM cities WHERE name = ?", (destination_city,))
            destination_row = cursor.fetchone()
            if not source_row or not destination_row:
                return False

            source_id = source_row[0]
            destination_id = destination_row[0]
            if source_id == destination_id:
                return True

            visited = {source_id}
            queue = [source_id]

            while queue:
                current = queue.pop(0)
                cursor.execute("""
                    SELECT city1, city2 FROM roads
                    WHERE city1 = ? OR city2 = ?
                """, (current, current))
                for city1_id, city2_id in cursor.fetchall():
                    neighbor = city2_id if city1_id == current else city1_id
                    if neighbor in visited:
                        continue
                    cursor.execute("SELECT faction FROM cities WHERE id = ?", (neighbor,))
                    neighbor_row = cursor.fetchone()
                    if not neighbor_row or neighbor_row[0] != faction:
                        continue
                    if neighbor == destination_id:
                        return True
                    visited.add(neighbor)
                    queue.append(neighbor)

            return False
        except sqlite3.Error as e:
            print(f"Ошибка при проверке пути по своей территории: {e}")
            return False

    def initialize_turn_check_attack_faction(self):
        """
        Инициализирует запись в таблице turn_check_attack_faction, если её нет.
        Устанавливает значение check_attack в True по умолчанию.
        """
        try:
            cursor = self.conn.cursor()
            # Проверяем, существует ли уже запись для текущей фракции
            cursor.execute("""
                SELECT faction FROM turn_check_attack_faction 
                WHERE faction = ?
            """, (self.ai_fraction,))
            result = cursor.fetchone()

            if not result:
                # Если записи нет, создаем новую с check_attack = True
                cursor.execute("""
                    INSERT INTO turn_check_attack_faction (faction, check_attack)
                    VALUES (?, ?)
                """, (self.ai_fraction, True))
                self.conn.commit()
                print(f"Инициализирована запись для фракции {self.ai_fraction} с check_attack=True")
            else:
                print(f"Запись для фракции {self.ai_fraction} уже существует.")
        except sqlite3.Error as e:
            print(f"Ошибка при инициализации turn_check_attack_faction: {e}")

    def initialize_turn_check_move(self):
        """
        Инициализирует запись о возможности перемещения для текущей фракции.
        Устанавливает значение 'can_move' = True по умолчанию.
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS turn_check_move (
                    faction TEXT PRIMARY KEY,
                    can_move BOOLEAN
                )
            """)
            self.conn.commit()

            # Проверяем, существует ли запись для текущей фракции
            cursor.execute("SELECT faction FROM turn_check_move WHERE faction = ?", (self.player_fraction,))
            result = cursor.fetchone()
            if not result:
                # Если записи нет, создаем новую с can_move = True
                cursor.execute("""
                    INSERT INTO turn_check_move (faction, can_move)
                    VALUES (?, ?)
                """, (self.player_fraction, True))
                self.conn.commit()
                print(f"Инициализирована запись для фракции {self.player_fraction} с can_move=True")
            else:
                print(f"Запись для фракции {self.player_fraction} уже существует.")
        except sqlite3.Error as e:
            print(f"Ошибка при инициализации turn_check_move: {e}")



    def move_selected_group_to_city(self, instance=None):
        """Перемещает выбранную группу юнитов в город."""
        if not self.selected_group:
            show_popup_message("Ошибка", "Группа пуста. Добавьте юниты перед перемещением.")
            return

        try:
            current_player_kingdom = self.player_fraction
            cursor = self.conn.cursor()

            # Проверка возможности перемещения в рамках хода
            cursor.execute(
                "SELECT can_move FROM turn_check_move WHERE faction = ?",
                (current_player_kingdom,)
            )
            move_data = cursor.fetchone()
            if not move_data:
                cursor.execute(
                    "INSERT INTO turn_check_move (faction, can_move) VALUES (?, ?)",
                    (current_player_kingdom, True)
                )
                self.conn.commit()
                can_move_this_turn = True
            else:
                can_move_this_turn = move_data[0]

            if not can_move_this_turn:
                show_popup_message("Ошибка", "Вы уже использовали своё перемещение на этом ходу.")
                return

            # Если город назначения принадлежит текущей фракции — перемещение без ограничений
            cursor.execute(
                "SELECT faction FROM cities WHERE name = ?",
                (self.city_name,)
            )
            target_faction_row = cursor.fetchone()
            destination_owner = target_faction_row[0] if target_faction_row else None
            is_war_destination = False
            if destination_owner and destination_owner != current_player_kingdom:
                is_war_destination = self.get_relationship(current_player_kingdom, destination_owner) == 'война'

            if target_faction_row and target_faction_row[0] == current_player_kingdom:
                allowed_by_distance = False
                for unit in self.selected_group:
                    source_city = unit.get("city_name")
                    if not source_city:
                        show_popup_message("Ошибка", "Не указан исходный город для перемещения.")
                        return

                    source_owner = self.get_city_owner(source_city)
                    if source_owner == current_player_kingdom:
                        if self.has_own_territory_path(source_city, self.city_name, current_player_kingdom):
                            allowed_by_distance = True
                            break
                    elif self.has_road_between_cities(source_city, self.city_name):
                        allowed_by_distance = True
                        break
            else:
                # Проверяем условие по наличию дороги хотя бы для одного юнита
                allowed_by_distance = False
                for unit in self.selected_group:
                    source_city = unit.get("city_name")
                    if not source_city:
                        show_popup_message("Ошибка", "Не указан исходный город для перемещения.")
                        return

                    if self.has_road_between_cities(source_city, self.city_name):
                        allowed_by_distance = True
                        break  # достаточно одного юнита

            if not allowed_by_distance:
                show_popup_message(
                    "Нет дороги",
                    f"Нет дороги к городу {self.city_name} от ваших войск."
                )
                return

            # Группируем юниты по их исходным городам
            grouped_by_city = defaultdict(lambda: defaultdict(int))
            for unit in self.selected_group:
                city = unit["city_name"]
                name = unit["unit_name"]
                count = unit["unit_count"]
                grouped_by_city[city][name] += count

            # Перемещаем по каждому городу отдельно
            for source_city, units in grouped_by_city.items():
                source_units = [u for u in self.selected_group if u.get("city_name") == source_city]
                for unit_name, total_count in units.items():
                    success = self.transfer_troops_between_cities(
                        source_fortress_name=source_city,
                        destination_fortress_name=self.city_name,
                        unit_name=unit_name,
                        taken_count=total_count,
                        attacking_units=source_units
                    )
                    if not success:
                        show_popup_message(
                            "Ошибка",
                            f"Не удалось переместить {unit_name} из {source_city}"
                        )
                        return
                    if is_war_destination:
                        break

            # Фиксируем факт использования перемещения
            cursor.execute(
                "UPDATE turn_check_move SET can_move = ? WHERE faction = ?",
                (False, current_player_kingdom)
            )
            self.conn.commit()

            # Закрываем попап и обновляем интерфейс
            if hasattr(self, 'current_popup') and self.current_popup:
                self.current_popup.dismiss()
                self.current_popup = None
            if hasattr(self, 'dismiss'):
                self.dismiss()

        except Exception as e:
            show_popup_message("Ошибка", f"Произошла ошибка при перемещении группы: {e}")

        finally:
            self.selected_group.clear()
            self.update_garrison()

    def transfer_troops_between_cities(self,
                                       source_fortress_name,
                                       destination_fortress_name,
                                       unit_name,
                                       taken_count,
                                       attacking_units=None):

        try:
            cursor = self.conn.cursor()

            # Получаем владельцев городов
            source_owner = self.get_city_owner(source_fortress_name)
            destination_owner = self.get_city_owner(destination_fortress_name)
            # Проверяем, является ли город нейтральным
            cursor.execute("SELECT faction FROM cities WHERE name = ?", (destination_fortress_name,))
            dest_kingdom_result = cursor.fetchone()
            dest_kingdom = dest_kingdom_result[0] if dest_kingdom_result else None
            # Проверяем существование обоих городов
            if not source_owner or not destination_owner:
                show_popup_message("Ошибка", "Один из городов не существует.")
                return False

            # Проверяем маршрут для движения
            if source_owner == self.player_fraction and destination_owner == self.player_fraction:
                if not (self.has_road_between_cities(source_fortress_name, destination_fortress_name) or
                        self.has_own_territory_path(source_fortress_name, destination_fortress_name,
                                                   self.player_fraction)):
                    show_popup_message("Нет дороги",
                                       f"Нет пути между {source_fortress_name} и {destination_fortress_name} по вашей территории.")
                    return False
            else:
                if not self.has_road_between_cities(source_fortress_name, destination_fortress_name):
                    show_popup_message("Нет дороги", f"Нет дороги между {source_fortress_name} и {destination_fortress_name}.")
                    return False

            current_player_kingdom = self.player_fraction

            # 1) Сценарий: войска в своём городе
            if source_owner == current_player_kingdom:

                # Свой город или союзник — просто перемещаем
                if destination_owner == current_player_kingdom or self.is_ally(current_player_kingdom,
                                                                               destination_owner):
                    self.move_troops(source_fortress_name, destination_fortress_name, unit_name, taken_count)
                    cursor.execute("UPDATE turn_check_move SET can_move = ? WHERE faction = ?",
                                   (False, current_player_kingdom))
                    self.conn.commit()
                    return True

                # Нейтральный город — захват без боя
                elif dest_kingdom == "Нейтрал":
                    self.capture_city(destination_fortress_name, current_player_kingdom, self.selected_group)
                    cursor.execute("UPDATE turn_check_move SET can_move = ? WHERE faction = ?",
                                   (False, current_player_kingdom))
                    self.conn.commit()
                    return True

                # Вражеский город — начинаем атаку
                relationship = self.get_relationship(current_player_kingdom, destination_owner)

                if relationship == "война":
                    # проверка, была ли атака уже
                    cursor.execute(
                        "SELECT check_attack FROM turn_check_attack_faction WHERE faction = ?",
                        (destination_owner,)
                    )
                    attack_data = cursor.fetchone()
                    if attack_data and attack_data[0]:
                        show_popup_message("Ошибка",
                                           f"Фракция '{destination_owner}' уже была атакована на этом ходу.")
                        return False

                    # Обновляем данные об атаке и возможности движения
                    cursor.execute(
                        "INSERT OR REPLACE INTO turn_check_attack_faction (faction, check_attack) VALUES (?, ?)",
                        (destination_owner, True)
                    )
                    cursor.execute(
                        "UPDATE turn_check_move SET can_move = ? WHERE faction = ?",
                        (False, current_player_kingdom)
                    )
                    self.conn.commit()

                    # Запускаем бой
                    battle_units = attacking_units if attacking_units is not None else self.selected_group
                    self.start_battle_group(source_fortress_name,
                                            destination_fortress_name,
                                            battle_units)
                    return True

                elif relationship == "нейтралитет":
                    show_popup_message("Дипломатия",
                                       f"Сначала надо объявить им войну.\nГород контролируется фракцией '{destination_owner}'.")
                    return False

                else:
                    show_popup_message("Нет дороги",
                                       "Нет дороги к этому городу.")
                    return False


            # 2) Сценарий: войска в городе союзника
            elif self.is_ally(current_player_kingdom, source_owner):

                if (destination_owner == current_player_kingdom or
                        self.is_ally(current_player_kingdom, destination_owner)):

                    self.move_troops(source_fortress_name, destination_fortress_name, unit_name, taken_count)
                    return True

                else:
                    show_popup_message("Нет дороги",
                                       "Нет дороги к этому городу")
                    return False

            # 3) Во всех остальных случаях (нейтральный или враждебный источник)
            else:
                show_popup_message("Ошибка",
                                   "Вы можете перемещать свои войска на свою территорию только из города союзника.")
                return False

        except sqlite3.Error as e:
            show_popup_message("Ошибка",
                               f"Произошла ошибка при работе с базой данных (transfer): {e}")
            return False
        except Exception as e:
            print(f"[ERROR] Текущее имя города {destination_fortress_name}")
            show_popup_message("Ошибка",
                               f"Произошла ошибка при переносе войск: {e}")
            return False

    def move_troops(self, source_fortress_name, destination_fortress_name, unit_name, taken_count):
        """
        Перемещает войска между городами.
        """
        try:
            cursor = self.conn.cursor()

            # Проверяем наличие юнита в источнике
            cursor.execute("""
                SELECT unit_count, unit_image FROM garrisons 
                WHERE city_name = ? AND unit_name = ?
            """, (source_fortress_name, unit_name))
            source_unit = cursor.fetchone()

            if not source_unit or source_unit[0] < taken_count:
                print(f"Ошибка: недостаточно юнитов '{unit_name}' в городе '{source_fortress_name}'.")
                return

            unit_image = source_unit[1]
            remaining_count = source_unit[0] - taken_count

            # Обновляем или удаляем из исходного города
            if remaining_count > 0:
                cursor.execute("""
                    UPDATE garrisons 
                    SET unit_count = ? 
                    WHERE city_name = ? AND unit_name = ?
                """, (remaining_count, source_fortress_name, unit_name))
            else:
                cursor.execute("""
                    DELETE FROM garrisons 
                    WHERE city_name = ? AND unit_name = ?
                """, (source_fortress_name, unit_name))

            # Переносим в целевой город с защитой от дубликатов
            cursor.execute("""
                INSERT INTO garrisons (city_name, unit_name, unit_count, unit_image)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(city_name, unit_name) DO UPDATE
                SET unit_count = unit_count + excluded.unit_count
            """, (destination_fortress_name, unit_name, taken_count, unit_image))

            self.conn.commit()
            print("Войска успешно перенесены.")
            self.close_current_popup()

        except sqlite3.Error as e:
            self.conn.rollback()
            print(f"[ERROR] Ошибка SQLite при перемещении войск: {e}")
            show_popup_message("Ошибка", f"Не удалось переместить войска: {e}")

        except Exception as e:
            self.conn.rollback()
            print(f"[ERROR] Неожиданная ошибка при перемещении войск: {e}")
            show_popup_message("Ошибка", f"Произошла системная ошибка: {e}")

    def start_battle_group(self, source_fortress_name, destination_fortress_name, attacking_units):
        try:
            with self.conn:
                try:
                    self.conn.execute("PRAGMA wal_checkpoint(FULL);")
                except sqlite3.Error as e:
                    print(f"[WARNING] Не удалось выполнить wal_checkpoint: {e}")

                cursor = self.conn.cursor()

                source_owner = self.get_city_owner(source_fortress_name)
                destination_owner = self.get_city_owner(destination_fortress_name)

                if not source_owner or not destination_owner:
                    print(f"[ERROR] Не удалось определить фракции. source={source_owner}, dest={destination_owner}")
                    show_popup_message("Ошибка", "Не удалось определить фракции.")
                    return

                # вытаскиваем гарнизон
                cursor.execute(
                    "SELECT unit_name, unit_count, unit_image FROM garrisons WHERE city_name = ?",
                    (destination_fortress_name,)
                )
                rows = cursor.fetchall()
                # вот здесь конвертим Row в dict
                defending_garrison = [dict(row) for row in rows]
                print(f"defending_garrison={defending_garrison}")

                if not defending_garrison:
                    self.capture_city(destination_fortress_name, source_owner, attacking_units)
                    self.close_current_popup()
                    return

                # собираем имена из атакующих
                unit_names = {u.get('unit_name', '').strip() for u in attacking_units if u.get('unit_name')}
                # и из защищающихся
                for unit in defending_garrison:
                    name = unit.get('unit_name', '').strip()
                    if name:
                        unit_names.add(name)
                unit_names = list(unit_names)
                print(f"unit_names={unit_names}")

                if not unit_names:
                    print("[WARNING] Нет имён юнитов для запроса характеристик.")
                    show_popup_message("Ошибка", "Нет данных о юнитах для боя.")
                    return

                # достаём статы
                placeholders = ','.join('?' * len(unit_names))
                query = f"""
                    SELECT unit_name, attack, durability, defense, unit_class, image_path 
                    FROM units 
                    WHERE unit_name IN ({placeholders})
                """
                cursor.execute(query, unit_names)
                results = cursor.fetchall()

                cols = [d[0] for d in cursor.description]
                idx = {k: cols.index(k) for k in
                       ('unit_name', 'attack', 'durability', 'defense', 'unit_class', 'image_path')}

                unit_stats = {
                    row[idx['unit_name']].strip(): {
                        'unit_name': row[idx['unit_name']].strip(),
                        'attack': row[idx['attack']],
                        'durability': row[idx['durability']],
                        'defense': row[idx['defense']],
                        'unit_class': row[idx['unit_class']],
                        'image_path': row[idx['image_path']],
                    }
                    for row in results
                }

                # Формируем армии
                attacking_army = []
                for u in attacking_units:
                    name = u.get('unit_name', '').strip()
                    stats = unit_stats.get(name)
                    if not stats:
                        print(f"Ошибка: данные о юните '{name}' не найдены.")
                        continue
                    attacking_army.append({
                        "unit_name": name,
                        "unit_count": u.get('unit_count', 0),
                        "unit_image": stats['image_path'],
                        "units_stats": {
                            "Урон": stats['attack'],
                            "Живучесть": stats['durability'],
                            "Защита": stats['defense'],
                            "Класс юнита": stats['unit_class'],
                        }
                    })

                defending_army = []
                for u in defending_garrison:
                    name = u.get('unit_name', '').strip()
                    stats = unit_stats.get(name)
                    if not stats:
                        print(f"Ошибка: данные о юните '{name}' не найдены.")
                        continue
                    defending_army.append({
                        "unit_name": name,
                        "unit_count": u.get('unit_count', 0),
                        "unit_image": stats['image_path'],
                        "units_stats": {
                            "Урон": stats['attack'],
                            "Живучесть": stats['durability'],
                            "Защита": stats['defense'],
                            "Класс юнита": stats['unit_class'],
                        }
                    })

                # Запускаем сам бой
                fight(
                    attacking_city=source_fortress_name,
                    defending_city=destination_fortress_name,
                    defending_army=defending_army,
                    attacking_army=attacking_army,
                    attacking_fraction=source_owner,
                    defending_fraction=destination_owner,
                    conn=self.conn
                )
                self.close_current_popup()

        except sqlite3.Error as e:
            print(f"[ERROR] Ошибка базы данных при запуске боя: {e}")
            show_popup_message("Ошибка", f"Ошибка БД: {e}")
            self.close_current_popup()
        except Exception as e:
            print(f"[ERROR] Неожиданная ошибка при запуске боя: {e}")
            show_popup_message("Ошибка", f"Неизвестная ошибка: {e}")
            self.close_current_popup()

    def capture_city(self, city_name, new_owner, attacking_units):
        try:
            with self.conn:
                cursor = self.conn.cursor()

                # 1. Обновляем владельца города
                cursor.execute("""
                    UPDATE cities 
                    SET faction = ? 
                    WHERE name = ?
                """, (new_owner, city_name))

                # 2. Переносим только атакующие юниты
                for unit in attacking_units:
                    # Удаляем из исходного города
                    cursor.execute("""
                        UPDATE garrisons 
                        SET unit_count = unit_count - ? 
                        WHERE city_name = ? AND unit_name = ?
                    """, (unit["unit_count"], unit["city_name"], unit["unit_name"]))

                    # Удаляем запись, если юнитов больше нет
                    cursor.execute("""
                        DELETE FROM garrisons 
                        WHERE city_name = ? AND unit_name = ? AND unit_count <= 0
                    """, (unit["city_name"], unit["unit_name"]))

                    # Добавляем в захваченный город
                    cursor.execute("""
                        INSERT INTO garrisons 
                        (city_name, unit_name, unit_count, unit_image) 
                        VALUES (?, ?, ?, ?)
                        ON CONFLICT(city_name, unit_name) DO UPDATE 
                        SET unit_count = unit_count + ?
                    """, (city_name, unit["unit_name"], unit["unit_count"],
                          unit["unit_image"], unit["unit_count"]))

                # 3. Передаем здания новому владельцу
                cursor.execute("""
                    UPDATE buildings 
                    SET faction = ? 
                    WHERE city_name = ?
                """, (new_owner, city_name))

            show_popup_message("Успех", f"Город {city_name} захвачен!")
            self.update_garrison()

        except sqlite3.Error as e:
            show_popup_message("Ошибка", f"Ошибка при захвате города: {e}")

    def get_city_coordinates(self, city_name):
        """
        Возвращает координаты указанного города.
        :param city_name: Название города.
        :return: Кортеж (x, y) с координатами города.
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT coordinates FROM cities WHERE name = ?", (city_name,))
        result = cursor.fetchone()
        if result:
            # Преобразуем строку "[x, y]" в кортеж (x, y)
            coords_str = result[0].strip('[]')
            x, y = map(int, coords_str.split(','))
            return x, y
        raise ValueError(f"Город '{city_name}' не найден в базе данных.")

    def is_ally(self, faction1_id, faction2_id):
        """
        Проверяет, являются ли две фракции союзниками.
        :param faction1_id: Идентификатор первой фракции.
        :param faction2_id: Идентификатор второй фракции.
        :return: True, если фракции союзники, иначе False.
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT relationship FROM diplomacies 
                WHERE (faction1 = ? AND faction2 = ?) OR (faction1 = ? AND faction2 = ?)
            """, (faction1_id, faction2_id, faction2_id, faction1_id))
            result = cursor.fetchone()
            return result and result[0] == "союз"
        except sqlite3.Error as e:
            print(f"Ошибка при проверке союзников: {e}")
            return False

    def get_relationship(self, faction1_id, faction2_id):
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT relationship FROM diplomacies 
                WHERE (faction1 = ? AND faction2 = ?) OR (faction1 = ? AND faction2 = ?)
            """, (faction1_id, faction2_id, faction2_id, faction1_id))
            result = cursor.fetchone()
            return result[0] if result else None
        except sqlite3.Error as e:
            print(f"Ошибка при получении дипломатических отношений: {e}")
            return None

    def is_enemy(self, faction1_id, faction2_id):
        """
        Проверяет, находятся ли две фракции в состоянии войны.
        :param faction1_id: Идентификатор первой фракции.
        :param faction2_id: Идентификатор второй фракции.
        :return: True, если фракции враги, иначе False.
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT relationship FROM diplomacies 
                WHERE (faction1 = ? AND faction2 = ?) OR (faction1 = ? AND faction2 = ?)
            """, (faction1_id, faction2_id, faction2_id, faction1_id))
            result = cursor.fetchone()
            return result and result[0] == "война"
        except sqlite3.Error as e:
            print(f"Ошибка при проверке враждебности: {e}")
            return False

    def transfer_army_to_garrison(self, selected_unit, taken_count):
        """
        Переносит юнитов из армии в гарнизон и создаёт слоты экипировки для героев 3 класса.
        """
        try:
            with self.conn:
                cursor = self.conn.cursor()
                unit_type = selected_unit.get("unit_type")
                stats = selected_unit.get("stats", {})
                unit_image = selected_unit.get("unit_image")
                faction = self.player_fraction

                unit_class = stats.get("Класс", None)
                print(f"[DEBUG] transfer_army_to_garrison called with:")
                print(f"  unit_type: {unit_type}")
                print(f"  taken_count: {taken_count}")
                print(f"  unit_class from stats: {unit_class} (type: {type(unit_class)})")
                print(f"  faction: {faction}")

                if not all([unit_type, taken_count, stats, unit_image]):
                    raise ValueError("Некорректные данные для переноса юнита.")

                # --- ЛОГИКА ДОБАВЛЕНИЯ В ГАРИЗОН ---
                cursor.execute("""
                    SELECT unit_count FROM garrisons
                    WHERE city_name = ? AND unit_name = ?
                """, (self.city_name, unit_type))
                existing_unit = cursor.fetchone()

                if existing_unit:
                    new_count = existing_unit[0] + taken_count
                    cursor.execute("""
                        UPDATE garrisons
                        SET unit_count = ?
                        WHERE city_name = ? AND unit_name = ?
                    """, (new_count, self.city_name, unit_type))
                    print(f"[DEBUG] Updated garrisons: {unit_type} count to {new_count}")
                else:
                    cursor.execute("""
                        INSERT INTO garrisons
                        (city_name, unit_name, unit_count, unit_image)
                        VALUES (?, ?, ?, ?)
                    """, (self.city_name, unit_type, taken_count, unit_image))
                    print(f"[DEBUG] Inserted new unit into garrisons: {unit_type}, count {taken_count}")

                # Уменьшаем количество юнитов в армии
                cursor.execute("""
                    UPDATE armies
                    SET quantity = quantity - ?
                    WHERE unit_type = ?
                """, (taken_count, unit_type))
                print(f"[DEBUG] Decreased army quantity for {unit_type} by {taken_count}")

                cursor.execute("""
                    DELETE FROM armies
                    WHERE unit_type = ? AND quantity <= 0
                """, (unit_type,))
                print(f"[DEBUG] Cleaned up armies table for {unit_type} if quantity <= 0")

                # Работа с таблицей results
                cursor.execute("""
                    INSERT INTO results (faction, Units_Combat)
                    VALUES (?, ?)
                    ON CONFLICT(faction) DO UPDATE SET Units_Combat = Units_Combat + excluded.Units_Combat
                """, (faction, taken_count))
                print(f"[DEBUG] Updated results table for faction {faction} with +{taken_count} Units_Combat")

                # --- КОНЕЦ ЛОГИКИ ДОБАВЛЕНИЯ В ГАРИЗОН ---

                # --- НОВАЯ ЛОГИКА: СОЗДАНИЕ СЛОТОВ ЭКИПИРОВКИ ДЛЯ ГЕРОЕВ 3 КЛАССА ---
                if unit_class == "3" and taken_count > 0:
                    print(f"[DEBUG] Detected Hero (Class 3) being added: {unit_type}")
                    hero_name = unit_type

                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS hero_equipment (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            faction_name TEXT NOT NULL,
                            hero_name TEXT NOT NULL,
                            slot_type INTEGER NOT NULL,
                            artifact_id INTEGER,
                            UNIQUE(faction_name, hero_name, slot_type)
                        );
                    """)
                    print("[DEBUG] Ensured hero_equipment table exists")

                    equipment_data = [
                        (faction, hero_name, slot_type, None)
                        for slot_type in range(5)
                    ]
                    print(f"[DEBUG] Prepared equipment data for {hero_name}: {equipment_data}")

                    cursor.executemany("""
                        INSERT OR IGNORE INTO hero_equipment (faction_name, hero_name, slot_type, artifact_id)
                        VALUES (?, ?, ?, ?)
                    """, equipment_data)
                    print(f"[DEBUG] Attempted to insert 5 equipment slots for hero '{hero_name}'.")
                # --- КОНЕЦ НОВОЙ ЛОГИКИ ---

                # === КЛЮЧЕВОЕ ИЗМЕНЕНИЕ: НЕМЕДЛЕННОЕ ОБНОВЛЕНИЕ ПОТРЕБЛЕНИЯ И ЛИМИТА В БД ===
                self.recalculate_and_update_army_consumption()

                # Обновляем отображение гарнизона
                self.update_garrison()
                self.close_current_popup()

        except sqlite3.Error as e:
            error_msg = f"Не удалось перенести юниты или создать слоты экипировки: {e}"
            print(f"[ERROR] SQLite Error: {error_msg}")
            show_popup_message("Ошибка", error_msg)
        except Exception as e:
            error_msg = f"Произошла ошибка: {e}"
            print(f"[ERROR] General Error: {error_msg}")
            import traceback
            traceback.print_exc()
            show_popup_message("Ошибка", error_msg)

    def close_current_popup(self):
        """Закрывает текущее всплывающее окно."""
        if self.current_popup:
            self.current_popup.dismiss()
            self.current_popup = None  # Очищаем ссылку

    def close_popup(self):
        """
        Закрывает текущее всплывающее окно и освобождает ресурсы.
        """
        self.dismiss()  # Закрываем окно
        self.clear_widgets()  # Очищаем все виджеты


def show_popup_message(title, message):
    """
    Отображает всплывающее окно с сообщением,
    расположенным по центру, белым цветом и размером 18sp.
    :param title: Заголовок окна.
    :param message: Текст сообщения (короткий, без прокрутки).
    """

    # Основной контейнер: заполняет всё пространство popup
    content = BoxLayout(
        orientation='vertical',
        padding=dp(15),
        spacing=dp(10),
        size_hint=(1, 1)
    )

    # Label с сообщением: белый цвет, 18sp, по центру и внутри
    message_label = Label(
        text=message,
        size_hint=(1, 1),
        font_size=dp(18),
        color=(1, 1, 1, 1),  # чисто белый
        halign='center',
        valign='middle'
    )
    # Чтобы текст правильно оборачивался и центрировался внутри Label:
    # связываем text_size с размером самой метки
    message_label.bind(size=lambda instance, value: instance.setter('text_size')(instance, value))

    content.add_widget(message_label)

    # Кнопка «Закрыть» внизу — красная с RoundedRectangle
    close_button = Button(
        text="Закрыть",
        size_hint_y=None,
        height=dp(50),
        background_color=(0, 0, 0, 0),
        color=(1, 1, 1, 1),
        font_size=sp(16),
        bold=True
    )
    with close_button.canvas.before:
        close_button._bc = Color(0.55, 0.14, 0.14, 1)
        close_button._br = RoundedRectangle(pos=close_button.pos, size=close_button.size, radius=[dp(12)])
    close_button.bind(pos=lambda i, v: setattr(i._br, 'pos', v),
                      size=lambda i, v: setattr(i._br, 'size', v))
    content.add_widget(close_button)

    # Тёмный фон контейнера
    with content.canvas.before:
        content._bgc = Color(0.07, 0.08, 0.13, 1)
        content._bgr = Rectangle(pos=content.pos, size=content.size)
    content.bind(pos=lambda i, v: setattr(i._bgr, 'pos', v),
                 size=lambda i, v: setattr(i._bgr, 'size', v))

    # Размер popup: максимум 90% ширины и 70% высоты экрана
    popup_width = min(dp(500), Window.width * 0.9)
    popup_height = min(dp(600), Window.height * 0.7)

    # Создаём само окно с тёмным дизайном
    popup = Popup(
        title=title,
        title_size=sp(18),
        title_align='center',
        title_color=(1, 1, 1, 1),
        content=content,
        separator_color=(0.25, 0.52, 0.92, 0.5),
        separator_height=dp(1),
        size_hint=(None, None),
        size=(popup_width, popup_height),
        background_color=(0.07, 0.08, 0.13, 1),
        overlay_color=(0, 0, 0, 0.5),
        auto_dismiss=False
    )

    # Обработчик изменения размера окна (если пользователь повернёт экран или сменит размер)
    def update_size(*args):
        new_w = min(dp(500), Window.width * 0.9)
        new_h = min(dp(600), Window.height * 0.7)
        popup.size = (new_w, new_h)

    Window.bind(on_resize=update_size)
    popup.bind(on_dismiss=lambda *x: Window.unbind(on_resize=update_size))

    close_button.bind(on_release=popup.dismiss)

    popup.open()
