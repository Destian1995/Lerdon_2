
from db_lerdon_connect import *
from economic import format_number


PRIMARY_COLOR = get_color_from_hex('#2E7D32')
SECONDARY_COLOR = get_color_from_hex('#388E3C')
BACKGROUND_COLOR = get_color_from_hex('#212121')
TEXT_COLOR = get_color_from_hex('#FFFFFF')
INPUT_BACKGROUND = get_color_from_hex('#FFFFFF')

class ArmyButton(Button):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.background_normal = ''
        self.background_color = (0,0,0,0)
        self.color = TEXT_COLOR
        self.font_size = dp(18)
        self.bold = True
        self.size_hint = (1, None)
        self.height = dp(60)
        self.padding = (dp(20), dp(10))

        with self.canvas.before:
            Color(*PRIMARY_COLOR)
            self.rect = RoundedRectangle(
                radius=[dp(15)],
                pos=self.pos,
                size=self.size
            )

        self.bind(pos=self.update_rect, size=self.update_rect)

    def update_rect(self, *args):
        self.rect.pos = self.pos
        self.rect.size = self.size

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            Animation(background_color=(*SECONDARY_COLOR, 1), d=0.1).start(self)
        return super().on_touch_down(touch)

    def on_touch_up(self, touch):
        Animation(background_color=(*PRIMARY_COLOR, 1), d=0.2).start(self)
        return super().on_touch_up(touch)

