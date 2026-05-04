# nobles_generator.py
import random
import json

from kivy.core.window import Window
from kivy.metrics import dp, sp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.graphics import Color, RoundedRectangle
from kivy.clock import Clock

EVENT_COUNT_FOR_SYMPATHIES = 3  # После N мероприятий появляются симпатии (взгляды)
SHOW_SYMPATHIES = False         # Флаг, показывать ли симпатии
SYMPATHIES_VISIBLE_UNTIL_PRIORITY_CHANGE = False  # Симпатии скрываются при смене приоритетов

# Список рас (5 штук)
RACES = ['Север', 'Эльфы', 'Адепты', 'Вампиры', 'Элины']

# Список идеологий (всего 2)
IDEOLOGIES = ['Борьба', 'Смирение']

# Список имен для каждой расы
NAMES = {
    'Север': [
        'Николай', 'Леонид', 'Карами', 'Генрих', 'Уильям', 'Мирослав',
        'Александр', 'Дмитрий', 'Иван', 'Сергей', 'Людмила', 'Алексей',
        'Евгений', 'Владимир', 'Павел', 'Максим', 'Олег', 'Виктор',
        'Антон', 'Игорь', 'Юрий', 'Анастасия', 'Фёдор', 'Константин',
        'Артём', 'Роман', 'Станислав', 'Борис', 'Валерий', 'Григорий',
        'Екатерина', 'Анатолий', 'Валентин', 'Эдуард', 'Дарья', 'Ульяна'
    ],
    'Эльфы': [
        'Закани', 'Миордания', 'Риндайли', 'Широни', 'Глория', 'Амрелия',
        'Зимолас', 'Арлен', 'Халандриэль', 'Малронд', 'Карандуил', 'Финрод',
        'Идрис', 'Кейлибан', 'Нимуэ', 'Эрандир', 'Индриль', 'Фингольфин',
        'Маглор', 'Маэглин', 'Нармелин', 'Орфен', 'Тай-фэль', 'Аэдриан',
        'Брендуил', 'Каландрель', 'Дориат', 'Имильме', 'Линду', 'Морвен',
        'Нимфадор', 'Олорин', 'Пенлар', 'Румил', 'Туор'
    ],
    'Адепты': [
        'Серафим', 'Михаил', 'Гавриил', 'Рафаил', 'Уриил', 'Иоанн',
        'Хафез', 'Матфей', 'Марк', 'Лука', 'Иуда', 'Варнава',
        'Тимофей', 'Тит', 'Филипп', 'Яков', 'Иоанн', 'Пётр',
        'Андрей', 'Фома', 'Варфоломей', 'Матфей', 'Симон', 'Фаддей',
        'Авраам', 'Исаак', 'Иаков', 'Иосиф', 'Моисей', 'Аарон',
        'Давид', 'Соломон', 'Иеремия', 'Даниил', 'Эдна'
    ],
    'Вампиры': [
        'Люци', 'Стефан', 'Вильгельм', 'Виктор', 'Бальтазар', 'Габриэль',
        'Дракула', 'Каин', 'Абель', 'Азраэль', 'Баал', 'Валентин',
        'Герман', 'Дамиан', 'Эдриан', 'Фредерик', 'Готиер', 'Иннокентий',
        'Йохан', 'Клаус', 'Лоренцо', 'Маркус', 'Никодим', 'Орландо',
        'Персиваль', 'Рудольф', 'Сильвестр', 'Теодор', 'Ульрих', 'Фауст',
        'Хаим', 'Кайзер', 'Чарльз', 'Эрик', 'Юлиан'
    ],
    'Элины': [
        'Ария', 'Шакира', 'Селена', 'Элион', 'Мирана', 'Фаари',
        'Лиана', 'Кассандра', 'Изольда', 'Ариэль', 'Бьянка', 'Вивиана',
        'Габриэлла', 'Диана', 'Елена', 'Жасмин', 'Зара', 'Инесса',
        'Йорин', 'Камилла', 'Лилия', 'Мелания', 'Ника', 'Офелия',
        'Полина', 'Регина', 'София', 'Татьяна', 'Флора',
        'Хлоя', 'Цветана', 'Чарлотта', 'Элоиза', 'Юлия', 'Карами'
    ]
}

