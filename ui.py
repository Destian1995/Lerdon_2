from db_lerdon_connect import *
from kivy.uix.image import AsyncImage

from fight import fight
from utils.helpers import format_number


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

    _is_mobile = platform in ('android', 'ios')
    popup = Popup(
        title=title, content=content,
        size_hint=(0.88 if _is_mobile else 0.72, 0.40 if _is_mobile else 0.32),
        background_color=(0.07, 0.08, 0.13, 1),
        separator_color=(0.78, 0.18, 0.18, 0.85),
        title_color=(1, 0.55, 0.55, 1),
        title_size=sp(18) if _is_mobile else sp(16), title_align='center',
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
            SELECT name, faction FROM cities
            WHERE coordinates = ?
        """, (coords_str,))

        city_data = self.cursor.fetchone()
        if city_data:
            self.city_name = city_data[0]
            self.city_faction = city_data[1] if city_data[1] else ''
        else:
            print(f"Город с координатами {self.city_coords} не найден в базе данных")
            return

        faction_label = f" ({self.city_faction})" if self.city_faction and self.city_faction != 'Нейтрал' else ""
        self.title = f"Информация о поселении {self.city_name}{faction_label}"

        # ── Стиль как в Мастерской артефактов ──
        self.background_color = (0.06, 0.07, 0.11, 0.98)
        self.separator_color = (0.60, 0.35, 0.85, 0.7)
        self.title_color = (0.85, 0.70, 0.20, 1)
        self.title_size = sp(16 if platform != 'android' else 14)
        self.title_align = 'center'
        self.auto_dismiss = False

        self.create_ui()
        self.bind(on_open=self._tutorial_city_opened)

    def _tutorial_city_opened(self, *args):
        if self.city_faction == self.player_fraction:
            from tutorial import notify_event
            notify_event('owned_city_opened')

    def create_ui(self):
        from strategy_ui import build_city_window
        build_city_window(self)

    def load_buildings(self):
        from city_construction import city_owner
        if not hasattr(self,'city_preview'):return
        self.city_faction=city_owner(self.conn,self.city_name) or self.city_faction
        self.city_preview.refresh()


    # ── Система строительства ────────────────────────────────────
    from city_construction import CATALOG as BUILDING_CATALOG

    def _open_build_menu(self):
        from town_ui import TownPopup
        existing=getattr(self,'town_popup',None)
        if existing is not None and existing.parent is not None:return existing
        self.town_popup=TownPopup(self)
        self.town_popup.open()
        return self.town_popup


    def _build_building(self, building_type, cost=None):
        from city_construction import buy_building
        try:
            with self.conn:buy_building(self.conn,self.city_name,self.player_fraction,building_type)
        except ValueError as exc:
            self._construction_error=str(exc)
            return False
        from utils.resource_payments import sync_resources
        sync_resources(self.conn,self.player_fraction)
        self.load_buildings()
        self.get_garrison()
        return True


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
            from city_construction import building_name
            buildings = [f"{building_name(self.ai_fraction,building_type)}: {format_number(count)}" for building_type, count in buildings_data]

            # Если зданий нет, возвращаем пустой список
            return buildings if buildings else []

        except Exception as e:
            print(f"Ошибка при получении данных о зданиях: {e}")
            return []

    def _show_ally_transfer_choice(self, troop_type, ally_faction):
        """Popup: передать войска союзнику или оставить под контролем."""
        from kivy.uix.popup import Popup as _ATPop
        from kivy.uix.boxlayout import BoxLayout as _ATBox
        from kivy.uix.button import Button as _ATBtn
        from kivy.uix.label import Label as _ATLbl
        from kivy.metrics import dp as _dp, sp as _sp

        content = _ATBox(orientation='vertical', spacing=_dp(10), padding=_dp(14))

        _title = _ATLbl(text=f"[b]Город фракции {ally_faction}[/b]", markup=True,
                         font_size=_sp(16), halign='center', valign='middle',
                         color=(0.95, 0.85, 0.4, 1), size_hint_y=None, height=_dp(36))
        _title.bind(size=lambda w, v: setattr(w, 'text_size', (w.width, None)))
        content.add_widget(_title)

        _desc = _ATLbl(text="Передать войска союзнику\nили оставить под своим командованием?",
                        font_size=_sp(13), halign='center', valign='middle',
                        color=(0.8, 0.85, 0.95, 1), size_hint_y=None, height=_dp(44))
        _desc.bind(size=lambda w, v: setattr(w, 'text_size', (w.width, None)))
        content.add_widget(_desc)

        _hint = _ATLbl(text="При передаче доступны только обычные юниты (класс 1).\n"
                             "Под вашим командованием — все юниты включая героев.",
                        font_size=_sp(11), halign='center', valign='middle',
                        color=(0.55, 0.6, 0.7, 1), size_hint_y=None, height=_dp(40))
        _hint.bind(size=lambda w, v: setattr(w, 'text_size', (w.width, None)))
        content.add_widget(_hint)

        btn_row = _ATBox(size_hint_y=None, height=_dp(46), spacing=_dp(10))
        _is_m = platform in ('android', 'ios')

        popup = _ATPop(title='', content=content,
                        size_hint=(0.95 if _is_m else 0.5, 0.9 if _is_m else 0.7),
                        auto_dismiss=False, separator_height=0,
                        background='', background_color=(0.04, 0.05, 0.09, 0.98))

        transfer_btn = _ATBtn(text="Передать союзнику", background_normal='',
                               background_color=(0.15, 0.55, 0.25, 1),
                               font_size=_sp(13), bold=True)
        control_btn = _ATBtn(text="Под моим командованием", background_normal='',
                              background_color=(0.2, 0.4, 0.8, 1),
                              font_size=_sp(13), bold=True)

        def _on_transfer(inst):
            popup.dismiss()
            self._ally_transfer_mode = 'transfer'
            self.load_troops_by_type(troop_type, None, _transfer_mode='transfer')

        def _on_control(inst):
            popup.dismiss()
            self._ally_transfer_mode = 'control'
            self.load_troops_by_type(troop_type, None, _transfer_mode='control')

        transfer_btn.bind(on_press=_on_transfer)
        control_btn.bind(on_press=_on_control)
        btn_row.add_widget(transfer_btn)
        btn_row.add_widget(control_btn)
        content.add_widget(btn_row)

        cancel_btn = _ATBtn(text="Отмена", background_normal='',
                             background_color=(0.5, 0.15, 0.15, 1),
                             font_size=_sp(12), size_hint_y=None, height=_dp(38))
        cancel_btn.bind(on_press=lambda i: popup.dismiss())
        content.add_widget(cancel_btn)

        popup.open()

    def load_troops_by_type(self, troop_type, previous_popup, _transfer_mode=None):
        """
        Загружает войска из гарнизонов в зависимости от выбранного типа.
        :param troop_type: Тип войск ("Defensive", "Offensive", "Any").
        :param previous_popup: Предыдущее всплывающее окно для закрытия.
        :param _transfer_mode: None (авто), 'transfer' (передать союзнику, class 1),
                               'control' (под контролем игрока, все классы).
        """
        try:
            if previous_popup is not None:
                previous_popup.dismiss()

            cursor = self.conn.cursor()
            target_city = self.city_name

            # Получаем id и владельца целевого города
            cursor.execute("SELECT id, faction FROM cities WHERE name = ?", (target_city,))
            target_row = cursor.fetchone()
            if not target_row:
                _show_dark_error_popup("Ошибка", f"Город '{target_city}' не найден.")
                return
            target_id, target_faction = target_row

            # Если город союзника и режим не задан — спрашиваем
            _is_ally_target = (target_faction != self.player_fraction and
                               self.is_ally(self.player_fraction, target_faction))
            if _is_ally_target and _transfer_mode is None:
                self._show_ally_transfer_choice(troop_type, target_faction)
                return

            from utils.movement_rules import reachable_source_cities
            self._ally_transfer_mode = _transfer_mode or 'control'
            reachable_names = reachable_source_cities(self.conn, target_city, self.player_fraction)
            drag_source = getattr(self, '_drag_source', None)
            if drag_source:
                reachable_names.intersection_update({drag_source})
            reachable_garr_ids = [cid for cid, name in cursor.execute('SELECT id,name FROM cities')
                                  if name in reachable_names]

            if not reachable_garr_ids:
                _show_dark_error_popup("Нет войск", f"Нет ваших войск в городах, откуда можно достичь {target_city}.")
                return

            placeholders = ','.join('?' * len(reachable_garr_ids))
            # Передача союзнику — только юниты 1 класса; под контролем игрока — все
            _class_filter = "AND u.unit_class = '1'" if _transfer_mode == 'transfer' else ""
            cursor.execute(f"""
                SELECT g.city_name, g.unit_name, g.unit_count,
                       COALESCE(NULLIF(g.unit_image, ''), u.image_path, '') as unit_image,
                       u.attack, u.defense, u.durability
                FROM garrisons g
                JOIN cities c ON c.name = g.city_name
                JOIN units u ON u.unit_name = g.unit_name
                WHERE c.id IN ({placeholders})
                  AND u.faction = ? AND g.unit_count > 0
                  {_class_filter}
            """, reachable_garr_ids + [self.player_fraction])

            rows = cursor.fetchall()

            filtered_troops = []
            for city_name, unit_name, unit_count, unit_image, attack, defense, durability in rows:
                if troop_type == "Защитных":
                    if defense > attack and defense > durability:
                        filtered_troops.append((city_name, unit_name, unit_count, unit_image))
                elif troop_type == "Атакующих":
                    if attack > defense and attack > durability:
                        filtered_troops.append((city_name, unit_name, unit_count, unit_image))
                else:
                    filtered_troops.append((city_name, unit_name, unit_count, unit_image))

            if not filtered_troops:
                _show_dark_error_popup("Нет войск", f"Нет доступных войск для перемещения в {target_city}.")
                return

            # Открываем окно с выбором войск
            if drag_source and len(filtered_troops) == 1:
                city, unit, count, image = filtered_troops[0]
                self.selected_group = [dict(city_name=city, unit_name=unit,
                                            unit_count=count, unit_image=image)]
                self.selected_units_set = {(city, unit)}
                self.move_selected_group_to_city()
                return
            self.show_troops_selection(filtered_troops)

        except Exception as e:
            print(f"Ошибка при загрузке войск: {e}")

    def show_troops_selection(self, troops_data):
        from troop_ui import show_troop_selection
        return show_troop_selection(self, troops_data)

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
        _is_mobile = platform in ('android', 'ios')
        popup = Popup(
            title=f"Добавление {unit_name} в группу",
            size_hint=(0.95 if _is_mobile else 0.8, 0.82 if _is_mobile else 0.7),
            background_color=(0.07, 0.08, 0.13, 1),
            separator_color=(0.25, 0.52, 0.92, 0.5),
            title_color=(1, 1, 1, 1),
            title_size=sp(16) if _is_mobile else sp(18),
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

            # 1. Пересчёт потребления: сумма потребления ВСЕХ юнитов в гарнизонах городов фракции игрока
            #    (включая перешедших юнитов из других фракций)
            cursor.execute("""
                SELECT g.unit_name, g.unit_count, u.consumption
                FROM garrisons g
                JOIN units u ON g.unit_name = u.unit_name
                LEFT JOIN cities c ON c.name = g.city_name
                WHERE c.faction = ? OR (g.city_name LIKE '@terrain:%' AND u.faction = ?)
            """, (self.player_fraction,self.player_fraction))
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

        # Перезапрашиваем данные из БД (с фолбэком на image_path из units)
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT g.city_name, g.unit_name, g.unit_count,
                   COALESCE(NULLIF(g.unit_image, ''), u.image_path, '') as unit_image
            FROM garrisons g
            LEFT JOIN units u ON g.unit_name = u.unit_name
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
        """Обновляет данные о гарнизоне — делегирует в get_garrison()."""
        self.get_garrison()

    def get_garrison(self):
        """Получает гарнизон города из таблицы garrisons и отображает его с учетом класса и специализации юнитов."""
        try:
            from utils.garrison_stats import garrison_profiles,garrison_totals
            profiles=garrison_profiles(self.conn,self.city_name)
            self.garrison_profiles_snapshot=profiles
            if hasattr(self, 'garrison_attack_total'):
                totals = garrison_totals(self.conn, self.city_name,profiles)
                self.garrison_totals_snapshot = totals
                self.garrison_attack_total.text = format_number(totals['attack'])
                self.garrison_defense_total.text = format_number(totals['defense'])
            # Запрос к базе данных для получения гарнизона
            # Используем COALESCE: если unit_image пустой/NULL — берём image_path из units
            self.cursor.execute("""
                SELECT g.unit_name, g.unit_count,
                       COALESCE(NULLIF(g.unit_image, ''), u.image_path, '') as unit_image,
                       COALESCE(g.experience, 0) as experience
                FROM garrisons g
                LEFT JOIN units u ON g.unit_name = u.unit_name
                WHERE g.city_name = ?
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
                '1': (0.09, 0.12, 0.17, 1),
                '2': (0.12, 0.09, 0.17, 1),
                '3': (0.17, 0.13, 0.08, 1),
                '4': (0.18, 0.075, 0.075, 1),
            }

            # Вычисляем бонус героев (класс 2-3) для юнитов класса 1
            _hero_bonus_atk = 0
            _hero_bonus_def = 0
            _hero_bonus_dur = 0
            _has_hero_in_garrison = False
            for rd in garrison_data:
                try:
                    self.cursor.execute(
                        "SELECT unit_class, attack, defense, durability FROM units WHERE unit_name = ?",
                        (rd[0],)
                    )
                    hi = self.cursor.fetchone()
                    if hi and int(hi[0]) >= 2 and rd[1] > 0:
                        _has_hero_in_garrison = True
                    if hi and int(hi[0]) in (2, 3) and rd[1] > 0:
                        _hero_bonus_atk += hi[1] or 0
                        _hero_bonus_def += hi[2] or 0
                        _hero_bonus_dur += hi[3] or 0
                except Exception:
                    pass

            # Бонус стен столицы нежити (+100 атаки, +850 защиты)
            try:
                self.cursor.execute("SELECT faction FROM cities WHERE name = ?", (self.city_name,))
                _city_fac = self.cursor.fetchone()
                if _city_fac and _city_fac[0] == 'Нежить':
                    self.cursor.execute("SELECT COALESCE(is_undead, 0) FROM cities WHERE name = ?", (self.city_name,))
                    _is_und = self.cursor.fetchone()
                    if _is_und and _is_und[0]:
                        self.cursor.execute("SELECT capital_city FROM undead_invasion WHERE id = 1")
                        _cap = self.cursor.fetchone()
                        if _cap and _cap[0] == self.city_name:
                            _hero_bonus_atk += 100
                            _hero_bonus_def += 850
                            _has_hero_in_garrison = True
            except Exception:
                pass

            # Проверяем боевой дух (2+ побед над контрпиком за 4 хода)
            _has_battle_spirit = False
            _COUNTER_PICKS = {
                'Адепты': ['Элины', 'Север'],
                'Элины': ['Север', 'Эльфы'],
                'Вампиры': ['Адепты', 'Элины'],
                'Север': ['Вампиры', 'Эльфы'],
                'Эльфы': ['Адепты', 'Вампиры'],
            }
            try:
                _cpicks = _COUNTER_PICKS.get(self.ai_fraction, [])
                if _cpicks:
                    self.cursor.execute("SELECT turn_count FROM turn LIMIT 1")
                    _tr = self.cursor.fetchone()
                    _cur_turn = _tr[0] if _tr else 0
                    _ph = ','.join('?' * len(_cpicks))
                    self.cursor.execute(
                        f"SELECT COUNT(*) FROM faction_victories "
                        f"WHERE faction = ? AND defeated IN ({_ph}) AND turn > ?",
                        [self.ai_fraction] + _cpicks + [_cur_turn - 4]
                    )
                    _has_battle_spirit = self.cursor.fetchone()[0] >= 2
            except Exception:
                pass

            for row_data in garrison_data:
                unit_name, unit_count, unit_image = row_data[0], row_data[1], row_data[2]
                unit_exp = row_data[3] if len(row_data) > 3 else 0
                from monster_sites import effective_experience,experience_multiplier
                _rank_exp = effective_experience(self.conn,self.ai_fraction,unit_exp,self.city_name,unit_name)
                _unit_exp_mult = experience_multiplier(self.conn,self.ai_fraction,unit_exp,self.city_name,unit_name)
                unit_class = '1'
                specialization_icon_path = None
                unit_attack = 0
                unit_defense = 0
                unit_durability = 0
                unit_morale = 100
                unit_type = 'infantry'
                try:
                    try:
                        self.cursor.execute(
                            "SELECT unit_class, attack, defense, durability, morale, unit_type FROM units WHERE unit_name = ?",
                            (unit_name,)
                        )
                    except Exception:
                        self.cursor.execute(
                            "SELECT unit_class, attack, defense, durability FROM units WHERE unit_name = ?",
                            (unit_name,)
                        )
                    unit_info = self.cursor.fetchone()
                    if unit_info:
                        unit_class = str(unit_info[0])
                        attack, defense = unit_info[1], unit_info[2]
                        unit_attack = attack
                        unit_defense = defense
                        unit_durability = unit_info[3] if unit_info[3] else 0
                        _raw_morale = unit_info[4] if len(unit_info) > 4 and unit_info[4] is not None else 100
                        # Без героя в гарнизоне: -30 мораль
                        unit_morale = max(0, _raw_morale - 30) if not _has_hero_in_garrison else _raw_morale
                        unit_type = unit_info[5] if len(unit_info) > 5 and unit_info[5] else 'infantry'
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
                # Тонкая акцентная обводка для карточки
                _card_border_alpha = 0.45 if unit_class in ('3', '4') else 0.20
                _card_border_clr = (
                    card_bg[0] * 1.8, card_bg[1] * 1.8, card_bg[2] * 1.8, _card_border_alpha
                )
                with card.canvas.before:
                    Color(*card_bg)
                    card._bg = RoundedRectangle(pos=card.pos, size=card.size, radius=[dp(10)])
                    Color(*_card_border_clr)
                    card._border = Line(
                        rounded_rectangle=(*card.pos, *card.size, dp(10)),
                        width=1.0
                    )
                card.bind(
                    pos=lambda i, v: (setattr(i._bg, 'pos', v),
                                      setattr(i._border, 'rounded_rectangle', (*v, *i.size, dp(10)))),
                    size=lambda i, v: (setattr(i._bg, 'size', v),
                                       setattr(i._border, 'rounded_rectangle', (*i.pos, *v, dp(10))))
                )

                # Изображение юнита
                from otherworld_themes import asset_exists
                img_src = unit_image if unit_image and asset_exists(unit_image) else ''
                from strategy_ui import frame
                frame(card, (0.36, 0.43, 0.51, 1) if unit_class == '1' else (0.76, 0.60, 0.34, 1))
                img_size = dp(56) if unit_class == '1' else dp(64)
                unit_img = Image(
                    source=img_src, size_hint=(None, None),
                    size=(img_size, img_size),
                    pos_hint={'center_y': 0.5},
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

                # Количество + опыт (только для класса 1)
                if unit_class == '1':
                    cnt_lbl = Label(
                        text=f'[color=#FFD700]{format_number(unit_count)}[/color] бойцов',
                        markup=True, font_size=sp(11), color=(0.80, 0.80, 0.80, 1),
                        halign='left', valign='middle', size_hint_y=None, height=dp(18)
                    )
                    cnt_lbl.bind(size=lambda i, s: setattr(i, 'text_size', (s[0], None)))
                    info.add_widget(cnt_lbl)

                    # Уровень опыта
                    if _rank_exp >= 7:
                        rank_text = f"[color=#FF4444]Элита[/color] (+25%) [{unit_exp} побед]"
                    elif _rank_exp >= 3:
                        rank_text = f"[color=#FFD700]Ветеран[/color] (+15%) [{unit_exp} побед]"
                    elif _rank_exp >= 1:
                        rank_text = f"[color=#88CCFF]Воин[/color] (+5%) [{unit_exp} побед]"
                    else:
                        rank_text = "[color=#888888]Новобранец[/color]"
                    if _unit_exp_mult>1.25:
                        rank_text += ' [color=#66CC66]ещё +15%[/color]'
                    exp_lbl = Label(
                        text=rank_text, markup=True,
                        font_size=sp(10), halign='left', valign='middle',
                        size_hint_y=None, height=dp(16)
                    )
                    exp_lbl.bind(size=lambda i, s: setattr(i, 'text_size', (s[0], None)))
                    info.add_widget(exp_lbl)

                card.add_widget(info)

                # Бонус фракции — справа в карточке (с учётом опыта)
                if unit_class == '1':
                    # Множитель опыта
                    _exp_mult = _unit_exp_mult

                    from utils.faction_bonuses import combat_multiplier, combat_bonus_status
                    _faction_mult = combat_multiplier(self.ai_fraction, self.conn)
                    _bonus_name, _bonus_active, _, _bonus_power = combat_bonus_status(
                        self.ai_fraction, unit_attack, unit_defense, unit_durability,
                        (_hero_bonus_atk, _hero_bonus_def, _hero_bonus_dur))
                    unit_profile=profiles.get(unit_name)
                    if unit_profile:
                        _bonus_name=unit_profile['bonus_name']
                        _bonus_active=unit_profile['bonus_active']
                    _faction_bonus_text = None
                    if _bonus_name:
                        if _bonus_active:
                            effective_power=(unit_profile['attack'] if _bonus_name=='Шквал' else unit_profile['defense']) if unit_profile else _bonus_power*_faction_mult*_exp_mult
                            _faction_bonus_text = f'[color=#66CC66]{_bonus_name}\nПрименяется\n{format_number(effective_power)}[/color]'
                        else:
                            _faction_bonus_text = f'[color=#999999]{_bonus_name}\nНе применяется[/color]'
                    if _faction_bonus_text:
                        _fb_lbl = Label(
                            text=_faction_bonus_text, markup=True,
                            font_size=sp(9), halign='center', valign='middle',
                            size_hint=(None, 1), width=dp(100)
                        )
                        _fb_lbl.bind(size=lambda i, s: setattr(i, 'text_size', (s[0], None)))
                        card.add_widget(_fb_lbl)

                # Иконка специализации для героев
                if unit_class in ('2', '3') and specialization_icon_path:
                    if os.path.exists(specialization_icon_path):
                        card.add_widget(Image(
                            source=specialization_icon_path,
                            size_hint=(None, None), size=(dp(40), dp(40)),
                            pos_hint={'center_y': 0.5},
                            allow_stretch=True, keep_ratio=True, mipmap=True
                        ))

                # Обработчик нажатия — показать статы и изображение юнита
                _u_name = unit_name
                _u_atk = unit_attack
                _u_def = unit_defense
                _u_dur = unit_durability
                _u_cnt = unit_count
                _u_cls = unit_class
                _u_img = unit_image

                _hba = _hero_bonus_atk
                _hbd = _hero_bonus_def
                _hbdu = _hero_bonus_dur
                _uexp = unit_exp
                _umor = unit_morale
                _utype = unit_type
                _uspirit = _has_battle_spirit

                def _on_card_touch(instance, touch, n=_u_name, a=_u_atk,
                                   d=_u_def, dur=_u_dur, cnt=_u_cnt, cls=_u_cls, img=_u_img,
                                   hba=_hba, hbd=_hbd, hbdu=_hbdu, uexp=_uexp, mor=_umor,
                                   utp=_utype, spirit=_uspirit):
                    if instance.collide_point(*touch.pos):
                        self._show_unit_stats_popup(n, a, d, dur, cnt, cls, img, hba, hbd, hbdu, uexp, mor, utp, spirit)
                        return True
                    return False

                from strategy_ui import bind_row_tap
                bind_row_tap(card, _on_card_touch)

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

    def _show_unit_stats_popup(self, name, attack, defense, durability, count, unit_class, unit_image='',
                               hero_bonus_atk=0, hero_bonus_def=0, hero_bonus_dur=0, unit_exp=0,
                               morale=100, unit_type='infantry', battle_spirit=False):
        """Попап с изображением юнита справа и характеристиками слева."""
        _is_mobile = platform in ('android', 'ios')
        class_labels = {'1': '', '2': 'Герой', '3': 'Чемпион', '4': 'Легенда'}
        cls_text = class_labels.get(unit_class, '')
        title = f"{name}  {cls_text}" if cls_text else name

        # Главный контейнер (вертикальный: верх — контент, низ — кнопка)
        content = BoxLayout(
            orientation='vertical', spacing=dp(6),
            padding=[dp(4), dp(4), dp(4), dp(4)]
        )
        content._responsive_keep_geometry = True
        with content.canvas.before:
            Color(0.06, 0.07, 0.11, 1)
            content._bg = Rectangle(pos=content.pos, size=content.size)
        content.bind(
            pos=lambda i, v: setattr(i._bg, 'pos', v),
            size=lambda i, v: setattr(i._bg, 'size', v)
        )

        # Горизонтальный контейнер: статы слева, изображение справа
        body = BoxLayout(orientation='horizontal', spacing=dp(8), size_hint=(1, 1))

        # === Левая часть: характеристики (заполняет всю высоту) ===
        _cnt = max(count, 1)
        from monster_sites import experience_multiplier
        _has_hero = unit_class == '1' and (hero_bonus_atk > 0 or hero_bonus_def > 0 or hero_bonus_dur > 0)
        if unit_class == '1':
            _eff_atk = attack + hero_bonus_atk
            _eff_def = defense + hero_bonus_def
            _eff_dur = durability + hero_bonus_dur
            # Множитель опыта
            _exp_m = experience_multiplier(self.conn,self.ai_fraction,unit_exp,self.city_name,name)
            from utils.faction_bonuses import combat_multiplier
            _faction_mult = combat_multiplier(self.ai_fraction, self.conn)
            _shkval_active = self.ai_fraction == 'Север' and attack > 0 and _eff_atk / attack >= 20
            # Север: Шквал — текущий сезонный множитель при пороге x20.
            if _shkval_active:
                _eff_atk = int(_eff_atk * _faction_mult * _exp_m)
            elif _exp_m > 1.0:
                _eff_atk = int(_eff_atk * _exp_m)
            # Адепты: Оплот — если защита увеличена в 20+ раз, +55% с сезонным усилением
            from utils.faction_bonuses import combat_bonus_status
            _oplot_name, _oplot_active, _, _combat_def = combat_bonus_status(
                self.ai_fraction, attack, defense, durability,
                (hero_bonus_atk, hero_bonus_def, hero_bonus_dur))
            if _oplot_name == 'Оплот' and _oplot_active:
                _eff_def = int(_combat_def * _faction_mult * _exp_m)
            elif _exp_m > 1.0:
                _eff_def = int(_eff_def * _exp_m)
            if _has_hero:
                if _shkval_active:
                    _atk_text = f'Шквал: {format_number(_eff_atk)} × {format_number(_cnt)} = {format_number(_eff_atk * _cnt)}'
                else:
                    _atk_text = f'({format_number(attack)}+{format_number(hero_bonus_atk)}) × {format_number(_cnt)} = {format_number(_eff_atk * _cnt)}'
                if _oplot_name == 'Оплот' and _oplot_active:
                    _def_text = f'Оплот: {format_number(_eff_def)} × {format_number(_cnt)} = {format_number(_eff_def * _cnt)} (с ½ живучести)'
                else:
                    _def_text = f'({format_number(defense)}+{format_number(hero_bonus_def)}) × {format_number(_cnt)} = {format_number(_eff_def * _cnt)}'
                _dur_text = f'({format_number(durability)}+{format_number(hero_bonus_dur)}) × {format_number(_cnt)} = {format_number(_eff_dur * _cnt)}'
            else:
                _atk_text = f'{format_number(_eff_atk)} × {format_number(_cnt)} = {format_number(_eff_atk * _cnt)}'
                _def_text = f'{format_number(_eff_def)} × {format_number(_cnt)} = {format_number(_eff_def * _cnt)}'
                _dur_text = f'{format_number(durability)} × {format_number(_cnt)} = {format_number(durability * _cnt)}'
        else:
            _atk_text = format_number(attack)
            _def_text = format_number(defense)
            _dur_text = format_number(durability)

        unit_profile=None
        if unit_class=='1':
            from utils.garrison_stats import garrison_profiles
            unit_profile=garrison_profiles(self.conn,self.city_name).get(name)
            if unit_profile:
                _atk_text=f'{format_number(unit_profile["attack"])} × {format_number(_cnt)} = {format_number(unit_profile["attack"]*_cnt)}'
                _def_text=f'{format_number(unit_profile["defense"])} × {format_number(_cnt)} = {format_number(unit_profile["defense"]*_cnt)} (с ½ живучести)'

        # Цвет морали: зелёный ≥50, красный <50
        if morale >= 50:
            _morale_text = f'[color=#66CC66]{morale}[/color]'
        else:
            _morale_text = f'[color=#FF6644]{morale}[/color]'
        # Русские названия типов
        _TYPE_NAMES = {
            'infantry': 'Пехота',
            'cavalry': 'Рыцари',
            'archer': 'Охотники',
            'mage': 'Маги',
            'beast': 'Бестии',
            'siege': 'Восставшие',
        }
        _type_name = _TYPE_NAMES.get(unit_type, unit_type)
        _TYPE_ADVANTAGES = {
            'infantry': {'strong': ['archer', 'mage'], 'weak': ['cavalry', 'beast']},
            'cavalry':  {'strong': ['infantry', 'beast'], 'weak': ['archer', 'mage']},
            'archer':   {'strong': ['cavalry', 'mage'], 'weak': ['infantry', 'beast']},
            'mage':     {'strong': ['cavalry', 'beast'], 'weak': ['infantry', 'archer']},
            'beast':    {'strong': ['infantry', 'archer'], 'weak': ['cavalry', 'mage']},
            'siege':    {'strong': ['infantry', 'cavalry', 'archer', 'mage', 'beast'], 'weak': []},
        }
        _adv = _TYPE_ADVANTAGES.get(unit_type, {'strong': [], 'weak': []})
        _strong_text = ', '.join(_TYPE_NAMES.get(t, t) for t in _adv['strong']) or '—'
        _weak_text = ', '.join(_TYPE_NAMES.get(t, t) for t in _adv['weak']) or '—'

        if unit_class == '1':
            stats_icons = [
                ('Урон',       'files/pict/hire/sword.png',  _atk_text),
                ('Защита',     'files/pict/hire/shield.png', _def_text),
                ('Тип',        'files/pict/hire/type.png',   _type_name),
                ('Силён',      'files/pict/hire/strong.png', f'[color=#66CC66]{_strong_text}[/color]'),
                ('Слаб',       'files/pict/hire/weak.png',   f'[color=#FF6644]{_weak_text}[/color]'),
                ('Мораль',     'files/pict/hire/moral.png',  _morale_text),
            ]
            if battle_spirit:
                stats_icons.append(('Дух', 'files/pict/hire/strong.png', '[color=#FFD700]+15% урон[/color]'))
        else:
            stats_icons = [
                ('Урон',       'files/pict/hire/sword.png',  _atk_text),
                ('Защита',     'files/pict/hire/shield.png', _def_text),
                ('Живучесть',  'files/pict/hire/health.png', _dur_text),
                ('Класс',      'files/pict/hire/class.png',  unit_class),
            ]

        if unit_class == '1':
            from monster_sites import progress
            from city_war import current_turn
            training_left = progress(self.conn,self.ai_fraction)['veteran_until']-current_turn(self.conn)
            if training_left>0:
                training_status='Элита: ещё +15%' if _exp_m>1.25 else 'Применяется'
                stats_icons.append(('Ветеранство','files/pict/hire/strong.png',
                                    f'[color=#66CC66]{training_status}, ещё {training_left} х.[/color]'))
            from utils.faction_bonuses import combat_bonus_status, combat_multiplier
            name, active, _, _ = combat_bonus_status(
                self.ai_fraction, attack, defense, durability,
                (hero_bonus_atk, hero_bonus_def, hero_bonus_dur))
            if unit_profile:
                name,active=unit_profile['bonus_name'],unit_profile['bonus_active']
            if name:
                status = 'Применяется' if active else 'Не применяется'
                color = '66CC66' if active else '999999'
                mult = combat_multiplier(self.ai_fraction, self.conn) if active else 1
                stats_icons.append((name, 'files/pict/hire/strong.png',
                                    f'[color=#{color}]{status} (×{mult:g})[/color]'))

        from utils.city_terrain import defense_multiplier
        terrain_defense = defense_multiplier(self.conn,self.city_name)
        if terrain_defense>1:
            stats_icons.append(('Высота','files/pict/hire/shield.png',
                                '[color=#66CC66]+30% к боевой защите гарнизона[/color]'))
        elif terrain_defense<1:
            stats_icons.append(('Низина','files/pict/hire/shield.png',
                                '[color=#FF6644]−20% к боевой защите гарнизона[/color]'))

        from unit_stats_ui import UnitStatsPanel
        stats_panel = UnitStatsPanel(stats_icons, hero=unit_class != '1', size_hint_x=.55)
        body.add_widget(stats_panel)

        from otherworld_themes import asset_exists
        if unit_image and asset_exists(unit_image):
            img = Image(
                source=unit_image,
                allow_stretch=True, keep_ratio=True,
                size_hint_x=0.45,
            )
            from portrait_ui import style_portrait_image
            style_portrait_image(img, enabled=True)
            body.add_widget(img)

            def fit_card(*_):
                stacked = body.height > body.width
                body.orientation = 'vertical' if stacked else 'horizontal'
                stats_panel.size_hint = (1, .55) if stacked else (.55, 1)
                img.size_hint = (1, .45) if stacked else (.45, 1)

            body.bind(size=fit_card)
            fit_card()

        content.add_widget(body)

        popup = Popup(
            title=title,
            content=content,
            size_hint=(0.96, 0.96),
            background_color=(0.04, 0.05, 0.09, 0.98),
            separator_color=(0.3, 0.55, 0.9, 0.4),
            title_color=(0.95, 0.90, 0.70, 1),
            title_size=sp(16) if _is_mobile else sp(18),
            title_align='center'
        )
        popup.open()

    def show_warning_popup(self):
        _is_mobile = platform in ('android', 'ios')
        popup = Popup(
            title="Внимание!",
            size_hint=(0.85 if _is_mobile else 0.55, 0.38 if _is_mobile else 0.28),
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

            # Проверяем, не отрезан ли город от основной территории
            from game_process import _active_game_screen
            if _active_game_screen and hasattr(_active_game_screen, 'game_state_manager'):
                faction_obj = _active_game_screen.game_state_manager.faction
                supplied = faction_obj._get_supplied_cities()
                if self.city_name not in supplied:
                    show_popup_message("Отрезан от снабжения",
                                       f"Город {self.city_name} отрезан от основной территории.\n"
                                       f"Восстановите сообщение через дороги.")
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

            from army_deployment_ui import show_army_reserve
            show_army_reserve(self, army_data)

        except sqlite3.Error as e:
            show_popup_message("Ошибка", f"Произошла ошибка при работе с базой данных (place_army): {e}")
        except Exception as e:
            show_popup_message("Ошибка", f"Произошла ошибка: {e}")

    def add_to_garrison_with_slider(self, unit_data, name_label):
        from army_deployment_ui import show_deployment_quantity
        return show_deployment_quantity(self, unit_data)

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
        Элины получают 2 перемещения за ход, остальные — 1.
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS turn_check_move (
                    faction TEXT PRIMARY KEY,
                    can_move BOOLEAN,
                    moves_left INTEGER DEFAULT 1
                )
            """)
            # Миграция: добавляем moves_left если нет
            try:
                cursor.execute("ALTER TABLE turn_check_move ADD COLUMN moves_left INTEGER DEFAULT 1")
            except sqlite3.OperationalError:
                pass
            self.conn.commit()

            moves = 2 if self.player_fraction == 'Элины' else 1
            cursor.execute("SELECT faction FROM turn_check_move WHERE faction = ?", (self.player_fraction,))
            result = cursor.fetchone()
            if not result:
                cursor.execute(
                    "INSERT INTO turn_check_move (faction, can_move, moves_left) VALUES (?, ?, ?)",
                    (self.player_fraction, True, moves)
                )
            else:
                cursor.execute(
                    "UPDATE turn_check_move SET can_move = ?, moves_left = ? WHERE faction = ?",
                    (True, moves, self.player_fraction)
                )
            self.conn.commit()
        except sqlite3.Error as e:
            print(f"Ошибка при инициализации turn_check_move: {e}")



    def move_selected_group_to_city(self, instance=None):
        """Перемещает выбранную группу юнитов в город."""
        from troop_movement import movement_busy
        if movement_busy(self) and not getattr(self, '_movement_arrived', False):
            return
        if not self.selected_group:
            show_popup_message("Ошибка", "Группа пуста. Добавьте юниты перед перемещением.")
            return

        deferred = False
        try:
            current_player_kingdom = self.player_fraction
            cursor = self.conn.cursor()

            # Миграция: добавляем moves_left если нет
            try:
                cursor.execute("ALTER TABLE turn_check_move ADD COLUMN moves_left INTEGER DEFAULT 1")
                self.conn.commit()
            except Exception:
                pass

            # Проверяем moves_left — единый счётчик перемещений
            cursor.execute(
                "SELECT moves_left FROM turn_check_move WHERE faction = ?",
                (current_player_kingdom,)
            )
            _ml_row = cursor.fetchone()
            if not _ml_row:
                # Нет записи — создаём (Элины: 2, остальные: 1)
                _init_moves = 2 if current_player_kingdom == 'Элины' else 1
                cursor.execute(
                    "INSERT INTO turn_check_move (faction, can_move, moves_left) VALUES (?, ?, ?)",
                    (current_player_kingdom, True, _init_moves)
                )
                self.conn.commit()
                print(f"[MOVE CHECK] Создана запись для {current_player_kingdom}, moves_left={_init_moves}")
            else:
                _moves_left = _ml_row[0] if _ml_row[0] is not None else 0
                print(f"[MOVE CHECK] {current_player_kingdom} moves_left={_moves_left}")
                if _moves_left <= 0:
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

            from utils.movement_rules import reachable_source_cities
            reachable = reachable_source_cities(self.conn, self.city_name, current_player_kingdom)
            for unit in self.selected_group:
                source_city = unit.get('city_name')
                if not source_city or source_city not in reachable:
                    show_popup_message('Нет дороги',
                                       f'Из города {source_city or "—"} нельзя достичь {self.city_name}.')
                    return

            # Группируем юниты по их исходным городам
            grouped_by_city = defaultdict(lambda: defaultdict(int))
            for unit in self.selected_group:
                city = unit["city_name"]
                name = unit["unit_name"]
                count = unit["unit_count"]
                grouped_by_city[city][name] += count

            # Перемещаем по каждому городу отдельно
            # Arrival revalidates the whole command before moving any stack.
            for source_city, units in grouped_by_city.items():
                for unit_name, total_count in units.items():
                    cursor.execute('SELECT unit_count FROM garrisons WHERE city_name=? AND unit_name=?',
                                   (source_city, unit_name))
                    available = cursor.fetchone()
                    if not available or total_count <= 0 or available[0] < total_count:
                        show_popup_message('Недостаточно войск',
                                           f'В городе {source_city} недостаточно юнитов {unit_name}.')
                        return
            if not getattr(self, '_movement_arrived', False):
                from terrain_journeys import route_stops, start_journey
                from utils.movement_rules import movement_city_route
                terrain_sources = {source for source in grouped_by_city if route_stops(
                    self.conn,movement_city_route(self.conn,source,self.city_name,current_player_kingdom))}
                if terrain_sources:
                    if (destination_owner not in (current_player_kingdom,'Нейтрал') and not is_war_destination
                            and not self.is_ally(current_player_kingdom,destination_owner)):
                        raise ValueError('Сначала объявите войну владельцу этого города.')
                    if destination_owner == 'Нейтрал':
                        cursor.execute('SELECT COALESCE(is_undead,0) FROM cities WHERE name=?',(self.city_name,))
                        hidden = cursor.fetchone()
                        if hidden and hidden[0]:
                            from undead_invasion import is_invasion_active
                            if not is_invasion_active(self.conn):
                                raise ValueError('Эти земли недоступны до начала вторжения нежити.')
                    for source, units in grouped_by_city.items():
                        selected = [dict(unit_name=name,unit_count=count) for name,count in units.items()]
                        if source in terrain_sources:
                            mode = 'gift' if getattr(self,'_ally_transfer_mode','control') == 'transfer' else 'move'
                            start_journey(self.conn,current_player_kingdom,source,self.city_name,selected,mode)
                        else:
                            from troop_movement import queue_ai_march
                            queue_ai_march(self.conn,current_player_kingdom,source,self.city_name,selected)
                            for unit in selected:
                                if not self.transfer_troops_between_cities(source,self.city_name,unit['unit_name'],
                                        unit['unit_count'],attacking_units=[u for u in self.selected_group if u['city_name']==source]):
                                    raise ValueError('Не удалось отправить часть группы.')
                                if is_war_destination:
                                    break
                    cursor.execute('UPDATE turn_check_move SET moves_left=MAX(0,moves_left-1) WHERE faction=?',
                                   (current_player_kingdom,))
                    self.conn.commit()
                    from troop_movement import close_transfer_windows
                    close_transfer_windows(self)
                    from game_process import _active_game_screen, refresh_map
                    from troop_movement import play_ai_marches
                    refresh_map()
                    if _active_game_screen:
                        play_ai_marches(_active_game_screen)
                    return
                from troop_movement import animate_transfer
                if animate_transfer(self, grouped_by_city):
                    deferred = True
                    return
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

            # Фиксируем одно использование перемещения (один раз за всю группу)
            cursor.execute(
                "UPDATE turn_check_move SET moves_left = MAX(0, moves_left - 1) WHERE faction = ?",
                (current_player_kingdom,)
            )
            self.conn.commit()

            # Закрываем попап и обновляем интерфейс
            from troop_movement import close_transfer_windows
            close_transfer_windows(self)

        except Exception as e:
            show_popup_message("Ошибка", f"Произошла ошибка при перемещении группы: {e}")

        finally:
            if not deferred:
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

            # Selection and execution use the same route rules, including allied targets.
            from utils.movement_rules import can_move_between_cities
            if not can_move_between_cities(self.conn, source_fortress_name,
                                           destination_fortress_name, self.player_fraction):
                show_popup_message('Нет дороги',
                                   f'Нет доступного пути из {source_fortress_name} в {destination_fortress_name}.')
                return False

            current_player_kingdom = self.player_fraction

            # 1) Сценарий: войска в своём городе
            if source_owner == current_player_kingdom:

                # Свой город — просто перемещаем
                if destination_owner == current_player_kingdom:
                    self.move_troops(source_fortress_name, destination_fortress_name, unit_name, taken_count)
                    return True

                # Город союзника — выбор уже сделан в _show_ally_transfer_choice
                if self.is_ally(current_player_kingdom, destination_owner):
                    _mode = getattr(self, '_ally_transfer_mode', 'control')
                    if _mode == 'transfer':
                        # Передаём союзнику — конвертируем в его юнит 1 класса
                        try:
                            cursor.execute(
                                "UPDATE garrisons SET unit_count = unit_count - ? WHERE city_name = ? AND unit_name = ?",
                                (taken_count, source_fortress_name, unit_name))
                            cursor.execute("DELETE FROM garrisons WHERE unit_count <= 0")
                            cursor.execute(
                                "SELECT unit_name, image_path FROM units WHERE faction = ? AND unit_class = '1' LIMIT 1",
                                (destination_owner,))
                            _ally_unit = cursor.fetchone()
                            if _ally_unit:
                                _ally_name, _ally_img = _ally_unit
                                cursor.execute("""
                                    INSERT INTO garrisons (city_name, unit_name, unit_count, unit_image)
                                    VALUES (?, ?, ?, ?)
                                    ON CONFLICT(city_name, unit_name) DO UPDATE SET unit_count = unit_count + ?
                                """, (destination_fortress_name, _ally_name, taken_count, _ally_img or '', taken_count))
                            self.conn.commit()
                            try:
                                from game_process import _active_game_screen
                                gs = _active_game_screen
                                if gs and hasattr(gs, 'faction'):
                                    gs.faction.load_resources_from_db()
                                    gs.faction.calculate_and_deduct_consumption()
                                    gs.faction._sync_resources()
                                    gs.faction.save_resources_to_db()
                                    if hasattr(gs, 'resource_box'):
                                        gs.resource_box.update_resources()
                            except Exception as _e:
                                print(f"[ALLY TRANSFER] Ошибка пересчёта: {_e}")
                            show_popup_message("Передача", f"{taken_count} юнитов передано фракции {destination_owner}")
                        except Exception as e:
                            print(f"[ALLY TRANSFER] Ошибка: {e}")
                    else:
                        # Под контролем игрока — просто перемещаем
                        self.move_troops(source_fortress_name, destination_fortress_name, unit_name, taken_count)
                    return True

                # Нейтральный город — захват без боя (кроме скрытых городов нежити до инвазии)
                elif dest_kingdom == "Нейтрал":
                    cursor.execute("SELECT COALESCE(is_undead, 0) FROM cities WHERE name = ?",
                                   (destination_fortress_name,))
                    undead_row = cursor.fetchone()
                    if undead_row and undead_row[0]:
                        from undead_invasion import is_invasion_active
                        if not is_invasion_active(self.conn):
                            show_popup_message("Невозможно", "У этого места дурная слава, наши воины не полезут сюда без острой необходимости.")
                            return False
                    self.capture_city(destination_fortress_name, current_player_kingdom, self.selected_group)
                    return True

                # Вражеский город — начинаем атаку
                relationship = self.get_relationship(current_player_kingdom, destination_owner)

                if relationship == "война":
                    # moves_left проверяется и уменьшается в move_selected_group_to_city

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


            # 2) Сценарий: войска в городе союзника — те же правила что из своего города
            elif self.is_ally(current_player_kingdom, source_owner):

                # К себе или к союзнику — просто перемещаем
                if (destination_owner == current_player_kingdom or
                        self.is_ally(current_player_kingdom, destination_owner)):
                    self.move_troops(source_fortress_name, destination_fortress_name, unit_name, taken_count)
                    return True

                # Нейтральный город — захват
                elif dest_kingdom == "Нейтрал":
                    cursor.execute("SELECT COALESCE(is_undead, 0) FROM cities WHERE name = ?",
                                   (destination_fortress_name,))
                    undead_row = cursor.fetchone()
                    if undead_row and undead_row[0]:
                        from undead_invasion import is_invasion_active
                        if not is_invasion_active(self.conn):
                            show_popup_message("Невозможно", "У этого места дурная слава, наши воины не полезут сюда без острой необходимости.")
                            return False
                    self.capture_city(destination_fortress_name, current_player_kingdom, self.selected_group)
                    return True

                # Вражеский город — атака
                else:
                    relationship = self.get_relationship(current_player_kingdom, destination_owner)
                    if relationship == "война":
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
                        show_popup_message("Нет дороги", "Нет дороги к этому городу.")
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
            from monster_sites import copy_training
            copy_training(self.conn,source_fortress_name,destination_fortress_name,unit_name)
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
            refresh_map()
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
                    # Определяем фракцию юнитов для захвата
                    _cap_factions = {}
                    for _cu in attacking_units:
                        try:
                            cursor.execute("SELECT faction FROM units WHERE unit_name = ?", (_cu.get('unit_name', ''),))
                            _cf = cursor.fetchone()
                            if _cf:
                                _cap_factions[_cf[0]] = _cap_factions.get(_cf[0], 0) + _cu.get('unit_count', 0)
                        except Exception:
                            pass
                    _cap_owner = list(_cap_factions.keys())[0] if len(_cap_factions) == 1 else source_owner
                    self.capture_city(destination_fortress_name, _cap_owner, attacking_units)
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

                # Определяем фракцию атакующих юнитов (может отличаться от владельца города)
                _atk_factions = {}
                for u in attacking_army:
                    try:
                        cursor.execute("SELECT faction FROM units WHERE unit_name = ?", (u['unit_name'],))
                        _uf_row = cursor.fetchone()
                        if _uf_row:
                            _uf = _uf_row[0]
                            _atk_factions[_uf] = _atk_factions.get(_uf, 0) + u['unit_count']
                    except Exception:
                        pass
                if len(_atk_factions) == 1:
                    _actual_atk_fraction = list(_atk_factions.keys())[0]
                else:
                    _actual_atk_fraction = source_owner

                # Запускаем сам бой
                result = fight(
                    attacking_city=source_fortress_name,
                    defending_city=destination_fortress_name,
                    defending_army=defending_army,
                    attacking_army=attacking_army,
                    attacking_fraction=_actual_atk_fraction,
                    defending_fraction=destination_owner,
                    conn=self.conn
                )
                self.close_current_popup()
                refresh_map()  # Моментальное обновление карты


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

                from city_war import record_capture
                record_capture(self.conn, city_name, new_owner)

            self.update_garrison()
            # Обновляем количество городов и лимит армии
            from game_process import _active_game_screen
            if _active_game_screen:
                _active_game_screen.faction.load_cities()
                _active_game_screen.faction._sync_resources()
            refresh_map()

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

                # Обновляем отображение гарнизона и карту
                self.update_garrison()
                self.close_current_popup()
                refresh_map()

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


from ui_components import show_message as show_popup_message
from utils.helpers import format_number
from game_process import refresh_map