class ArmyCash:
    def __init__(self, faction, class_faction, conn):
        """
        Инициализация класса ArmyCash.
        :param faction: Название фракции.
        :param class_faction: Экземпляр класса Faction (экономический модуль).
        """
        self.faction = faction
        self.class_faction = class_faction  # Экономический модуль
        self.conn = conn  # Подключение к
        self.cursor = self.conn.cursor()
        self.resources = self.load_resources()  # Загрузка начальных ресурсов

    def load_resources(self):
        """
        Загружает текущие ресурсы фракции из базы данных.
        """
        try:
            rows = self.load_data("resources", ["resource_type", "amount"], "faction = ?", (self.faction,))
            resources = {"Кроны": 0, "Рабочие": 0}
            for resource_type, amount in rows:
                if resource_type in resources:
                    resources[resource_type] = amount

            # Отладочный вывод: загруженные ресурсы
            print(f"[DEBUG] Загружены ресурсы для фракции '{self.faction}': {resources}")
            return resources
        except sqlite3.Error as e:
            print(f"Ошибка при загрузке ресурсов: {e}")
            return {"Кроны": 0, "Рабочие": 0}

    def load_data(self, table, columns, condition=None, params=None):
        """
        Универсальный метод для загрузки данных из таблицы базы данных.
        """
        try:
            query = f"SELECT {', '.join(columns)} FROM {table}"
            if condition:
                query += f" WHERE {condition}"
            self.cursor.execute(query, params or ())
            result = self.cursor.fetchall()

            # Отладочный вывод: SQL-запрос и результат
            print(f"[DEBUG] SQL-запрос: {query}, параметры: {params}")
            print(f"[DEBUG] Результат запроса: {result}")

            return result
        except sqlite3.Error as e:
            print(f"Ошибка при загрузке данных из таблицы {table}: {e}")
            return []

    def deduct_resources(self, crowns, workers):
        """
        Списывает ресурсы через экономический модуль.

        :param crowns: Количество крон для списания.
        :param workers: Количество рабочих для списания.
        :return: True, если ресурсы успешно списаны; False, если недостаточно ресурсов.
        """
        try:
            # Проверяем доступность ресурсов через экономический модуль
            current_crowns = self.class_faction.get_resource_now("Кроны")
            current_workers = self.class_faction.get_resource_now("Рабочие")

            print(f"[DEBUG] Текущие ресурсы: Кроны={current_crowns}, Рабочие={current_workers}")

            if current_crowns < crowns or current_workers < workers:
                print("[DEBUG] Недостаточно ресурсов для списания.")
                return False

            # Списываем ресурсы через экономический модуль
            self.class_faction.update_resource_now("Кроны", current_crowns - crowns)
            self.class_faction.update_resource_now("Рабочие", current_workers - workers)

            return True

        except Exception as e:
            print(f"Ошибка при списании ресурсов: {e}")
            return False

    def hire_unit(self, unit_name, unit_cost, quantity, unit_stats, unit_image):
        """
        Нанимает юнит (оружие), если ресурсов достаточно и соблюдены правила найма по классам.

        :param unit_name: Название юнита.
        :param unit_cost: Стоимость юнита в виде кортежа (кроны, рабочие).
        :param quantity: Количество нанимаемых юнитов.
        :param unit_stats: Характеристики юнита (должен быть словарём).
        :param unit_image: Путь к изображению юнита.
        :return: True, если найм успешен; False в противном случае.
        """
        crowns, workers = unit_cost
        required_crowns = int(crowns) * int(quantity)
        required_workers = int(workers) * int(quantity)

        # Проверка типа unit_stats
        if not isinstance(unit_stats, dict):
            print("[ERROR] unit_stats должен быть словарём!")
            return False

        # Получаем класс юнита
        try:
            unit_class_str = unit_stats.get("Класс юнита", "")
            unit_class = int(unit_class_str.split()[0])  # Например, "1 класс" -> 1
        except (ValueError, KeyError, IndexError):
            print(f"[ERROR] Не удалось определить класс юнита. Получено значение: '{unit_class_str}'")
            return False

        # --- Проверка ограничений по классу ДО списания ресурсов ---
        if unit_class == 1:
            # Класс 1 — можно нанимать всегда, без дополнительных проверок
            pass

        elif unit_class in [2, 3, 4]:
            # Герои: только один
            if quantity > 1:
                self.show_message(
                    title="Ошибка найма",
                    message=f"Можно нанять только одного героя {unit_class} класса."
                )
                return False

            # Проверяем, есть ли уже живой герой этого класса в armies
            try:
                # unit_class хранится в armies как строка вида "N класс"
                self.cursor.execute("""
                    SELECT 1
                    FROM armies
                    WHERE faction = ? AND unit_class LIKE ?
                    LIMIT 1
                """, (self.faction, f"{unit_class} %"))

                exists_in_armies = self.cursor.fetchone()

                # Проверка в garrisons через units (unit_class в units — целое число)
                self.cursor.execute("""
                    SELECT 1
                    FROM garrisons g
                    JOIN units u ON g.unit_name = u.unit_name
                    WHERE u.faction = ? AND CAST(u.unit_class AS INTEGER) = ?
                    LIMIT 1
                """, (self.faction, unit_class))

                exists_in_garrisons = self.cursor.fetchone()

                if exists_in_armies or exists_in_garrisons:
                    self.show_message(
                        title="Ошибка найма",
                        message=f"Герой {unit_class} класса уже существует у вашей фракции.\n"
                                f"Одновременно можно иметь только одного героя такого класса."
                    )
                    return False

            except sqlite3.Error as e:
                print(f"[ERROR] Ошибка при проверке существующего героя: {e}")
                return False

        else:
            self.show_message(
                title="Ошибка найма",
                message="Неизвестный класс юнита."
            )
            return False

        # Проверка наличия ресурсов (после всех проверок, чтобы не списывать при ошибке)
        if not self.deduct_resources(required_crowns, required_workers):
            self.show_message(
                title="Ошибка найма",
                message=f"Нанять юнитов невозможно: недостаточно ресурсов.\n"
                        f"Необходимые: {format_number(required_crowns)} крон и {format_number(required_workers)} рабочих."
            )
            return False

        # Добавление юнитов в базу данных
        self.add_or_update_army_unit(unit_name, quantity, unit_stats, unit_image)

        # Отображение сообщения об успехе
        self.show_message(
            title="Успех",
            message=f"{unit_name} нанят!\n"
                    f"Потрачено: {format_number(required_crowns)} крон и {format_number(required_workers)} рабочих."
        )

        return True

    def add_or_update_army_unit(self, unit_name, quantity, unit_stats, unit_image):
        """
        Добавляет или обновляет данные о юните в базе данных.
        """
        self.cursor.execute("""
            SELECT quantity, total_attack, total_defense, total_durability, unit_image
            FROM armies
            WHERE faction = ? AND unit_type = ?
        """, (self.faction, unit_name))
        result = self.cursor.fetchone()

        if result:
            # Если юнит уже существует, обновляем его данные
            current_quantity, total_attack, total_defense, total_durability, _ = result
            new_quantity = current_quantity + quantity
            self.cursor.execute("""
                UPDATE armies
                SET quantity = ?, total_attack = ?, total_defense = ?, total_durability = ?, unit_image = ?
                WHERE faction = ? AND unit_type = ?
            """, (
                new_quantity,
                total_attack + unit_stats["Урон"] * quantity,
                total_defense + unit_stats["Защита"] * quantity,
                total_durability + unit_stats["Живучесть"] * quantity,
                unit_image,  # Обновляем изображение
                self.faction,
                unit_name
            ))
        else:
            # Если юнит новый, добавляем его в базу
            self.cursor.execute("""
                INSERT INTO armies (faction, unit_type, quantity, total_attack, total_defense, total_durability, unit_class, unit_image)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                self.faction,
                unit_name,
                quantity,
                unit_stats["Урон"] * quantity,
                unit_stats["Защита"] * quantity,
                unit_stats["Живучесть"] * quantity,
                unit_stats["Класс юнита"],
                unit_image  # Добавляем изображение
            ))

        self.conn.commit()

    def hire_weapons(self, weapon_name, unit_cost, quantity):
        """
        Обновляет или создает запись в таблице weapons.
        :param unit_cost: кортеж, содержащий стоимость оружия в кронах и рабочих.
        """
        crowns, workers = unit_cost
        required_crowns = int(crowns) * int(quantity)
        required_workers = int(workers) * int(quantity)


        # Проверка наличия ресурсов
        if not self.deduct_resources(required_crowns, required_workers):
            self.show_message(
                title="Ошибка найма",
                message=f"Нанять юнитов невозможно: недостаточно ресурсов.\n"
                        f"Необходимые: {format_number(required_crowns)} крон и {format_number(required_workers)} рабочих."
            )
            return False
        return True

    def update_weapon_in_db(self, faction, weapon_name, quantity, damage, koef):
        """
        Обновляет или создает запись в таблице weapons.
        :param faction: Название фракции.
        :param weapon_name: Название оружия.
        :param quantity: Количество единиц оружия.
        :param damage: Урон оружия.
        :param koef: Коэффициент преодоления ПВО.
        """
        try:
            # Проверяем, существует ли запись для данного оружия
            self.cursor.execute('''
                SELECT quantity
                FROM weapons
                WHERE faction = ? AND weapon_name = ?
            ''', (faction, weapon_name))
            result = self.cursor.fetchone()

            if result:
                # Если запись существует, обновляем количество
                current_quantity = result[0]
                new_quantity = current_quantity + quantity
                self.cursor.execute('''
                    UPDATE weapons
                    SET quantity = ?, damage = ?, koef = ?
                    WHERE faction = ? AND weapon_name = ?
                ''', (new_quantity, damage, koef, faction, weapon_name))
            else:
                # Если запись отсутствует, создаем новую
                self.cursor.execute('''
                    INSERT INTO weapons (faction, weapon_name, quantity, damage, koef)
                    VALUES (?, ?, ?, ?, ?)
                ''', (faction, weapon_name, quantity, damage, koef))

            self.conn.commit()
            print(f"[DEBUG] Данные оружия '{weapon_name}' успешно обновлены в таблице weapons.")

        except sqlite3.Error as e:
            print(f"Ошибка при обновлении таблицы weapons: {e}")

    def show_message(self, title, message):
        # Определяем акцент по заголовку
        is_error = 'ошибк' in title.lower()
        acc = (0.72, 0.18, 0.18, 1) if is_error else (0.20, 0.55, 0.88, 1)
        sep = (0.78, 0.18, 0.18, 0.85) if is_error else (0.20, 0.55, 0.88, 0.7)
        title_clr = (1, 0.55, 0.55, 1) if is_error else (0.65, 0.88, 1, 1)

        content_layout = BoxLayout(
            orientation='vertical',
            padding=[dp(14), dp(10), dp(14), dp(12)],
            spacing=dp(10)
        )

        # Разделительная полоска-акцент вверху
        accent_bar = Widget(size_hint=(1, None), height=dp(3))
        with accent_bar.canvas:
            Color(*acc)
            accent_bar._r = RoundedRectangle(pos=accent_bar.pos, size=accent_bar.size, radius=[dp(2)])
        accent_bar.bind(pos=lambda i, v: setattr(i._r, 'pos', v),
                        size=lambda i, v: setattr(i._r, 'size', v))
        content_layout.add_widget(accent_bar)

        message_label = Label(
            text=message,
            color=(0.94, 0.94, 0.94, 1),
            font_size=sp(14),
            halign='center',
            valign='middle',
            markup=True
        )
        message_label.bind(size=message_label.setter('text_size'))
        content_layout.add_widget(message_label)

        close_button = Button(
            text="Закрыть",
            font_size=sp(14),
            size_hint_y=None,
            height=dp(40),
            background_color=(0, 0, 0, 0),
            color=(1, 1, 1, 1),
            bold=True
        )
        with close_button.canvas.before:
            close_button._bc = Color(*acc)
            close_button._br = RoundedRectangle(
                pos=close_button.pos, size=close_button.size, radius=[dp(10)]
            )
        close_button.bind(
            pos=lambda i, v: setattr(i._br, 'pos', v),
            size=lambda i, v: setattr(i._br, 'size', v)
        )
        content_layout.add_widget(close_button)

        _is_mobile = platform in ('android', 'ios')
        popup = Popup(
            title=title,
            content=content_layout,
            size_hint=(0.90 if _is_mobile else 0.78, 0.42 if _is_mobile else 0.34),
            auto_dismiss=False,
            background_color=(0.07, 0.08, 0.13, 1),
            separator_color=sep,
            title_color=title_clr,
            title_size=sp(17) if _is_mobile else sp(15),
            title_align='center'
        )
        close_button.bind(on_release=popup.dismiss)
        popup.open()


def load_unit_data(faction, conn):
    """Загружает данные о юнитах для выбранной фракции из базы данных."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT unit_name, consumption, cost_money, cost_time, image_path, attack, defense, durability, unit_class
        FROM units WHERE faction = ?
    """, (faction,))
    rows = cursor.fetchall()

    unit_data = {}
    for row in rows:
        unit_name, consumption, cost_money, cost_time, image_path, attack, defense, durability, unit_class = row
        unit_data[unit_name] = {
            "cost": [cost_money, cost_time],
            "image": image_path,
            "stats": {
                "Урон": attack,
                "Защита": defense,
                "Живучесть": durability,
                "Класс юнита": unit_class,
                "Потребление Кристаллов": consumption
            }
        }
    return unit_data


def start_army_mode(faction, game_area, class_faction, conn):
    army_hire = ArmyCash(faction, class_faction, conn)
    faction_colors = {
        "Север": (0.2, 0.4, 0.9, 0.8),
        "Эльфы": (0.2, 0.7, 0.3, 0.8),
        "Вампиры": (0.5, 0.2, 0.6, 0.8),
        "Адепты": (0, 0, 0, 0.8),
        "Элины": (0.6, 0.5, 0.1, 0.8),
    }
    bg_color = faction_colors.get(faction, (0.15, 0.15, 0.15, 1))
    main_box = BoxLayout(
        orientation='horizontal',
        size_hint=(1, 1),
        padding=dp(10),
        spacing=dp(5)
    )
    left_space = BoxLayout(size_hint=(0.3, 1))
    right_container = FloatLayout(size_hint=(1, 1))

    # Карусель
    carousel = Carousel(
        direction='right',
        size_hint=(1, 1),
        loop=True,
        scroll_distance=30,
        pos_hint={'top': 1.1, 'right': 1.06}
    )

    # Загрузка и сортировка юнитов
    unit_data = load_unit_data(faction, conn)
    sorted_units = sorted(
        unit_data.items(),
        key=lambda x: int(x[1]['stats']['Класс юнита'].split()[0])
    )

    # Создание слайдов
    for unit_name, unit_info in sorted_units:
        slide = BoxLayout(
            orientation='vertical',
            size_hint=(0.8, 0.8),
            spacing=dp(1),
            padding=dp(1)
        )
        card = BoxLayout(
            orientation='vertical',
            size_hint=(1, 1),
            spacing=dp(1),
            padding=dp(20)
        )

        # Фон карточки
        with card.canvas.before:
            Color(rgba=bg_color)
            shadow_rect = RoundedRectangle(size=card.size, radius=[dp(25)])
            Color(rgba=(0.05, 0.05, 0.05, 0))
            rect = RoundedRectangle(size=card.size, radius=[dp(20)])

        def update_bg(instance, rect=rect, shadow_rect=shadow_rect):
            rect.pos = instance.pos
            rect.size = instance.size
            shadow_rect.pos = (instance.x - dp(2), instance.y - dp(2))
            shadow_rect.size = instance.size

        card.bind(pos=update_bg, size=update_bg)

        unit_class = int(unit_info['stats']['Класс юнита'].split()[0])
        cost_money, cost_time = unit_info['cost']

        # ── Класс-специфичные цвета ──────────────────────────────────
        CLASS_ACCENT = {1: (0.20, 0.55, 0.88, 1), 2: (0.55, 0.20, 0.80, 1),
                        3: (0.85, 0.60, 0.10, 1), 4: (0.85, 0.15, 0.15, 1)}
        accent = CLASS_ACCENT.get(unit_class, (0.20, 0.55, 0.88, 1))

        # ── Тело: статы слева, картинка+название справа ─────────────
        body = BoxLayout(orientation='horizontal', size_hint=(1, 1), spacing=dp(4))

        stats_icons = [
            ('Урон',     'files/pict/hire/sword.png',       'Урон'),
            ('Защита',   'files/pict/hire/shield.png',      'Защита'),
            ('Живучесть','files/pict/hire/health.png',      'Живучесть'),
            ('Класс',    'files/pict/hire/class.png',       'Класс юнита'),
            ('Расход',   'files/pict/hire/consumption.png', 'Потребление Кристаллов'),
        ]
        stats_box = BoxLayout(orientation='vertical', size_hint=(0.42, 1),
                              spacing=dp(4), padding=[dp(6), dp(4)])
        for label, icon, key in stats_icons:
            row = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(26), spacing=dp(6))
            row.add_widget(Image(source=icon, size_hint=(None, None), size=(dp(22), dp(22)),
                                 allow_stretch=True, keep_ratio=True))
            val = unit_info['stats'].get(key, 0)
            if key in ('Урон', 'Защита', 'Живучесть', 'Потребление Кристаллов'):
                val = format_number(val)
            stat_lbl = Label(text=f'[color=#CCCCCC]{label}:[/color] [b]{val}[/b]',
                             markup=True, font_size=sp(12), color=TEXT_COLOR,
                             halign='left', valign='middle')
            stat_lbl.bind(size=lambda i, s: setattr(i, 'text_size', (s[0], None)))
            row.add_widget(stat_lbl)
            stats_box.add_widget(row)
        body.add_widget(stats_box)

        # Правая колонка: картинка сверху, название снизу
        cls_names = {1: 'Рекрут', 2: 'Герой', 3: 'Чемпион', 4: 'Легенда'}
        right_col = BoxLayout(orientation='vertical', size_hint=(0.58, 1),
                              spacing=dp(4), padding=[0, dp(4), dp(4), dp(4)])
        right_col.add_widget(Image(source=unit_info['image'], size_hint=(1, 1),
                                   keep_ratio=True, allow_stretch=True, mipmap=True))
        name_lbl = Label(
            text=f'[b]{unit_name}[/b]  [color=#AAAAAA]{cls_names.get(unit_class, "")} кл.{unit_class}[/color]',
            markup=True, font_size=sp(13), color=(0.96, 0.96, 0.96, 1),
            size_hint=(1, None), height=dp(32),
            halign='center', valign='middle'
        )
        name_lbl.bind(size=lambda i, s: setattr(i, 'text_size', s))
        right_col.add_widget(name_lbl)
        body.add_widget(right_col)

        # ── Стоимость ────────────────────────────────────────────────
        cost_row = BoxLayout(orientation='horizontal', size_hint=(1, None), height=dp(34),
                             spacing=dp(10), padding=[dp(8), dp(2)])
        cost_row.add_widget(Label(text='[b]Цена:[/b]', markup=True, font_size=sp(13),
                                  color=TEXT_COLOR, size_hint=(None, 1), width=dp(48)))
        cost_row.add_widget(Label(
            text=f'[color=#FFD700]{format_number(cost_money)}[/color] крон  '
                 f'[color=#88CCFF]{format_number(cost_time)}[/color] раб.',
            markup=True, font_size=sp(13), color=TEXT_COLOR, halign='left', valign='middle'
        ))

        # ── Контроллер найма ─────────────────────────────────────────
        ctrl = BoxLayout(size_hint=(1, None), height=dp(46),
                         orientation='horizontal', spacing=dp(8),
                         padding=[dp(8), dp(4), dp(8), dp(4)])

        def _styled_btn(txt, bg, w=None):
            b = Button(text=txt, font_size=sp(14), bold=True,
                       background_color=(0, 0, 0, 0), color=TEXT_COLOR,
                       size_hint_x=(None if w else 1), width=(w or 0))
            with b.canvas.before:
                b._c = Color(*bg)
                b._r = RoundedRectangle(pos=b.pos, size=b.size, radius=[dp(10)])
            b.bind(pos=lambda i, v: setattr(i._r, 'pos', v),
                   size=lambda i, v: setattr(i._r, 'size', v))
            return b

        if unit_class == 1:
            # ── Слайдер + поле ввода + НАНЯТЬ ────────────────────────
            ctrl.height = dp(76)
            ctrl.orientation = 'vertical'
            ctrl.padding = [dp(8), dp(2), dp(8), dp(2)]
            ctrl.spacing = dp(4)

            qty_state = {'n': 1}

            # Максимум = сколько можно купить на текущие ресурсы
            try:
                avail_crowns  = int(army_hire.class_faction.get_resource_now("Кроны")  or 0)
                avail_workers = int(army_hire.class_faction.get_resource_now("Рабочие") or 0)
                max_by_crowns  = int(avail_crowns  // cost_money)  if cost_money  > 0 else 99999
                max_by_workers = int(avail_workers // cost_time)   if cost_time   > 0 else 99999
                max_affordable = max(1, min(max_by_crowns, max_by_workers))
            except Exception:
                max_affordable = 10000

            # — Строка 1: слайдер с подписью ——————————————————————————
            slider_row = BoxLayout(size_hint=(1, None), height=dp(32),
                                   orientation='horizontal', spacing=dp(8))
            slider_lbl = Label(text='[b]1[/b]', markup=True, font_size=sp(14),
                               color=(1, 1, 1, 1), size_hint=(None, 1), width=dp(56),
                               halign='right', valign='middle')
            slider_lbl.bind(size=lambda i, s: setattr(i, 'text_size', s))
            qty_slider = Slider(min=1, max=max_affordable, value=1, step=1,
                                size_hint=(1, 1),
                                cursor_size=(dp(22), dp(22)))

            slider_row.add_widget(slider_lbl)
            slider_row.add_widget(qty_slider)

            def _set_qty(val, *, lbl=slider_lbl, sl=qty_slider, st=qty_state):
                st['n'] = int(val)
                sl.value = int(val)
                lbl.text = f'[b]{int(val):,}[/b]'.replace(',', ' ')

            def _on_slider(inst, val):
                _set_qty(val)
            qty_slider.bind(value=_on_slider)

            # — Строка 2: TextInput + НАНЯТЬ ——————————————————————————
            hire_row = BoxLayout(size_hint=(1, None), height=dp(34),
                                 orientation='horizontal', spacing=dp(6))
            qty_input = TextInput(
                text='1', font_size=sp(14), multiline=False,
                size_hint=(0.40, 1),
                background_color=(0.12, 0.16, 0.22, 1),
                foreground_color=(1, 1, 1, 1),
                cursor_color=(1, 1, 1, 1),
                input_filter='int',
                halign='center',
            )

            def _on_input_text(inst, val):
                try:
                    v = max(1, min(max_affordable, int(val) if val else 1))
                    qty_state['n'] = v
                    qty_slider.value = v
                    slider_lbl.text = f'[b]{v:,}[/b]'.replace(',', ' ')
                except ValueError:
                    pass
            qty_input.bind(text=_on_input_text)

            def _on_slider_sync(inst, val, inp=qty_input):
                inp.text = str(int(val))
            qty_slider.bind(value=_on_slider_sync)

            btn_hire = _styled_btn('НАНЯТЬ', accent)

            class _FakeInput:
                def __init__(self): self.text = ''
            _fi = _FakeInput()

            def _do_hire(inst, name=unit_name, cost=unit_info['cost'],
                         stats=unit_info['stats'], image=unit_info['image']):
                _fi.text = str(qty_state['n'])
                broadcast_units(name, cost, _fi, army_hire, image, stats)

            btn_hire.bind(on_release=_do_hire)

            hire_row.add_widget(qty_input)
            hire_row.add_widget(btn_hire)

            for row in (slider_row, hire_row):
                ctrl.add_widget(row)
        else:
            # Герои и выше — просто кнопка «НАНЯТЬ»
            btn_hero = _styled_btn('НАНЯТЬ ГЕРОЯ', accent)
            btn_hero.bind(
                on_release=lambda inst, name=unit_name, cost=unit_info['cost'],
                                  stats=unit_info['stats'], image=unit_info['image']:
                broadcast_units(name, cost, None, army_hire, image, stats)
            )
            ctrl.add_widget(btn_hero)

        # ── Сборка карточки ──────────────────────────────────────────
        card.add_widget(body)
        card.add_widget(cost_row)
        card.add_widget(ctrl)
        carousel.add_widget(slide)
        slide.add_widget(card)

    # Добавляем стрелки прокрутки
    arrow_size = dp(60)
    arrow_right = Image(
        source='files/pict/right.png',
        size_hint=(None, None),
        size=(arrow_size, arrow_size),
        pos_hint={'center_y': 0.5, 'right': 1.27},
        allow_stretch=True,
        keep_ratio=True,
        mipmap=True
    )

    def on_arrow_right(instance, touch):
        if instance.collide_point(*touch.pos):
            carousel.load_next()
            animate_arrow_click(arrow_right)

    arrow_right.bind(on_touch_down=on_arrow_right)

    right_container.add_widget(carousel)
    right_container.add_widget(arrow_right)

    # Анимация для стрелок
    def animate_arrow_click(arrow):
        anim = (
                Animation(size=(dp(65), dp(65)), duration=0.1, t='in_out_elastic') +
                Animation(size=(dp(60), dp(60)), duration=0.2, t='in_out_elastic')
        )
        anim.start(arrow)

    # Мигание правой стрелки
    def blink_arrow(instance, duration=0.5):
        anim = Animation(opacity=0.3, duration=duration) + Animation(opacity=1.0, duration=duration)
        anim.repeat = True
        anim.start(instance)

    blink_arrow(arrow_right)

    # Сборка интерфейса
    main_box.add_widget(left_space)
    main_box.add_widget(right_container)

    float_layout = FloatLayout(size_hint=(1, 1))
    float_layout.add_widget(main_box)

    # Кнопка закрытия
    close_icon = Image(
        source='files/pict/close.png',
        size_hint=(None, None),
        size=(dp(60), dp(60)),
        pos_hint={'top': 0.85, 'right': 1.18},
        allow_stretch=True,
        keep_ratio=True,
        mipmap=True,
        color=(1, 1, 1, 0.9)
    )

    def on_close_press(instance, touch):
        if instance.collide_point(*touch.pos):
            game_area.clear_widgets()
            animate_arrow_click(instance)

    close_icon.bind(on_touch_down=on_close_press)
    float_layout.add_widget(close_icon)

    game_area.add_widget(float_layout)


def broadcast_units(unit_name, unit_cost, quantity_input, army_hire, image, unit_stats):
    try:
        # Если input передан — берём оттуда, иначе — один юнит
        if quantity_input is not None:
            qty_text = quantity_input.text.strip()
            quantity = int(qty_text) if qty_text else 0
        else:
            quantity = 1

        if quantity <= 0:
            raise ValueError("Количество должно быть положительным числом")

        army_hire.hire_unit(
            unit_name=unit_name,
            unit_cost=unit_cost,
            quantity=quantity,
            unit_stats=unit_stats,
            unit_image=image
        )

    except ValueError as e:
        show_army_message(
            title="Ошибка",
            message=f"[color=#FF0000]{str(e) or 'Введите корректное число!'}[/color]"
        )

def show_army_message(title, message):
    is_error = 'ошибк' in title.lower()
    acc = (0.72, 0.18, 0.18, 1) if is_error else (0.20, 0.55, 0.88, 1)
    sep = (0.78, 0.18, 0.18, 0.85) if is_error else (0.20, 0.55, 0.88, 0.7)
    title_clr = (1, 0.55, 0.55, 1) if is_error else (0.65, 0.88, 1, 1)

    content = BoxLayout(orientation='vertical', padding=[dp(14), dp(10), dp(14), dp(12)], spacing=dp(10))

    lbl = Label(
        text=message, markup=True,
        font_size=sp(14), color=(0.94, 0.94, 0.94, 1),
        halign='center', valign='middle'
    )
    lbl.bind(size=lbl.setter('text_size'))
    content.add_widget(lbl)

    btn = Button(
        text="Закрыть", size_hint_y=None, height=dp(40),
        background_color=(0, 0, 0, 0), color=(1, 1, 1, 1),
        font_size=sp(14), bold=True
    )
    with btn.canvas.before:
        btn._bc = Color(*acc)
        btn._br = RoundedRectangle(pos=btn.pos, size=btn.size, radius=[dp(10)])
    btn.bind(pos=lambda i, v: setattr(i._br, 'pos', v),
             size=lambda i, v: setattr(i._br, 'size', v))
    content.add_widget(btn)

    popup = Popup(
        title=title, content=content,
        size_hint=(0.78, 0.34),
        background_color=(0.07, 0.08, 0.13, 1),
        separator_color=sep,
        title_color=title_clr,
        title_size=sp(15), title_align='center',
        auto_dismiss=False
    )
    btn.bind(on_release=popup.dismiss)
    popup.open()

def set_font_size(relative_size):
    """Вычисляет размер шрифта относительно размера окна"""
    from kivy.core.window import Window
    return Window.width * relative_size

#---------------------------------------------------------------
class StyledButton(Button):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        with self.canvas.before:
            Color(0.2, 0.6, 0.8, 1)  # Основной цвет кнопки
            self.rect = RoundedRectangle(radius=[20], size=self.size, pos=self.pos)
        self.bind(pos=self.update_rect, size=self.update_rect)

    def update_rect(self, *args):
        self.rect.pos = self.pos
        self.rect.size = self.size
        # Фиксируем радиус закругления
        self.rect.radius = [20]

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            # Сохраняем радиус при анимации
            self.rect.size = (self.size[0] - 5, self.size[1] - 5)
            self.rect.radius = [20]  # Форсируем обновление радиуса
        return super().on_touch_down(touch)

    def on_touch_up(self, touch):
        if self.collide_point(*touch.pos):
            self.rect.size = self.size
            self.rect.radius = [20]  # Форсируем обновление радиуса
        return super().on_touch_up(touch)