# --- КОНФИГУРАЦИЯ СТИЛЕЙ (THEME) ---
class UIStyles:
    # Цветовая палитра "Королевство"
    COLOR_BG = (0.05, 0.05, 0.1, 1)       # Темно-синий фон
    COLOR_CARD = (0.15, 0.15, 0.25, 1)    # Фон карточки
    COLOR_GOLD = (0.8, 0.65, 0.2, 1)      # Золото
    COLOR_TEXT = (0.9, 0.9, 0.9, 1)       # Белый текст
    COLOR_TEXT_DIM = (0.6, 0.6, 0.6, 1)   # Тусклый текст
    COLOR_SUCCESS = (0.2, 0.8, 0.4, 1)    # Зеленый
    COLOR_DANGER = (0.8, 0.2, 0.2, 1)     # Красный
    COLOR_WARNING = (0.9, 0.6, 0.2, 1)    # Оранжевый
    COLOR_ACTION = (0.3, 0.5, 0.8, 1)     # Синяя кнопка

    # Размеры
    PADDING = dp(10)
    RADIUS = dp(10)

    @staticmethod
    def is_android():
        return hasattr(Window, 'keyboard')

    @staticmethod
    def get_font_size(base_size, is_label=False):
        """Адаптивный шрифт. Для лейблов делаем чуть крупнее для читаемости."""
        if UIStyles.is_android():
            if is_label:
                return base_size * 0.95  # Текст читаемый
            return base_size * 0.85      # Кнопки и второстепенное мельче
        return base_size

    @staticmethod
    def get_popup_size():
        return (0.9, 0.55) if UIStyles.is_android() else (0.85, 0.5)

    @staticmethod
    def get_toast_duration():
        return 1.2  # Уменьшено до 1.2 секунды

# --- Вспомогательные функции ---

def get_player_faction(conn):
    """Получение фракции игрока из БД"""
    cursor = conn.cursor()
    cursor.execute("SELECT faction_name FROM user_faction")
    result = cursor.fetchone()
    return result[0] if result else None

def get_faction_ideology(conn, faction_name):
    """Получение идеологии фракции из БД"""
    cursor = conn.cursor()
    cursor.execute("SELECT system FROM political_systems WHERE faction = ?", (faction_name,))
    result = cursor.fetchone()
    return result[0] if result else 'Борьба' # По умолчанию 'Борьба'

def get_player_ideology(conn):
    """Получает текущую идеологию фракции игрока."""
    faction = get_player_faction(conn)
    if faction:
        return get_faction_ideology(conn, faction)
    return 'Борьба'

def get_diplomacy_relation(conn, faction1, faction2):
    """Получение статуса отношений между двумя фракциями."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT relationship FROM diplomacies 
        WHERE (faction1 = ? AND faction2 = ?) OR (faction1 = ? AND faction2 = ?)
    """, (faction1, faction2, faction2, faction1))
    result = cursor.fetchone()
    return result[0] if result else 'нейтралитет' # По умолчанию нейтралитет

def get_noble_traits(ideology_str):
    """
    Парсит строку ideology и возвращает словарь с типом и значением черты.
    """
    if ideology_str.startswith('{'):
        try:
            return json.loads(ideology_str)
        except json.JSONDecodeError:
            return {'type': 'ideology', 'value': 'Борьба'} # fallback
    elif ideology_str.startswith("Любит "):
        race = ideology_str.split(" ", 1)[1]
        return {'type': 'race_love', 'value': race}
    else: # Простая идеология
        return {'type': 'ideology', 'value': ideology_str}

def record_coup_attempt(conn, is_successful):
    """
    Записывает результат попытки переворота в таблицу coup_attempts.
    """
    if is_successful:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO coup_attempts (status) VALUES (?)", ('successful',))
        conn.commit()
        print("✅ Успешный переворот записан в базу данных")

