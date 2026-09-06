from lerdon_libraries import *
from db_lerdon_connect import *
from utils.helpers import format_number

def get_adaptive_font_size(min_size=15, max_size=20):
    """Адаптирует размер шрифта под ширину экрана с учетом Android"""
    screen_width = Window.width

    # Увеличенный коэффициент для лучшей читаемости
    dynamic_size = min(max(screen_width * 1.8, min_size), max_size)

    # Учет масштабирования Android (если доступно)
    if platform == 'android':
        from jnius import autoclass
        context = autoclass('org.kivy.android.PythonActivity').mActivity
        resources = context.getResources()
        configuration = resources.getConfiguration()
        scaled_density = resources.getDisplayMetrics().scaledDensity
        dynamic_size = int(dynamic_size * scaled_density)

    return dynamic_size


class EventManager:
    def __init__(self, player_faction, game_screen, class_faction_economic, conn):
        self.player_faction = player_faction
        self.game_screen = game_screen  # Ссылка на экран игры для отображения событий
        self.db_connection = conn # Используем единую сессию с БД
        self.economics = class_faction_economic  # Экономический модуль

    def generate_event(self, current_turn):
        """
        Генерирует случайное событие из базы данных и определяет его тип.
        За один ход происходит максимум одно событие.
        Сначала проверяет отложенные цепочки событий.
        :param current_turn: Текущий ход игры.
        """
        # Сначала проверяем отложенные цепочки событий
        chain_fired = self._check_pending_chains(current_turn)
        if chain_fired:
            return

        # Проверяем карму и пытаемся сгенерировать событие sequences
        generated = self.check_karma_and_generate_sequence(current_turn)
        if generated:
            return  # Если событие sequences сгенерировано — выходим

        # Иначе генерируем обычное событие (active или passive)
        cursor = self.db_connection.cursor()
        cursor.execute("""
            SELECT id, description, event_type, effects, option_1_description, option_2_description
            FROM events
            WHERE event_type IN ('active', 'passive')
            ORDER BY RANDOM()
            LIMIT 1
        """)
        event = cursor.fetchone()
        if not event:
            print("События не найдены в базе данных.")
            return

        # Распаковываем данные события
        event_id, description, event_type, effects, option_1_description, option_2_description = event
        effects = json.loads(effects)  # Преобразуем JSON-строку в словарь
        effects["option_1_description"] = option_1_description
        effects["option_2_description"] = option_2_description

        # Обрабатываем событие в зависимости от его типа
        if event_type == "active":
            print(f"Активное событие: {description}")
            self.handle_active_event(description, effects)
        elif event_type == "passive":
            print(f"Пассивное событие: {description}")
            self.handle_passive_event(description, effects)

    def handle_active_event(self, description, effects):
        """
        Обрабатывает активное событие: отображает модальное окно с выбором.
        """
        print(f'-------------------------------------------- effects прилетело: {effects}')

        # Извлекаем текст опций из словаря effects или из базы данных
        option_1 = effects.get("option_1_description", "Не подгрузилось")
        option_2 = effects.get("option_2_description", "Не подгрузилось")

        self.show_event_active_popup(description, option_1, option_2, effects)

    def check_karma_and_generate_sequence(self, current_turn):
        """
        Проверяет карму и генерирует событие типа 'sequences' на основе значения karma_score.
        После успешной генерации события очищает значение кармы.
        """
        cursor = self.db_connection.cursor()
        cursor.execute("SELECT karma_score, last_check_turn FROM karma WHERE faction = ?", (self.player_faction,))
        result = cursor.fetchone()
        if not result:
            return False
        karma_score, last_check_turn = result

        turns_since_last_check = current_turn - last_check_turn

        # Проверяем, прошло ли достаточно ходов для нового "среза"
        if turns_since_last_check < random.randint(10, 15):  # ↑ увеличили интервал
            return False

        # Обновляем last_check_turn, чтобы избежать повторной попытки в ближайших ходах
        cursor.execute("""
            UPDATE karma
            SET last_check_turn = ?
            WHERE faction = ?
        """, (current_turn, self.player_faction))
        self.db_connection.commit()

        # Генерируем событие только если карма соответствует условиям
        if karma_score > 6:
            print("Положительное событие sequences!")
            success = self.generate_sequence_event('posi')
            if success:
                self.clear_karma(current_turn)
                return True
            return False
        elif karma_score < 0:
            print("Отрицательное событие sequences!")
            success = self.generate_sequence_event('negat')
            if success:
                self.clear_karma(current_turn)
                return True
            return False
        else:
            print("Нейтральная карма. События sequences не генерируются.")
        return False

    def clear_karma(self, current_turn):
        """
        Обнуляет значение кармы и обновляет last_check_turn.
        """
        cursor = self.db_connection.cursor()
        cursor.execute("""
            UPDATE karma
            SET karma_score = 0, last_check_turn = ?
            WHERE faction = ?
        """, (current_turn, self.player_faction))
        self.db_connection.commit()
        print(f"[DEBUG] Карма для фракции '{self.player_faction}' очищена.")

    def generate_sequence_event(self, karma_type):
        """
        Генерирует событие sequences с учётом типа кармы.
        :param karma_type: 'posi' или 'negat'
        """
        kf_condition = "> 1.0" if karma_type == "posi" else "< 1.0"
        query = f"""
            SELECT id, description, effects 
            FROM events
            WHERE event_type = 'sequences'
              AND json_extract(effects, '$.kf') {kf_condition}
            ORDER BY RANDOM()
            LIMIT 1
        """
        cursor = self.db_connection.cursor()
        cursor.execute(query)
        event = cursor.fetchone()
        if not event:
            print(f"[WARN] Нет подходящих событий для '{karma_type}' (kf {kf_condition})")
            return False

        event_id, description, effects_json = event
        effects = json.loads(effects_json)

        # Получаем тип ресурса и коэффициент
        resource_type = effects.get("resource", None)
        kf = effects.get("kf", 1.0)

        if resource_type:
            current_value = self.get_resource_amount(resource_type)
            if kf > 1.0:
                # Увеличиваем ресурс по коэффициенту
                new_value = int(current_value * kf)
                self.economics.update_resource_now(resource_type, new_value)
                full_description = f"{description} [b]{resource_type}[/b] увеличено до {format_number(new_value)}."
            else:
                # Обнуляем ресурс, если kf <= 1.0
                self.economics.update_resource_now(resource_type, 0)
                full_description = f"{description} Мы потеряли: [b]{resource_type}[/b]"
        else:
            full_description = description

        # Отображаем как бегущую строку
        self.show_temporary_build(full_description, "sequences")
        return True

    def zero_resource(self, resource_type):
        """
        Обнуляет указанный ресурс через экономический модуль.
        """
        print(f"[DEBUG] Обнуление ресурса '{resource_type}' через экономический модуль.")
        self.economics.update_resource_now(resource_type, 0)  # ← Теперь через модуль

    def handle_passive_event(self, description, effects, event_type=None):
        """
        Обрабатывает пассивное событие: применяет эффекты (если они есть)
        и отображает бегущую строку для всех событий с event_type='passive' или 'sequences'.
        """
        # Применяем эффекты, если они есть
        if "resource" in effects and "kf" in effects:
            resource = effects["resource"]
            kf = effects["kf"]
            current_value = self.get_resource_amount(resource)
            change = int(current_value * kf)
            self.update_resource(resource, change)
            print(f"Событие {event_type}: {description}. {resource} изменен на {change}.")

        # Всегда отображаем бегущую строку
        self.show_temporary_build(description, event_type or "passive")

    def show_event_active_popup(self, description, option_1, option_2, effects):
        """Отображение активного события — стилизованный popup с выбором."""
        from kivy.uix.floatlayout import FloatLayout

        content = FloatLayout()

        # Тёмный фон
        with content.canvas.before:
            Color(0.06, 0.07, 0.12, 1)
            content._bg = RoundedRectangle(pos=content.pos, size=content.size, radius=[dp(16)])
        content.bind(
            pos=lambda i, v: setattr(i._bg, 'pos', v),
            size=lambda i, v: setattr(i._bg, 'size', v)
        )

        # Заголовок «Событие»
        title_lbl = Label(
            text="[b]Событие[/b]", markup=True,
            font_size=sp(20), color=(0.92, 0.82, 0.52, 1),
            size_hint=(0.9, None), height=dp(30),
            pos_hint={'center_x': 0.5, 'top': 0.96}, halign='center',
        )
        title_lbl.bind(size=title_lbl.setter('text_size'))

        # Золотая линия
        sep = Widget(size_hint=(0.85, None), height=dp(1), pos_hint={'center_x': 0.5, 'top': 0.86})
        with sep.canvas:
            Color(0.85, 0.75, 0.45, 0.5)
            sep._r = Rectangle(pos=sep.pos, size=sep.size)
        sep.bind(pos=lambda i, v: setattr(i._r, 'pos', v), size=lambda i, v: setattr(i._r, 'size', v))

        # Текст события
        desc_lbl = Label(
            text=description, markup=True,
            font_size=sp(14), color=(0.85, 0.87, 0.92, 1),
            size_hint=(0.88, None), height=dp(120),
            pos_hint={'center_x': 0.5, 'center_y': 0.55},
            halign='center', valign='middle',
        )
        desc_lbl.bind(size=desc_lbl.setter('text_size'))

        # Кнопки выбора
        def _make_event_btn(text, color, y_pos):
            btn = Button(
                text=text, font_size=sp(13), bold=True, markup=True,
                size_hint=(0.88, None), height=dp(46),
                pos_hint={'center_x': 0.5, 'y': y_pos},
                background_normal='', background_color=(0, 0, 0, 0),
                color=(1, 1, 1, 1),
            )
            with btn.canvas.before:
                Color(*color)
                btn._bg = RoundedRectangle(pos=btn.pos, size=btn.size, radius=[dp(10)])
            btn.bind(
                pos=lambda i, v: setattr(i._bg, 'pos', v),
                size=lambda i, v: setattr(i._bg, 'size', v)
            )
            return btn

        btn_1 = _make_event_btn(option_1, (0.15, 0.45, 0.65, 1), 0.18)
        btn_2 = _make_event_btn(option_2, (0.55, 0.15, 0.15, 1), 0.04)

        content.add_widget(title_lbl)
        content.add_widget(sep)
        content.add_widget(desc_lbl)
        content.add_widget(btn_1)
        content.add_widget(btn_2)

        popup = Popup(
            title='', separator_height=0,
            content=content,
            size_hint=(0.5, None), height=dp(350),
            auto_dismiss=False,
            background='', background_color=(0, 0, 0, 0.55),
        )

        def on_button_1(instance):
            self.apply_effects_with_economic_module(effects.get("option_1", {}))
            self.update_karma(self.player_faction, 4)
            # Запускаем цепочку последствий от позитивного выбора
            self._schedule_chain_event(description, 'positive')
            popup.dismiss()

        def on_button_2(instance):
            self.apply_effects_with_economic_module(effects.get("option_2", {}))
            self.update_karma(self.player_faction, -6)
            # Запускаем цепочку последствий от негативного выбора
            self._schedule_chain_event(description, 'negative')
            popup.dismiss()

        btn_1.bind(on_release=on_button_1)
        btn_2.bind(on_release=on_button_2)

        popup.opacity = 0
        popup.open()
        Animation(opacity=1, duration=0.25).start(popup)

    def apply_effects_with_economic_module(self, effects):
        """
        Применение эффектов события через экономический модуль.
        """
        if "resource_changes" in effects:
            for resource, change_data in effects["resource_changes"].items():
                kf = change_data.get("kf", 1)
                current_value = self.get_resource_amount(resource)
                change = int(current_value * (kf - 1))  # Рассчитываем изменение
                print(f"[DEBUG] Изменение ресурса '{resource}': {change}")

                # Передаем изменения в экономический модуль
                self.economics.update_resource_now(resource, current_value + change)


    def get_resource_amount(self, resource_type):
        """Получение текущего значения ресурса."""
        cursor = self.db_connection.cursor()
        cursor.execute("SELECT amount FROM resources WHERE faction = ? AND resource_type = ?", (self.player_faction, resource_type))
        result = cursor.fetchone()
        return result[0] if result else 0

    def update_resource(self, resource_type, change):
        """Обновление ресурсов."""
        cursor = self.db_connection.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO resources (faction, resource_type, amount)
            VALUES (?, ?, COALESCE((SELECT amount FROM resources WHERE faction = ? AND resource_type = ?), 0) + ?)
        """, (self.player_faction, resource_type, self.player_faction, resource_type, change))
        self.db_connection.commit()

    def update_karma(self, faction, karma_change):
        """
        Обновляет счетчик кармы для указанной фракции.
        :param faction: Название фракции.
        :param karma_change: Изменение кармы (+2 или -3).
        """
        cursor = self.db_connection.cursor()
        # Получаем текущее значение кармы
        cursor.execute("SELECT karma_score FROM karma WHERE faction = ?", (faction,))
        result = cursor.fetchone()
        current_karma = result[0] if result else 0

        # Обновляем значение кармы
        new_karma = current_karma + karma_change
        cursor.execute("""
            INSERT OR REPLACE INTO karma (id, faction, karma_score, last_check_turn)
            VALUES ((SELECT id FROM karma WHERE faction = ?), ?, ?, 
                    COALESCE((SELECT last_check_turn FROM karma WHERE faction = ?), 0))
        """, (faction, faction, new_karma, faction))
        self.db_connection.commit()

        print(f"[DEBUG] Карма для фракции '{faction}' обновлена: {new_karma}")

    # === Система цепочек событий ===

    CHAIN_CONSEQUENCES = {
        'positive': [
            {"desc": "Ваше мудрое решение привело к росту торговли! Купцы стекаются в ваши земли.",
             "effect": {"resource": "Кроны", "kf": 1.15}},
            {"desc": "Благодарные жители организовали ополчение. Ваша армия пополнилась добровольцами.",
             "effect": {"resource": "Рабочие", "kf": 1.20}},
            {"desc": "Слава о вашей справедливости разнеслась по землям. Народ процветает!",
             "effect": {"resource": "Население", "kf": 1.10}},
            {"desc": "Ваши рудники заработали на полную мощность благодаря новым порядкам.",
             "effect": {"resource": "Кристаллы", "kf": 1.12}},
            {"desc": "Ваша репутация мудрого правителя укрепилась. Дворяне стали лояльнее.",
             "effect": {"resource": "Кроны", "kf": 1.08}},
        ],
        'negative': [
            {"desc": "Последствия жёсткого решения: часть населения покинула ваши земли в страхе.",
             "effect": {"resource": "Население", "kf": 0.85}},
            {"desc": "Недовольство народа вылилось в саботаж на фабриках. Добыча кристаллов упала.",
             "effect": {"resource": "Кристаллы", "kf": 0.80}},
            {"desc": "Торговцы опасаются вести дела с вашей фракцией. Доходы казны снизились.",
             "effect": {"resource": "Кроны", "kf": 0.85}},
            {"desc": "Дезертиры покинули армию из-за жестокости командования.",
             "effect": {"resource": "Рабочие", "kf": 0.75}},
            {"desc": "Ваша жестокость вызвала волну беженцев. Города пустеют.",
             "effect": {"resource": "Население", "kf": 0.90}},
        ],
    }

    def _schedule_chain_event(self, original_desc, choice_type):
        """Планирует последствие выбора через 3-5 ходов."""
        try:
            cursor = self.db_connection.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS event_chains (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    faction TEXT,
                    trigger_turn INTEGER,
                    choice_type TEXT,
                    original_event TEXT,
                    fired INTEGER DEFAULT 0
                )
            """)
            # Получаем текущий ход
            cursor.execute("SELECT turn_count FROM turn WHERE faction = ?", (self.player_faction,))
            row = cursor.fetchone()
            current_turn = row[0] if row else 1
            trigger_turn = current_turn + random.randint(3, 5)

            cursor.execute("""
                INSERT INTO event_chains (faction, trigger_turn, choice_type, original_event)
                VALUES (?, ?, ?, ?)
            """, (self.player_faction, trigger_turn, choice_type, original_desc[:100]))
            self.db_connection.commit()
            print(f"[CHAIN] Запланировано последствие '{choice_type}' на ход {trigger_turn}")
        except Exception as e:
            print(f"[CHAIN] Ошибка планирования: {e}")

    def _check_pending_chains(self, current_turn):
        """Проверяет и запускает отложенные цепочки событий."""
        try:
            cursor = self.db_connection.cursor()
            # Проверяем существование таблицы
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='event_chains'")
            if not cursor.fetchone():
                return False

            cursor.execute("""
                SELECT id, choice_type, original_event FROM event_chains
                WHERE faction = ? AND trigger_turn <= ? AND fired = 0
                ORDER BY trigger_turn ASC LIMIT 1
            """, (self.player_faction, current_turn))
            row = cursor.fetchone()
            if not row:
                return False

            chain_id, choice_type, original_event = row

            # Выбираем случайное последствие
            consequences = self.CHAIN_CONSEQUENCES.get(choice_type, [])
            if not consequences:
                return False

            consequence = random.choice(consequences)

            # Применяем эффект
            resource = consequence['effect']['resource']
            kf = consequence['effect']['kf']
            current_value = self.get_resource_amount(resource)
            new_value = int(current_value * kf)
            self.economics.update_resource_now(resource, new_value)

            # Формируем описание
            change = new_value - current_value
            change_text = f"+{format_number(change)}" if change > 0 else format_number(change)
            full_desc = f"{consequence['desc']} ({resource}: {change_text})"

            # Помечаем как сработавшее
            cursor.execute("UPDATE event_chains SET fired = 1 WHERE id = ?", (chain_id,))
            self.db_connection.commit()

            # Показываем как бегущую строку
            self.show_temporary_build(full_desc, "sequences")
            print(f"[CHAIN] Последствие '{choice_type}': {consequence['desc']}")
            return True
        except Exception as e:
            print(f"[CHAIN] Ошибка проверки: {e}")
            return False

    def show_temporary_build(self, description, event_type):
        """
        Отображает бегущую строку: появляется Label с черным фоном на всю ширину,
        по которому скользит текст события целиком, не обрезаясь.
        Label исчезает только после того, как текст полностью выйдет за левый край.
        """

        # Проверяем, есть ли уже активная бегущая строка
        if hasattr(self, '_running_marquee') and self._running_marquee:
            Clock.schedule_once(lambda dt: self.show_temporary_build(description, event_type), 1)
            return

        # === Цвет текста в зависимости от типа события ===
        if event_type == "passive":
            text_color = (1, 1, 1, 1)  # Белый
        elif event_type == "sequences":
            text_color = (0.5, 0.8, 1, 1)  # Светло-синий
        else:
            text_color = (1, 1, 1, 1)

        font_size = get_adaptive_font_size(min_size=14, max_size=20)

        # === Ширина контейнера — вся доступная область между панелью и правым краем экрана ===
        mode_panel_width = dp(90)  # ширина панели с кнопками режимов
        screen_width = Window.width
        label_height = dp(36)
        start_y = Window.height * 0.15  # ~15% от низа экрана

        # Создаем Label с полной длиной текста
        build_label = Label(
            text=description,
            font_size=font_size,
            color=text_color,
            halign="left",
            valign="middle",
            size_hint=(None, None),
            height=label_height,
            width=screen_width - mode_panel_width * 2,
            text_size=(None, label_height),
            shorten=False,
            markup=True
        )
        build_label.texture_update()
        text_width = build_label.texture_size[0] + dp(20)

        # === Контейнер для Label (начинается за правым краем экрана) ===
        container_width = screen_width - mode_panel_width * 2
        container = BoxLayout(
            orientation='horizontal',
            size_hint=(None, None),
            size=(text_width, label_height),
            pos=(screen_width, start_y)
        )

        # === Устанавливаем Label в контейнер и выравниваем по левому краю ===
        build_label.pos = (0, 0)
        build_label.size = (text_width, label_height)
        container.add_widget(build_label)

        # === Черный фон с прозрачностью вокруг контейнера ===
        with container.canvas.before:
            Color(0, 0, 0, 0.7)
            container.rect = Rectangle(pos=container.pos, size=container.size)

        def update_rect(instance, value):
            instance.rect.pos = instance.pos
            instance.rect.size = instance.size

        container.bind(pos=update_rect, size=update_rect)

        # Добавляем контейнер на экран
        self.game_screen.add_widget(container)

        # === Анимация движения текста внутри контейнера ===
        move_distance = text_width + container_width  # полное перемещение текста через контейнер
        duration = move_distance / dp(180)  # скорость движения (можно регулировать)

        # === Анимация всего контейнера ===
        anim_container = Animation(pos=(-text_width, start_y), duration=duration, t='linear')

        # === Привязка завершения анимации ===
        def on_animation_complete(*args):
            self.game_screen.remove_widget(container)
            self._running_marquee = False

        # Запуск анимации
        self._running_marquee = True
        anim_container.bind(on_complete=on_animation_complete)
        anim_container.start(container)