def generate_new_noble(conn, faction_race):
    """
    Генерирует нового дворянина.
    """
    cursor = conn.cursor()

    available_names = [
        n for n in NAMES[faction_race]
        if n not in [noble['name'] for noble in get_all_nobles(conn) if noble['status'] != 'eliminated']
    ]
    if not available_names:
        available_names = NAMES[faction_race]

    new_name = random.choice(available_names)
    new_loyalty = random.uniform(55, 75)
    new_priority = 99  # Будет пересчитан
    new_status = 'active'

    # Новая черта характера
    trait_type = random.choice(['ideology', 'race_love', 'greed'])
    if trait_type == 'ideology':
        new_ideology = random.choice(IDEOLOGIES)
    elif trait_type == 'race_love':
        new_ideology = f"Любит {random.choice([r for r in RACES if r != faction_race])}"
    else:  # greed
        base_demand = 1_000
        percentage = random.uniform(0.35, 0.75)
        additional_demand = int(10_000 * percentage)
        total_demand = base_demand + additional_demand
        new_ideology = json.dumps({'type': 'greed', 'demand': total_demand})

    new_attendance_history = ""

    cursor.execute("""
        INSERT INTO nobles (priority, loyalty, status, name, ideology, attendance_history) 
        VALUES (?, ?, ?, ?, ?, ?)
    """, (new_priority, new_loyalty, new_status, new_name, new_ideology, new_attendance_history))

    conn.commit()

# --- Основные функции управления дворянами ---

def generate_initial_nobles(conn):
    """Генерация начальных советников при старте игры"""
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM nobles")
    count = cursor.fetchone()[0]

    if count > 0:
        return  # Советники уже существуют

    faction_race = get_player_faction(conn)
    if not faction_race:
        return

    available_names = NAMES[faction_race].copy()
    random.shuffle(available_names)

    for i in range(3):
        if i < len(available_names):
            name = available_names[i]
        else:
            name = random.choice(NAMES[faction_race])

        loyalty = 60.0
        priority = i
        status = 'active'

        trait_type = random.choice(['ideology', 'race_love', 'greed'])
        if trait_type == 'ideology':
            ideology = random.choice(IDEOLOGIES)
        elif trait_type == 'race_love':
            loved_race = random.choice([r for r in RACES if r != faction_race])
            ideology = f"Любит {loved_race}"
        else: # greed
            base_demand = 1_000
            percentage = random.uniform(0.25, 0.85)
            additional_demand = int(10_000 * percentage)
            total_demand = base_demand + additional_demand
            ideology = json.dumps({'type': 'greed', 'demand': total_demand})

        attendance_history = ""

        cursor.execute("""
            INSERT INTO nobles (priority, loyalty, status, name, ideology, attendance_history) 
            VALUES (?, ?, ?, ?, ?, ?)
        """, (priority, loyalty, status, name, ideology, attendance_history))

    conn.commit()
    print("Начальные советники (дворяне) инициализированы.")

def decrease_loyalty_over_time(conn):
    """Снижение лояльности всех дворян на 3% за ход, с учетом идеологии."""
    cursor = conn.cursor()
    cursor.execute("SELECT id, loyalty, ideology FROM nobles WHERE status = 'active'")
    nobles = cursor.fetchall()

    player_ideology = get_player_ideology(conn)

    for noble_id, current_loyalty, ideology_str in nobles:
        noble_traits = get_noble_traits(ideology_str)

        decrease = 3.0

        if noble_traits['type'] == 'ideology' and noble_traits['value'] == player_ideology:
            decrease = 0.5

        new_loyalty = max(0.0, current_loyalty - decrease)
        cursor.execute("UPDATE nobles SET loyalty = ? WHERE id = ?", (new_loyalty, noble_id))

    conn.commit()

def calculate_attendance_probability(conn, noble_id, player_faction, event_type, event_season):
    """
    Рассчитывает вероятность посещения мероприятия дворянином.
    """
    cursor = conn.cursor()
    cursor.execute("SELECT name, ideology, attendance_history FROM nobles WHERE id = ?", (noble_id,))
    result = cursor.fetchone()

    if not result:
        return 1.0

    name, ideology_str, attendance_history = result
    noble_traits = get_noble_traits(ideology_str)

    TURNS_PAID_EFFECT_LASTS = 4
    RECENT_HISTORY_LENGTH = TURNS_PAID_EFFECT_LASTS

    if noble_traits['type'] == 'greed' and attendance_history:
        history_list = attendance_history.split(',')
        recent_history = history_list[-RECENT_HISTORY_LENGTH:]
        if 'P' in recent_history:
            return 1.0

    probability = 1.0

    if noble_traits['type'] == 'greed':
        return 0.4

    if noble_traits['type'] == 'ideology':
        player_ideology = get_player_ideology(conn)
        if noble_traits['value'] != player_ideology:
            probability *= 0.4

    if noble_traits['type'] == 'race_love':
        loved_race = noble_traits['value']
        season_to_race_map = {
            'Зима': 'Север', 'Весна': 'Эльфы', 'Лето': 'Элины', 'Осень': 'Вампиры'
        }
        event_race = season_to_race_map.get(event_season)
        if event_race and loved_race != event_race:
            relation = get_diplomacy_relation(conn, player_faction, loved_race)
            if relation in ['война', 'нейтралитет']:
                probability *= 0.4

    final_prob = max(0.0, min(1.0, probability))
    return final_prob

def update_noble_loyalty_for_event(conn, noble_id, player_faction, event_type, event_season):
    """
    Обновление лояльности конкретного советника после мероприятия.
    """
    cursor = conn.cursor()
    cursor.execute("SELECT loyalty, attendance_history, ideology FROM nobles WHERE id = ?", (noble_id,))
    result = cursor.fetchone()

    if not result:
        return

    loyalty, history_str, ideology_str = result

    attendance_prob = calculate_attendance_probability(conn, noble_id, player_faction, event_type, event_season)

    attended = random.random() < attendance_prob

    loyalty_change = 0
    if attended:
        loyalty_change = 2.0
    else:
        loyalty_change = -1.0

    new_loyalty = max(0.0, min(100.0, loyalty + loyalty_change))

    history_list = history_str.split(',') if history_str else []
    history_list.append('1' if attended else '0')
    if len(history_list) > 10:
        history_list = history_list[-10:]
    new_history_str = ','.join(history_list)

    cursor.execute("UPDATE nobles SET loyalty = ?, attendance_history = ? WHERE id = ?", (new_loyalty, new_history_str, noble_id))
    conn.commit()

def check_coup_attempts(conn):
    """
    Проверка попыток переворота.
    """
    cursor = conn.cursor()
    cursor.execute("SELECT id, loyalty, name FROM nobles WHERE status = 'active'")
    all_nobles = cursor.fetchall()

    disloyal_nobles = [(id, name) for id, loyalty, name in all_nobles if loyalty < 30]
    very_disloyal_nobles = [(id, name) for id, loyalty, name in all_nobles if loyalty < 15]

    coup_occurred = False

    if disloyal_nobles:
        if len(disloyal_nobles) >= 2 or len(very_disloyal_nobles) >= 1:
            success_chance = 0.5 if len(disloyal_nobles) >= 2 else 0.3

            if random.random() < success_chance:
                coup_occurred = True
                record_coup_attempt(conn, True)
                eliminated_names = []
                for noble_id, noble_name in disloyal_nobles:
                    cursor.execute("UPDATE nobles SET status = 'eliminated' WHERE id = ?", (noble_id,))
                    eliminated_names.append(noble_name)
                    faction_race = get_player_faction(conn)
                    if not faction_race:
                        faction_race = 'Север'
                    generate_new_noble(conn, faction_race)

                conn.commit()
                message = (f"Они прорвались! Уничтожены дворяне: {', '.join(eliminated_names)}.\n "
                           f"Но оставшиеся прорвались, нас заставили отречься от престола....мы ПРОИГРАЛИ...")
                show_coup_attempt_popup(successful=True, message_override=message)
            else:
                eliminated_names = []
                for noble_id, noble_name in disloyal_nobles:
                    cursor.execute("UPDATE nobles SET status = 'eliminated' WHERE id = ?", (noble_id,))
                    eliminated_names.append(noble_name)
                    faction_race = get_player_faction(conn)
                    if not faction_race:
                        faction_race = 'Север'
                    generate_new_noble(conn, faction_race)

                conn.commit()
                outcome = random.choice(['fear', 'indifferent', 'weakness'])
                if outcome == 'fear':
                    increase_all_loyalty(conn, 8.0)
                    message = f"Попытка переворота провалилась. Уничтожены дворяне: {', '.join(eliminated_names)}. Оперативность службы вызвала шок, лояльность повысилась на 8%. Кому еще не имется?"
                elif outcome == 'indifferent':
                    message = f"Попытка переворота провалилась. Уничтожены дворяне: {', '.join(eliminated_names)}. Ну и земля стекловатой, лояльность не изменилась."
                elif outcome == 'weakness':
                    decrease_all_loyalty(conn, 4.0)
                    message = f"Попытка переворота провалилась. Уничтожены дворяне: {', '.join(eliminated_names)}. Многие увидели в этом слабость, лояльность снизилась на 4%."
                show_coup_attempt_popup(successful=False, message_override=message)

    else:
        disloyal_count = sum(1 for _, loyalty, _ in all_nobles if loyalty < 30)
        very_disloyal_count = sum(1 for _, loyalty, _ in all_nobles if loyalty < 15)

        if disloyal_count >= 2:
            if random.random() < 0.5:
                coup_occurred = True
                record_coup_attempt(conn, True)
                show_coup_attempt_popup(successful=True)
            else:
                handle_failed_coup(conn, all_nobles)
        elif very_disloyal_count >= 1:
            if random.random() < 0.3:
                coup_occurred = True
                record_coup_attempt(conn, True)
                show_coup_attempt_popup(successful=True)
            else:
                handle_failed_coup(conn, all_nobles)

    return coup_occurred

def handle_failed_coup(conn, all_nobles):
    """
    Обработка неудачной попытки переворота.
    """
    cursor = conn.cursor()

    disloyal_nobles = [(id, name) for id, loyalty, name in all_nobles if loyalty < 30]
    if not disloyal_nobles:
        active_nobles = [(id, name) for id, _, name in all_nobles]
        if not active_nobles:
            return
        target_id, target_name = random.choice(active_nobles)
    else:
        target_id, target_name = random.choice(disloyal_nobles)

    cursor.execute("UPDATE nobles SET status = 'eliminated' WHERE id = ?", (target_id,))
    conn.commit()

    outcome = random.choice(['fear', 'indifferent', 'weakness'])

    if outcome == 'fear':
        increase_all_loyalty(conn, 8.0)
        message = f"Попытка переворота провалилась. {target_name} убит. Оперативность службы вызвала шок, лояльность повысилась на 8%. Кому еще не имется?"
    elif outcome == 'indifferent':
        message = f"Попытка переворота провалилась. {target_name} убит. Ну и земля стекловатой, лояльность не изменилась."
    elif outcome == 'weakness':
        decrease_all_loyalty(conn, 4.0)
        message = f"Попытка переворота провалилась. {target_name} убит. Многие увидели в этом слабость, лояльность снизилась на 4%."

    faction_race = get_player_faction(conn)
    if not faction_race:
        faction_race = 'Север'
    generate_new_noble(conn, faction_race)

    show_coup_attempt_popup(successful=False, message_override=message)

def show_coup_attempt_popup(successful=False, message_override=None):
    """Отображает popup с информацией о попытке переворота. (БЕЗ КНОПОК, авто-скрытие)"""
    try:
        is_android = UIStyles.is_android()

        # Адаптивные размеры (уменьшены для Android)
        font_title = sp(UIStyles.get_font_size(16, is_label=True))
        font_message = sp(UIStyles.get_font_size(12, is_label=True))
        padding_main = dp(15) if is_android else dp(20)
        spacing_main = dp(8) if is_android else dp(10)

        content = BoxLayout(orientation='vertical', padding=padding_main, spacing=spacing_main)

        # Фон карточки
        with content.canvas.before:
            Color(*UIStyles.COLOR_CARD)
            content.rect = RoundedRectangle(pos=content.pos, size=content.size, radius=[UIStyles.RADIUS])

        def update_rect(instance, value):
            content.rect.pos = instance.pos
            content.rect.size = instance.size
        content.bind(pos=update_rect, size=update_rect)

        if successful:
            title_text = "⚠ Переворот!"
            title_color = UIStyles.COLOR_DANGER
            message_text = message_override or "Тайная служба пресекла попытку государственного переворота!"
        else:
            title_text = "⚠ Переворот!"
            title_color = UIStyles.COLOR_WARNING
            message_text = message_override or "Тайная служба пресекла попытку переворота."

        title_label = Label(
            text=f"[b]{title_text}[/b]",
            font_size=font_title,
            markup=True,
            halign='center',
            valign='middle',
            size_hint_y=None,
            height=dp(35) if is_android else dp(40),
            color=title_color
        )
        title_label.bind(size=title_label.setter('text_size'))

        message_label = Label(
            text=message_text,
            font_size=font_message,
            halign='center',
            valign='middle',
            markup=True,
            color=UIStyles.COLOR_TEXT
        )
        message_label.bind(size=message_label.setter('text_size'))

        content.add_widget(title_label)
        content.add_widget(message_label)

        popup = Popup(
            title="",
            content=content,
            size_hint=UIStyles.get_popup_size(),
            pos_hint={'center_x': 0.5, 'center_y': 0.5},
            auto_dismiss=False,  # Отключаем авто-закрытие, управляем через Clock
            background_color=(0, 0, 0, 0.7),
            separator_height=0
        )

        def close_popup(dt):
            try:
                if popup._is_open:
                    popup.dismiss()
            except:
                pass

        popup.open()
        # Авто-закрытие через 1.5 секунды
        Clock.schedule_once(close_popup, 1.5)

    except Exception as e:
        print(f"Ошибка при отображении popup: {e}")

def update_nobles_periodically(conn, current_turn, events_count=0):
    """
    Периодическое обновление состояния дворян.
    """
    if current_turn % 1 == 0:
        update_loyalty_dynamically(conn)

    check_coup_attempts(conn)

    global SHOW_SYMPATHIES
    if events_count >= EVENT_COUNT_FOR_SYMPATHIES:
        SHOW_SYMPATHIES = True
    else:
        SHOW_SYMPATHIES = False

    if current_turn % 13 == 0 and current_turn > 0:
        change_noble_priorities(conn)
        SHOW_SYMPATHIES = False

def get_noble_display_name_with_sympathies(noble):
    """
    Возвращает имя дворянина с симпатиями в скобках.
    """
    name = noble['name']
    if not SHOW_SYMPATHIES:
        return name

    traits = get_noble_traits(noble['ideology'])

    if traits['type'] == 'greed':
        return name

    ideology_to_text = {
        'Борьба': " (Выжить можно только в Борьбе!)",
        'Смирение': " (Смирение залог процветания!)",
        'Любит Эльфы': " (Только Эльфы знают как жить в гармонии!)",
        'Любит Элины': " (Как же грациозен повелитель Элинов!)",
        'Любит Север': " (Север единственный баланс в мире!)",
        'Любит Вампиры': " (Наш мир принадлежит Вампирам!)",
        'Любит Адепты': " (Вера наше спасение!)",
    }

    sympathies = ideology_to_text.get(traits['value'], "")
    return name + sympathies

def update_loyalty_dynamically(conn):
    """Обновление лояльности всех дворян на основе их предпочтений."""
    cursor = conn.cursor()
    cursor.execute("SELECT id, loyalty, ideology FROM nobles WHERE status = 'active'")
    nobles = cursor.fetchall()

    player_faction = get_player_faction(conn)
    player_ideology = get_player_ideology(conn)

    for noble_id, current_loyalty, ideology_str in nobles:
        noble_traits = get_noble_traits(ideology_str)
        loyalty_change = 0

        loyalty_change -= 1.0

        if noble_traits['type'] == 'ideology':
            if noble_traits['value'] == player_ideology:
                loyalty_change += 2.0
            else:
                loyalty_change -= 1.0

        elif noble_traits['type'] == 'race_love':
            loved_race = noble_traits['value']
            loved_ideology = get_faction_ideology(conn, loved_race)
            if loved_ideology == player_ideology:
                loyalty_change += 2.0
            relation = get_diplomacy_relation(conn, player_faction, loved_race)
            try:
                if isinstance(relation, str) and relation.endswith('%'):
                    relation_value = int(relation.rstrip('%'))
                else:
                    relation_value = int(relation) if relation else 0
            except (ValueError, TypeError):
                relation_value = 0

            if relation_value >= 55:
                loyalty_change += 4.0
            else:
                loyalty_change -= 1.5

        elif noble_traits['type'] == 'greed':
            pass

        new_loyalty = max(0.0, min(100.0, current_loyalty + loyalty_change))
        cursor.execute("UPDATE nobles SET loyalty = ? WHERE id = ?", (new_loyalty, noble_id))

    conn.commit()

def change_noble_priorities(conn):
    """Смена приоритетов дворян каждые 13 ходов"""
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM nobles WHERE status = 'active'")
    noble_ids = [row[0] for row in cursor.fetchall()]

    if len(noble_ids) >= 2:
        new_priorities = list(range(len(noble_ids)))
        random.shuffle(new_priorities)

        for i, noble_id in enumerate(noble_ids):
            cursor.execute("UPDATE nobles SET priority = ? WHERE id = ?", (new_priorities[i], noble_id))

        conn.commit()
        print("Приоритеты дворян изменены.")

def get_all_nobles(conn):
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, priority, loyalty, status, name, ideology, attendance_history
        FROM nobles
        WHERE status = 'active'
        ORDER BY priority ASC
    """)
    rows = cursor.fetchall()
    nobles = []
    for row in rows:
        nobles.append({
            'id': row[0],
            'priority': row[1],
            'loyalty': row[2],
            'status': row[3],
            'name': row[4],
            'ideology': row[5],
            'attendance_history': row[6]
        })
    return nobles

def attempt_secret_service_action(conn, player_faction=None, target_noble_id=None):
    """
    Попытка устранения конкретного дворянина Тайной Службой.
    """
    cursor = conn.cursor()

    if target_noble_id is None:
        return {'success': False, 'message': "Цель не указана.", 'noble_name': None}

    cursor.execute("SELECT name FROM nobles WHERE id = ?", (target_noble_id,))
    name_result = cursor.fetchone()
    if not name_result:
        return {'success': False, 'message': "Цель не найдена.", 'noble_name': None}

    noble_name = name_result[0]

    cursor.execute("SELECT id FROM nobles WHERE id = ? AND status = 'active'", (target_noble_id,))
    result = cursor.fetchone()
    if not result:
        return {'success': False, 'message': f"{noble_name} недоступен или уже устранён.", 'noble_name': noble_name}

    noble_to_eliminate_id = target_noble_id

    success_chance = random.uniform(0.55, 0.70)
    is_success = random.random() <= success_chance

    if not is_success:
        is_discovered = random.random() <= 0.5
        if is_discovered:
            decrease_all_loyalty(conn, 11.0)
            return {
                'success': False,
                'message': f"Операция против {noble_name} провалена и раскрыта! Лояльность знати снизилась на 11%.",
                'noble_name': noble_name
            }
        else:
            return {
                'success': False,
                'message': f"Операция против {noble_name} провалена, но осталась незамеченной.",
                'noble_name': noble_name
            }

    cursor.execute(
        "UPDATE nobles SET status = 'eliminated' WHERE id = ?",
        (noble_to_eliminate_id,)
    )

    faction_race = get_player_faction(conn)
    if not faction_race:
        faction_race = 'Север'
    generate_new_noble(conn, faction_race)

    is_discovered = random.random() <= 0.5
    if is_discovered:
        increase_all_loyalty(conn, 6.0)
        message_suffix = " Операция раскрыта! Акция устрашения повысила лояльность парламента на 6%."
    else:
        message_suffix = " Операция прошла незамеченной."

    return {
        'success': True,
        'message': f"Цель {noble_name} успешно устранена.{message_suffix}",
        'noble_name': noble_name
    }

def show_secret_service_result_popup(result_dict):
    """Отображает popup с результатом операции Тайной Службы. (БЕЗ КНОПОК, авто-скрытие)"""
    is_android = UIStyles.is_android()

    # Адаптивные размеры (уменьшены для Android)
    font_title = sp(UIStyles.get_font_size(15, is_label=True))
    font_message = sp(UIStyles.get_font_size(11, is_label=True))
    padding_main = dp(13) if is_android else dp(20)
    spacing_main = dp(6) if is_android else dp(10)

    content = BoxLayout(orientation='vertical', padding=padding_main, spacing=spacing_main)

    # Фон карточки
    with content.canvas.before:
        Color(*UIStyles.COLOR_CARD)
        content.rect = RoundedRectangle(pos=content.pos, size=content.size, radius=[UIStyles.RADIUS])

    def update_rect(instance, value):
        content.rect.pos = instance.pos
        content.rect.size = instance.size
    content.bind(pos=update_rect, size=update_rect)

    if result_dict.get('success', False):
        title_text = "✓ Операция выполнена"
        title_color = UIStyles.COLOR_SUCCESS
    else:
        title_text = "✗ Операция провалена"
        title_color = UIStyles.COLOR_DANGER

    title_label = Label(
        text=f"[b]{title_text}[/b]",
        font_size=font_title,
        markup=True,
        halign='center',
        valign='middle',
        size_hint_y=None,
        height=dp(35) if is_android else dp(40),
        color=title_color
    )
    title_label.bind(size=title_label.setter('text_size'))

    message_label = Label(
        text=result_dict.get('message', 'Неизвестный результат операции'),
        font_size=font_message,
        halign='center',
        valign='middle',
        markup=True,
        color=UIStyles.COLOR_TEXT
    )
    message_label.bind(size=message_label.setter('text_size'))

    content.add_widget(title_label)
    content.add_widget(message_label)

    popup = Popup(
        title="",
        content=content,
        size_hint=UIStyles.get_popup_size(),
        pos_hint={'center_x': 0.5, 'center_y': 0.5},
        auto_dismiss=False,
        background_color=(0, 0, 0, 0.7),
        separator_height=0
    )

    def close_popup(dt):
        try:
            if popup._is_open:
                popup.dismiss()
        except:
            pass

    popup.open()
    # Авто-закрытие через 1.5 секунды
    Clock.schedule_once(close_popup, 1.5)

def increase_all_loyalty(conn, amount):
    """Повышение лояльности всех активных дворян."""
    cursor = conn.cursor()
    cursor.execute("UPDATE nobles SET loyalty = MIN(100.0, loyalty + ?) WHERE status = 'active'", (amount,))
    conn.commit()

def decrease_all_loyalty(conn, amount):
    """Снижение лояльности всех активных дворян."""
    cursor = conn.cursor()
    cursor.execute("UPDATE nobles SET loyalty = MAX(0.0, loyalty - ?) WHERE status = 'active'", (amount,))
    conn.commit()

def pay_greedy_noble(conn, noble_id, amount):
    """
    Обрабатывает оплату продажному дворянину.
    """
    cursor = conn.cursor()

    cursor.execute("SELECT ideology FROM nobles WHERE id = ?", (noble_id,))
    result = cursor.fetchone()

    if not result:
        print(f"Ошибка: Дворянин с ID {noble_id} не найден.")
        return False

    ideology_str = result[0]
    noble_traits = get_noble_traits(ideology_str)

    if noble_traits['type'] != 'greed':
        print(f"Ошибка: Дворянин с ID {noble_id} не является продажным.")
        return False

    required_amount = noble_traits.get('demand', 0)
    if amount < required_amount:
        print(f"Ошибка: Предложена сумма {amount}, требуется {required_amount}.")

    cursor.execute("SELECT attendance_history FROM nobles WHERE id = ?", (noble_id,))
    history_result = cursor.fetchone()
    current_history = history_result[0] if history_result and history_result[0] else ""

    history_list = current_history.split(',') if current_history else []
    history_list.append('P')

    MAX_HISTORY_LENGTH = 20
    if len(history_list) > MAX_HISTORY_LENGTH:
        history_list = history_list[-MAX_HISTORY_LENGTH:]

    new_history_str = ','.join(history_list)

    cursor.execute("UPDATE nobles SET attendance_history = ? WHERE id = ?", (new_history_str, noble_id))
    conn.commit()

    return True

def process_nobles_turn(conn, current_turn):
    """Обработка хода для дворян."""
    update_nobles_periodically(conn, current_turn)