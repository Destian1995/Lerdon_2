# ai_models/diplomacy_chat.py
import random
import re

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.utils import platform as kivy_platform

from kivy.uix.textinput import TextInput
from kivy.uix.spinner import Spinner
from kivy.graphics import Color, Rectangle, RoundedRectangle, Line
from kivy.core.window import Window, Animation
from kivy.metrics import dp
from kivy.clock import Clock
from datetime import datetime

from .manipulation_strategy import ManipulationStrategy
import platform
from .android_keyboard import AndroidKeyboardHelper

class EnhancedDiplomacyChat():
    """Улучшенная версия дипломатического чата с адаптацией для Android"""

    def __init__(self, advisor_view, db_connection):
        self.advisor = advisor_view
        self.db_connection = db_connection
        self.faction = advisor_view.faction

        # Инициализируем стратегию манипуляций
        self.manipulation_strategy = ManipulationStrategy()

        # Контекст переговоров
        self.negotiation_context = {}

        # Активные переговоры
        self.active_negotiations = {}

        # История предложений в текущей сессии
        self.current_offers = {}

        # Память о предыдущих разговорах (последние 10 сообщений)
        self.conversation_memory = []

        # Эмоциональное состояние ИИ
        self.emotional_state = {
            'mood': 'neutral',  # neutral, happy, angry, suspicious, friendly
            'trust_level': 50,  # 0-100
            'patience': 100     # 0-100, уменьшается при повторяющихся вопросах
        }

        # Инициализация помощника для Android клавиатуры
        self.keyboard_helper = AndroidKeyboardHelper(self)

        # Ссылки на UI элементы
        self.chat_scroll = None
        self.chat_container = None
        self.message_input = None
        self.faction_spinner = None
        self.chat_title = None
        self.relation_display = None
        self.trade_history_label = None

        # Фразы фракций (без изменений)
        self.faction_phrases = {
            "Эльфы": {
                "war_declaration": "Еще один решил что может гадить в наших лесах!",
                "alliance": "Природа восторжествует!",
                "peace": "Мир в лесах восстановлен.",
                "rejection": "Деревья шепчут об осторожности..."
            },
            "Север": {
                "war_declaration": "Грядет холодный ветер перемен...",
                "alliance": "Светлого неба!",
                "peace": "Да стихнет буря...",
                "rejection": "Снежная буря заставляет быть осторожным."
            },
            "Адепты": {
                "war_declaration": "Смерть еретикам!",
                "alliance": "Да хранит нас Бог!",
                "peace": "Божья воля исполнена.",
                "rejection": "Нам нужно время для молитвы."
            },
            "Элины": {
                "war_declaration": "Песок поглотит Вас...",
                "alliance": "Огонь пустыни защитит Вас!",
                "peace": "Знойный ветер утих.",
                "rejection": "В пустыне нужно взвешивать каждый шаг."
            },
            "Вампиры": {
                "war_declaration": "Что с головушкой совсем беда? Ну ничего....исправим..",
                "alliance": "Теплокровных оставьте нам...",
                "peace": "Кровь больше не будет проливаться.",
                "rejection": "Ночь еще не наступила для таких решений."
            }
        }

    def update_emotional_state(self, message, relation_level):
        """Обновляет эмоциональное состояние ИИ на основе сообщения"""
        message_lower = message.lower()

        # Анализируем тон сообщения
        if any(word in message_lower for word in ['спасибо', 'благодарю', 'хорошо', 'отлично']):
            self.emotional_state['mood'] = 'happy'
            self.emotional_state['trust_level'] = min(100, self.emotional_state['trust_level'] + 5)
        elif any(word in message_lower for word in ['ублюдок', 'сука', 'пошел', 'заткнись', 'идиот']):
            self.emotional_state['mood'] = 'angry'
            self.emotional_state['trust_level'] = max(0, self.emotional_state['trust_level'] - 10)
            self.emotional_state['patience'] = max(0, self.emotional_state['patience'] - 15)
        elif any(word in message_lower for word in ['обман', 'лжешь', 'не верю']):
            self.emotional_state['mood'] = 'suspicious'
            self.emotional_state['trust_level'] = max(0, self.emotional_state['trust_level'] - 5)

        # Проверяем на повторяющиеся вопросы
        if len(self.conversation_memory) > 1:
            last_messages = [msg['player'] for msg in self.conversation_memory[-3:]]
            if all(msg.lower().strip() == message_lower.strip() for msg in last_messages):
                self.emotional_state['patience'] = max(0, self.emotional_state['patience'] - 20)

        # Восстанавливаем терпение со временем
        self.emotional_state['patience'] = min(100, self.emotional_state['patience'] + 1)

    def add_to_memory(self, player_message, ai_response):
        """Добавляет сообщение в память разговора"""
        self.conversation_memory.append({
            'player': player_message,
            'ai': ai_response,
            'timestamp': datetime.now(),
            'relation_level': None  # будет заполнено позже
        })

        # Ограничиваем память последними 10 сообщениями
        if len(self.conversation_memory) > 10:
            self.conversation_memory.pop(0)

    def get_contextual_response(self, base_response, relation_level):
        """Добавляет контекстуальную окраску к ответу на основе эмоционального состояния"""
        mood = self.emotional_state['mood']
        patience = self.emotional_state['patience']

        # Модификаторы ответа
        if mood == 'happy' and relation_level > 50:
            modifiers = ["", " 😊", " Рад слышать!", " Отлично!"]
            base_response += random.choice(modifiers)
        elif mood == 'angry':
            modifiers = ["", " 😠", " Не зли меня!", " Хватит!"]
            base_response += random.choice(modifiers)
        elif patience < 30:
            modifiers = ["", " (устал повторять)", " Опять то же самое...", " Слушай внимательно!"]
            base_response += random.choice(modifiers)

        return base_response

    def contextual_return(self, response, relation_level):
        """Обертка для возврата ответа с контекстуальной окраской"""
        return self.get_contextual_response(response, relation_level)

    def open_diplomacy_window(self):
        """Открывает окно дипломатических переговоров (адаптировано для Android)"""
        # Теперь этот метод создает содержимое для таба
        return self.create_chat_interface()

    def create_control_panel_android(self):
        """Создает панель управления для Android (расположена внизу)"""
        panel = BoxLayout(
            orientation='vertical',
            size_hint=(1, None),
            height=dp(120) if kivy_platform == 'android' else dp(140),
            spacing=dp(6),
            padding=[dp(10), dp(8)]
        )

        # Верхняя строка: выбор фракции
        faction_row = BoxLayout(
            orientation='horizontal',
            size_hint=(1, 0.4),
            spacing=dp(8)
        )

        faction_label = Label(
            text="Фракция:",
            font_size='14sp',
            color=(0.8, 0.8, 0.9, 1),
            size_hint=(0.3, 1),
            valign='middle'
        )

        self.faction_spinner = Spinner(
            text='Выберите фракцию',
            values=[],
            size_hint=(0.7, 1),
            background_color=(0.2, 0.3, 0.5, 1),
            font_size='14sp',
            background_normal='',
            background_down=''
        )

        # Заполняем список фракций из базы данных
        factions = self.load_factions_from_db()
        if factions:
            for faction in factions:
                if faction != self.faction:
                    self.faction_spinner.values.append(faction)

            if not self.faction_spinner.values:
                self.faction_spinner.text = "Нет доступных фракций"
                self.faction_spinner.disabled = True
        else:
            # Фолбэк — загружаем живые фракции из городов
            try:
                _cur = self.db_connection.cursor()
                _cur.execute("SELECT DISTINCT faction FROM cities WHERE faction != 'Нейтрал' AND faction != 'Мятежники' AND faction != 'Нежить'")
                for _row in _cur.fetchall():
                    if _row[0] != self.faction:
                        self.faction_spinner.values.append(_row[0])
            except Exception:
                pass

        self.faction_spinner.bind(text=self.on_faction_selected_android)

        # Автовыбор фракции если передана через уведомление
        preselect = getattr(self.advisor, 'preselect_faction', None)
        if preselect and preselect in self.faction_spinner.values:
            self.faction_spinner.text = preselect

        faction_row.add_widget(faction_label)
        faction_row.add_widget(self.faction_spinner)

        # Средняя строка: информация об отношениях
        info_row = BoxLayout(
            orientation='horizontal',
            size_hint=(1, 0.3),
            spacing=dp(8)
        )

        self.relation_info_label = Label(
            text="Выберите фракцию для отображения отношений",
            font_size='13sp',
            color=(0.7, 0.7, 0.8, 1),
            halign='center',
            valign='middle'
        )
        self.relation_info_label.bind(size=self.relation_info_label.setter('text_size'))

        info_row.add_widget(self.relation_info_label)

        # Нижняя строка: кнопка подробной информации
        button_row = BoxLayout(
            orientation='horizontal',
            size_hint=(1, 0.3),
            spacing=dp(8)
        )

        # Кнопка подробной информации
        info_button = Button(
            text="Подробнее об отношениях",
            size_hint=(1, 1),
            background_normal='',
            background_color=(0.3, 0.3, 0.5, 0.7),
            font_size='12sp',
            on_press=self.show_relation_info
        )
        button_row.add_widget(info_button)

        panel.add_widget(faction_row)
        panel.add_widget(info_row)
        panel.add_widget(button_row)

        # Фон панели
        with panel.canvas.before:
            Color(0.12, 0.12, 0.18, 1)
            bg = Rectangle(pos=panel.pos, size=panel.size)

        panel.bind(
            pos=lambda i, v: setattr(bg, 'pos', v),
            size=lambda i, v: setattr(bg, 'size', v)
        )

        return panel

    def create_input_panel_android(self):
        """Создает панель ввода для Android"""
        panel = BoxLayout(
            orientation='horizontal',
            size_hint=(1, None),
            height=dp(56) if kivy_platform == 'android' else dp(50),
            spacing=dp(8),
            padding=[dp(8), dp(6)]
        )

        # Поле ввода
        textinput_kwargs = {
            'hint_text': "Введите сообщение...",
            'multiline': False,
            'background_normal': '',
            'background_active': '',
            'background_color': (0.18, 0.18, 0.25, 1),
            'foreground_color': (1, 1, 1, 1),
            'cursor_color': (0.5, 0.7, 1, 1),
            'padding': [dp(12), dp(10)],
            'font_size': '16sp',
            'write_tab': False,
        }

        if kivy_platform == 'android':
            textinput_kwargs['keyboard_mode'] = 'managed'

        self.message_input = TextInput(**textinput_kwargs)

        # Вместо RoundedRectangle используем Line для рамки
        with self.message_input.canvas.after:
            Color(0.3, 0.3, 0.4, 1)
            # Создаем линию как рамку
            border_line = Line(
                rectangle=[self.message_input.x, self.message_input.y,
                           self.message_input.width, self.message_input.height],
                width=1
            )

        self.message_input.bind(
            pos=lambda i, v: setattr(border_line, 'rectangle',
                                     [i.x, i.y, i.width, i.height]),
            size=lambda i, v: setattr(border_line, 'rectangle',
                                      [i.x, i.y, i.width, i.height]),
            focus=lambda i, v: setattr(border_line, 'width', 2 if v else 1)  # Теперь работает
        )

        # Кнопка отправки
        send_btn = Button(
            text=">",
            size_hint=(None, 1),
            width=dp(50),
            background_normal='',
            background_color=(0.25, 0.5, 0.9, 1),
            font_size='20sp',
            bold=True
        )
        send_btn.bind(on_press=self.send_diplomatic_message)

        # Обработка фокуса для Android
        if kivy_platform == 'android':
            self.message_input.bind(focus=self._on_textinput_focus_android)

        panel.add_widget(self.message_input)
        panel.add_widget(send_btn)

        # Фон панели
        with panel.canvas.before:
            Color(0.14, 0.14, 0.2, 1)
            bg = Rectangle(pos=panel.pos, size=panel.size)

        panel.bind(
            pos=lambda i, v: setattr(bg, 'pos', v),
            size=lambda i, v: setattr(bg, 'size', v)
        )

        return panel

    def create_chat_area_android(self):
        """Создает основную область чата для Android"""
        chat_area = BoxLayout(
            orientation='vertical',
            size_hint=(1, 1),
            spacing=dp(2)
        )

        # Контейнер для истории чата
        chat_container = BoxLayout(
            orientation='vertical',
            size_hint=(1, 1)
        )

        # ScrollView для истории чата
        self.chat_scroll = ScrollView(
            size_hint=(1, 1),
            do_scroll_x=False,
            bar_width=dp(8),
            scroll_type=['bars', 'content'],
            effect_cls='ScrollEffect',
            bar_color=(0.3, 0.3, 0.5, 0.7),
            bar_inactive_color=(0.3, 0.3, 0.5, 0.3)
        )

        # Контейнер для сообщений
        self.chat_container = BoxLayout(
            orientation='vertical',
            size_hint_y=None,
            spacing=dp(8),
            padding=[dp(8), dp(8), dp(8), dp(8)]
        )
        self.chat_container.bind(minimum_height=self.chat_container.setter('height'))

        self.chat_scroll.add_widget(self.chat_container)
        chat_container.add_widget(self.chat_scroll)
        chat_area.add_widget(chat_container)

        return chat_area

    def _get_faction_resources(self, faction):
        """Получает точные данные о ресурсах фракции из базы данных"""
        try:
            cursor = self.db_connection.cursor()
            cursor.execute("""
                SELECT resource_type, amount 
                FROM resources 
                WHERE faction = ? 
                AND resource_type IN ('Кроны', 'Кристаллы', 'Рабочие')
            """, (faction,))
            resources = {row[0]: row[1] for row in cursor.fetchall()}
            # Убедимся, что все ресурсы присутствуют
            for res_type in ['Кроны', 'Кристаллы', 'Рабочие']:
                if res_type not in resources:
                    resources[res_type] = 0
            return resources
        except Exception as e:
            print(f"Ошибка при получении ресурсов для {faction}: {e}")
            return {'Кроны': 0, 'Кристаллы': 0, 'Рабочие': 0}

    def _is_resource_inquiry(self, message):
        """Определяет, является ли сообщение вопросом о количестве ресурсов"""
        message_lower = message.lower().strip()

        # Ключевые слова для вопросов
        question_words = ['че по', 'че с', 'сколько', 'как много', 'какое количество', 'есть ли', 'хватает ли', 'что с', 'есть']
        has_question = any(word in message_lower for word in question_words)

        if not has_question:
            return False

        # Типы ресурсов
        resource_keywords = {
            'all': ['ресурс', 'ресурсов', 'ресурсами', 'всего', 'всё', 'все ресурсы', 'положение с ресурсами', 'ресы', 'ресам'],
            'Кроны': ['крон', 'золот', 'деньг', 'монет', 'казна', 'финанс', 'капитал', 'денег'],
            'Кристаллы': ['кристалл', 'кристал', 'кристалов', 'минерал', 'камн'],
            'Рабочие': ['рабоч', 'люд', 'крестьян', 'работник']
        }

        # Проверяем упоминание любого ресурса
        for res_type, keywords in resource_keywords.items():
            if any(keyword in message_lower for keyword in keywords):
                return True

        return False

    def _handle_resource_inquiry(self, message, faction, relation_level):
        """Обрабатывает вопросы о количестве ресурсов с учётом уровня отношений"""
        message_lower = message.lower()

        # Определяем тип запрашиваемого ресурса
        resource_type = None
        if any(word in message_lower for word in ['крон', 'золот', 'деньг', 'монет', 'казна']):
            resource_type = 'Кроны'
        elif any(word in message_lower for word in ['кристалл', 'руда', 'минерал', 'камн']):
            resource_type = 'Кристаллы'
        elif any(word in message_lower for word in ['рабоч', 'люд', 'крестьян', 'работник']):
            resource_type = 'Рабочие'
        else:
            resource_type = 'all'  # Все ресурсы

        # Получаем реальные ресурсы
        real_resources = self._get_faction_resources(faction)

        # При плохих отношениях (<30) — дезинформация или отказ
        if relation_level < 30:
            deception_type = random.choice(['refuse', 'lie_small', 'lie_big'])

            if deception_type == 'refuse':
                responses = [
                    "Мои ресурсы — не твоё дело!",
                    "Думаешь, я буду раскрывать тебе свои секреты? Ха!",
                    "Иди узнай сам, если сможешь!",
                    "Ты мне не друг, чтобы я рассказывал о своих ресурсах.",
                    "Заткнись и убирайся со своими вопросами!"
                ]
                return random.choice(responses)

            elif deception_type == 'lie_small':
                # Небольшая дезинформация (±20%)
                fake_resources = {
                    'Кроны': int(real_resources['Кроны'] * random.uniform(0.8, 1.2)),
                    'Кристаллы': int(real_resources['Кристаллы'] * random.uniform(0.8, 1.2)),
                    'Рабочие': int(real_resources['Рабочие'] * random.uniform(0.8, 1.2))
                }
                if resource_type == 'all':
                    return (f"У меня есть {fake_resources['Кроны']:,} крон, "
                            f"{fake_resources['Кристаллы']:,} кристаллов и "
                            f"{fake_resources['Рабочие']:,} рабочих. Доволен?")
                else:
                    return f"У меня {fake_resources[resource_type]:,} {resource_type.lower()}."

            else:  # lie_big
                # Сильная дезинформация (завышение в 2-5 раз)
                multiplier = random.uniform(2.0, 5.0)
                fake_amount = int(real_resources[resource_type if resource_type != 'all' else 'Кроны'] * multiplier)
                if resource_type == 'all':
                    return (f"Мои казны переполнены! {int(real_resources['Кроны'] * multiplier):,} крон, "
                            f"{int(real_resources['Кристаллы'] * multiplier):,} кристаллов, "
                            f"{int(real_resources['Рабочие'] * multiplier):,} рабочих! Завидуешь?")
                else:
                    return f"У меня {fake_amount:,} {resource_type.lower()}! Хочешь позавидовать?"

        # При нейтральных отношениях (30-69) — честный ответ, но без энтузиазма
        elif 30 <= relation_level < 70:
            if resource_type == 'all':
                return (f"У меня есть {real_resources['Кроны']:,} крон, "
                        f"{real_resources['Кристаллы']:,} кристаллов и "
                        f"{real_resources['Рабочие']:,} рабочих.")
            else:
                return f"У меня {real_resources[resource_type]:,} {resource_type.lower()}."

        # При хороших отношениях (70-89) — честный ответ + дополнительная информация
        elif 70 <= relation_level < 90:
            if resource_type == 'all':
                responses = [
                    f"Рад поделиться: {real_resources['Кроны']:,} крон, {real_resources['Кристаллы']:,} кристаллов, {real_resources['Рабочие']:,} рабочих. Всё в порядке!",
                    f"На данный момент в казне {real_resources['Кроны']:,} крон, в хранилищах {real_resources['Кристаллы']:,} кристаллов, и {real_resources['Рабочие']:,} рабочих трудятся на благо фракции.",
                    f"Могу сказать точно: крон — {real_resources['Кроны']:,}, кристаллов — {real_resources['Кристаллы']:,}, рабочих — {real_resources['Рабочие']:,}."
                ]
                return random.choice(responses)
            else:
                responses = {
                    'Кроны': [
                        f"В казне {real_resources['Кроны']:,} крон. Хватает на текущие нужды.",
                        f"Крон в наличии: {real_resources['Кроны']:,}. Ситуация стабильна.",
                        f"На счету {real_resources['Кроны']:,} золотых монет."
                    ],
                    'Кристаллы': [
                        f"Кристаллов в хранилищах: {real_resources['Кристаллы']:,}.",
                        f"Магических кристаллов: {real_resources['Кристаллы']:,}. Достаточно для нужд.",
                        f"Запас кристаллов составляет {real_resources['Кристаллы']:,}."
                    ],
                    'Рабочие': [
                        f"Рабочих трудится {real_resources['Рабочие']:,}.",
                        f"Население активных рабочих: {real_resources['Рабочие']:,} душ.",
                        f"Рабочая сила: {real_resources['Рабочие']:,} человек."
                    ]
                }
                return random.choice(responses.get(resource_type, [
                    f"У меня {real_resources[resource_type]:,} {resource_type.lower()}."]))

        # При отличных отношениях (90+) — максимально открытый и дружелюбный ответ
        else:
            if resource_type == 'all':
                responses = [
                    f"Для тебя расскажу всё! Крон: {real_resources['Кроны']:,}, кристаллов: {real_resources['Кристаллы']:,}, рабочих: {real_resources['Рабочие']:,}. Можешь на меня положиться!",
                    f"Мой друг, у меня {real_resources['Кроны']:,} крон в казне, {real_resources['Кристаллы']:,} кристаллов в хранилищах и {real_resources['Рабочие']:,} верных рабочих. Всё прозрачно между нами!",
                    f"Как у брата: крон — {real_resources['Кроны']:,}, кристаллов — {real_resources['Кристаллы']:,}, рабочих — {real_resources['Рабочие']:,}."
                ]
                return random.choice(responses)
            else:
                friendly_responses = {
                    'Кроны': [
                        f"Для тебя без секретов: в казне {real_resources['Кроны']:,} крон!",
                        f"Золота у меня {real_resources['Кроны']:,} монет. Можешь не сомневаться!",
                        f"Крон в наличии: {real_resources['Кроны']:,}. Всё честно!"
                    ],
                    'Кристаллы': [
                        f"Кристаллов у меня {real_resources['Кристаллы']:,}. Сияют как никогда!",
                        f"В хранилищах {real_resources['Кристаллы']:,} кристаллов. Можешь проверить сам!",
                        f"Магических кристаллов: {real_resources['Кристаллы']:,}. Полный порядок!"
                    ],
                    'Рабочие': [
                        f"Рабочих трудится {real_resources['Рабочие']:,}. Все верны и преданы!",
                        f"Наш народ: {real_resources['Рабочие']:,} трудолюбивых рабочих!",
                        f"Рабочая сила в полном объёме: {real_resources['Рабочие']:,} человек."
                    ]
                }
                return random.choice(friendly_responses.get(resource_type, [
                    f"У меня {real_resources[resource_type]:,} {resource_type.lower()}."]))

    def _on_textinput_focus_android(self, instance, value):
        """Обработка фокуса для Android с адаптивной прокруткой"""
        if kivy_platform != 'android':
            return

        if value:  # Если поле получило фокус
            # Даем время клавиатуре появиться
            Clock.schedule_once(lambda dt: self._adjust_for_keyboard_android(), 0.2)
        else:
            # При скрытии клавиатуры возвращаем нормальную прокрутку
            Clock.schedule_once(lambda dt: self.scroll_chat_to_bottom(), 0.1)

    def _adjust_for_keyboard_android(self):
        """Адаптирует интерфейс при появлении клавиатуры на Android"""
        if not hasattr(self, 'chat_scroll'):
            return

        try:
            # Прокручиваем немного вверх, чтобы поле ввода было видно
            if hasattr(self.chat_scroll, 'scroll_y'):
                Animation(scroll_y=0.1, duration=0.1).start(self.chat_scroll)
        except:
            pass

    def on_faction_selected_android(self, spinner, text):
        """Обработчик выбора фракции для Android"""
        if text and text != 'Выберите фракцию':
            self.selected_faction = text
            self.update_relation_info_android(text)
            self.load_chat_history()

    def update_relation_info_android(self, faction):
        """Обновляет информацию об отношениях для Android"""
        if not hasattr(self, 'relation_info_label'):
            return

        relations = self.advisor.relations_manager.load_combined_relations()
        relation_data = relations.get(faction, {"relation_level": 50, "status": "нейтралитет"})

        try:
            relation_level = int(relation_data["relation_level"])
        except (ValueError, TypeError, KeyError):
            relation_level = 50

        coefficient = self.calculate_coefficient(relation_level)
        status = relation_data.get('status', 'нейтралитет')

        # Форматируем текст
        if coefficient == 0:
            coefficient_text = " (сделки невозможны)"
        else:
            coefficient_text = f" (сделки 1×{coefficient:.1f})"

        self.relation_info_label.text = f"Отношения: {relation_level}/100{coefficient_text}"

        # Цвет в зависимости от отношений
        if coefficient == 0:
            color = (0.8, 0.1, 0.1, 1)  # Красный
        elif coefficient < 0.7:
            color = (1.0, 0.5, 0.0, 1)  # Оранжевый
        elif coefficient < 1.0:
            color = (1.0, 0.8, 0.0, 1)  # Желтый
        elif coefficient < 1.5:
            color = (0.2, 0.7, 0.3, 1)  # Зеленый
        else:
            color = (0.1, 0.3, 0.9, 1)  # Синий

        self.relation_info_label.color = color


    def add_chat_message(self, message, sender, timestamp, is_player=False):
        """Добавляет сообщение в чат (с автоматическим выбором версии)"""
        if kivy_platform == 'android':
            return self.add_chat_message_android(message, sender, timestamp, is_player)

        # Десктопная версия
        max_width = Window.width * 0.65

        temp = Label(
            text=message,
            font_size='13sp',
            text_size=(max_width - dp(24), None)
        )
        temp.texture_update()
        text_height = temp.texture_size[1]

        bubble = BoxLayout(
            orientation='vertical',
            size_hint=(None, None),
            width=min(max_width, temp.texture_size[0] + dp(30)),
            height=text_height + dp(36),
            padding=[dp(12), dp(10)],
            pos_hint={'right': 1} if is_player else {'x': 0}
        )

        bg_color = (0.22, 0.42, 0.8, 1) if is_player else (0.28, 0.28, 0.36, 1)

        with bubble.canvas.before:
            Color(*bg_color)
            bg = RoundedRectangle(pos=bubble.pos, size=bubble.size, radius=[dp(10)])

        bubble.bind(
            pos=lambda i, v: setattr(bg, 'pos', v),
            size=lambda i, v: setattr(bg, 'size', v)
        )

        text_label = Label(
            text=message,
            font_size='13sp',
            color=(1, 1, 1, 1),
            halign='left',
            valign='top',
            text_size=(bubble.width - dp(24), None)
        )
        text_label.bind(
            size=lambda i, v: setattr(i, 'text_size', (v[0], None))
        )

        time_label = Label(
            text=timestamp,
            font_size='10sp',
            color=(0.7, 0.7, 0.7, 1),
            size_hint=(1, None),
            height=dp(14),
            halign='right'
        )

        bubble.add_widget(text_label)
        bubble.add_widget(time_label)

        self.chat_container.add_widget(bubble)
        Clock.schedule_once(lambda dt: self.scroll_chat_to_bottom(), 0)

    def add_chat_message_android(self, message, sender, timestamp, is_player=False):
        """Добавляет сообщение в чат (специальная версия для Android)"""
        max_width = Window.width * 0.85  # Шире для мобильных

        # Вычисляем высоту текста
        temp = Label(
            text=message,
            font_size='14sp',  # Чуть больше для мобильных
            text_size=(max_width - dp(20), None)
        )
        temp.texture_update()
        text_height = temp.texture_size[1]

        # Минимальная высота для коротких сообщений
        min_height = dp(50) if kivy_platform == 'android' else dp(40)
        bubble_height = max(min_height, text_height + dp(28))

        # Создаем контейнер для сообщения
        bubble = BoxLayout(
            orientation='vertical',
            size_hint=(None, None),
            width=min(max_width, temp.texture_size[0] + dp(24)),
            height=bubble_height,
            padding=[dp(10), dp(8)],
            pos_hint={'right': 0.95} if is_player else {'x': 0.05}  # Отступы от краев
        )

        # Цвет фона в зависимости от отправителя
        bg_color = (0.22, 0.42, 0.8, 1) if is_player else (0.28, 0.28, 0.36, 1)

        with bubble.canvas.before:
            Color(*bg_color)
            bg = RoundedRectangle(pos=bubble.pos, size=bubble.size, radius=[dp(12)])

        bubble.bind(
            pos=lambda i, v: setattr(bg, 'pos', v),
            size=lambda i, v: setattr(bg, 'size', v)
        )

        # Текст сообщения
        text_label = Label(
            text=message,
            font_size='14sp',
            color=(1, 1, 1, 1),
            halign='left',
            valign='top',
            text_size=(bubble.width - dp(20), None),
            size_hint=(1, 1)
        )

        # Время отправки (компактное)
        time_label = Label(
            text=timestamp,
            font_size='10sp',
            color=(0.7, 0.7, 0.7, 0.9),
            size_hint=(1, None),
            height=dp(14),
            halign='right'
        )

        bubble.add_widget(text_label)
        bubble.add_widget(time_label)

        # Добавляем сообщение в контейнер
        self.chat_container.add_widget(bubble)

        # Прокручиваем вниз (задержка для Android)
        Clock.schedule_once(lambda dt: self.scroll_chat_to_bottom_android(), 0.05)

    def scroll_chat_to_bottom_android(self):
        """Прокручивает чат вниз (оптимизированная для Android версия)"""
        if self.chat_scroll and hasattr(self.chat_scroll, 'scroll_y'):
            try:
                # Быстрая прокрутка без анимации для Android
                self.chat_scroll.scroll_y = 0
            except:
                pass

    # ОСТАЛЬНЫЕ МЕТОДЫ (БЕЗ ИЗМЕНЕНИЙ, КРОМЕ НЕБОЛЬШИХ АДАПТАЦИЙ)

    def load_chat_history(self):
        """Загружает историю переписки (адаптированная для Android)"""
        if not hasattr(self, 'selected_faction') or not self.selected_faction:
            return

        # Очищаем текущие сообщения
        self.chat_container.clear_widgets()

        # Добавляем системное сообщение о начале переписки
        self.add_chat_message_system(f"Начало переписки с {self.selected_faction}")

        try:
            cursor = self.db_connection.cursor()
            cursor.execute('''
                SELECT message, is_player, timestamp 
                FROM negotiation_history 
                WHERE (faction1 = ? AND faction2 = ?) 
                   OR (faction1 = ? AND faction2 = ?)
                ORDER BY timestamp ASC
                LIMIT 50
            ''', (self.faction, self.selected_faction, self.selected_faction, self.faction))

            history = cursor.fetchall()

            if history:
                for message, is_player, timestamp in history:
                    # Форматируем дату для мобильных
                    try:
                        dt = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')
                        if kivy_platform == 'android':
                            formatted_time = dt.strftime("%H:%M")  # Только время
                        else:
                            formatted_time = dt.strftime("%d.%m %H:%M")
                    except:
                        formatted_time = timestamp

                    # Определяем отправителя
                    if bool(is_player):
                        sender = self.faction
                        is_player_msg = True
                    else:
                        sender = self.selected_faction
                        is_player_msg = False

                    # Добавляем сообщение в чат
                    self.add_chat_message(
                        message=message,
                        sender=sender,
                        timestamp=formatted_time,
                        is_player=is_player_msg
                    )

            else:
                self.add_chat_message_system("История переписки пуста. Отправьте первое сообщение!")

        except Exception as e:
            print(f"Ошибка при загрузке истории чата: {e}")
            self.add_chat_message_system("Ошибка загрузки истории")

    def add_chat_message_system(self, message):
        """Добавляет системное сообщение (адаптированное)"""
        box = BoxLayout(
            size_hint=(0.95, None),
            padding=[dp(10), dp(6)],
            pos_hint={'center_x': 0.5}
        )

        label = Label(
            text=message,
            font_size='12sp',
            color=(1, 1, 0.8, 1),
            halign='center',
            valign='middle',
            text_size=(Window.width * 0.9, None)
        )
        label.texture_update()
        box.height = label.texture_size[1] + dp(16)

        with box.canvas.before:
            Color(0.18, 0.18, 0.28, 1)
            bg = RoundedRectangle(pos=box.pos, size=box.size, radius=[dp(8)])

        box.bind(
            pos=lambda i, v: setattr(bg, 'pos', v),
            size=lambda i, v: setattr(bg, 'size', v)
        )

        box.add_widget(label)
        self.chat_container.add_widget(box)

        # Прокручиваем вниз
        if kivy_platform == 'android':
            Clock.schedule_once(lambda dt: self.scroll_chat_to_bottom_android(), 0.05)
        else:
            Clock.schedule_once(lambda dt: self.scroll_chat_to_bottom(), 0)

    def scroll_chat_to_bottom(self):
        """Прокручивает чат вниз - с плавной анимацией (десктоп)"""
        if self.chat_scroll and hasattr(self.chat_scroll, 'scroll_y'):
            try:
                Animation(scroll_y=0, duration=0.3).start(self.chat_scroll)
            except:
                self.chat_scroll.scroll_y = 0

    def _scroll_to_input_android(self):
        """Прокручивает чат так, чтобы поле ввода было видно над клавиатурой"""
        if not hasattr(self, 'chat_scroll') or not self.chat_scroll:
            return

        try:
            # Прокручиваем в самый низ
            self.scroll_chat_to_bottom()

            # Дополнительная прокрутка для уверенности
            if hasattr(self.chat_scroll, 'scroll_y'):
                Animation(scroll_y=0, duration=0.2).start(self.chat_scroll)
        except:
            pass

    def create_status_panel(self):
        """Создает панель статуса"""
        status_panel = BoxLayout(
            orientation='horizontal',
            size_hint=(1, None),
            height=dp(30),
            padding=[dp(15), 0],
            pos_hint={'bottom': 1}
        )

        self.chat_status = Label(
            text="Готов к дипломатической переписке",
            font_size='12sp',
            color=(0.7, 0.7, 0.7, 1)
        )

        status_panel.add_widget(self.chat_status)
        return status_panel

    def on_faction_selected(self, spinner, text):
        """Обработчик выбора фракции"""
        if text and text != 'Выберите фракцию':
            self.selected_faction = text
            self.load_chat_history()
            self.update_chat_header(text)
            self.update_relation_display(text)  # Добавляем обновление отображения
            self.load_trade_history(text)  # Загружаем историю сделок

    def load_trade_history(self, faction):
        """Загружает историю сделок с фракцией"""
        if not hasattr(self, 'trade_history_label'):
            return

        try:
            cursor = self.db_connection.cursor()
            cursor.execute('''
                SELECT initiator, initiator_type_resource, initiator_summ_resource,
                       target_type_resource, target_summ_resource, timestamp
                FROM trade_agreements
                WHERE (initiator = ? AND target_faction = ?)
                   OR (initiator = ? AND target_faction = ?)
                ORDER BY timestamp DESC
                LIMIT 10
            ''', (self.faction, faction, faction, self.faction))

            trades = cursor.fetchall()

            if trades:
                history_text = "Последние сделки:\n\n"
                for trade in trades:
                    initiator, give_type, give_amount, get_type, get_amount, timestamp = trade

                    if initiator == self.faction:
                        direction = "Вы → "
                    else:
                        direction = "← " + faction

                    history_text += (
                            f"{direction}\n"
                            f"Отдали: {give_amount} {give_type}\n"
                            f"Получили: {get_amount} {get_type}\n"
                            f"[size=10]{timestamp}[/size]\n"
                            + "-" * 30 + "\n"
                    )
            else:
                history_text = "Нет истории сделок"

            self.trade_history_label.text = history_text
            self.trade_history_label.markup = True

        except Exception as e:
            print(f"Ошибка загрузки истории сделок: {e}")
            self.trade_history_label.text = "Ошибка загрузки истории"

    def update_chat_header(self, faction):
        """Обновляет заголовок чата"""

        # Обновляем заголовок
        self.chat_status.text = f"Переписка с {faction}"

        # Обновляем статус отношений
        # Добавляем информацию о коэффициенте сделок
        relations = self.advisor.relations_manager.load_combined_relations()
        relation_data = relations.get(faction, {"relation_level": 0, "status": "нейтралитет"})

        try:
            relation_level = int(relation_data["relation_level"])
        except (ValueError, TypeError, KeyError):
            relation_level = 0

        # Рассчитываем коэффициент
        coefficient = self.calculate_coefficient(relation_level)

        # Добавляем информацию о коэффициенте в статус
        coefficient_text = f" (сделки (×{coefficient:.1f}))" if coefficient > 0 else " (сделки невозможны)"

        self.relation_status.text = (
            f"Отношения: {relation_level}/100 "
            f"({relation_data.get('status', 'нейтралитет')}){coefficient_text}"
        )

        # Цвет в зависимости от коэффициента
        if coefficient == 0:
            rel_color = (0.8, 0.1, 0.1, 1)  # Красный
        elif coefficient < 0.7:
            rel_color = (1.0, 0.5, 0.0, 1)  # Оранжевый
        elif coefficient < 1.0:
            rel_color = (1.0, 0.8, 0.0, 1)  # Желтый
        elif coefficient < 1.5:
            rel_color = (0.2, 0.7, 0.3, 1)  # Зеленый
        else:
            rel_color = (0.1, 0.3, 0.9, 1)  # Синий

        self.relation_status.color = rel_color

    def _handle_context_reset(self, message, faction):
        """Обрабатывает команду сброса контекста чата"""
        # Сбрасываем контекст переговоров для этой фракции
        if faction in self.negotiation_context:
            # Полностью очищаем контекст
            self.negotiation_context[faction] = {
                "stage": "idle",
                "counter_offers": 0
            }

        # Очищаем активные переговоры для этой фракции
        if faction in self.active_negotiations:
            del self.active_negotiations[faction]

        # Очищаем текущие предложения
        if faction in self.current_offers:
            del self.current_offers[faction]

        # Добавляем сообщение о сбросе контекста
        reset_responses = [
            "Хорошо, забыли. Начинаем заново.",
            "Ладно, сбрасываю контекст. Говори что хотел.",
            "Забыл. Что там у тебя было?",
            "Контекст очищен. Можешь начать сначала.",
            "Принято. Забываю предыдущий разговор.",
            "Проехали. О чем ты хотел поговорить?."
        ]

        # В зависимости от отношений можно добавить разные ответы
        relations = self.advisor.relations_manager.load_combined_relations()
        relation_data = relations.get(faction, {"relation_level": 50})
        relation_level = int(relation_data.get("relation_level", 50))

        if relation_level >= 80:
            reset_responses.extend([
                "Как скажешь, друг. Начинаем с чистого листа!",
                "Хорошо, союзник. Забываю всё предыдущее.",
                "Понимаю. Иногда нужно начать заново. Забыто!"
            ])
        elif relation_level < 30:
            reset_responses.extend([
                "Ну ладно, забью. Только говори понятнее.",
                "Забыл. Только не морочь мне голову снова.",
                "Сбрасываю. И что теперь тебе нужно?"
            ])

        return random.choice(reset_responses)

    def send_diplomatic_message(self, instance):
        """Отправляет дипломатическое сообщение"""
        message = self.message_input.text.strip()
        if not message:
            return

        if not hasattr(self, 'selected_faction') or not self.selected_faction:
            self.add_chat_message_system("Сначала выберите фракцию для переписки!")
            return

        # ПРОВЕРКА: если игрок предлагает союз, проверяем ресурсы заранее
        message_lower = message.lower()
        if any(word in message_lower for word in ['союз', 'альянс', 'объединиться', 'сотрудничать']):
            # Проверяем стоимость альянса
            try:
                cursor = self.db_connection.cursor()
                # Получаем количество городов у целевой фракции
                cursor.execute("SELECT COUNT(*) FROM cities WHERE faction = ?", (self.selected_faction,))
                target_city_count = cursor.fetchone()[0]
                alliance_cost = 100_000 + (300_000 * target_city_count)

                # Проверяем, есть ли у игрока достаточно крон
                cursor.execute("SELECT amount FROM resources WHERE faction = ? AND resource_type = 'Кроны'",
                               (self.faction,))
                player_crowns = cursor.fetchone()

                if player_crowns is None or player_crowns[0] < alliance_cost:
                    self.add_chat_message_system(
                        f" У вас недостаточно крон для предложения союза! "
                        f"Нужно {alliance_cost:,}, а у вас {player_crowns[0] if player_crowns else 0:,}."
                    )
                    self.message_input.text = ""
                    return
            except Exception as e:
                print(f"Ошибка при проверке стоимости альянса: {e}")

        # Добавляем сообщение игрока
        current_time = datetime.now().strftime("%d.%m %H:%M")
        self.add_chat_message(
            message=message,
            sender=self.faction,
            timestamp=current_time,
            is_player=True
        )

        # Сохраняем в базу данных
        self.save_negotiation_message(self.selected_faction, message, is_player=True)

        # Очищаем поле ввода
        self.message_input.text = ""

        # Генерируем ответ ИИ
        response = self.generate_diplomatic_response(message, self.selected_faction)

        if response:
            ai_time = datetime.now().strftime("%d.%m %H:%M")

            # Добавляем сообщение ИИ в чат
            self.add_chat_message(
                message=response,
                sender=self.selected_faction,
                timestamp=ai_time,
                is_player=False
            )

            # Сохраняем ответ ИИ в БД
            self.save_negotiation_message(
                self.selected_faction,
                response,
                is_player=False
            )

            # Добавляем в память разговора
            self.add_to_memory(message, response)

    def generate_diplomatic_response(self, player_message, target_faction):
        """Генерирует ответ ИИ на сообщение игрока со всеми политическими функциями"""

        print(f"DEBUG: Получено сообщение: '{player_message}' от игрока")

        # Загружаем данные об отношениях
        relations = self.advisor.relations_manager.load_combined_relations()
        relation_data = relations.get(target_faction, {"relation_level": 50, "status": "нейтралитет"})
        relation_level = int(relation_data.get("relation_level", 50))
        status = relation_data.get('status', 'нейтралитет')

        # ОБНОВЛЯЕМ ЭМОЦИОНАЛЬНОЕ СОСТОЯНИЕ
        self.update_emotional_state(player_message, relation_level)

        message_lower = player_message.lower()

        # ===== ПЕРВЫЙ ПРИОРИТЕТ: Проверка на плохие отношения =====
        if relation_level < 20:
            # Если отношения очень плохие, проверяем на оскорбления/угрозы
            if self._is_insult_or_threat(player_message):
                # Усиливаем агрессию в ответ
                hostile_responses = [
                    "Ах ты сучий потрох! Да я тебя самого в мясо порублю! Война!",
                    "Как ты смеешь?! За такие слова твоя голова будет на пике! Война объявлена!",
                    "Ты перешёл все границы! Тебе конец! Между нами война!",
                    "Я из тебя кишки наматывать буду! Война! Сейчас же!",
                    "Твои слова - твой смертный приговор! Готовься к войне!",
                    "За такое оскорбление я сотру твою фракцию с лица земли! Война!"
                ]
                # Пытаемся объявить войну
                try:
                    cursor = self.db_connection.cursor()
                    cursor.execute("""
                        UPDATE diplomacies 
                        SET relationship = 'война' 
                        WHERE (faction1 = ? AND faction2 = ?) OR (faction1 = ? AND faction2 = ?)
                    """, (self.faction, target_faction, target_faction, self.faction))

                    cursor.execute("""
                        UPDATE relations 
                        SET relationship = 0 
                        WHERE (faction1 = ? AND faction2 = ?) OR (faction1 = ? AND faction2 = ?)
                    """, (self.faction, target_faction, target_faction, self.faction))

                    self.db_connection.commit()

                    return random.choice(hostile_responses)
                except:
                    return random.choice(hostile_responses)

            # При плохих отношениях на любой запрос ресурсов/армии - хамство
            if self._is_resource_request(player_message) or self._is_status_inquiry(player_message):
                rude_responses = [
                    "Ты что, совсем охренел?! Ресурсы у меня просить?! Иди к чёрту!",
                    "Ресурсы? Да ты совсем рехнулся! Убирайся, пока цел!",
                    "Какие ещё нахрен ресурсы?! Пошёл вон, говно собачье!",
                    "Хватит попрошайничать! Исчезни, тварь!",
                    "Тебе нужны ресурсы? А мне нужен мир без тебя! Проваливай!"
                ]
                return random.choice(rude_responses)

        # Проверяем на сброс контекста (добавляем в самое начало)
        if self._is_context_reset(player_message):
            return self._handle_context_reset(player_message, target_faction)

        # 0. Проверяем ответ на AI-инициированное предложение
        ai_proposal_response = self._check_ai_proposal_response(player_message, target_faction, relation_level)
        if ai_proposal_response:
            return ai_proposal_response

        # 1. Проверяем контекст переговоров
        context = self.negotiation_context.get(target_faction, {})

        # Добавляем обработку улучшения отношений в контекст
        if context.get("stage") == "improve_relations_choice":
            response = self._process_improvement_choice(player_message, target_faction, context)
            if response:
                return response

        if context.get("stage") in ("ask_resource_type", "ask_resource_amount",
                                    "ask_player_offer", "counter_offer", "evaluate"):
            forced = self._handle_forced_dialog(player_message, target_faction, context)
            if forced:
                return forced

        # 2. Проверка на социальные вопросы "Как дела?"
        if self._is_how_are_you_social(player_message):
            return self._handle_how_are_you_social(player_message, target_faction, relation_level)

        # 3. Проверка на другие социальные вопросы
        if self._is_what_do_you_think(player_message):
            return self._handle_what_do_you_think(player_message, target_faction, relation_level)

        if self._is_relationship_status_inquiry(player_message):
            return self._handle_relationship_status_inquiry(player_message, target_faction, relation_level, status)

        # 4. Проверка запроса о текущих отношениях (числовой уровень)
        if self._is_relation_check(player_message):
            return self._handle_relation_check(player_message, target_faction, relation_level, status)

        # 5. Проверка на запрос улучшения отношений
        if self._is_improve_relations_request(player_message):
            return self._handle_improve_relations_request(player_message, target_faction, relation_level)

        # 6. ПРОВЕРКА НА ВОПРОСЫ О РЕСУРСАХ (ТОЧНЫЕ ЦИФРЫ)
        if self._is_resource_inquiry(player_message):
            return self._handle_resource_inquiry(player_message, target_faction, relation_level)

        # 7. ПРОВЕРКА НА ОСКОРБЛЕНИЯ И УГРОЗЫ (ПЕРЕД ВОЙНОЙ)
        if self._is_insult_or_threat(player_message):
            return self._handle_insult_or_threat(player_message, target_faction, relation_level)

        # 8. ПРОВЕРКА НА ВОПРОСЫ О ДЕЛАХ/СОСТОЯНИИ/РЕСУРСАХ/АРМИИ (общие)
        if self._is_status_inquiry(player_message):
            # При плохих отношениях - хамим на запросы о ресурсах/армии
            if relation_level < 20:
                rude_responses = [
                    "Тебя не касается что у меня с ресурсами! Убирайся!",
                    "Хватит выспрашивать! Мои дела - не твои дела!",
                    "Иди к чёрту со своими вопросами о ресурсах!",
                    "Ты что, шпион? Заткнись уже!",
                    "Не твоё собачье дело что у меня есть! Пошёл вон!",
                    "Хватит лезть в мои дела! Проваливай!"
                ]
                return random.choice(rude_responses)
            # При хороших отношениях - нормальный ответ
            else:
                return self._generate_status_response(target_faction)

        # 9. ПРОВЕРКА НА ПРЕДЛОЖЕНИЯ СОЮЗА
        if self._is_alliance_proposal(player_message):
            return self._handle_alliance_proposal(player_message, target_faction, relation_level)

        # 10. ПРОВЕРКА НА ПРЕДЛОЖЕНИЯ МИРА
        if self._is_peace_proposal(player_message):
            return self._handle_peace_proposal(player_message, target_faction)

        # 11. ПРОВЕРКА НА ОБЪЯВЛЕНИЕ ВОЙНЫ
        if self._is_war_declaration(player_message):
            return self._handle_war_declaration(player_message, target_faction)

        # 12. ПРОВЕРКА НА ПОДСТРЕКАТЕЛЬСТВО/ПРОВОКАЦИЮ
        if self._is_provocation(player_message):
            return self._handle_provocation(player_message, target_faction, relation_level)

        # 13. ПРОВЕРКА НА РАЗРЫВ ОТНОШЕНИЙ
        if self._is_relationship_break(player_message):
            return self._handle_relationship_break(player_message, target_faction)

        # 14. НОВАЯ ЛОГИКА: Определяем запрос ресурсов БЕЗ указания типа/количества
        is_resource_request = self._is_resource_request(player_message)

        if is_resource_request:
            # При плохих отношениях - сразу хамим на запросы ресурсов
            if relation_level < 20:
                rude_responses = [
                    "Ты что, совсем охренел?! Ресурсы у меня просить?!",
                    "Ресурсы? Да ты совсем рехнулся! Убирайся!",
                    "Какие ещё нахрен ресурсы?! Пошёл вон!",
                    "Ресурсы? Для тебя? Ты мне насрал в борщ!",
                    "Хватит попрошайничать! Исчезни!",
                    "Тебе нужны ресурсы? А мне нужен мир без тебя! Убирайся!"
                ]
                return random.choice(rude_responses)

            # Извлекаем упоминания ресурсов (очищенные от общих слов)
            resource_mentions = self._extract_resource_mentions(player_message)
            amount = self._extract_number(player_message)

            print(
                f"DEBUG: is_resource_request={is_resource_request}, resource_mentions={resource_mentions}, amount={amount}")

            # Случай 1: Общий запрос без указания типа ("мне нужны ресурсы")
            if not resource_mentions:
                # Инициируем уточнение типа ресурса
                self.negotiation_context[target_faction] = {
                    "stage": "ask_resource_type",
                    "counter_offers": 0
                }
                return ("Если тебе нужны ресурсы то что именно: Кроны (деньги), Кристаллы (минералы) или Рабочие ("
                        "люди)? Если ты хотел что то другое, то попробуй перефразировать.")

            # Случай 2: Указан тип ресурса, но не количество ("мне нужны деньги")
            elif resource_mentions and not amount:
                resource_type = resource_mentions[0]
                self.negotiation_context[target_faction] = {
                    "stage": "ask_resource_amount",
                    "resource": resource_type,
                    "counter_offers": 0
                }
                return f"Сколько {resource_type} тебе нужно?"

            # Случай 3: Указан тип и количество ("дай 1000 крон")
            elif resource_mentions and amount:
                resource_type = resource_mentions[0]
                self.negotiation_context[target_faction] = {
                    "stage": "ask_player_offer",
                    "resource": resource_type,
                    "amount": amount,
                    "counter_offers": 0
                }
                return f"Хочешь {amount:,} {resource_type}? Что предлагаешь взамен?"

        # 15. Старый метод как запасной вариант для прямых запросов
        trade_offer = self._extract_trade_offer(player_message)
        if trade_offer:
            print(f"DEBUG: Найден готовый trade_offer: {trade_offer}")
            if trade_offer.get("amount"):
                self.negotiation_context[target_faction] = {
                    "stage": "ask_player_offer",
                    "resource": trade_offer["type"],
                    "amount": trade_offer["amount"],
                    "counter_offers": 0
                }
                return f"Хочешь {trade_offer['amount']:,} {trade_offer['type']}? Что предлагаешь взамен?"

        # 16. Простые интенты
        simple_responses = {
            "greeting": self._get_greeting_response(target_faction, relation_level),
            "farewell": self._get_farewell_response(target_faction),
            "ask_status": [
                f"Наши отношения с тобой на уровне {relation_level}/100 ({status}).",
                f"Сейчас я отношусь к тебе {status}.",
                f"Уровень наших отношений: {relation_level}/100 - {status}."
            ],
            "thanks": ["Пожалуйста!", "Рад помочь!", "Не за что!", "Всегда к твоим услугам."],
            "insult": [
                "Я не буду отвечать на оскорбления.",
                "Давай вести переговоры конструктивно.",
                "Такие слова не помогут нашим отношениям."
            ],
            "threat": [
                "Угрозы не помогут в переговорах.",
                "Я не реагирую на угрозы.",
                "Ты хочешь испортить наши отношения?"
            ]
        }

        # 17. ФОЛБЭК
        response = self._generate_fallback_response(player_message, target_faction, relation_level)
        return self.get_contextual_response(response, relation_level)

    def _is_what_do_you_think(self, message):
        """Определяет, является ли сообщение вопросом 'Что думаешь?'"""
        think_keywords = [
            'что думаешь', 'что скажешь', 'как считаешь', 'как думаешь',
            'твоё мнение', 'ты как', 'что на это скажешь', 'что скажешь по поводу',
            'как тебе', 'что думаешь о', 'что скажешь насчёт', 'твои мысли'
        ]

        message_lower = message.lower()
        return any(keyword in message_lower for keyword in think_keywords)

    def _handle_what_do_you_think(self, message, target_faction, relation_level):
        """Обрабатывает вопрос 'Что думаешь?' с учетом отношений"""

        # При плохих отношениях - хамим
        if relation_level < 20:
            responses = [
                "Думаю, что ты идиот!",
                "Что думаю? Думаю, как бы тебя поскорее отвадить!",
                "Моё мнение - убирайся к чёрту!",
                "Думаю, что пора тебе заткнуться!",
                "Что думаю? Думаю, что ты мне надоел!",
                "Моё мнение тебя не интересует! Заткнись!"
            ]
            return random.choice(responses)

        # При нейтральных отношениях
        elif relation_level < 60:
            responses = [
                "Хм... Интересный вопрос. Дай подумать.",
                "Сложно сказать сразу. Нужно время на размышление.",
                "Не знаю, что и думать. Сам как считаешь?",
                "Моё мнение? Пока не определился.",
                "Думаю... пока не придумал что.",
                "Нужно подумать над этим."
            ]
            return random.choice(responses)

        # При хороших отношениях
        else:
            responses = [
                "Думаю, что ты задаёшь интересные вопросы, друг!",
                "Скажу честно - мне нравится, как ты мыслишь.",
                "Твои вопросы заставляют задуматься. Это хорошо!",
                "Размышляю... и прихожу к выводу, что с тобой приятно общаться.",
                "Думаю, что у нас хорошие перспективы сотрудничества!",
                "Моё мнение - ты надёжный партнёр!"
            ]
            return random.choice(responses)

    def _is_relationship_status_inquiry(self, message):
        """Определяет, является ли сообщение запросом о статусе отношений (друзья/приятели и т.д.)"""
        status_keywords = [
            'мы друзья', 'друзья ли мы', 'мы с тобой друзья', 'дружим ли мы',
            'мы приятели', 'приятели ли мы', 'мы с тобой приятели',
            'мы партнеры', 'партнеры ли мы', 'мы с тобой партнеры',
            'как ты меня считаешь', 'кто я для тебя', 'ты меня как воспринимаешь',
            'ты меня как считаешь', 'какой у нас статус', 'какой наш статус',
            'ты мой друг', 'я тебе друг', 'ты мне друг',
            'ты мой приятель', 'я тебе приятель', 'ты мне приятель',
            'ты мой партнер', 'я тебе партнер', 'ты мне партнер',
            'кем я для тебя являюсь', 'кем ты меня считаешь'
        ]

        message_lower = message.lower()
        return any(keyword in message_lower for keyword in status_keywords)

    def _handle_relationship_status_inquiry(self, message, target_faction, relation_level, status):
        """Обрабатывает запрос о статусе отношений (друзья/приятели и т.д.)"""

        # Формируем ответ в зависимости от уровня отношений
        if relation_level >= 90:
            responses = [
                "Конечно, мы друзья! И не просто друзья - мы союзники! {}/100 - это говорит само за себя.".format(
                    relation_level),
                "Друг? Ты мне как брат! Наши отношения {}/100 - мы практически семья.".format(relation_level),
                "Да что ты спрашиваешь! Мы лучшие друзья и верные союзники! {}/100 - отличный результат.".format(
                    relation_level),
                "Ты мне не просто друг, ты мне брат по оружию! {}/100 - это высший уровень доверия.".format(
                    relation_level)
            ]

        elif relation_level >= 80:
            responses = [
                "Да, мы определённо друзья! {}/100 - это хороший показатель.".format(relation_level),
                "Конечно дружим! {}/100 - мы надёжные партнёры.".format(relation_level),
                "Без сомнений, мы друзья! {}/100 говорит о нашем взаимопонимании.".format(relation_level),
                "Ты мой друг, это несомненно! {}/100 - прекрасные отношения.".format(relation_level)
            ]

        elif relation_level >= 70:
            responses = [
                "Да, можно сказать, что мы друзья. {}/100 - неплохой уровень.".format(relation_level),
                "Мы скорее друзья, чем просто знакомые. {}/100 - это уже что-то.".format(relation_level),
                "Друзья? Да, пожалуй. {}/100 - мы на пути к настоящей дружбе.".format(relation_level),
                "Ты мне не враг, это точно. Можно считать, что дружим. {}/100.".format(relation_level)
            ]

        elif relation_level >= 60:
            responses = [
                "Хм... Мы скорее приятели, чем друзья. {}/100 - нейтрально-положительные отношения.".format(
                    relation_level),
                "Друзьями нас пока не назовёшь, но мы определённо приятели. {}/100.".format(relation_level),
                "Мы приятели. {}/100 - ничего особенного, но и не плохо.".format(relation_level),
                "Приятели, да. Друзьями пока рано. {}/100 - средний уровень.".format(relation_level)
            ]

        elif relation_level >= 50:
            responses = [
                "Мы... знакомые. {}/100 - нейтральные отношения.".format(relation_level),
                "Друзья? Нет. Просто знакомые. {}/100 - ничего личного.".format(relation_level),
                "Мы не друзья и не враги. Просто... есть. {}/100.".format(relation_level),
                "Знакомые, не более того. {}/100 - обычные деловые отношения.".format(relation_level)
            ]

        elif relation_level >= 40:
            responses = [
                "Мы... деловые партнёры. Не более. {}/100 - прохладные отношения.".format(relation_level),
                "Партнёры по необходимости. {}/100 - лучше не задавай таких вопросов.".format(relation_level),
                "Мы сотрудничаем, но это не значит, что мы друзья. {}/100.".format(relation_level),
                "Деловые отношения, и точка. {}/100 - не лезь в душу.".format(relation_level)
            ]

        elif relation_level >= 30:
            responses = [
                "Партнёры? Скорее вынужденные союзники. {}/100 - напряжённые отношения.".format(relation_level),
                "Мы не партнёры, мы... соседи по несчастью. {}/100.".format(relation_level),
                "Не партнёры мы с тобой. Просто пока не воюем. {}/100.".format(relation_level),
                "Какие партнёры? {}/100 - еле терпим друг друга.".format(relation_level)
            ]

        elif relation_level >= 20:
            responses = [
                "Партнёры? Ты смеёшься? {}/100 - мы почти враги!".format(relation_level),
                "Какие могут быть партнёры при {}/100? Ты мне не нравишься.".format(relation_level),
                "Партнёры? Да ты шутишь! {}/100 говорит о том, что я тебя терпеть не могу.".format(relation_level),
                "Ты мне не партнёр, ты мне головная боль. {}/100.".format(relation_level)
            ]

        elif relation_level >= 10:
            responses = [
                "Друзья? Партнёры? Да ты вообще кто такой? {}/100 - убирайся!".format(relation_level),
                "Какой ещё статус? Ты мне враг! {}/100 - хватит задавать глупые вопросы.".format(relation_level),
                "Ты серьёзно спрашиваешь? При {}/100? Да пошёл ты!".format(relation_level),
                "Статус? Враг! {}/100 - и не задавай больше таких вопросов.".format(relation_level)
            ]

        else:  # 0-9
            responses = [
                "Ты мой смертельный враг! {}/100 - я бы тебя убил, если бы мог!".format(relation_level),
                "Какой статус?! Ты для меня хуже чумы! {}/100 - исчезни!".format(relation_level),
                "Ты спрашиваешь о статусе при {}/100? Ты конченый идиот!".format(relation_level),
                "Ты мне не друг, не приятель и не партнёр. Ты - гнида! {}/100.".format(relation_level)
            ]

        return random.choice(responses)

    def _is_how_are_you_social(self, message):
        """Определяет, является ли сообщение чисто социальным вопросом 'Как дела?' без запроса о ресурсах/армии"""
        social_keywords = [
            'как дела', 'как ты', 'как ваши дела', 'что нового', 'как твои дела',
            'как поживаешь', 'как жизнь', 'как успехи', 'как сам', 'как ты там',
            'как оно', 'как делишки', 'что по жизни', 'как настроение',
            'как здоровье', 'как ты себя чувствуешь'
        ]

        # Исключаем слова, связанные с ресурсами/армией
        exclude_keywords = [
            'ресурсы', 'ресурс', 'войск', 'арми', 'сила', 'мощь', 'могущество',
            'казна', 'крон', 'кристалл', 'рабоч', 'люд', 'состояние', 'положение'
        ]

        message_lower = message.lower()

        # Проверяем наличие социальных ключевых слов
        has_social = any(keyword in message_lower for keyword in social_keywords)

        # Проверяем отсутствие ключевых слов ресурсов/армии
        has_resource = any(keyword in message_lower for keyword in exclude_keywords)

        return has_social and not has_resource

    def _handle_how_are_you_social(self, message, target_faction, relation_level):
        """Обрабатывает социальный вопрос 'Как дела?' с учетом отношений"""

        # При плохих отношениях - хамим
        if relation_level < 20:
            responses = [
                "Да пошёл ты со своими 'как дела'!",
                "Какие дела?! Убирайся отсюда!",
                "Мои дела тебя не касаются, ублюдок!",
                "Дела? Сейчас я тебе устрою дела!",
                "Отвали с этими вопросами!",
                "Иди к чёрту со своими 'как дела'!",
                "Закрой уже свою пасть!",
                "Заткнись и убирайся!"
            ]
            return random.choice(responses)

        # При нейтральных отношениях - даем краткий ответ
        elif relation_level < 60:
            responses = [
                "Дела идут. Чего хотел?",
                "Ничего особенного. К делу.",
                "Жив-здоров. Говори, что нужно.",
                "Всё нормально. Чего тебе?",
                "Пока не помер. Что там у тебя?",
                "Держусь. В чём дело?",
                "Дела как дела. Короче говоря.",
                "Поживаем. Быстрей к сути."
            ]
            return random.choice(responses)

        # При хороших отношениях - используем существующий метод генерации статуса
        else:
            # Используем существующий метод генерации ответа о делах
            return self._generate_status_response(target_faction)

    def _extract_number_from_text(self, text):
        """Извлекает число из текста с поддержкой 'тыс', 'миллионов', 'кк' и т.д. - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
        import re

        text = text.lower().strip()

        # Если текст пустой, возвращаем None
        if not text:
            return None

        # Удаляем пробелы между цифрами и запятыми/точками для удобства парсинга
        text = re.sub(r'(\d)\s*([.,])\s*(\d)', r'\1\2\3', text)

        # 0. ОБРАБОТКА "КК" (ТЫСЯЧА ТЫСЯЧ = МИЛЛИОН) - ДОБАВЛЯЕМ ЭТОТ КЕЙС ПЕРВЫМ
        kk_pattern = r'(\d+(?:[.,]\d+)?)\s*(?:кк|kk)'
        match = re.search(kk_pattern, text)
        if match:
            try:
                # Заменяем запятую на точку для float
                number_str = match.group(1).replace(',', '.')
                number = float(number_str)
                return int(number * 1000000)  # кк = тысяча тысяч = миллион
            except Exception as e:
                print(f"DEBUG: Ошибка парсинга кк: {e}")
                pass

        # 1. Обработка десятичных чисел с множителями "1.2 млн", "1,2 тысячи"
        decimal_thousand_pattern = r'(\d+(?:[.,]\d+)?)\s*(?:тыс|тысяч|тысячи|т\s*ыс|т\.|k|к)'
        decimal_million_pattern = r'(\d+(?:[.,]\d+)?)\s*(?:миллион|миллионов|милл|млн|м\.|m)'

        # Проверяем тысячи с десятичными
        match = re.search(decimal_thousand_pattern, text)
        if match:
            try:
                number_str = match.group(1).replace(',', '.')
                number = float(number_str)
                return int(number * 1000)
            except Exception as e:
                print(f"DEBUG: Ошибка парсинга тысяч с десятичными: {e}")
                pass

        # Проверяем миллионы с десятичными
        match = re.search(decimal_million_pattern, text)
        if match:
            try:
                number_str = match.group(1).replace(',', '.')
                number = float(number_str)
                return int(number * 1000000)
            except Exception as e:
                print(f"DEBUG: Ошибка парсинга миллионов с десятичными: {e}")
                pass

        # 2. Проверяем запись типа "1.2тыс", "1,2к", "1.5кк" (без пробела)
        compact_pattern = r'(\d+(?:[.,]\d+)?)(тыс|к|k|миллион|млн|м|кк|kk)'
        match = re.search(compact_pattern, text)
        if match:
            try:
                number_str = match.group(1).replace(',', '.')
                number = float(number_str)
                multiplier = match.group(2)

                multiplier_map = {
                    'тыс': 1000, 'к': 1000, 'k': 1000,
                    'миллион': 1000000, 'млн': 1000000, 'м': 1000000,
                    'кк': 1000000, 'kk': 1000000  # Добавляем кк
                }

                if multiplier in multiplier_map:
                    return int(number * multiplier_map[multiplier])
            except Exception as e:
                print(f"DEBUG: Ошибка парсинга компактной записи: {e}")
                pass

        # 3. Проверяем также русское "тыщ" (разговорное)
        tysh_pattern = r'(\d+(?:[.,]\d+)?)\s*(?:тыщ|тщ|тищ)'
        match = re.search(tysh_pattern, text)
        if match:
            try:
                number_str = match.group(1).replace(',', '.')
                number = float(number_str)
                return int(number * 1000)
            except Exception as e:
                print(f"DEBUG: Ошибка парсинга 'тыщ': {e}")
                pass

        # 4. Пробуем просто число (включая десятичные)
        decimal_match = re.search(r'(\d+(?:[.,]\d+)?)', text)
        if decimal_match:
            try:
                number_str = decimal_match.group(1).replace(',', '.')
                if '.' in number_str:
                    number = float(number_str)
                    if number < 1000:
                        return number
                    else:
                        return int(round(number))
                else:
                    return int(number_str)
            except Exception as e:
                print(f"DEBUG: Ошибка парсинга десятичного числа: {e}")
                pass

        # 5. Словарные числительные (используем общий словарь)
        return self._extract_number(text)

    def show_relation_tooltip(self, faction, pos=None):
        """Показывает всплывающую подсказку о влиянии отношений на сделки"""
        from kivy.uix.popup import Popup
        from kivy.uix.boxlayout import BoxLayout
        from kivy.uix.gridlayout import GridLayout
        from kivy.uix.label import Label
        from kivy.uix.button import Button
        from kivy.metrics import dp
        from kivy.graphics import Color, Rectangle, RoundedRectangle

        # Получаем данные об отношениях
        relations = self.advisor.relations_manager.load_combined_relations()
        relation_data = relations.get(faction, {"relation_level": 50, "status": "нейтралитет"})

        try:
            relation_level = int(relation_data.get("relation_level", 50))
        except (ValueError, TypeError):
            relation_level = 50

        coefficient = self.calculate_coefficient(relation_level)
        status = relation_data.get('status', 'нейтралитет')

        # Определяем цвет статуса
        if relation_level < 15:
            status_color = (0.8, 0.1, 0.1, 1)  # Красный
            status_desc = "Вражда"
        elif relation_level < 35:
            status_color = (1.0, 0.5, 0.0, 1)  # Оранжевый
            status_desc = "Напряженные"
        elif relation_level < 54:
            status_color = (1.0, 0.8, 0.0, 1)  # Желтый
            status_desc = "Прохладные"
        elif relation_level < 65:
            status_color = (0.2, 0.7, 0.3, 1)  # Зеленый
            status_desc = "Нейтральные"
        elif relation_level < 75:
            status_color = (0.0, 0.8, 0.8, 1)  # Бирюзовый
            status_desc = "Дружественные"
        elif relation_level < 90:
            status_color = (0.1, 0.3, 0.9, 1)  # Синий
            status_desc = "Очень дружественные"
        else:
            status_color = (1, 1, 1, 1)  # Белый
            status_desc = "Союзнические"

        # Создаем содержимое popup
        content = BoxLayout(
            orientation='vertical',
            spacing=dp(10),
            padding=dp(15)
        )

        # Фон
        with content.canvas.before:
            Color(0.1, 0.1, 0.15, 0.98)
            RoundedRectangle(
                pos=content.pos,
                size=content.size,
                radius=[dp(10), ]
            )

        # Заголовок
        header = Label(
            text=f"Отношения с {faction}",
            font_size='18sp',
            bold=True,
            color=(1, 1, 1, 1),
            size_hint=(1, None),
            height=dp(40)
        )
        content.add_widget(header)

        # Основная информация
        main_info = GridLayout(
            cols=2,
            spacing=dp(10),
            size_hint=(1, None),
            height=dp(80)
        )

        # Уровень отношений
        rel_label = Label(
            text="Уровень отношений:",
            font_size='14sp',
            color=(0.8, 0.8, 0.9, 1),
            halign='left'
        )

        rel_value = Label(
            text=f"{relation_level}/100",
            font_size='16sp',
            bold=True,
            color=status_color,
            halign='right'
        )

        # Коэффициент сделок
        coeff_label = Label(
            text="Коэффициент сделок:",
            font_size='14sp',
            color=(0.8, 0.8, 0.9, 1),
            halign='left'
        )

        coeff_value = Label(
            text=f"×{coefficient:.2f}",
            font_size='16sp',
            bold=True,
            color=status_color,
            halign='right'
        )

        main_info.add_widget(rel_label)
        main_info.add_widget(rel_value)
        main_info.add_widget(coeff_label)
        main_info.add_widget(coeff_value)

        content.add_widget(main_info)

        # Прогресс-бар отношений (визуализация)
        progress_container = BoxLayout(
            orientation='vertical',
            spacing=dp(5),
            size_hint=(1, None),
            height=dp(40)
        )

        progress_bg = BoxLayout(
            orientation='horizontal',
            size_hint=(1, None),
            height=dp(20)
        )

        # Визуализация прогресса отношений
        with progress_bg.canvas.before:
            Color(0.2, 0.2, 0.3, 1)
            Rectangle(pos=progress_bg.pos, size=progress_bg.size)

            # Заливка в зависимости от уровня
            fill_width = (relation_level / 100) * progress_bg.width
            Color(*status_color[:3], 0.7)
            Rectangle(
                pos=progress_bg.pos,
                size=(fill_width if fill_width > 0 else 0, progress_bg.height)
            )

        progress_label = Label(
            text=f"Статус: {status} ({status_desc})",
            font_size='12sp',
            color=status_color,
            size_hint=(1, None),
            height=dp(20)
        )

        progress_container.add_widget(progress_bg)
        progress_container.add_widget(progress_label)
        content.add_widget(progress_container)

        # Детали влияния на переговоры
        details = BoxLayout(
            orientation='vertical',
            spacing=dp(5),
            size_hint=(1, None),
            height=dp(150)
        )

        details_title = Label(
            text="Влияние на переговоры:",
            font_size='14sp',
            bold=True,
            color=(0.9, 0.9, 0.5, 1),
            size_hint=(1, None),
            height=dp(25)
        )
        details.add_widget(details_title)

        # Динамическое описание в зависимости от коэффициента
        descriptions = []

        if coefficient == 0:
            descriptions = [
                "• Сделки полностью невозможны",
                "• Любые предложения будут отклонены",
                "• Требуется улучшить отношения"
            ]
        elif coefficient < 0.5:
            descriptions = [
                "• Сделки крайне невыгодны для нас",
                "• Требуются предложения с премией 100%+",
                "• Могут обсуждаться только критически важные сделки"
            ]
        elif coefficient < 1.0:
            descriptions = [
                f"• Сделки требуют премии {int((1 / coefficient - 1) * 100)}%",
                "• Предложения оцениваются строго",
                "• Торг возможен, но сложен"
            ]
        elif coefficient < 1.5:
            descriptions = [
                "• Стандартные условия сделок",
                "• Рыночные цены и условия",
                "• Торг ведется на равных"
            ]
        elif coefficient < 2.0:
            descriptions = [
                "• Готовность идти на уступки",
                f"• Возможны скидки до {int((coefficient - 1) * 100)}%",
                "• Приоритет долгосрочным отношениям"
            ]
        else:
            descriptions = [
                "• Максимально выгодные условия",
                "• Готовы помочь в ущерб себе",
                "• Сделки укрепляют альянс"
            ]

        for desc in descriptions:
            desc_label = Label(
                text=desc,
                font_size='12sp',
                color=(0.8, 0.8, 0.9, 1),
                size_hint=(1, None),
                height=dp(20),
                halign='left'
            )
            details.add_widget(desc_label)

        content.add_widget(details)

        # Советы по улучшению отношений
        tips = BoxLayout(
            orientation='vertical',
            spacing=dp(5),
            size_hint=(1, None),
            height=dp(80)
        )

        tips_title = Label(
            text="Как улучшить отношения:",
            font_size='12sp',
            bold=True,
            color=(0.7, 0.9, 0.7, 1),
            size_hint=(1, None),
            height=dp(20)
        )
        tips.add_widget(tips_title)

        # Динамические советы
        improvement_tips = []

        if relation_level < 25:
            improvement_tips = [
                "* Заключите договор улучшения отношений через диалог",
                "* Предложите взаимовыгодную сделку",
                "* Избегайте конфликтных действий"
            ]
        elif relation_level < 50:
            improvement_tips = [
                "* Регулярно торгуйте с нами",
                "* Улучшайте отношения через беседу",
                "* Проявляйте дипломатичность"
            ]
        else:
            improvement_tips = [
                "* Заключайте союз",
                "* Поддерживайте отношения",
                "* Торгуйте с нами"
            ]

        for tip in improvement_tips:
            tip_label = Label(
                text=tip,
                font_size='11sp',
                color=(0.6, 0.8, 0.6, 1),
                size_hint=(1, None),
                height=dp(18),
                halign='left'
            )
            tips.add_widget(tip_label)

        content.add_widget(tips)

        # Кнопка закрытия
        close_btn = Button(
            text="Закрыть",
            size_hint=(1, None),
            height=dp(40),
            background_color=(0.3, 0.3, 0.5, 1),
            background_normal='',
            font_size='14sp'
        )
        content.add_widget(close_btn)

        # Создаем popup
        popup = Popup(
            title='',
            content=content,
            size_hint=(0.8, 0.7),
            auto_dismiss=True,
            separator_color=(0.3, 0.3, 0.5, 1),
            background=''
        )

        # Стилизуем фон popup
        popup.background_color = (0, 0, 0, 0.3)

        # Обработчик закрытия
        close_btn.bind(on_press=popup.dismiss)

        # Показываем popup
        popup.open()

        return popup

    def create_chat_header(self):
        """Создает шапку чата с иконками"""
        header = BoxLayout(
            orientation='horizontal',
            size_hint=(1, None),
            height=dp(60),
            padding=[dp(15), dp(10)],
            spacing=dp(10)
        )

        # Кнопка назад с иконкой
        back_button = Button(
            text="",
            size_hint=(None, None),
            size=(dp(40), dp(40)),
            background_normal='files/pict/sov/back.png',
            background_color=(0.3, 0.3, 0.5, 1),
            border=(0, 0, 0, 0),
            on_press=lambda x: self.advisor.return_to_main_tab()
        )

        # Информация о текущей фракции
        faction_info = BoxLayout(
            orientation='vertical',
            size_hint=(0.4, 1),
            spacing=dp(2)
        )

        # === Заголовок (нужен для update_chat_header) ===
        self.chat_title = Label(
            text="Дипломатическая переписка",
            font_size='18sp',
            bold=True,
            color=(1, 1, 1, 1),
            halign='center'
        )
        self.chat_title.bind(size=self.chat_title.setter('text_size'))
        faction_info.add_widget(self.chat_title)

        # === Статус чата (нужен для update_chat_header) ===
        self.chat_status = Label(
            text="",
            font_size='14sp',
            color=(0.85, 0.85, 0.9, 1),
            halign='center'
        )
        self.chat_status.bind(size=self.chat_status.setter('text_size'))
        faction_info.add_widget(self.chat_status)

        # === Статус отношений (нужен для update_chat_header) ===
        self.relation_status = Label(
            text="",
            font_size='13sp',
            color=(0.7, 0.7, 0.8, 1),
            halign='center'
        )
        self.relation_status.bind(size=self.relation_status.setter('text_size'))
        faction_info.add_widget(self.relation_status)

        # Выпадающий список фракций
        faction_selector_box = BoxLayout(
            orientation='horizontal',
            size_hint=(0.4, 1),
            spacing=dp(10)
        )

        selector_label = Label(
            text="Фракция:",
            font_size='16sp',
            color=(0.8, 0.8, 0.9, 1),
            size_hint=(0.4, 1)
        )

        self.faction_spinner = Spinner(
            text='Выберите фракцию',
            values=[],
            size_hint=(0.6, None),
            size=(dp(150), dp(40)),
            background_color=(0.2, 0.3, 0.5, 1),
            font_size='14sp',
            background_normal='',
            background_down=''
        )

        # Заполняем список фракций из базы данных
        factions = self.load_factions_from_db()
        if factions:
            for faction in factions:
                if faction != self.faction:
                    self.faction_spinner.values.append(faction)

            if not self.faction_spinner.values:
                self.faction_spinner.text = "Нет доступных фракций"
                self.faction_spinner.disabled = True
        else:
            # Фолбэк — загружаем живые фракции из городов
            try:
                _cur = self.db_connection.cursor()
                _cur.execute("SELECT DISTINCT faction FROM cities WHERE faction != 'Нейтрал' AND faction != 'Мятежники' AND faction != 'Нежить'")
                for _row in _cur.fetchall():
                    if _row[0] != self.faction:
                        self.faction_spinner.values.append(_row[0])
            except Exception:
                pass

        self.faction_spinner.bind(text=self.on_faction_selected)

        faction_selector_box.add_widget(selector_label)
        faction_selector_box.add_widget(self.faction_spinner)

        header.add_widget(back_button)
        header.add_widget(faction_info)
        header.add_widget(faction_selector_box)


        return header

    def create_relation_sidebar(self):
        """Создает боковую панель с информацией об отношениях (упрощенная версия)"""
        sidebar = BoxLayout(
            orientation='vertical',
            size_hint=(0.25, 1),
            spacing=dp(10),
            padding=dp(5)
        )

        # Заголовок панели
        sidebar_title = Label(
            text="Информация",
            font_size='16sp',
            bold=True,
            color=(1, 1, 1, 1),
            size_hint=(1, None),
            height=dp(30)
        )
        sidebar.add_widget(sidebar_title)

        # Область отображения отношений
        relations_box = BoxLayout(
            orientation='vertical',
            size_hint=(1, 0.6),
            spacing=dp(5),
            padding=dp(5)
        )

        self.relation_display = Label(
            text="Выберите фракцию",
            font_size='12sp',
            color=(0.9, 0.9, 0.9, 1),
            size_hint=(1, 1),
            valign='top',
            halign='center',
            text_size=(None, None)
        )
        relations_box.add_widget(self.relation_display)
        sidebar.add_widget(relations_box)

        # Кнопка подробной информации
        details_button = Button(
            text="Подробнее об отношениях",
            size_hint=(1, None),
            height=dp(40),
            background_color=(0.3, 0.3, 0.5, 1),
            background_normal='',
            font_size='12sp',
            on_press=self.show_relation_info
        )
        sidebar.add_widget(details_button)

        # История сделок
        history_box = BoxLayout(
            orientation='vertical',
            size_hint=(1, 0.4),
            spacing=dp(5),
            padding=dp(5)
        )

        history_title = Label(
            text="История сделок:",
            font_size='13sp',
            bold=True,
            color=(0.8, 0.8, 0.8, 1),
            size_hint=(1, None),
            height=dp(25)
        )
        history_box.add_widget(history_title)

        history_scroll = ScrollView(
            size_hint=(1, 1),
            bar_width=dp(5)
        )

        self.trade_history_label = Label(
            text="Нет истории сделок",
            font_size='11sp',
            color=(0.7, 0.7, 0.7, 1),
            size_hint_y=None,
            valign='top',
            halign='left'
        )
        self.trade_history_label.bind(
            texture_size=lambda *x: self.trade_history_label.setter('height')(
                self.trade_history_label, self.trade_history_label.texture_size[1])
        )

        history_scroll.add_widget(self.trade_history_label)
        history_box.add_widget(history_scroll)
        sidebar.add_widget(history_box)

        return sidebar

    def show_relation_info(self, instance):
        """Показывает информацию об отношениях с текущей выбранной фракцией"""
        if hasattr(self, 'selected_faction') and self.selected_faction:
            self.show_relation_tooltip(self.selected_faction)
        else:
            # Используем метод для добавления системного сообщения
            self.add_chat_message_system("Сначала выберите фракцию для просмотра информации об отношениях")

    def update_relation_display(self, faction=None):
        """Обновляет отображение информации об отношениях"""
        if not faction and hasattr(self, 'selected_faction'):
            faction = self.selected_faction

        if not faction:
            return

        # Получаем данные об отношениях
        relations = self.advisor.relations_manager.load_combined_relations()
        relation_data = relations.get(faction, {"relation_level": 50, "status": "нейтралитет"})

        try:
            relation_level = int(relation_data.get("relation_level", 50))
        except (ValueError, TypeError):
            relation_level = 50

        coefficient = self.calculate_coefficient(relation_level)
        status = relation_data.get('status', 'нейтралитет')

        # Форматируем текст для отображения
        display_text = f"""Отношения с {faction}

    Уровень: [b]{relation_level}/100[/b]
    Статус: {status}
    Коэффициент: ×{coefficient:.2f}

    [b]Влияние на сделки:[/b]
    """

        # Добавляем динамическое описание
        if coefficient == 0:
            display_text += "• Сделки невозможны\n"
        elif coefficient < 0.7:
            display_text += "• Требуется премия\n• Строгие условия\n"
        elif coefficient < 2:
            display_text += "• Стандартные условия\n• Равный торг\n"
        else:
            display_text += "• Выгодные условия\n• Готовы к уступкам\n"

        # Добавляем совет
        display_text += "\n[b]Совет:[/b]\n"
        if relation_level < 30:
            display_text += "Улучшите отношения\nперед сделками"
        elif relation_level < 60:
            display_text += "Торгуйтесь аккуратно"
        else:
            display_text += "Используйте преимущество"

        # Обновляем label
        if hasattr(self, 'relation_display'):
            self.relation_display.text = display_text
            self.relation_display.markup = True

    def _is_resource_request(self, message):
        """Определяет, является ли сообщение запросом ресурсов"""
        message_lower = message.lower().strip()

        # Список слов для запросов (расширенный)
        request_words = [
            'нужен', 'нужны', 'нужно', 'нуждаюсь', 'нуждается',
            'дай', 'дайте', 'предоставь', 'предоставьте', 'отдай', 'отдайте',
            'подкинь', 'скинь', 'переведи',
            'хочу', 'хотел', 'хотела', 'хотелось', 'желаю', 'желаем',
            'получить', 'получать', 'достать', 'надо', 'надобно',
            'можно', 'мог бы', 'могла бы', 'могли бы',
            'прошу', 'просим', 'просят', 'просите',
            'требую', 'требуем', 'требуют', 'требуется', 'требуются',
            'необходим', 'необходимы', 'необходимо', 'необходима',
            'хотелось бы', 'хотеться', 'хотят', 'хотим',
            'выдели', 'выделите', 'предоставишь', 'можешь дать',
            'помоги с', 'нужна помощь', 'помоги получить'
        ]

        # Проверяем наличие слов запроса
        has_request = any(req_word in message_lower for req_word in request_words)

        # Проверяем специальные фразы
        special_phrases = [
            'мне нужны', 'нужно мне', 'дайте мне', 'хочу получить',
            'можно получить', 'могли бы дать', 'хотел бы получить',
            'прошу тебя о', 'выдели мне', 'предоставь мне'
        ]

        has_special_phrase = any(phrase in message_lower for phrase in special_phrases)

        # Если есть запрос, но нет упоминания конкретного ресурса - это общий запрос
        if has_request or has_special_phrase:
            # Извлекаем упоминания ресурсов (с очисткой от общих слов)
            resource_mentions = self._extract_resource_mentions(message)

            # Если нет конкретных упоминаний - это общий запрос
            if not resource_mentions:
                return True  # Это общий запрос "мне нужны ресурсы"
            else:
                return True  # Это конкретный запрес "мне нужны деньги"

        return False

    def _extract_resource_mentions(self, message):
        """Извлекает все упоминания ресурсов из сообщения - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
        message_lower = message.lower()

        # Удаляем общие слова, которые не указывают на конкретный ресурс
        general_resource_words = ['ресурс', 'ресурсы', 'ресурсов']

        # Создаем копию сообщения без общих слов
        cleaned_message = message_lower
        for word in general_resource_words:
            cleaned_message = cleaned_message.replace(word, '')

        # Расширенное сопоставление (БЕЗ общих слов в маппинге)
        resource_mapping = {
            'крон': 'Кроны', 'кронн': 'Кроны', 'золот': 'Кроны', 'деньг': 'Кроны',
            'денег': 'Кроны', 'монет': 'Кроны', 'монеты': 'Кроны', 'золота': 'Кроны',
            'золото': 'Кроны', 'казна': 'Кроны', 'финанс': 'Кроны',

            'кристалл': 'Кристаллы', 'кристал': 'Кристаллы', 'кристалы': 'Кристаллы',
            'руда': 'Кристаллы', 'руды': 'Кристаллы', 'минерал': 'Кристаллы',
            'минералы': 'Кристаллы', 'камн': 'Кристаллы', 'самоцвет': 'Кристаллы',
            'эссенци': 'Кристаллы', 'магическ': 'Кристаллы',

            'рабоч': 'Рабочие', 'рабочих': 'Рабочие', 'рабочего': 'Рабочие',
            'люд': 'Рабочие', 'людей': 'Рабочие', 'крестьян': 'Рабочие',
            'работник': 'Рабочие', 'работников': 'Рабочие', 'рабочей': 'Рабочие',
            'населен': 'Рабочие', 'граждан': 'Рабочие', 'подданн': 'Рабочие',
            'жител': 'Рабочие', 'персон': 'Рабочие'
        }

        found_resources = []

        # Проверяем каждое слово в ОЧИЩЕННОМ сообщении
        words = cleaned_message.split()
        for word in words:
            for keyword, resource_type in resource_mapping.items():
                # Проверяем вхождение ключевого слова в слово
                if keyword in word:
                    if resource_type not in found_resources:
                        found_resources.append(resource_type)
                    break  # переходим к следующему слову

        # Также проверяем оригинальное сообщение для определенных паттернов
        if not found_resources:
            # Проверяем конкретные паттерны
            patterns = [
                (['крон', 'золот', 'деньг', 'монет'], 'Кроны'),
                (['кристалл', 'руда', 'минерал', 'камн'], 'Кристаллы'),
                (['рабоч', 'люд', 'работник', 'крестьян'], 'Рабочие')
            ]

            for pattern_list, resource_type in patterns:
                for pattern in pattern_list:
                    if pattern in message_lower:
                        if resource_type not in found_resources:
                            found_resources.append(resource_type)
                        break

        print(
            f"DEBUG _extract_resource_mentions: found {found_resources} in '{message}' (cleaned: '{cleaned_message}')")
        return found_resources

    def _extract_resource_request_info(self, message):
        """Извлекает информацию о запросе ресурсов из сообщения - УПРОЩЕННАЯ ВЕРСИЯ"""
        message_lower = message.lower()

        # Сначала пытаемся извлечь количество
        amount = self._extract_number(message)

        # Простое определение типа ресурса
        if any(word in message_lower for word in ['крон', 'золот', 'деньг', 'монет']):
            resource_type = 'Кроны'
        elif any(word in message_lower for word in ['кристалл', 'руда', 'минерал']):
            resource_type = 'Кристаллы'
        elif any(word in message_lower for word in ['рабоч', 'люд', 'крестьян', 'работник']):
            resource_type = 'Рабочие'
        else:
            resource_type = None

        if resource_type:
            return {
                'type': resource_type,
                'amount': amount if amount else 0  # 0 если количество не указано
            }

        return None

    def _extract_number(self, message):
        """Извлекает число из сообщения - улучшенная версия с поддержкой десятичных и 'кк'"""
        import re

        message_lower = message.lower()

        # 0. Нормализуем сообщение: удаляем лишние пробелы
        message_lower = re.sub(r'\s+', ' ', message_lower).strip()

        # 1. Сначала пробуем распознать "кк" отдельно (с поддержкой десятичных)
        kk_patterns = [
            (r'(\d+(?:[.,]\d+)?)\s*(?:кк|kk)', 1000000),  # "1кк" = 1,000,000
        ]

        for pattern, multiplier in kk_patterns:
            match = re.search(pattern, message_lower)
            if match:
                try:
                    number_str = match.group(1).replace(',', '.')
                    number = float(number_str)
                    # Для миллиона округляем до целого
                    return int(number * multiplier)
                except:
                    continue  # Пробуем следующий паттерн

        # 2. Пробуем распознать комбинации типа "70 тыс", "10 тысяч", "1.5 млн" (с десятичными)
        # Обновленный паттерн для десятичных чисел
        decimal_pattern = r'(\d+(?:[.,]\d+)?)\s*(тыс|тысяч|тысячи|т\s*ыс|миллион|миллионов|милл|млн|м)'
        match = re.search(decimal_pattern, message_lower)
        if match:
            try:
                number_str = match.group(1).replace(',', '.')
                number = float(number_str)
                multiplier = match.group(2)

                if any(word in multiplier for word in ['тыс', 'тысяч', 'тысячи', 'тс']):
                    result = number * 1000
                    return int(result) if result.is_integer() else result
                elif any(word in multiplier for word in ['миллион', 'миллионов', 'милл', 'млн']):
                    result = number * 1000000
                    return int(result) if result.is_integer() else result
                elif multiplier == 'м':
                    # Определяем по контексту - обычно "м" это миллионы, но проверим
                    # Смотрим на размер числа
                    if number < 10:  # Маловероятно что говорят "1.5м" имея в виду 1500
                        result = number * 1000000
                    else:
                        result = number * 1000
                    return int(result) if result.is_integer() else result
            except:
                pass  # Если не получилось с десятичными, пробуем дальше

        # 3. Пробуем словарные числа с множителями (с десятичными)
        word_patterns = [
            (r'(\d+(?:[.,]\d+)?)\s*к', 1000),  # "10.5к" = 10500
            (r'(\d+(?:[.,]\d+)?)\s*k', 1000),  # "10.5k" = 10500
            (r'(\d+(?:[.,]\d+)?)\s*т', 1000),  # "10.5т" = 10500
        ]

        for pattern, multiplier in word_patterns:
            match = re.search(pattern, message_lower)
            if match:
                try:
                    number_str = match.group(1).replace(',', '.')
                    number = float(number_str)
                    result = number * multiplier
                    return int(result) if result.is_integer() else result
                except:
                    continue

        # 4. Пробуем просто число (включая десятичные)
        # Ищем первое число в тексте
        decimal_match = re.search(r'(\d+(?:[.,]\d+)?)', message_lower)
        if decimal_match:
            try:
                number_str = decimal_match.group(1).replace(',', '.')
                if '.' in number_str:
                    number = float(number_str)
                    # Для небольших чисел возвращаем как float, для больших округляем
                    if number < 1000:
                        return number
                    else:
                        return int(round(number))
                else:
                    return int(number_str)
            except:
                pass

        # 5. Словарные числительные (без изменений)
        numeral_map = {
            # Единицы
            'один': 1, 'одну': 1, 'одного': 1, 'одной': 1,
            'два': 2, 'две': 2, 'двух': 2,
            'три': 3, 'трёх': 3, 'трех': 3,
            'четыре': 4, 'четырёх': 4, 'четырех': 4,
            'пять': 5, 'пяти': 5,
            'шесть': 6, 'шести': 6,
            'семь': 7, 'семи': 7,
            'восемь': 8, 'восьми': 8,
            'девять': 9, 'девяти': 9,
            'десять': 10, 'десяти': 10,

            # Десятки
            'одиннадцать': 11, 'двенадцать': 12,
            'тринадцать': 13, 'четырнадцать': 14,
            'пятнадцать': 15, 'шестнадцать': 16,
            'семнадцать': 17, 'восемнадцать': 18,
            'девятнадцать': 19,

            # Круглые числа
            'двадцать': 20, 'тридцать': 30, 'сорок': 40,
            'пятьдесят': 50, 'шестьдесят': 60,
            'семьдесят': 70, 'восемьдесят': 80,
            'девяносто': 90,
            'сто': 100, 'двести': 200, 'триста': 300,
            'четыреста': 400, 'пятьсот': 500,
            'шестьсот': 600, 'семьсот': 700,
            'восемьсот': 800, 'девятьсот': 900,

            # Тысячи словами
            'тысяча': 1000, 'тысячу': 1000, 'тысяч': 1000,
            'одна тысяча': 1000, 'две тысячи': 2000,
            'три тысячи': 3000, 'четыре тысячи': 4000,
            'пять тысяч': 5000, 'шесть тысяч': 6000,
            'семь тысяч': 7000, 'восемь тысяч': 8000,
            'девять тысяч': 9000,

            # Миллионы словами
            'миллион': 1000000, 'миллиона': 1000000, 'миллионов': 1000000,
            'один миллион': 1000000, 'два миллиона': 2000000,
            'три миллиона': 3000000, 'четыре миллиона': 4000000,
            'пять миллионов': 5000000, 'шесть миллионов': 6000000,
            'семь миллионов': 7000000, 'восемь миллионов': 8000000,
            'девять миллионов': 9000000,
        }

        # Проверяем каждую пару в словаре
        for numeral, value in numeral_map.items():
            if numeral in message_lower:
                # Для составных числительных типа "семьдесят тысяч"
                if 'тысяч' in numeral and 'тысяч' in message_lower:
                    # Ищем число перед "тысяч"
                    before_thousand = re.search(r'(\w+)\s+тысяч', message_lower)
                    if before_thousand:
                        before_word = before_thousand.group(1)
                        if before_word in ['двадцать', 'тридцать', 'сорок', 'пятьдесят',
                                           'шестьдесят', 'семьдесят', 'восемьдесят', 'девяносто']:
                            tens_map = {
                                'двадцать': 20, 'тридцать': 30, 'сорок': 40,
                                'пятьдесят': 50, 'шестьдесят': 60,
                                'семьдесят': 70, 'восемьдесят': 80,
                                'девяносто': 90
                            }
                            return tens_map.get(before_word, 0) * 1000
                return value

        return None

    def _extract_resource_request_full(self, message):
        """Полностью извлекает информацию о запросе ресурсов с поддержкой любых числительных"""
        message_lower = message.lower()

        resource_patterns = {
            r'крон': 'Кроны',
            r'золот': 'Кроны',
            r'деньг': 'Кроны',
            r'монет': 'Кроны',
            r'кристалл': 'Кристаллы',
            r'минерал': 'Кристаллы',
            r'ресурс': 'Кристаллы',
            r'рабоч': 'Рабочие',
            r'люд': 'Рабочие',
            r'крестьян': 'Рабочие',
            r'работник': 'Рабочие',
            r'арми': 'Солдаты',
            r'солдат': 'Солдаты',
            r'войск': 'Солдаты',
            r'воин': 'Солдаты'
        }

        # Ищем ресурс
        found_resource = None
        for pattern, resource in resource_patterns.items():
            if re.search(pattern, message_lower):
                found_resource = resource
                break

        if not found_resource:
            return None

        # Извлекаем количество с помощью улучшенного метода
        amount = self._extract_number(message)

        return {
            'type': found_resource,
            'amount': amount if amount else None
        }

    def _extract_trade_info_enhanced(self, message):
        """Улучшенное извлечение информации о торговом предложении"""
        message_lower = message.lower()

        # Паттерны для поиска торговых предложений
        patterns = [
            # "дай 100 крон"
            r'(?:дай|дайте|хочу|нужно|нужны|нужен|необходимо)\s+(?P<amount>\d+)\s+(?P<type>крон|золот|кристалл|ресурс|рабоч|люд)',
            # "мне нужно 500 кристаллов"
            r'(?:мне|нам)\s+(?:нужно|нужны|необходимо)\s+(?P<amount>\d+)\s+(?P<type>крон|золот|кристалл|ресурс|рабоч|люд)',
            # "хочу получить 200 рабочих"
            r'(?:хочу|желаю|хотел|хотела)\s+(?:получить|приобрести|взять)\s+(?P<amount>\d+)\s+(?P<type>крон|золот|кристалл|ресурс|рабоч|люд)'
        ]

        import re
        for pattern in patterns:
            match = re.search(pattern, message_lower)
            if match:
                resource_map = {
                    'крон': 'Кроны', 'золот': 'Кроны',
                    'кристалл': 'Кристаллы', 'ресурс': 'Кристаллы',
                    'рабоч': 'Рабочие', 'люд': 'Рабочие'
                }

                amount = int(match.group('amount'))
                resource_type = resource_map.get(match.group('type'), 'Кроны')

                return {
                    'type': resource_type,
                    'amount': amount
                }

        return None

    def _extract_trade_offer(self, message):
        """Извлекает торговое предложение из сообщения - УЛУЧШЕННЫЙ ВАРИАНТ"""

        message_lower = message.lower()

        # Словарь соответствий ресурсов
        resource_map = {
            'крон': 'Кроны', 'кронн': 'Кроны', 'золот': 'Кроны', 'деньг': 'Кроны',
            'кристалл': 'Кристаллы', 'кристал': 'Кристаллы', 'минерал': 'Кристаллы',
            'рабоч': 'Рабочие', 'люд': 'Рабочие', 'работник': 'Рабочие'
        }

        # Ищем тип ресурса
        resource_type = None
        for key, resource in resource_map.items():
            if key in message_lower:
                resource_type = resource
                break

        if not resource_type:
            return None

        # Используем новый метод для парсинга чисел
        amount = self._extract_number_from_text(message_lower)

        if amount is None:
            # Пробуем старый метод как запасной вариант
            amount = self._extract_number(message_lower)

        if amount is None or amount <= 0:
            return None

        return {
            "type": resource_type,
            "amount": amount
        }

    def _improve_resource_clarification(self):
        """Дополнительные улучшения для уточнения ресурсов"""

        # Можно добавить более умные подсказки
        clarification_responses = {
            "ask_resource_type": [
                "Какой ресурс тебя интересует? Выбери: Кроны (деньги), Кристаллы (минералы) или Рабочие (люди).",
                "Уточни, что тебе нужно: золото (Кроны), драгоценные камни (Кристаллы) или рабочие руки (Рабочие)?",
                "Я могу предоставить: Кроны для казны, Кристаллы для магии и строительства, Рабочих для работы."
            ],
            "ask_resource_amount": [
                "Назови количество цифрами или словами (например: 1000, 1.5 тысячи, 2.2 млн, пятьсот).",
                "Сколько именно? Укажи число. Можно так: 1.5к, 2.3 млн и т.д.",
                "Какое количество тебе нужно? Можешь указать не целые числа, если нужно."
            ]
        }

        return clarification_responses

    def _handle_forced_dialog(self, message, faction, context):
        """Обрабатывает принудительный диалог (уточнение деталей)"""
        message_lower = message.lower()

        # Этап 1: Уточнение типа ресурса
        if context.get("stage") == "ask_resource_type":
            resource = self._extract_resource_type(message)
            if not resource:
                responses = [
                    "Пожалуйста, укажи какой ресурс: Кроны (деньги), Кристаллы (минералы) или Рабочие (люди)?",
                    "Какой ресурс тебе нужен? Выбери: Кроны, Кристаллы или Рабочие.",
                    "Уточни, что тебе нужно: золото (Кроны), драгоценные камни (Кристаллы) или рабочие руки (Рабочие)?"
                ]
                return random.choice(responses)

            context["resource"] = resource
            context["stage"] = "ask_resource_amount"
            return f"Хорошо, тебе нужны {resource}. Сколько именно?"

        # Этап 2: Уточнение количества
        elif context.get("stage") == "ask_resource_amount":
            # Используем улучшенный метод для парсинга чисел
            amount = self._extract_number_from_text(message)
            if not amount or amount <= 0:
                responses = [
                    "Пожалуйста, назови конкретное количество. Примеры: 100, 1.000, 10 тыс, 1.5 млн, пятьсот, тысяча.",
                    "Сколько именно? Можешь указать: 500, 2 тысячи, 1.2 млн, 70.5к и т.д.",
                    "Какое количество тебе нужно? Назови число цифрами или словами."
                ]
                return random.choice(responses)

            # Проверяем дробные числа
            fractional_msg = self._handle_fractional_amounts(amount, context)
            if fractional_msg:
                return fractional_msg

            # Проверяем, не слишком ли большое количество
            max_reasonable = 5000000  # Максимальное разумное количество
            if amount > max_reasonable:
                return f"Слишком большое количество! Назови число не больше {max_reasonable:,}."

            context["amount"] = amount
            context["stage"] = "ask_player_offer"

            # Проверяем наличие ресурсов у ИИ
            return self._check_ai_stock_and_respond(faction, context)

            # Добавляем обработку улучшения отношений
        if context.get("stage") == "improve_relations_choice":
            return self._process_improvement_choice(message, faction, context)

        if context.get("stage") == "ask_player_offer":
            # Используем улучшенный парсинг для торговых предложений
            offer = self._extract_trade_offer_enhanced(message)  # Нужно создать этот метод
            if not offer:
                # Проверяем, может быть игрок говорит "ничего" или отказывается
                if any(word in message_lower for word in
                       ['ничего', 'не хочу', 'отказываюсь', 'нет', 'хватит', 'прекратим']):
                    context["stage"] = "idle"
                    return "Хорошо, тогда не будем торговать."

                # Пробуем извлечь ресурс напрямую из сообщения
                resource = self._extract_resource_type(message)
                if resource:
                    # Если есть число, создаем предложение
                    amount = self._extract_number_from_text(message)
                    if amount:
                        offer = {
                            "type": resource,
                            "amount": amount
                        }
                        context["player_offer"] = offer
                        context["stage"] = "evaluate"
                        return self._evaluate_trade(faction, context)

                return "Что именно ты предлагаешь взамен? Назови ресурс и количество."

            # Сохраняем предложение и переходим к оценке
            context["player_offer"] = offer
            context["stage"] = "evaluate"
            return self._evaluate_trade(faction, context)

        # Обработка стадии counter_offer (предложение улучшения)
        if context.get("stage") == "counter_offer":
            # Проверяем, соглашается ли игрок на предложенное улучшение
            if any(word in message_lower for word in ['да', 'согласен', 'ок', 'хорошо', 'ладно', 'принимаю']):
                # Игрок согласился на улучшение - обновляем контекст и оцениваем
                context["stage"] = "evaluate"
                return self._evaluate_trade(faction, context)
            elif any(word in message_lower for word in ['нет', 'не согласен', 'отказываюсь']):
                context["stage"] = "idle"
                return "Хорошо, тогда сделку отменяем."
            else:
                # Игрок предлагает новый вариант
                offer = self._extract_trade_offer_enhanced(message)
                if offer:
                    context["player_offer"] = offer
                    context["stage"] = "evaluate"
                    return self._evaluate_trade(faction, context)
                else:
                    return "Назови свое предложение или ответь на мое предложение."

        return None

    def _is_relation_check(self, message):
        """Определяет, является ли сообщение запросом о текущих отношениях"""
        relation_keywords = [
            'какие отношения', 'как ты ко мне относишься', 'как наши отношения',
            'отношения с', 'что думаешь о', 'как воспринимаешь',
            'наши взаимоотношения', 'как обстоят дела между нами',
            'что скажешь о наших отношениях', 'как мы ладим'
        ]

        message_lower = message.lower()
        return any(keyword in message_lower for keyword in relation_keywords)

    def _handle_relation_check(self, message, target_faction, relation_level, status):
        """Обрабатывает запрос о текущих отношениях"""
        responses = []

        if relation_level >= 90:
            responses = [
                f"Ты мой верный союзник! Наши отношения на уровне {relation_level}/100. Я доверяю тебе как себе!",
                f"Мы как братья! {relation_level}/100 - что может быть лучше?",
                f"Наши знамёна реют вместе! Отношения: {relation_level}/100 ({status}).",
                f"С тобой я готов идти в огонь и воду! {relation_level}/100 говорит само за себя."
            ]
        elif relation_level >= 75:
            responses = [
                f"Ты мой хороший друг! Наши отношения: {relation_level}/100 ({status}).",
                f"Мы находим общий язык! {relation_level}/100 - неплохой результат.",
                f"Я тебе доверяю, но не безоговорочно. Отношения: {relation_level}/100.",
                f"Ты надёжный партнёр! {relation_level}/100 - мы на правильном пути."
            ]
        elif relation_level >= 60:
            responses = [
                f"Наши отношения нейтральны: {relation_level}/100 ({status}).",
                f"Ты мне не враг, но и не друг. {relation_level}/100 - так себе.",
                f"Мы сотрудничаем, но без особого энтузиазма. {relation_level}/100.",
                f"Отношения на среднем уровне: {relation_level}/100."
            ]
        elif relation_level >= 40:
            responses = [
                f"Между нами напряжённость: {relation_level}/100 ({status}).",
                f"Ты мне не очень нравишься. {relation_level}/100 - могло быть и хуже.",
                f"Наши отношения прохладные: {relation_level}/100.",
                f"Я к тебе не испытываю симпатии. {relation_level}/100."
            ]
        elif relation_level >= 20:
            responses = [
                f"Ты мой враг! {relation_level}/100 ({status}) - лучше держись подальше!",
                f"Я тебя ненавижу! {relation_level}/100 - даже смотреть на тебя противно!",
                f"Наши отношения враждебные: {relation_level}/100.",
                f"Ты мне откровенно не нравишься! {relation_level}/100."
            ]
        else:
            responses = [
                f"Ты смертельный враг! {relation_level}/100 ({status}) - готов убить при первой возможности!",
                f"Ненавижу всем сердцем! {relation_level}/100 - не хочу даже разговаривать!",
                f"Отношения на дне: {relation_level}/100.",
                f"Ты для меня хуже чумы! {relation_level}/100."
            ]

        return random.choice(responses)

    def _extract_trade_offer_enhanced(self, message):
        """Улучшенное извлечение торгового предложения с поддержкой десятичных чисел"""

        message_lower = message.lower()

        # Словарь соответствий ресурсов
        resource_map = {
            'крон': 'Кроны', 'кронн': 'Кроны', 'золот': 'Кроны', 'деньг': 'Кроны',
            'кристалл': 'Кристаллы', 'кристал': 'Кристаллы', 'минерал': 'Кристаллы',
            'рабоч': 'Рабочие', 'люд': 'Рабочие', 'работник': 'Рабочие'
        }

        # Ищем тип ресурса
        resource_type = None
        for key, resource in resource_map.items():
            if key in message_lower:
                resource_type = resource
                break

        if not resource_type:
            return None

        # Используем улучшенный метод для парсинга чисел
        amount = self._extract_number_from_text(message_lower)

        if amount is None:
            # Пробуем старый метод как запасной вариант
            amount = self._extract_number(message_lower)

        if amount is None or amount <= 0:
            return None

        return {
            "type": resource_type,
            "amount": amount
        }

    def _handle_fractional_amounts(self, amount, context):
        """Обрабатывает дробные количества в сделках"""
        # Если количество дробное
        if isinstance(amount, float):
            # Округляем до целого для некоторых ресурсов
            resource = context.get("resource", "")

            if resource == "Рабочие":
                # Рабочие должны быть целыми
                rounded_amount = int(round(amount))
                return f"Рабочих не может быть дробным. Округляю до {rounded_amount:,}."
            elif resource in ["Кроны", "Кристаллы"]:
                # Для денег и кристаллов можем оставить дробным
                return None  # Нет сообщения, принимаем как есть
            else:
                # По умолчанию округляем
                rounded_amount = int(round(amount))
                return f"Округляю до {rounded_amount:,}."

        return None

    def _check_ai_stock_and_respond(self, faction, context):
        """Проверяет наличие ресурсов у ИИ и генерирует ответ"""
        ai_resources = self._get_ai_resources(faction)
        have = ai_resources.get(context["resource"], 0)
        need = context["amount"]

        # Форматируем количество для читаемости
        if isinstance(need, float):
            # Для дробных чисел
            if need < 1000:
                formatted_amount = f"{need:.1f}"
            elif need < 1000000:
                formatted_amount = f"{need:,.1f} ({need / 1000:.1f} тыс)"
            else:
                formatted_amount = f"{need:,.1f} ({need / 1000000:.1f} млн)"
        else:
            # Для целых чисел
            formatted_amount = f"{need:,}"
            if need >= 1000:
                if need < 1000000:
                    formatted_amount = f"{formatted_amount} ({need // 1000} тыс)"
                else:
                    formatted_amount = f"{formatted_amount} ({need // 1000000} млн)"

        if have < need:
            context["stage"] = "idle"
            if isinstance(have, float):
                formatted_have = f"{have:.1f}"
            else:
                formatted_have = f"{have:,}"
            return f"У меня нет столько {context['resource']}. У меня всего {formatted_have}, а ты просишь {formatted_amount}. Сделка невозможна."

        context["stage"] = "ask_player_offer"
        return f"У меня есть {formatted_amount} {context['resource']}. Что ты предлагаешь взамен?"

    def _evaluate_trade(self, faction, context):
        """Оценивает торговое предложение с учетом отношений"""
        # Получаем данные о сделке из контекста
        resource = context.get("resource")
        amount = context.get("amount")
        player_offer = context.get("player_offer")

        if not all([resource, amount, player_offer]):
            return "Что-то пошло не так. Давайте начнем переговоры заново."

        # Создаем информацию о сделке
        deal_info = {
            'ai_gives_type': resource,
            'ai_gives_amount': amount,
            'player_gives_type': player_offer['type'],
            'player_gives_amount': player_offer['amount']
        }

        # Рассчитываем привлекательность
        attractiveness_data = self.calculate_deal_attractiveness(faction, deal_info, is_ai_giving=True)
        attractiveness = attractiveness_data['attractiveness']

        # Определяем порог принятия на основе отношений
        relations = self.advisor.relations_manager.load_combined_relations()
        relation_data = relations.get(faction, {"relation_level": 50})
        relation_level = int(relation_data.get("relation_level", 50))

        # Динамический порог: лучше отношения = более выгодные сделки для игрока
        if relation_level < 35:
            threshold = 1.5  # При плохих отношениях требуем очень выгодную сделку
        elif relation_level < 60:
            threshold = 1.2  # При нейтральных отношениях
        elif relation_level < 80:
            threshold = 1.0  # При дружественных
        else:
            threshold = 0.9  # При союзнических готовы на менее выгодные сделки

        # Отладочная информация
        print(f"DEBUG: Привлекательность сделки: {attractiveness:.2f}")
        print(f"DEBUG: Порог принятия: {threshold}")
        print(f"DEBUG: Коэффициент отношений: {attractiveness_data['relation_coefficient']}")

        # Принимаем решение
        if attractiveness >= threshold:
            # Сделка выгодна
            context["stage"] = "agreement"
            context["active_request"] = {
                "type": "resource_trade",
                "player_offers": player_offer,
                "ai_offers": {"type": resource, "amount": amount},
            }

            # Выполняем сделку
            if self.execute_agreed_trade(faction, context["active_request"]):
                # Улучшаем отношения при успешной сделке
                self.improve_relations_from_trade(faction, amount)
                return f"Согласен! Если не возникнет форс-мажора, жди поставки через день."
            else:
                context["stage"] = "idle"
                return "Согласен, но возникла ошибка при обработке."

        else:
            # Сделка невыгодна - предлагаем улучшение
            context["stage"] = "counter_offer"

            # Рассчитываем, что нужно изменить
            needed_improvement = threshold - attractiveness

            # Предлагаем конкретные изменения
            if needed_improvement > 0.5:
                # Нужно значительно улучшить предложение
                suggested_multiplier = 1.0 + needed_improvement
                suggested_amount = int(player_offer['amount'] * suggested_multiplier)

                return (f"При наших отношениях ({relation_level}/100) это предложение недостаточно выгодно. "
                        f"Предложи хотя бы {suggested_amount} {player_offer['type'].lower()}.")

            elif needed_improvement > 0.2:
                # Небольшое улучшение
                suggested_amount = int(player_offer['amount'] * 1.3)

                return (f"Для текущего уровня отношений ({relation_level}/100) нужно немного улучшить предложение. "
                        f"Добавь еще {suggested_amount - player_offer['amount']} {player_offer['type'].lower()}.")

            else:
                # Почти достигли порога
                return (f"Мы почти договорились! При наших отношениях ({relation_level}/100) "
                        f"нужно совсем немного улучшить предложение. Можешь добавить еще "
                        f"{int(player_offer['amount'] * 0.1)} {player_offer['type'].lower()}?")

    def improve_relations_from_trade(self, faction, trade_amount):
        """Улучшает отношения после успешной сделки"""
        try:
            cursor = self.db_connection.cursor()

            # Рассчитываем улучшение отношений в зависимости от размера сделки
            if trade_amount < 100:
                improvement = 1
            elif trade_amount < 500:
                improvement = 2
            elif trade_amount < 1000:
                improvement = 3
            else:
                improvement = 5

            # Обновляем отношения
            cursor.execute('''
                UPDATE ai_relations 
                SET relation_level = relation_level + ? 
                WHERE ai_faction = ? AND target_faction = ?
            ''', (improvement, faction, self.faction))

            # Также обновляем в другую сторону
            cursor.execute('''
                UPDATE ai_relations 
                SET relation_level = relation_level + ? 
                WHERE ai_faction = ? AND target_faction = ?
            ''', (improvement, self.faction, faction))

            self.db_connection.commit()

            # Обновляем кэш отношений
            self.advisor.relations_manager.refresh_relations()

            print(f"Отношения с {faction} улучшены на {improvement}")

        except Exception as e:
            print(f"Ошибка при улучшении отношений: {e}")

    def _extract_trade_info(self, message):
        """Извлекает информацию о торговом предложении"""
        message_lower = message.lower()

        # Паттерны для поиска торговых предложений
        patterns = [
            r'(?P<give_amount>\d+)\s*(?P<give_type>крон|золот|кристалл|ресурс|рабоч|люд)[^\d]*(?P<get_amount>\d+)\s*(?P<get_type>крон|золот|кристалл|ресурс|рабоч|люд)',
            r'(?P<give_type>крон|золот|кристалл|ресурс|рабоч|люд)[^\d]*(?P<give_amount>\d+)[^\d]*(?P<get_type>крон|золот|кристалл|ресурс|рабоч|люд)[^\d]*(?P<get_amount>\d+)'
        ]

        import re
        for pattern in patterns:
            match = re.search(pattern, message_lower)
            if match:
                resource_map = {
                    'крон': 'Кроны', 'золот': 'Кроны',
                    'кристалл': 'Кристаллы', 'ресурс': 'Кристаллы',
                    'рабоч': 'Рабочие', 'люд': 'Рабочие'
                }

                return {
                    'give_type': resource_map.get(match.group('give_type'), 'Кроны'),
                    'give_amount': int(match.group('give_amount')),
                    'get_type': resource_map.get(match.group('get_type'), 'Кристаллы'),
                    'get_amount': int(match.group('get_amount'))
                }

        return None

    def _extract_resource_type(self, message):
        message_lower = message.lower()
        if any(word in message_lower for word in ['крон', 'золот', 'деньг']):
            return 'Кроны'
        elif any(word in message_lower for word in ['кристалл', 'ресурс', 'материал']):
            return 'Кристаллы'
        elif any(word in message_lower for word in ['рабоч', 'люд']):
            return 'Рабочие'
        return None

    def _get_ai_resources(self, faction):
        """Получает текущие ресурсы ИИ фракции"""
        # Используем соединение из AIController
        from ii import AIController

        # Создаем временный контроллер для проверки ресурсов
        ai = AIController(faction, self.db_connection)
        ai.load_resources_from_db()

        return {
            'Кроны': ai.resources.get('Кроны', 0),
            'Кристаллы': ai.resources.get('Кристаллы', 0),
            'Рабочие': ai.resources.get('Рабочие', 0)
        }

    def _calculate_trade_ratio(self, trade_info, faction, relation_data):
        """Рассчитывает соотношение торговой сделки"""

        # Получаем ресурсы ИИ
        ai_resources = self._get_ai_resources(faction)

        # Ценности ресурсов (более сбалансированные)
        resource_values = {
            'Кроны': 1.0,
            'Кристаллы': 1.0,
            'Рабочие': 1.0
        }

        # Что ИИ отдает
        ai_gives_value = trade_info['give_amount'] * resource_values.get(trade_info['give_type'], 1.0)

        # Что ИИ получает
        ai_gets_value = trade_info['get_amount'] * resource_values.get(trade_info['get_type'], 1.0)

        # Учитываем доступность ресурсов (но менее строго)
        ai_has_amount = ai_resources.get(trade_info['give_type'], 0)
        if ai_has_amount == 0:
            availability = 0  # Нет ресурсов вообще
        else:
            availability = min(1.0, ai_has_amount / max(1, trade_info['give_amount']))
            if availability < 0.5:
                availability = 0.5  # Минимальный доступный коэффициент

        # Учитываем отношения
        relation_level = int(relation_data.get("relation_level", 50))
        relation_factor = 0.8 + (relation_level - 50) / 100.0  # От 0.3 до 1.3

        # Рассчитываем выгодность
        if ai_gives_value > 0:
            base_ratio = ai_gets_value / ai_gives_value
            final_ratio = base_ratio * availability * relation_factor

            # Отладочная печать
            print(
                f"DEBUG: give={trade_info['give_amount']} {trade_info['give_type']}, get={trade_info['get_amount']} {trade_info['get_type']}")
            print(
                f"DEBUG: base_ratio={base_ratio}, availability={availability}, relation_factor={relation_factor}, final={final_ratio}")

            return final_ratio

        return 0

    def _suggest_trade_improvement(self, trade_info, current_ratio, threshold):
        """Предлагает улучшение торгового предложения"""

        # На сколько нужно улучшить предложение
        improvement_needed = threshold - current_ratio

        if improvement_needed > 0:
            # Предлагаем увеличить то, что игрок дает
            suggested_amount = int(trade_info['get_amount'] * (1 + improvement_needed * 1.5))

            # Проверяем разумность предложения (не более чем в 2 раза)
            if suggested_amount > trade_info['get_amount'] * 2:
                suggested_amount = trade_info['get_amount'] * 2

            return f"Это предложение недостаточно выгодно. Предложи {suggested_amount} {trade_info['get_type'].lower()} вместо {trade_info['get_amount']}?"

        return f"Предложи больше {trade_info['get_type'].lower()} или меньше {trade_info['give_type'].lower()}"

    def create_trade_agreement(self, initiator, target_faction, give_resource, give_amount, get_resource, get_amount):
        """Создает торговое соглашение"""
        try:
            cursor = self.db_connection.cursor()

            cursor.execute('''
                INSERT INTO trade_agreements 
                (initiator, target_faction, initiator_type_resource, initiator_summ_resource, 
                 target_type_resource, target_summ_resource, agree)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                initiator,
                target_faction,
                give_resource,
                give_amount,
                get_resource,
                get_amount,
                0  # 0 = ожидает подтверждения, 1 = принято, 2 = отклонено
            ))

            self.db_connection.commit()
            print(f"Создано торговое соглашение: {initiator} -> {target_faction}")
            return True

        except Exception as e:
            print(f"Ошибка при создании торгового соглашения: {e}")
            return False

    def _create_trade_query(self, faction, trade_info):
        """Создает торговое соглашение вместо записи в queries"""
        try:
            # trade_info содержит:
            # give_type: что ИИ отдает (ресурс игроку)
            # give_amount: сколько отдает
            # get_type: что ИИ получает (ресурс от игрока)
            # get_amount: сколько получает

            # С точки зрения ИИ:
            # initiator = игрок (self.faction)
            # target_faction = ИИ (faction)
            # Инициатор отдает get_type:get_amount, получает give_type:give_amount

            # Но в чате игрок - инициатор, поэтому:
            return self.create_trade_agreement(
                initiator=self.faction,  # Игрок инициирует сделку
                target_faction=faction,  # ИИ - цель
                give_resource=trade_info['get_type'],  # Что игрок отдает (то, что ИИ получает)
                give_amount=trade_info['get_amount'],
                get_resource=trade_info['give_type'],  # Что игрок получает (то, что ИИ отдает)
                get_amount=trade_info['give_amount']
            )

        except Exception as e:
            print(f"Ошибка при создании торгового соглашения: {e}")
            return False

    def execute_agreed_trade(self, faction, offer):
        """Выполняет согласованную сделку через trade_agreements"""
        try:
            if offer['type'] == 'resource_trade':
                player_offers = offer['player_offers']
                ai_offers = offer['ai_offers']

                # Создаем торговое соглашение
                success = self.create_trade_agreement(
                    initiator=self.faction,  # Игрок инициирует
                    target_faction=faction,  # ИИ принимает
                    give_resource=player_offers['type'],  # Игрок отдает
                    give_amount=player_offers['amount'],
                    get_resource=ai_offers['type'],  # Игрок получает
                    get_amount=ai_offers['amount']
                )

                if success:
                    # Очищаем контекст переговоров
                    if faction in self.negotiation_context:
                        self.negotiation_context[faction]['stage'] = 'completed'
                        self.negotiation_context[faction]['active_request'] = None

                    return True
                else:
                    return False

        except Exception as e:
            print(f"Ошибка при выполнении сделки: {e}")
            return False

    def save_negotiation_message(self, target_faction, message, is_player=True):
        """Сохраняет сообщение переговоров в БД"""
        try:
            cursor = self.db_connection.cursor()
            cursor.execute('''
                INSERT INTO negotiation_history 
                (faction1, faction2, message, is_player, timestamp) 
                VALUES (?, ?, ?, ?, datetime('now'))
            ''', (self.faction, target_faction, message, 1 if is_player else 0))

            self.db_connection.commit()
        except Exception as e:
            print(f"Ошибка при сохранении сообщения переговоров: {e}")

    def calculate_deal_attractiveness(self, faction, deal_info, is_ai_giving=True):
        """
        Рассчитывает привлекательность сделки с учетом отношений
        deal_info: словарь с информацией о сделке
        is_ai_giving: True если ИИ отдает ресурсы, False если получает
        """
        # Получаем уровень отношений
        relations = self.advisor.relations_manager.load_combined_relations()
        relation_data = relations.get(faction, {"relation_level": 50})
        relation_level = int(relation_data.get("relation_level", 50))

        # Базовый коэффициент отношений
        relation_coefficient = self.calculate_coefficient(relation_level)

        # Получаем ресурсы ИИ
        ai_resources = self._get_ai_resources(faction)

        # Определяем что ИИ отдает и получает
        if is_ai_giving:
            give_type = deal_info.get('ai_gives_type')
            give_amount = deal_info.get('ai_gives_amount', 0)
            get_type = deal_info.get('player_gives_type')
            get_amount = deal_info.get('player_gives_amount', 0)
        else:
            give_type = deal_info.get('player_gives_type')
            give_amount = deal_info.get('player_gives_amount', 0)
            get_type = deal_info.get('ai_gives_type')
            get_amount = deal_info.get('ai_gives_amount', 0)

        # Базовые ценности ресурсов (можно настроить)
        resource_values = {
            'Кроны': 1.0,
            'Кристаллы': 1.1,
            'Рабочие': 1.5
        }

        # Рассчитываем базовую стоимость
        give_value = give_amount * resource_values.get(give_type, 1.0)
        get_value = get_amount * resource_values.get(get_type, 1.0)

        # Учитываем доступность ресурсов у ИИ
        if give_type in ai_resources:
            ai_has = ai_resources[give_type]
            availability_factor = min(1.0, ai_has / max(1, give_amount))
        else:
            availability_factor = 0

        # Учитываем потребность в ресурсах
        need_factor = 1.0
        if get_type in ai_resources:
            # Если у ИИ мало этого ресурса, ценность выше
            current_amount = ai_resources[get_type]
            if current_amount < 100:  # Порог недостатка
                need_factor = 1.5

        # Итоговая формула привлекательности
        if give_value > 0:
            base_ratio = get_value / give_value
            attractiveness = base_ratio * relation_coefficient * availability_factor * need_factor
        else:
            attractiveness = 0

        return {
            'attractiveness': attractiveness,
            'base_ratio': get_value / give_value if give_value > 0 else 0,
            'relation_coefficient': relation_coefficient,
            'availability_factor': availability_factor,
            'need_factor': need_factor
        }

    def calculate_coefficient(self, relation_level):
        """Рассчитывает коэффициент на основе уровня отношений"""
        try:
            rel = int(relation_level)
        except (ValueError, TypeError):
            rel = 50

        if rel < 15:
            return 0
        if 15 <= rel < 25:
            return 0.1
        if 25 <= rel < 35:
            return 0.4
        if 35 <= rel < 54:
            return 0.95
        if 54 <= rel < 65:
            return 1.5
        if 65 <= rel < 75:
            return 2
        if 75 <= rel < 90:
            return 3.1
        if 90 <= rel <= 100:
            return 4
        return 0

    def get_relation_color(self, value):
        """Возвращает цвет в зависимости от значения"""
        try:
            value = int(value)
        except (ValueError, TypeError):
            value = 50

        if value <= 15:
            return (0.8, 0.1, 0.1, 1)
        elif 15 < value <= 25:
            return (1.0, 0.5, 0.0, 1)
        elif 25 < value <= 35:
            return (1.0, 0.8, 0.0, 1)
        elif 35 < value <= 54:
            return (0.2, 0.7, 0.3, 1)
        elif 54 < value <= 65:
            return (0.0, 0.8, 0.8, 1)
        elif 65 < value <= 75:
            return (0.0, 0.6, 1.0, 1)
        elif 75 < value <= 90:
            return (0.1, 0.3, 0.9, 1)
        else:
            return (1, 1, 1, 1)

    def _is_status_inquiry(self, message):
        """Определяет, является ли сообщение общим запросом о состоянии (без упоминания конкретных ресурсов)"""
        message_lower = message.lower()

        # Исключаем вопросы с упоминанием конкретных ресурсов
        resource_words = ['крон', 'золот', 'деньг', 'монет', 'кристалл', 'руда', 'минерал',
                          'рабоч', 'люд', 'крестьян', 'работник', 'ресурс']
        if any(word in message_lower for word in resource_words):
            return False

        inquiry_keywords = [
            'как дела', 'как ты', 'как ваши дела', 'что нового', 'как твои дела', 'ты как',
            'как поживаешь', 'как жизнь', 'как успехи', 'что по войскам',
            'как армия', 'сила армии', 'мощь', 'могущество', 'состояние',
            'положение', 'обстановка', 'ситуация'
        ]
        return any(keyword in message_lower for keyword in inquiry_keywords)

    def _generate_status_response(self, faction):
        """Генерирует ответ о состоянии дел фракции"""
        try:
            cursor = self.db_connection.cursor()

            # 1. Получаем ресурсы
            resources = {}
            cursor.execute("""
                SELECT resource_type, amount FROM resources 
                WHERE faction = ? AND resource_type IN ('Кроны', 'Кристаллы', 'Рабочие')
            """, (faction,))
            for res_type, amount in cursor.fetchall():
                resources[res_type] = amount

            # 2. Рассчитываем силу армии
            army_strength = self._calculate_army_strength(faction)

            # 3. Получаем количество городов
            cursor.execute("SELECT COUNT(*) FROM cities WHERE faction = ?", (faction,))
            city_count = cursor.fetchone()[0]

            # 4. Получаем текущие отношения
            relations = self.advisor.relations_manager.load_combined_relations()
            relation_data = relations.get(self.faction, {"relation_level": 50, "status": "нейтралитет"})
            relation_level = relation_data.get("relation_level", 50)

            # 5. Формируем ответ
            responses = [
                f"Дела идут своим чередом. У нас {city_count} городов, армия силой {army_strength:,}. "
                f"Ресурсы: {resources.get('Кроны', 0):,} крон, {resources.get('Кристаллы', 0):,} кристаллов, "
                f"{resources.get('Рабочие', 0):,} рабочих.",

                f"Все под контролем. Владеем {city_count} поселениями, военная мощь - {army_strength:,}. "
                f"Казна: {resources.get('Кроны', 0):,}, минералы: {resources.get('Кристаллы', 0):,}, "
                f"рабочие руки: {resources.get('Рабочие', 0):,}.",

                f"Ситуация стабильна. {city_count} городов под нашей властью, армия в {army_strength:,} мощи. "
                f"Ресурсы позволяют нам развиваться."
            ]

            return random.choice(responses)

        except Exception as e:
            print(f"Ошибка при генерации статуса: {e}")
            return "Дела идут своим чередом. Что конкретно тебя интересует?"

    def _calculate_army_strength(self, faction):
        """Рассчитывает силу армии фракции"""
        try:
            cursor = self.db_connection.cursor()

            cursor.execute("""
                SELECT g.unit_name, g.unit_count, u.attack, u.defense, u.durability, u.unit_class 
                FROM garrisons g
                JOIN units u ON g.unit_name = u.unit_name
                WHERE u.faction = ?
            """, (faction,))
            units_data = cursor.fetchall()

            total_strength = 0
            class_1_count = 0
            hero_bonus = 0
            others_stats = 0

            for unit_name, unit_count, attack, defense, durability, unit_class in units_data:
                stats_sum = attack + defense + durability

                if unit_class == "1":
                    class_1_count += unit_count
                    total_strength += stats_sum * unit_count
                elif unit_class in ("2", "3"):
                    hero_bonus += stats_sum * unit_count
                else:
                    others_stats += stats_sum * unit_count

            if class_1_count > 0:
                total_strength += hero_bonus * class_1_count

            total_strength += others_stats

            return total_strength

        except Exception as e:
            print(f"Ошибка при расчете силы армии: {e}")
            return 0

    def _is_alliance_proposal(self, message):
        """Определяет, является ли сообщение предложением союза"""
        alliance_keywords = [
            'союз', 'альянс', 'объединиться', 'сотрудничать',
            'вместе', 'союзники', 'дружить', 'помогать друг другу',
            'заключить союз', 'создать альянс', 'стать союзниками',
            'общий союз', 'военный союз', 'договор о союзе'
        ]

        message_lower = message.lower()
        return any(keyword in message_lower for keyword in alliance_keywords)

    def _handle_alliance_proposal(self, message, faction, relation_level):
        """Обрабатывает предложение союза с разнообразными репликами"""
        try:
            cursor = self.db_connection.cursor()

            # Проверяем существующий союз
            cursor.execute("""
                SELECT COUNT(*) FROM diplomacies 
                WHERE ((faction1 = ? AND faction2 = ?) OR (faction1 = ? AND faction2 = ?)) 
                AND relationship = 'союз'
            """, (self.faction, faction, faction, self.faction))

            if cursor.fetchone()[0] > 0:
                existing_alliance_responses = [
                    "У нас уже есть действующий союз! Зачем его заключать снова?",
                    "Ты что, забыл? Мы уже союзники!",
                    "Наш союз и так действует. Ты проверяешь мою память?",
                    "Мы уже связаны договором. Хочешь укрепить его дополнительными клятвами?"
                ]
                return random.choice(existing_alliance_responses)

            # Проверяем уровень отношений и выбираем соответствующие реплики
            if relation_level >= 90:
                # Получаем количество городов у целевой фракции
                cursor.execute("SELECT COUNT(*) FROM cities WHERE faction = ?", (faction,))
                target_city_count = cursor.fetchone()[0]

                # Стоимость альянса
                alliance_cost = 100_000 + (300_000 * target_city_count)

                # Проверяем, есть ли у игрока достаточно крон
                cursor.execute("SELECT amount FROM resources WHERE faction = ? AND resource_type = 'Кроны'",
                               (self.faction,))
                result = cursor.fetchone()
                player_crowns = result[0] if result else 0

                if player_crowns < alliance_cost:
                    insufficient_responses = [
                        f"У тебя недостаточно крон для заключения союза! Нужно {alliance_cost:,}, а у тебя всего {player_crowns:,}.",
                        f"Сначала накопи {alliance_cost:,} крон, тогда поговорим о союзе. У тебя сейчас {player_crowns:,}.",
                        f"Союз стоит {alliance_cost:,} крон. Проверь свою казну!",
                        f"Без {alliance_cost:,} крон в казне союз невозможен."
                    ]
                    return random.choice(insufficient_responses)

                # СПИСЫВАЕМ КРОНЫ У ИГРОКА
                cursor.execute("""
                    UPDATE resources 
                    SET amount = amount - ? 
                    WHERE faction = ? AND resource_type = 'Кроны'
                """, (alliance_cost, self.faction))

                # ПРОВЕРЯЕМ И ОБНОВЛЯЕМ/СОЗДАЕМ ЗАПИСЬ В ДИПЛОМАЦИЯХ
                cursor.execute("""
                    SELECT COUNT(*) FROM diplomacies 
                    WHERE (faction1 = ? AND faction2 = ?) OR (faction1 = ? AND faction2 = ?)
                """, (self.faction, faction, faction, self.faction))

                count = cursor.fetchone()[0]

                if count > 0:
                    # Обновляем существующую запись
                    cursor.execute("""
                        UPDATE diplomacies 
                        SET relationship = 'союз' 
                        WHERE (faction1 = ? AND faction2 = ?) OR (faction1 = ? AND faction2 = ?)
                    """, (self.faction, faction, faction, self.faction))
                else:
                    # Создаем новую запись (обычно faction1 < faction2 для однозначности)
                    factions_sorted = sorted([self.faction, faction])
                    cursor.execute("""
                        INSERT INTO diplomacies (faction1, faction2, relationship)
                        VALUES (?, ?, ?)
                    """, (factions_sorted[0], factions_sorted[1], 'союз'))

                # ПРОВЕРЯЕМ И ОБНОВЛЯЕМ/СОЗДАЕМ ЗАПИСЬ В RELATIONS
                cursor.execute("""
                    SELECT COUNT(*) FROM relations 
                    WHERE (faction1 = ? AND faction2 = ?) OR (faction1 = ? AND faction2 = ?)
                """, (self.faction, faction, faction, self.faction))

                count = cursor.fetchone()[0]

                if count > 0:
                    # Обновляем существующую запись
                    cursor.execute("""
                        UPDATE relations 
                        SET relationship = 100 
                        WHERE (faction1 = ? AND faction2 = ?) OR (faction1 = ? AND faction2 = ?)
                    """, (self.faction, faction, faction, self.faction))
                else:
                    # Создаем новую запись (обычно faction1 < faction2 для однозначности)
                    factions_sorted = sorted([self.faction, faction])
                    cursor.execute("""
                        INSERT INTO relations (faction1, faction2, relationship)
                        VALUES (?, ?, ?)
                    """, (factions_sorted[0], factions_sorted[1], 100))

                # Создаем запись в trade_agreements как подтверждение союза
                cursor.execute("""
                    INSERT INTO trade_agreements 
                    (initiator, target_faction, initiator_type_resource, initiator_summ_resource,
                     target_type_resource, target_summ_resource, agree, agreement_type, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                """, (
                    self.faction, faction, "Союз", alliance_cost,
                    "Согласие", 1, 1, "alliance"  # agree = 1 (принято)
                ))

                # Добавляем запись в историю переговоров
                cursor.execute("""
                    INSERT INTO negotiation_history 
                    (faction1, faction2, message, is_player, timestamp)
                    VALUES (?, ?, ?, ?, datetime('now'))
                """, (self.faction, faction, f"Заключён союз! Стоимость: {alliance_cost:,} крон.", 0))

                self.db_connection.commit()

                # Получаем фразу для фракции
                phrase = self.faction_phrases.get(faction, {}).get("alliance", "Союз заключён!")

                # Союзнические отношения (90-100)
                alliance_responses = [
                    "С радостью принимаю предложение! Наши народы станут едины!",
                    "Наконец-то! Я ждал этого момента. Союз заключён!",
                    "Это исторический день! Отныне наши судьбы переплетены навеки!",
                    "Сердце моё ликует! Принимаю твоё предложение о союзе без колебаний!"
                ]

                response = random.choice(alliance_responses)
                return f"{phrase} {response} Союз заключён! С твоей казны списано {alliance_cost:,} крон."

            elif 75 <= relation_level < 90:
                # Получаем количество городов для информации
                cursor.execute("SELECT COUNT(*) FROM cities WHERE faction = ?", (faction,))
                target_city_count = cursor.fetchone()[0]
                alliance_cost = 100_000 + (300_000 * target_city_count)

                # Очень дружественные отношения (75-89)
                friendly_responses = [
                    f"Друг, мы должны сильнее доверять друг другу, тогда союз будет крепким. Он обойдётся тебе в {alliance_cost:,} крон.",
                    f"Твоё предложение лестно, но давай сначала укрепим наше взаимное доверие. Союз стоит {alliance_cost:,} крон.",
                    f"Мы на верном пути! Ещё немного, и наши знамёна сольются воедино. Будь готов заплатить {alliance_cost:,} крон.",
                    f"Сердце говорит 'да', но разум советует немного подождать. Укрепим дружбу, а потом поговорим о союзе за {alliance_cost:,} крон."
                ]
                return random.choice(friendly_responses)

            elif 50 <= relation_level < 75:
                # Получаем количество городов для информации
                cursor.execute("SELECT COUNT(*) FROM cities WHERE faction = ?", (faction,))
                target_city_count = cursor.fetchone()[0]
                alliance_cost = 100_000 + (300_000 * target_city_count)

                # Дружественные отношения (50-74)
                neutral_responses = [
                    f"Приятель, пока рано говорить о союзе. Для начала {alliance_cost:,} крон нужно накопить.",
                    f"Интересное предложение, но спешить не стоит. Союз стоит {alliance_cost:,} крон - серьёзная сумма.",
                    f"Союз — серьёзный шаг. Начнём с малого, а там посмотрим. Кстати, цена вопроса: {alliance_cost:,} крон.",
                    f"Ты забегаешь вперёд, друг мой. Сначала докажи, что вам можно доверять. {alliance_cost:,} крон. были бы убедительным доводом"
                ]
                return random.choice(neutral_responses)

            elif 30 <= relation_level < 50:
                # Напряжённые отношения (30-49)
                tense_responses = [
                    "Не сказал бы, что в данный момент нас интересуют подобные предложения.",
                    "Ты серьёзно? Сейчас не самое подходящее время для таких разговоров.",
                    "Наши отношения ещё не готовы к подобным серьёзным шагам.",
                    "Пока не чувствую достаточного доверия для заключения союза. Давай сначала наладим отношения."
                ]
                return random.choice(tense_responses)

            elif 15 <= relation_level < 30:
                # Плохие отношения (15-29)
                bad_responses = [
                    "Я скорее башку в осиное гнездо засуну, чем заключу союз с тобой!",
                    "Да лучше я себя кастрирую тупыми ножницами!",
                    "Мои предки в гробу перевернулись бы от такого предложения!",
                    "Союз с тобой? Я лучше с голодным медведем в берлоге заночую!"
                ]
                return random.choice(bad_responses)

            else:
                # Враждебные отношения (0-14)
                hostile_responses = [
                    "Вы там ещё не сдохли? Ну ничего, мы это исправим!",
                    "Шутите что-ли? Ничего мы знаем что с такими шутниками делать.",
                    "Неужели вы действительно в таком отчаянном положении чтобы обращаться к нам за союзом?",
                    "Я сейчас кому-то в лицо плюну."
                ]
                return random.choice(hostile_responses)

        except Exception as e:
            print(f"Ошибка при обработке предложения союза: {e}")
            error_responses = [
                "Согласен"
            ]
            return random.choice(error_responses)

    def _is_peace_proposal(self, message):
        """Определяет, является ли сообщение предложением мира"""
        peace_keywords = [
            'мир', 'перемирие', 'закончить войну', 'прекратить войну',
            'договор о мире', 'заключить мир', 'прекратить боевые действия',
            'остановить войну', 'мирный договор', 'примирение'
        ]

        message_lower = message.lower()
        return any(keyword in message_lower for keyword in peace_keywords)

    def _handle_peace_proposal(self, message, faction):
        """Обрабатывает предложение мира с разнообразными репликами"""
        try:
            cursor = self.db_connection.cursor()

            # Проверяем текущие отношения
            cursor.execute("""
                SELECT relationship FROM diplomacies 
                WHERE (faction1 = ? AND faction2 = ?) OR (faction1 = ? AND faction2 = ?)
            """, (self.faction, faction, faction, self.faction))

            result = cursor.fetchone()
            if not result or result[0] != "война":
                no_war_responses = [
                    "Мы с тобой и так не воюем. Зачем мир?",
                    "Ты что, не в курсе? Между нами нет войны!",
                    "Мир? Но мы и так не сражаемся!",
                    "Какая война? У нас и так тишина."
                ]
                return random.choice(no_war_responses)

            # Рассчитываем силы армий
            player_strength = self._calculate_army_strength(self.faction)
            enemy_strength = self._calculate_army_strength(faction)

            if player_strength == 0 and enemy_strength > 0:
                player_weak_responses = [
                    "Обойдёшься. Сейчас я отыграюсь по полной.",
                    "Ты без армии, а у меня войска есть. Какие могут быть переговоры?",
                    "Сначала собери хоть какую-то армию, тогда и поговорим о мире.",
                    "Мир предлагает тот, у кого есть сила. А у тебя её нет."
                ]
                return random.choice(player_weak_responses)

            # Если у противника нет армии
            if enemy_strength == 0 and player_strength >= enemy_strength:
                cursor.execute("""
                    UPDATE diplomacies SET relationship = 'нейтралитет' 
                    WHERE (faction1 = ? AND faction2 = ?) OR (faction1 = ? AND faction2 = ?)
                """, (self.faction, faction, faction, self.faction))
                self.db_connection.commit()

                enemy_weak_responses = [
                    "Мы согласны на мир! Нам пока и воевать-то нечем...",
                    "Что ж... раз армии нет, приходится соглашаться. Мир!",
                    "Без войск сопротивляться нечем. Принимаем твоё предложение о мире.",
                    "С мечом у груди не спорят. Мир заключён по твоей милости."
                ]
                return random.choice(enemy_weak_responses)

            # Если превосходство игрока
            if player_strength > enemy_strength:
                superiority = ((player_strength - enemy_strength) / max(enemy_strength, 1)) * 100

                if superiority >= 70:
                    crushing_superiority_responses = [
                        "Ваша милость наконец соизволила нас пощадить...",
                        "Мы разбиты вдребезги. Соглашаемся на мир, пока ещё живы.",
                        "Перед такой мощью не устоять. Принимаем твои условия.",
                        "Когда противник сильнее вдесятеро, о победе не мечтают. Мир."
                    ]
                    response = random.choice(crushing_superiority_responses)
                elif 50 <= superiority < 70:
                    strong_superiority_responses = [
                        "Мы уже сдаёмся, что Вам ещё надо?...",
                        "Силы слишком неравны. Заключаем мир на твоих условиях.",
                        "Продолжать сопротивление - самоубийство. Согласны на мир.",
                        "Твоё превосходство очевидно. Принимаем предложение."
                    ]
                    response = random.choice(strong_superiority_responses)
                elif 20 <= superiority < 50:
                    moderate_superiority_responses = [
                        "У нас не осталось тех, кто готов сопротивляться...",
                        "Потери слишком велики. Лучше мир, чем полное уничтожение.",
                        "Ещё немного, и нас не останется. Заключаем мир.",
                        "Силы на исходе. Вынуждены принять твоё предложение."
                    ]
                    response = random.choice(moderate_superiority_responses)
                elif 5 <= superiority < 20:
                    slight_superiority_responses = [
                        "Это геноцид... мы вряд ли когда-то сможем воевать...",
                        "Едва держимся. Мир - единственный шанс выжить.",
                        "Капля переполнила чашу. Соглашаемся на перемирие.",
                        "Ещё один удар - и нас не станет. Принимаем мир."
                    ]
                    response = random.choice(slight_superiority_responses)
                else:
                    minimal_superiority_responses = [
                        "В следующий раз мы будем лучше готовы.",
                        "Отступаем, но не сдаёмся. Мир - лишь передышка.",
                        "Сейчас вы сильнее, но это временно. Заключаем перемирие.",
                        "Уступаем поле боя. Но война ещё не окончена."
                    ]
                    response = random.choice(minimal_superiority_responses)

                cursor.execute("""
                    UPDATE diplomacies SET relationship = 'нейтралитет' 
                    WHERE (faction1 = ? AND faction2 = ?) OR (faction1 = ? AND faction2 = ?)
                """, (self.faction, faction, faction, self.faction))
                self.db_connection.commit()

                return response

            # Если превосходство врага
            elif player_strength < enemy_strength:
                inferiority = ((enemy_strength - player_strength) / max(player_strength, 1)) * 100

                if inferiority <= 15:
                    slight_inferiority_responses = [
                        "Может Вы и правы, но мы ещё готовы продолжать сопротивление...",
                        "Не время для мира! Мы ещё можем дать бой.",
                        "Победа не так уж и далека. Отказываемся от перемирия.",
                        "Слишком рано сдаваться. Битва продолжается!"
                    ]
                    return random.choice(slight_inferiority_responses)
                else:
                    strong_inferiority_responses = [
                        "Уже сдаётесь?! Мы ещё не закончили Вас бить!",
                        "Победа близка! Зачем нам мир сейчас?",
                        "Вы на грани поражения! Сами предлагайте капитуляцию.",
                        "Мир? Только после вашей безоговорочной капитуляции!"
                    ]
                    return random.choice(strong_inferiority_responses)
            else:
                equal_responses = [
                    "Сейчас передохнём и в рыло дадим!",
                    "Никто не побеждён! Зачем прекращать битву?",
                    "Равные силы - лучший повод продолжить сражение!",
                    "Исход не ясен. Битва должна решиться!"
                ]
                return random.choice(equal_responses)

        except Exception as e:
            print(f"Ошибка при обработке предложения мира: {e}")
            error_responses = [
                "Что-то пошло не так при рассмотрении твоего предложения.",
                "Мои полководцы не могут дать ответ. Попробуй позже.",
                "В ставке разлад. Не могу принять решение сейчас.",
                "Ситуация неясна. Не могу ответить на твоё предложение."
            ]
            return random.choice(error_responses)

    def _is_provocation(self, message):
        """Определяет, является ли сообщение подстрекательством - УЛУЧШЕННАЯ ВЕРСИЯ"""
        message_lower = message.lower()

        # Словарь склонений фракций
        faction_declensions = {
            "эльфы": ["эльф", "эльфа", "эльфу", "эльфов", "эльфам", "эльфами",
                      "остроух", "остроухих", "лесн", "лесных", "древних"],
            "север": ["север", "севера", "северу", "северян", "северянам",
                      "северянин", "северянка", "холодн", "морозн", "ледян"],
            "адепты": ["адепт", "адепта", "адепту", "адептов", "адептам",
                       "адепти", "сектант", "сектантов", "верующий", "верующих"],
            "вампиры": ["вампир", "вампира", "вампиру", "вампиров", "вампирам",
                        "кровосос", "кровопийц", "ночн", "ночных", "нежить"],
            "элины": ["элин", "элина", "элину", "элинов", "элинам",
                      "песчан", "пустынн", "южан", "южанин", "южанка"]
        }

        # Ключевые слова для подстрекательства (расширенные)
        provocation_keywords = [
            'напади', 'атакуй', 'уничтожь', 'разгроми', 'бей', 'вреж', 'ударь',
            'воевать', 'воюй', 'сражайся', 'воевал', 'воевать с', 'воюй с',
            'устрани', 'ликвидируй', 'уничтожить', 'раздави', 'сотри', 'стереть',
            'напасть', 'атаковать', 'нападение', 'атака', 'вторжение',
            'подстрека', 'спровоцируй', 'спровоцировать', 'провоцируй',
            'объяви войну', 'объявить войну', 'объявляй войну',
            'иди войной', 'иди на', 'иди против', 'выступи против',
            'уничтожь их', 'разбей их', 'победи их', 'расправься с'
        ]

        # Проверяем наличие ключевых слов провокации
        has_provocation = any(keyword in message_lower for keyword in provocation_keywords)

        if not has_provocation:
            return False

        # Проверяем, упоминается ли любая фракция (кроме своей) с учетом склонений
        all_factions = ["Эльфы", "Север", "Адепты", "Вампиры", "Элины"]
        mentioned_factions = []

        for faction in all_factions:
            if faction.lower() == self.faction.lower():
                continue

            # Проверяем прямое упоминание
            if faction.lower() in message_lower:
                mentioned_factions.append(faction)
                continue

            # Проверяем склонения
            if faction.lower() in faction_declensions:
                for declension in faction_declensions[faction.lower()]:
                    if declension in message_lower:
                        mentioned_factions.append(faction)
                        break

        return len(mentioned_factions) > 0

    def _handle_provocation(self, message, faction, relation_level):
        """Обрабатывает подстрекательство с учетом уровня отношений - УЛУЧШЕННАЯ ВЕРСИЯ"""
        try:
            cursor = self.db_connection.cursor()

            # Извлекаем упомянутую фракцию
            all_factions = ["Эльфы", "Север", "Адепты", "Вампиры", "Элины"]
            faction_declensions = {
                "эльфы": ["эльф", "эльфа", "эльфу", "эльфов", "эльфам", "эльфами",
                          "остроух", "остроухих", "лесн", "лесных"],
                "север": ["север", "севера", "северу", "северян", "северянам",
                          "северянин", "холодн", "морозн"],
                "адепты": ["адепт", "адепта", "адепту", "адептов", "адептам",
                           "сектант", "верующий"],
                "вампиры": ["вампир", "вампира", "вампиру", "вампиров", "вампирам",
                            "кровосос", "ночн", "нежить"],
                "элины": ["элин", "элина", "элину", "элинов", "элинам",
                          "песчан", "пустынн", "южан"]
            }

            target_faction = None
            message_lower = message.lower()

            for f in all_factions:
                if f.lower() == self.faction.lower():
                    continue

                # Прямое упоминание
                if f.lower() in message_lower:
                    target_faction = f
                    break

                # По склонениям
                if f.lower() in faction_declensions:
                    for declension in faction_declensions[f.lower()]:
                        if declension in message_lower:
                            target_faction = f
                            break
                if target_faction:
                    break

            if not target_faction:
                return "На кого именно ты предлагаешь напасть? Уточни фракцию."

            # ========== УРОВЕНЬ 1: Отношения < 30 ==========
            if relation_level < 30:
                # Хамские ответы
                rude_responses = [
                    f"Ты что, совсем охренел?! Сам иди воюй с {target_faction} если хочешь!",
                    f"На провокации не ведусь! Убирайся отсюда со своими глупыми идеями!",
                    f"Я буду слушать твои дурацкие предложения? Да ты совсем рехнулся!",
                    f"Ты думаешь, я такой же идиот как ты? Сам нападай на {target_faction} если охота!",
                    f"Иди к чёрту со своими провокациями! Я с тобой даже разговаривать не хочу!",
                    f"Ты мне не нравишься, а твои идеи ещё больше! Заткнись и убирайся!",
                    f"С такими как ты я даже в сортире не сидел бы! Проваливай!",
                    f"Твои провокации смешны! Я не буду рисковать ради такого как ты!"
                ]
                return random.choice(rude_responses)

            # Проверяем отношения с целевой фракцией
            cursor.execute("""
                SELECT relationship FROM relations 
                WHERE (faction1 = ? AND faction2 = ?) OR (faction1 = ? AND faction2 = ?)
            """, (faction, target_faction, target_faction, faction))

            result = cursor.fetchone()
            target_relation = int(result[0]) if result else 50

            # ========== УРОВЕНЬ 2: Отношения 30-60 ==========
            if 30 <= relation_level < 60:
                # Вежливые, но осторожные ответы
                if target_relation < 30:
                    # Если и так плохие отношения с целью
                    polite_responses = [
                        f"С {target_faction} у нас и так напряжённые отношения, но начинать войну без серьёзной причины неразумно.",
                        f"Я понимаю твоё предложение, но война с {target_faction} потребует больших ресурсов и подготовки.",
                        f"Нападение на {target_faction} - серьёзный шаг. Нужно хорошо подготовиться.",
                        f"Мы не в лучших отношениях с {target_faction}, но для войны нужен веский повод."
                    ]
                elif 30 <= target_relation < 60:
                    # Нейтральные отношения
                    neutral_responses = [
                        f"С {target_faction} у нас нейтральные отношения. Зачем их портить без причины?",
                        f"Ты предлагаешь мне поссориться с {target_faction}? Это рискованный шаг.",
                        f"Напасть на {target_faction} без провокации с их стороны - не самый мудрый поступок.",
                        f"У нас нет конфликта с {target_faction}. Зачем начинать войну?"
                    ]
                else:
                    # Хорошие отношения с целью
                    good_responses = [
                        f"С {target_faction} у нас хорошие отношения! Я не собираюсь их портить.",
                        f"Ты предлагаешь мне предать {target_faction}? Это недостойно.",
                        f"{target_faction} - наши друзья. Я не стану на них нападать.",
                        f"Мы сотрудничаем с {target_faction}. Зачем разрушать это?"
                    ]

                responses = polite_responses if target_relation < 30 else (
                    good_responses if target_relation >= 60 else neutral_responses)
                return random.choice(responses)

            # ========== УРОВЕНЬ 3: Отношения 60-80 ==========
            if 60 <= relation_level < 80:
                # Может согласиться за ресурсы
                # Рассчитываем требуемое количество ресурсов
                # Чем ближе к 60, тем больше, чем ближе к 80, тем меньше
                progress = (relation_level - 60) / 20  # от 0 до 1
                base_amount = 10000  # Базовая сумма
                multiplier = 3 - (progress * 2)  # от 3x до 1x
                required_amount = int(base_amount * multiplier)

                # Проверяем текущие отношения с целью
                if target_relation >= 60:
                    # С друзьями не воюем
                    responses = [
                        f"{target_faction} - наши друзья. Я не стану на них нападать, какие бы ресурсы ты не предлагал.",
                        f"За деньги предавать друзей? Я не такой как ты!",
                        f"С {target_faction} у нас союзнические отношения. Это предложение оскорбительно.",
                        f"Я не продажный! {target_faction} нам доверяет."
                    ]
                    return random.choice(responses)

                # Предлагаем сделку
                deal_responses = [
                    f"Хм... Нападение на {target_faction} возможно, но мне нужно {required_amount:,} крон за этот риск.",
                    f"Я могу рассмотреть твоё предложение, но за {required_amount:,} крон. Война - дорогое удовольствие.",
                    f"Если ты дашь мне {required_amount:,} крон, я подумаю о нападении на {target_faction}.",
                    f"Рисковать отношениями с {target_faction} стоит {required_amount:,} крон. Готов платить?"
                ]

                # Сохраняем предложение в контексте
                self.negotiation_context[faction] = {
                    "stage": "provocation_deal",
                    "target_faction": target_faction,
                    "required_amount": required_amount,
                    "counter_offers": 0
                }

                return random.choice(deal_responses)

            # ========== УРОВЕНЬ 4: Отношения 80-90 ==========
            if 80 <= relation_level < 90:
                # 75% вероятность согласиться бесплатно
                if random.random() < 0.75:
                    # Соглашаемся бесплатно
                    if target_relation >= 60:
                        # Но не на друзей
                        responses = [
                            f"Хотя я тебе доверяю, но нападать на {target_faction} не могу. Они наши друзья.",
                            f"Друг, я бы помог, но {target_faction} нам не враги. Не могу предать.",
                            f"С {target_faction} у нас хорошие отношения. Не хочу их портить даже ради тебя.",
                            f"Я тебе доверяю, но это переходит границы. {target_faction} - наши союзники."
                        ]
                        return random.choice(responses)

                    # Объявляем войну
                    self._declare_war_on_faction(faction, target_faction)

                    free_responses = [
                        f"Для друга ничего не жалко! Объявляю войну {target_faction}!",
                        f"Раз ты просишь - так тому и быть! Наши войска выдвигаются против {target_faction}!",
                        f"Ты мой друг, поэтому я доверяю твоему суждению. Война {target_faction} объявлена!",
                        f"Ради нашей дружбы! {target_faction} теперь наши враги!"
                    ]
                    return random.choice(free_responses)
                else:
                    # 25% вероятность потребовать плату
                    required_amount = random.randint(5000, 15000)

                    self.negotiation_context[faction] = {
                        "stage": "provocation_deal",
                        "target_faction": target_faction,
                        "required_amount": required_amount,
                        "counter_offers": 0
                    }

                    payment_responses = [
                        f"Друг, я бы помог, но война с {target_faction} обойдётся в {required_amount:,} крон. Можешь оплатить?",
                        f"Я подумал... Помогу, но за {required_amount:,} крон. Согласен?",
                        f"Для такого серьёзного шага нужно {required_amount:,} крон. Готов спонсировать?",
                        f"Объявить войну {target_faction} могу, но за {required_amount:,} крон."
                    ]
                    return random.choice(payment_responses)

            # ========== УРОВЕНЬ 5: Отношения 90-100 ==========
            if relation_level >= 90:
                # Всегда соглашаемся
                if target_relation >= 70:
                    # Но не на очень близких друзей
                    responses = [
                        f"Брат, ты что? {target_faction} - наши кровные союзники! Я не могу на них напасть!",
                        f"Даже для тебя я не предам {target_faction}! Мы связаны клятвой!",
                        f"Нет, это слишком! {target_faction} нам как братья!",
                        f"Я бы для тебя жизнь отдал, но не предам {target_faction}!"
                    ]
                    return random.choice(responses)

                # Объявляем войну
                self._declare_war_on_faction(faction, target_faction)

                always_agree_responses = [
                    f"Без вопросов! Для брата всё что угодно! Война {target_faction} объявлена!",
                    f"Ты сказал - я сделал! {target_faction} теперь наши враги!",
                    f"Наше братство важнее всего! Война против {target_faction} начинается!",
                    f"Ты мой кровный брат! {target_faction} будет уничтожен по твоей просьбе!"
                ]
                return random.choice(always_agree_responses)

            return "Я не могу принять решение по этому поводу."

        except Exception as e:
            print(f"Ошибка при обработке провокации: {e}")
            return "Что-то пошло не так при рассмотрении твоего предложения."

    def _handle_provocation_deal(self, message, faction, context):
        """Обрабатывает сделку по провокации"""
        message_lower = message.lower()

        # Проверяем согласие
        if any(word in message_lower for word in ['да', 'согласен', 'ок', 'хорошо', 'ладно', 'принимаю', 'плачу']):
            # Проверяем наличие ресурсов у игрока
            required_amount = context.get("required_amount", 0)
            target_faction = context.get("target_faction")

            try:
                cursor = self.db_connection.cursor()

                # Проверяем ресурсы игрока
                cursor.execute("SELECT amount FROM resources WHERE faction = ? AND resource_type = 'Кроны'",
                               (self.faction,))
                player_resources = cursor.fetchone()

                if not player_resources or player_resources[0] < required_amount:
                    context["stage"] = "idle"
                    return f"У тебя недостаточно крон! Нужно {required_amount:,}, а у тебя {player_resources[0] if player_resources else 0:,}."

                # Списываем ресурсы
                cursor.execute("""
                    UPDATE resources 
                    SET amount = amount - ? 
                    WHERE faction = ? AND resource_type = 'Кроны'
                """, (required_amount, self.faction))

                # Объявляем войну
                self._declare_war_on_faction(faction, target_faction)

                # Добавляем запись о сделке
                cursor.execute("""
                    INSERT INTO trade_agreements 
                    (initiator, target_faction, initiator_type_resource, initiator_summ_resource,
                     target_type_resource, target_summ_resource, agree, agreement_type, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                """, (
                    self.faction, faction, "Кроны", required_amount,
                    "Подстрекательство", 1, 1, "provocation"
                ))

                self.db_connection.commit()

                context["stage"] = "idle"

                success_responses = [
                    f"Принято! {required_amount:,} крон получены. Объявляю войну {target_faction}!",
                    f"Сделка заключена! Война {target_faction} начинается.",
                    f"Ресурсы получены. Как и договаривались, {target_faction} теперь наши враги!",
                    f"Платеж принят. Наши войска выдвигаются против {target_faction}!"
                ]
                return random.choice(success_responses)

            except Exception as e:
                print(f"Ошибка при обработке сделки провокации: {e}")
                context["stage"] = "idle"
                return "Ошибка при обработке сделки. Попробуй позже."

        # Проверяем отказ
        elif any(word in message_lower for word in ['нет', 'не согласен', 'отказываюсь', 'не буду', 'дорого']):
            context["stage"] = "idle"
            refusal_responses = [
                "Жаль. Тогда не будем ничего предпринимать.",
                "Как скажешь. Остаёмся при своих интересах.",
                "Хорошо, я понял. Предложение снято.",
                "Принято к сведению."
            ]
            return random.choice(refusal_responses)

        # Торг
        else:
            # Пробуем извлечь предложение суммы
            amount = self._extract_number_from_text(message)
            if amount:
                required_amount = context.get("required_amount", 0)

                if amount >= required_amount * 0.8:  # Принимаем от 80% от запрошенного
                    # Принимаем предложение
                    context["required_amount"] = amount
                    return f"Хорошо, принимаю {amount:,} крон. Согласен?"
                else:
                    # Отказываем
                    return f"{amount:,} крон недостаточно. Мне нужно минимум {int(required_amount * 0.8):,}."

            return "Назови сумму которую готов заплатить или ответь 'да'/'нет'."

    def _declare_war_on_faction(self, requesting_faction, target_faction):
        """Вспомогательный метод для объявления войны фракции"""
        try:
            cursor = self.db_connection.cursor()

            # Объявляем войну
            cursor.execute("""
                UPDATE diplomacies 
                SET relationship = 'война' 
                WHERE (faction1 = ? AND faction2 = ?) OR (faction1 = ? AND faction2 = ?)
            """, (requesting_faction, target_faction, target_faction, requesting_faction))

            cursor.execute("""
                UPDATE relations 
                SET relationship = 0 
                WHERE (faction1 = ? AND faction2 = ?) OR (faction1 = ? AND faction2 = ?)
            """, (requesting_faction, target_faction, target_faction, requesting_faction))

            self.db_connection.commit()

            # Добавляем запись в историю
            cursor.execute("""
                INSERT INTO negotiation_history 
                (faction1, faction2, message, is_player, timestamp)
                VALUES (?, ?, ?, ?, datetime('now'))
            """, (requesting_faction, target_faction, f"Объявлена война по подстрекательству игрока", 0))

            self.db_connection.commit()

            return True

        except Exception as e:
            print(f"Ошибка при объявлении войны: {e}")
            return False

    def _is_relationship_break(self, message):
        """Определяет, является ли сообщение разрывом отношений"""
        break_keywords = [
            'разорвать', 'прекратить', 'конец', 'хватит',
            'достало', 'надоело', 'закончить', 'покончить',
            'больше не', 'не хочу', 'не буду', 'хватит общаться',
            'прекращаю', 'заканчиваю', 'прощай навсегда'
        ]

        message_lower = message.lower()
        return any(keyword in message_lower for keyword in break_keywords)

    def _handle_relationship_break(self, message, faction):
        """Обрабатывает разрыв отношений"""
        try:
            cursor = self.db_connection.cursor()

            # Ухудшаем отношения
            cursor.execute("""
                UPDATE relations 
                SET relationship = relationship - 30 
                WHERE (faction1 = ? AND faction2 = ?) OR (faction1 = ? AND faction2 = ?)
            """, (self.faction, faction, faction, self.faction))

            self.db_connection.commit()

            responses = [
                "Как скажешь. Наши отношения ухудшились.",
                "Жаль. Теперь ты мне нравишься еще меньше.",
                "Хорошо, я понял. Но помни - ты сам этого захотел.",
                "Как хочешь. Тебе будет сложнее вести со мной дела."
            ]

            return random.choice(responses)

        except Exception as e:
            print(f"Ошибка при разрыве отношений: {e}")
            return "Что-то пошло не так."

    def _get_greeting_response(self, faction, relation_level):
        """Генерирует приветствие в зависимости от отношений"""
        if relation_level >= 80:
            greetings = [
                f"Привет, друг! Рад тебя видеть!",
                f"Здравствуй, союзник! Как твои дела?",
                f"Приветствую тебя, верный друг!"
            ]
        elif relation_level >= 60:
            greetings = [
                f"Привет! Рад тебя видеть.",
                f"Здравствуйте! Как ваши дела?",
                f"Приветствую!"
            ]
        elif relation_level >= 40:
            greetings = [
                f"Здравствуйте.",
                f"Привет.",
                f"Добрый день."
            ]
        elif relation_level >= 20:
            greetings = [
                f"Что тебе нужно?",
                f"Говори.",
                f"Я слушаю."
            ]
        else:
            greetings = [
                f"Чего пришел?",
                f"Говори быстро.",
                f"У меня мало времени."
            ]

        return random.choice(greetings)

    def _get_farewell_response(self, faction):
        """Генерирует прощание"""
        farewells = [
            "До свидания!",
            "Пока! Будем ждать ваших предложений.",
            "Всего хорошего!",
            "Удачи!",
            "Береги себя!"
        ]

        return random.choice(farewells)

    def _check_ai_proposal_response(self, message, faction, relation_level):
        """
        Проверяет, отвечает ли игрок на предложение AI (торговля, союз, дружба и т.д.).
        Ищет последнее AI-сообщение в истории и анализирует ответ игрока.
        """
        message_lower = message.lower().strip()

        # Слова согласия
        agree_words = ['да', 'согласен', 'согласна', 'принимаю', 'ок', 'хорошо',
                       'ладно', 'давай', 'идёт', 'конечно', 'разумеется',
                       'по рукам', 'договорились', 'принято', 'deal', 'yes',
                       'годится', 'подходит', 'отлично', 'замечательно', 'одобряю']
        # Слова отказа
        refuse_words = ['нет', 'отказываюсь', 'не согласен', 'не хочу', 'не буду',
                        'не нужно', 'отклоняю', 'не интересно', 'отвали', 'нафиг',
                        'не надо', 'передумал', 'забудь', 'отстань', 'пошёл',
                        'no', 'отказ', 'обойдусь', 'не стоит']
        # Слова уточнения
        clarify_words = ['что предлагаешь', 'какие условия', 'подробнее', 'что конкретно',
                         'сколько', 'на каких условиях', 'что взамен', 'поясни',
                         'что именно', 'расскажи', 'объясни', 'а что', 'что ты имеешь',
                         'зачем', 'почему', 'как именно']
        # Слова благодарности
        thanks_words = ['спасибо', 'благодарю', 'спс', 'thanks', 'мерси',
                        'ценю', 'признателен']

        is_agree = any(w in message_lower for w in agree_words)
        is_refuse = any(w in message_lower for w in refuse_words)
        is_clarify = any(w in message_lower for w in clarify_words)
        is_thanks = any(w in message_lower for w in thanks_words)

        if not (is_agree or is_refuse or is_clarify or is_thanks):
            return None  # Не похоже на ответ на предложение

        # Ищем последнее AI-сообщение к этой фракции
        try:
            cursor = self.db_connection.cursor()
            player_faction = None
            cursor.execute("SELECT faction FROM turn LIMIT 1")
            row = cursor.fetchone()
            if row:
                player_faction = row[0]

            cursor.execute("""
                SELECT message FROM negotiation_history
                WHERE faction1 = ? AND faction2 = ? AND is_player = 0
                ORDER BY id DESC LIMIT 1
            """, (faction, player_faction))
            result = cursor.fetchone()
            if not result:
                return None  # Нет предложений от AI

            last_ai_msg = result[0]
        except Exception:
            return None

        # Определяем тип предложения AI
        proposal_type = None
        if '[ТОРГОВЛЯ]' in last_ai_msg:
            proposal_type = 'trade'
        elif '[СОЮЗ]' in last_ai_msg:
            proposal_type = 'alliance'
        elif '[ПРОСЬБА]' in last_ai_msg:
            proposal_type = 'resource_request'
        elif '[УГРОЗА]' in last_ai_msg or '[ПРЕДУПРЕЖДЕНИЕ]' in last_ai_msg:
            proposal_type = 'warning'
        elif any(w in last_ai_msg.lower() for w in ['дружб', 'отношени', 'сотрудничеств']):
            proposal_type = 'friendship'
        elif any(w in last_ai_msg.lower() for w in ['приветств', 'рад', 'визит']):
            proposal_type = 'greeting'

        if not proposal_type:
            return None

        # === Обработка согласия ===
        if is_agree:
            return self._handle_proposal_accept(faction, proposal_type, last_ai_msg, relation_level)

        # === Обработка отказа ===
        if is_refuse:
            return self._handle_proposal_refuse(faction, proposal_type, relation_level)

        # === Обработка уточнения ===
        if is_clarify:
            return self._handle_proposal_clarify(faction, proposal_type, last_ai_msg, relation_level)

        # === Обработка благодарности ===
        if is_thanks:
            if relation_level > 50:
                return f"Не за что! Мы ценим нашу дружбу. Наши отношения ({relation_level}%) — залог процветания."
            else:
                return f"Пустяки. Надеюсь, это укрепит наши отношения ({relation_level}%)."

        return None

    def _handle_proposal_accept(self, faction, proposal_type, ai_msg, relation_level):
        """Обработка согласия игрока на предложение AI."""
        import re

        if proposal_type == 'trade':
            # Извлекаем предложенные ресурсы из сообщения AI
            # Формат: "Предлагаем: 4724 Кроны, 1 Кристаллы."
            offer_match = re.search(r'Предлагаем?:?\s*(.+?)\.', ai_msg)
            if offer_match:
                offer_text = offer_match.group(1)
                # Пытаемся улучшить отношения
                try:
                    cursor = self.db_connection.cursor()
                    new_rel = min(100, relation_level + 5)
                    cursor.execute("""
                        UPDATE relations SET relationship = ?
                        WHERE (faction1 = ? AND faction2 = ?) OR (faction1 = ? AND faction2 = ?)
                    """, (new_rel, faction, self._get_player_faction(), self._get_player_faction(), faction))
                    self.db_connection.commit()
                except Exception:
                    pass

                responses = [
                    f"Превосходно! Сделка заключена. {offer_text} уже в пути к вам. Наши отношения улучшились до {min(100, relation_level + 5)}%.",
                    f"Отлично! Мы рады сотрудничеству. Наши торговцы доставят {offer_text}. Отношения: {min(100, relation_level + 5)}%.",
                    f"Мудрое решение! {offer_text} будут переданы. Надеемся на дальнейшую торговлю.",
                ]
                return random.choice(responses)
            else:
                return f"Отлично! Мы рады, что вы согласны на торговлю. Отношения улучшились."

        elif proposal_type == 'alliance':
            try:
                cursor = self.db_connection.cursor()
                new_rel = min(100, relation_level + 10)
                cursor.execute("""
                    UPDATE relations SET relationship = ?
                    WHERE (faction1 = ? AND faction2 = ?) OR (faction1 = ? AND faction2 = ?)
                """, (new_rel, faction, self._get_player_faction(), self._get_player_faction(), faction))
                self.db_connection.commit()
            except Exception:
                pass

            responses = [
                f"Великолепно! Союз заключён! Вместе мы — несокрушимая сила. Отношения: {min(100, relation_level + 10)}%.",
                f"Это исторический момент! Наши народы объединяются. Отношения выросли до {min(100, relation_level + 10)}%.",
                f"Да будет так! Отныне мы союзники. Враги содрогнутся! Отношения: {min(100, relation_level + 10)}%.",
            ]
            return random.choice(responses)

        elif proposal_type == 'resource_request':
            try:
                cursor = self.db_connection.cursor()
                new_rel = min(100, relation_level + 3)
                cursor.execute("""
                    UPDATE relations SET relationship = ?
                    WHERE (faction1 = ? AND faction2 = ?) OR (faction1 = ? AND faction2 = ?)
                """, (new_rel, faction, self._get_player_faction(), self._get_player_faction(), faction))
                self.db_connection.commit()
            except Exception:
                pass

            responses = [
                f"Мы бесконечно благодарны за вашу щедрость! Наш народ не забудет этого. Отношения: {min(100, relation_level + 3)}%.",
                f"Спасибо! Эта помощь спасёт множество жизней. Мы в долгу перед вами. Отношения: {min(100, relation_level + 3)}%.",
                f"Ваша поддержка бесценна! Мы обязательно отблагодарим вас, когда окрепнем.",
            ]
            return random.choice(responses)

        elif proposal_type == 'friendship':
            try:
                cursor = self.db_connection.cursor()
                new_rel = min(100, relation_level + 5)
                cursor.execute("""
                    UPDATE relations SET relationship = ?
                    WHERE (faction1 = ? AND faction2 = ?) OR (faction1 = ? AND faction2 = ?)
                """, (new_rel, faction, self._get_player_faction(), self._get_player_faction(), faction))
                self.db_connection.commit()
            except Exception:
                pass

            return f"Замечательно! Рады, что наши народы нашли общий язык. Отношения выросли до {min(100, relation_level + 5)}%."

        elif proposal_type == 'warning':
            return "Благодарим за бдительность! Вместе мы будем следить за угрозой. Если понадобится помощь — обращайтесь."

        elif proposal_type == 'greeting':
            try:
                cursor = self.db_connection.cursor()
                new_rel = min(100, relation_level + 2)
                cursor.execute("""
                    UPDATE relations SET relationship = ?
                    WHERE (faction1 = ? AND faction2 = ?) OR (faction1 = ? AND faction2 = ?)
                """, (new_rel, faction, self._get_player_faction(), self._get_player_faction(), faction))
                self.db_connection.commit()
            except Exception:
                pass
            return f"Приятно слышать! Надеемся на долгое и плодотворное сотрудничество. Отношения: {min(100, relation_level + 2)}%."

        return "Отлично! Мы рады вашему решению."

    def _handle_proposal_refuse(self, faction, proposal_type, relation_level):
        """Обработка отказа игрока."""
        try:
            cursor = self.db_connection.cursor()
            penalty = -3 if proposal_type in ('trade', 'alliance') else -1
            new_rel = max(0, relation_level + penalty)
            cursor.execute("""
                UPDATE relations SET relationship = ?
                WHERE (faction1 = ? AND faction2 = ?) OR (faction1 = ? AND faction2 = ?)
            """, (new_rel, faction, self._get_player_faction(), self._get_player_faction(), faction))
            self.db_connection.commit()
        except Exception:
            pass

        if proposal_type == 'trade':
            responses = [
                f"Жаль. Наше предложение было выгодным. Отношения: {max(0, relation_level - 3)}%.",
                f"Что ж, может в другой раз. Мы не настаиваем.",
                f"Понимаю. Но если передумаете — наши двери открыты.",
            ]
        elif proposal_type == 'alliance':
            responses = [
                f"Очень жаль. Мы надеялись на большее... Отношения: {max(0, relation_level - 3)}%.",
                f"Мы разочарованы, но уважаем ваше решение.",
                f"Что ж, союз — дело добровольное. Но помните: одиночество — плохой советник.",
            ]
        elif proposal_type == 'resource_request':
            responses = [
                "Мы понимаем. У каждого свои трудности. Не будем настаивать.",
                f"Жаль, но мы не в обиде. Отношения: {max(0, relation_level - 1)}%.",
                "Ничего. Справимся сами. Но помните — мы не просили бы без нужды.",
            ]
        else:
            responses = [
                "Понятно. Что ж, всякое бывает.",
                "Принято к сведению.",
                "Хорошо, забудем об этом.",
            ]
        return random.choice(responses)

    def _handle_proposal_clarify(self, faction, proposal_type, ai_msg, relation_level):
        """Обработка запроса уточнения от игрока."""
        if proposal_type == 'trade':
            import re
            offer_match = re.search(r'Предлагаем?:?\s*(.+?)\.', ai_msg)
            offer = offer_match.group(1) if offer_match else "ресурсы"
            return (f"Конкретно: мы предлагаем {offer}. "
                    f"Это выгодно нам обоим. У нас сейчас отношения на уровне {relation_level}%. "
                    f"Согласны на обмен?")
        elif proposal_type == 'alliance':
            return (f"Военный союз означает: мы поддерживаем друг друга в войнах, "
                    f"делимся разведданными и не нападаем друг на друга. "
                    f"Наши отношения ({relation_level}%) позволяют заключить такой союз. Согласны?")
        elif proposal_type == 'resource_request':
            return (f"Нам нужны любые ресурсы — кроны или кристаллы. "
                    f"Даже небольшая помощь будет кстати. "
                    f"Взамен мы можем улучшить наши отношения. Поможете?")
        elif proposal_type == 'warning':
            return (f"Наша разведка обнаружила, что враг наращивает армию. "
                    f"Если они нападут — нам лучше быть готовыми. "
                    f"Совместная оборона — лучший вариант. Что скажете?")
        else:
            return f"Мы просто хотели наладить контакт. Наши отношения сейчас {relation_level}%. Чего бы вы хотели?"

    def _get_player_faction(self):
        """Получает фракцию игрока из БД."""
        try:
            cursor = self.db_connection.cursor()
            cursor.execute("SELECT faction FROM turn LIMIT 1")
            row = cursor.fetchone()
            return row[0] if row else None
        except Exception:
            return None

    def _generate_fallback_response(self, message, faction, relation_level):
        """Генерирует ответ, когда не распознан интент, используя память разговора"""

        # Проверяем вручную на ключевые слова
        message_lower = message.lower()

        # Приветствия
        greeting_words = ['привет', 'здравствуй', 'здравствуйте', 'добрый', 'хай', 'здаров', 'ку', 'hello', 'hi']
        if any(word in message_lower for word in greeting_words):
            return self._get_greeting_response(faction, relation_level)

        # Прощания
        farewell_words = ['пока', 'до свидания', 'прощай', 'удачи', 'всего', 'bye', 'goodbye']
        if any(word in message_lower for word in farewell_words):
            return self._get_farewell_response(faction)

        # Благодарности
        thanks_words = ['спасибо', 'благодарю', 'thanks', 'thank you']
        if any(word in message_lower for word in thanks_words):
            return random.choice(["Пожалуйста!", "Рад помочь!", "Не за что!"])

        # Проверяем на повторяющиеся вопросы в памяти
        if self._is_repeated_question(message):
            return self._handle_repeated_question(message, faction, relation_level)

        # Анализируем контекст предыдущих сообщений
        context_hint = self._analyze_conversation_context()
        if context_hint:
            return context_hint

        # Если ничего не распознано
        if relation_level >= 60:
            fallbacks = [
                "Я не совсем понял твой запрос. Можешь уточнить?",
                "Попробуй перефразировать, я не понял.",
                "Прости, я не уловил суть твоего сообщения."
            ]
        elif relation_level >= 30:
            fallbacks = [
                "Я не понимаю что ты хочешь, давай по существу...",
                "Слушай друг, я не так умен как ты думаешь, поэтому давай по существу, тебе нужны ресурсы, "
                "информация? что именно?.",
                "Попробуй перефразировать.."
            ]
        else:
            fallbacks = [
                "Говори понятнее.",
                "Чего бормочешь?",
                "Выражайся яснее."
            ]

        return random.choice(fallbacks)

    def _is_repeated_question(self, message):
        """Проверяет, является ли сообщение повторяющимся вопросом"""
        if len(self.conversation_memory) < 2:
            return False

        message_lower = message.lower().strip()
        recent_messages = [msg['player'].lower().strip() for msg in self.conversation_memory[-3:]]

        # Проверяем, повторяется ли сообщение
        return recent_messages.count(message_lower) >= 2

    def _handle_repeated_question(self, message, faction, relation_level):
        """Обрабатывает повторяющиеся вопросы"""
        if relation_level < 30:
            responses = [
                "Сколько можно повторять одно и то же?!",
                "Ты что, издеваешься надо мной?!",
                "Хватит уже долдонить одно и то же!",
                "Ты тупой что ли? Я же уже ответил!",
                "Прекрати повторяться, идиот!"
            ]
        elif relation_level < 60:
            responses = [
                "Я уже отвечал на этот вопрос...",
                "Мы же только что об этом говорили.",
                "Давай сменим тему, я уже устал повторять.",
                "Ты что, не помнишь наш разговор?"
            ]
        else:
            responses = [
                "Как я уже говорил...",
                "Повторюсь, поскольку ты спросил снова...",
                "Напомню, что мы обсуждали ранее..."
            ]

        return random.choice(responses)

    def _analyze_conversation_context(self):
        """Анализирует контекст разговора для подсказок"""
        if len(self.conversation_memory) < 2:
            return None

        # Анализируем последние сообщения
        recent = self.conversation_memory[-3:]

        # Если пользователь спрашивал о ресурсах, но не уточнил тип
        resource_questions = ['ресурсы', 'ресурс', 'деньги', 'кроны', 'кристаллы', 'рабочие']
        for msg in recent:
            if any(word in msg['player'].lower() for word in resource_questions):
                if not any(word in msg['ai'].lower() for word in ['кроны', 'кристаллы', 'рабочие']):
                    return "Если ты спрашиваешь о ресурсах, уточни какие именно: Кроны (деньги), Кристаллы (минералы) или Рабочие (люди)?"

        # Если пользователь спрашивал об отношениях
        relation_questions = ['отношения', 'друзья', 'союз', 'война', 'мир']
        for msg in recent:
            if any(word in msg['player'].lower() for word in relation_questions):
                return "Если хочешь узнать об отношениях, спроси 'Как у нас отношения?' или 'Какой у нас статус?'"

        return None

    def _is_improve_relations_request(self, message):
        """Определяет, является ли сообщение запросом на улучшение отношений"""
        improve_keywords = [
            'улучшить отношения', 'наладить отношения', 'налаживать отношения',
            'подружиться', 'стать друзьями', 'укрепить отношения',
            'наладить связи', 'улучшить контакт', 'наладить диалог',
            'сблизиться', 'наладить дружбу', 'улучшить взаимопонимание',
            'построить мосты', 'наладить сотрудничество'
        ]

        message_lower = message.lower()
        return any(keyword in message_lower for keyword in improve_keywords)

    def _handle_improve_relations_request(self, message, target_faction, relation_level):
        """Обрабатывает запрос на улучшение отношений"""
        try:
            cursor = self.db_connection.cursor()

            # Проверяем текущие отношения
            cursor.execute("""
                SELECT relationship FROM relations 
                WHERE (faction1 = ? AND faction2 = ?) OR (faction1 = ? AND faction2 = ?)
            """, (self.faction, target_faction, target_faction, self.faction))

            result = cursor.fetchone()
            if not result:
                return "У нас с тобой ещё не установлены отношения. Сначала нужно познакомиться."

            current_relationship = int(result[0])

            # Если отношения уже максимальные
            if current_relationship >= 90:
                responses = [
                    f"Наши отношения уже прекрасны! {current_relationship}/100 - что ещё можно улучшить?",
                    f"Мы и так хорошие друзья! Отношения на уровне {current_relationship}/100.",
                    f"Ты что, не видишь? Мы уже почти родственники! {current_relationship}/100."
                ]
                return random.choice(responses)

            # Рассчитываем стоимость улучшения
            cursor.execute("SELECT COUNT(*) FROM cities WHERE faction = ?", (target_faction,))
            target_city_count = cursor.fetchone()[0]

            # Стоимость улучшения зависит от:
            # 1. Количества городов цели
            # 2. Текущего уровня отношений (чем лучше отношения, тем дешевле)
            base_cost = 50000  # Базовая стоимость

            # Модификатор количества городов
            city_modifier = 1 + (target_city_count * 0.1)

            # Модификатор текущих отношений (чем лучше, тем дешевле)
            relation_modifier = max(0.5, 1.0 - (current_relationship / 200))

            # Итоговая стоимость
            cost = int(base_cost * city_modifier * relation_modifier)

            # Проверяем ресурсы игрока
            cursor.execute("SELECT amount FROM resources WHERE faction = ? AND resource_type = 'Кроны'",
                           (self.faction,))
            player_resources = cursor.fetchone()

            if not player_resources or player_resources[0] < cost:
                return (f"Для улучшения отношений нужно {cost:,} крон. "
                        f"У тебя всего {player_resources[0] if player_resources else 0:,}. "
                        f"Сначала накопи нужную сумму.")

            # Генерируем предложение с вариантами
            improvement_options = [
                {
                    'name': 'культурный обмен',
                    'cost': cost,
                    'improvement': 7,
                    'description': 'Обмен культурными ценностями и традициями'
                },
                {
                    'name': 'торговый договор',
                    'cost': int(cost * 0.8),
                    'improvement': 5,
                    'description': 'Соглашение о взаимовыгодной торговле'
                },
                {
                    'name': 'дипломатический визит',
                    'cost': int(cost * 1.2),
                    'improvement': 10,
                    'description': 'Официальный визит делегации'
                }
            ]

            # Сохраняем варианты в контексте
            self.negotiation_context[target_faction] = {
                'stage': 'improve_relations_choice',
                'options': improvement_options,
                'counter_offers': 0
            }

            # Формируем предложение
            response = (f"Я могу предложить несколько вариантов улучшения отношений:\n\n"
                        f"1. **Культурный обмен** ({improvement_options[0]['description']}) - "
                        f"{improvement_options[0]['improvement']} к отношениям, стоимость {improvement_options[0]['cost']:,} крон\n"
                        f"2. **Торговый договор** ({improvement_options[1]['description']}) - "
                        f"{improvement_options[1]['improvement']} к отношениям, стоимость {improvement_options[1]['cost']:,} крон\n"
                        f"3. **Дипломатический визит** ({improvement_options[2]['description']}) - "
                        f"{improvement_options[2]['improvement']} к отношениям, стоимость {improvement_options[2]['cost']:,} крон\n\n"
                        f"Выбери вариант (1, 2 или 3) или откажись ('нет').")

            return response

        except Exception as e:
            print(f"Ошибка при обработке запроса улучшения отношений: {e}")
            return "Что-то пошло не так. Попробуй позже."

    def _process_improvement_choice(self, message, target_faction, context):
        """Обрабатывает выбор варианта улучшения отношений"""
        message_lower = message.lower()

        # Проверяем отказ
        if any(word in message_lower for word in ['нет', 'отказываюсь', 'не хочу', 'не буду', 'отмена']):
            context['stage'] = 'idle'
            return "Хорошо, может быть в другой раз."

        # Проверяем выбор варианта
        if '1' in message_lower or 'культур' in message_lower or 'обмен' in message_lower:
            choice_index = 0
        elif '2' in message_lower or 'торгов' in message_lower or 'договор' in message_lower:
            choice_index = 1
        elif '3' in message_lower or 'визит' in message_lower or 'дипломат' in message_lower:
            choice_index = 2
        else:
            return "Пожалуйста, выбери вариант: 1 (культурный обмен), 2 (торговый договор) или 3 (дипломатический визит)."

        options = context.get('options', [])
        if not options or choice_index >= len(options):
            return "Что-то пошло не так. Попробуй начать заново."

        chosen_option = options[choice_index]

        try:
            cursor = self.db_connection.cursor()

            # Проверяем текущие отношения
            cursor.execute("""
                SELECT relationship FROM relations 
                WHERE (faction1 = ? AND faction2 = ?) OR (faction1 = ? AND faction2 = ?)
            """, (self.faction, target_faction, target_faction, self.faction))

            result = cursor.fetchone()
            if not result:
                return "Что-то пошло не так. Отношения не найдены."

            current_relationship = int(result[0])

            # Если отношения уже максимальные
            if current_relationship >= 90:
                context['stage'] = 'idle'
                return f"Наши отношения уже прекрасны! {current_relationship}/100 - дальнейшее улучшение невозможно."

            # Проверяем ресурсы игрока
            cursor.execute("SELECT amount FROM resources WHERE faction = ? AND resource_type = 'Кроны'",
                           (self.faction,))
            player_resources = cursor.fetchone()

            cost = chosen_option['cost']
            if not player_resources or player_resources[0] < cost:
                context['stage'] = 'idle'
                return (
                    f"У тебя недостаточно крон! Нужно {cost:,}, а у тебя {player_resources[0] if player_resources else 0:,}. "
                    f"Накопи нужную сумму и возвращайся.")

            # Списываем ресурсы
            cursor.execute("""
                UPDATE resources 
                SET amount = amount - ? 
                WHERE faction = ? AND resource_type = 'Кроны'
            """, (cost, self.faction))

            # Улучшаем отношения
            new_relationship = min(100, current_relationship + chosen_option['improvement'])

            cursor.execute("""
                UPDATE relations 
                SET relationship = ? 
                WHERE (faction1 = ? AND faction2 = ?) OR (faction1 = ? AND faction2 = ?)
            """, (new_relationship, self.faction, target_faction, target_faction, self.faction))

            # Обновляем дипломатии если нужно
            if new_relationship >= 80:
                new_status = "союз" if new_relationship >= 90 else "дружба"
                cursor.execute("""
                    UPDATE diplomacies 
                    SET relationship = ? 
                    WHERE (faction1 = ? AND faction2 = ?) OR (faction1 = ? AND faction2 = ?)
                """, (new_status, self.faction, target_faction, target_faction, self.faction))

            # Создаем запись в trade_agreements как подтверждение
            cursor.execute("""
                INSERT INTO trade_agreements 
                (initiator, target_faction, initiator_type_resource, initiator_summ_resource,
                 target_type_resource, target_summ_resource, agree, agreement_type, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """, (
                self.faction, target_faction, "Кроны", cost,
                "Улучшение отношений", chosen_option['improvement'], 1, "relation_improvement"
            ))

            # Добавляем запись в историю переговоров
            cursor.execute("""
                INSERT INTO negotiation_history 
                (faction1, faction2, message, is_player, timestamp)
                VALUES (?, ?, ?, ?, datetime('now'))
            """, (self.faction, target_faction,
                  f"Улучшение отношений через {chosen_option['name']}. Улучшено на {chosen_option['improvement']} %.",
                  0))

            self.db_connection.commit()

            # Очищаем контекст
            context['stage'] = 'idle'

            # Формируем ответ
            improvement = chosen_option['improvement']
            response_options = [
                f"Отлично! Наши отношения улучшились на {improvement}%! Теперь они на уровне {new_relationship}/100.",
                f"Прекрасно! Благодаря {chosen_option['name']} наши отношения выросли до {new_relationship}/100 (+{improvement}).",
                f"Принято! Отношения улучшены. Теперь они составляют {new_relationship}/100.",
                f"Соглашение заключено! Наше взаимопонимание улучшилось на {improvement}%."
            ]

            # Добавляем фразы фракций
            faction_response = self.faction_phrases.get(target_faction, {}).get("rejection", "")
            if faction_response and random.random() > 0.5:
                return f"{faction_response} {random.choice(response_options)}"

            return random.choice(response_options)

        except Exception as e:
            print(f"Ошибка при обработке улучшения отношений: {e}")
            context['stage'] = 'idle'
            return "Произошла ошибка при обработке. Попробуй позже."

    def _is_context_reset(self, message):
        """Определяет, является ли сообщение командой сброса контекста"""
        reset_keywords = [
            'забудь', 'забей', 'обнули', 'сбрось', 'начнем заново', 'отстань', 'отвали',
            'очисти', 'удали контекст', 'стереть', 'забудь все',
            'сбросить контекст', 'забудь что было', 'начни сначала',
            'рестарт', 'перезагрузка', 'очистить историю',
            'сбросим', 'забудем', 'начать с начала',
            'очистить чат', 'стереть память', 'новый диалог',
            'сбрось все', 'забудь предыдущее', 'очисти разговор'
        ]

        message_lower = message.lower()

        # Также проверяем комбинации с дополнениями
        reset_phrases = [
            'забудь все что было',
            'сбрось контекст чата',
            'очисти историю разговора',
            'начнем диалог заново',
            'забудь предыдущий разговор',
            'стереть память о чате',
            'новый разговор'
        ]

        # Проверяем отдельные слова
        if any(keyword in message_lower for keyword in reset_keywords):
            return True

        # Проверяем фразы
        if any(phrase in message_lower for phrase in reset_phrases):
            return True

        return False

    def _is_war_declaration(self, message):
        """Определяет, является ли сообщение объявлением войны - УЛУЧШЕННАЯ ВЕРСИЯ"""
        war_keywords = [
            'война', 'объявляю войну', 'нападу', 'нападем', 'нападете', 'напасть',
            'атаковать', 'атакую', 'атакуем', 'атакуете',
            'вторгнуться', 'вторгнусь', 'вторгнемся', 'вторгнетесь',
            'воевать', 'буду воевать', 'будем воевать', 'будете воевать',
            'военные действия', 'начать войну', 'развязать войну',
            'уничтожить', 'уничтожу', 'уничтожим', 'уничтожите',
            'разгромить', 'разгромлю', 'разгромим', 'разгромите',
            'сокрушить', 'сокрушу', 'сокрушим', 'сокрушите',
            'убить', 'убью', 'убьем', 'убьете',
            'ликвидировать', 'ликвидирую', 'ликвидируем', 'ликвидируете',
            'стереть с лица земли', 'стереть с карты',
            'конец', 'конец нашему миру', 'конец переговорам',
            'умри', 'сдохни', 'погибни', 'пропади',
            'ненавижу', 'ненавидим', 'ненавидите',
            'уничтожу тебя', 'убью тебя', 'раздавлю тебя',
            'в моих глазах ты уже мертв', 'ты труп',
            'готовься к бою', 'готовься к войне', 'готовься умирать',
            'между нами война', 'сейчас будет война',
            'твоя смерть близка', 'ваша гибель неизбежна',
            'кровопролитие', 'кровь прольется', 'будет кровь'
        ]

        message_lower = message.lower()

        # Проверяем наличие явных слов войны
        has_war_keywords = any(keyword in message_lower for keyword in war_keywords)

        # Проверяем агрессивные конструкции
        aggressive_patterns = [
            r'я теб[ея] убью',
            r'я теб[ея] уничтожу',
            r'ты умр[её]шь',
            r'ты сдохнешь',
            r'мы тебя уничтожим',
            r'мы вас уничтожим',
            r'твой конец',
            r'твоя смерть',
            r'тебе конец',
            r'ваш конец',
            r'смерть тебе',
            r'смерть вам',
            r'на ножах',
            r'к оружию'
        ]

        import re
        has_aggressive_patterns = any(re.search(pattern, message_lower) for pattern in aggressive_patterns)

        # Проверяем комбинацию угроз с упоминанием войны
        threat_words = ['убью', 'уничтожу', 'раздавлю', 'сотру', 'стеру', 'сожгу', 'разорву']
        war_words = ['война', 'сражение', 'битва', 'бой', 'конфликт', 'войну', 'воевать', 'драться', 'дратся', 'подеремся', 'подраться']

        has_threat = any(threat in message_lower for threat in threat_words)
        has_war_mention = any(war_word in message_lower for war_word in war_words)

        return has_war_keywords or has_aggressive_patterns or (has_threat and has_war_mention)

    def _handle_war_declaration(self, message, faction):
        """Обрабатывает объявление войны с разнообразными репликами - УЛУЧШЕННАЯ ВЕРСИЯ"""
        try:
            cursor = self.db_connection.cursor()

            # Проверяем текущий ход
            cursor.execute("SELECT turn_count FROM turn")
            turn_result = cursor.fetchone()
            if turn_result is None or turn_result[0] < 14:
                early_turn_responses = [
                    "Слишком рано для войны. Подожди 14-го хода.",
                    "Ещё не время начинать войны. Давай подождём 14 ходов.",
                    "Потерпи до 14-го хода. Тогда и поговорим о войне.",
                    "Рано размахивать мечами. Сначала окрепнем."
                ]
                return random.choice(early_turn_responses)

            # Проверяем текущие отношения
            cursor.execute("""
                SELECT relationship FROM diplomacies 
                WHERE (faction1 = ? AND faction2 = ?) OR (faction1 = ? AND faction2 = ?)
            """, (self.faction, faction, faction, self.faction))

            result = cursor.fetchone()
            if result and result[0] == "война":
                already_war_responses = [
                    "Мы с тобой уже воюем! Ты что, забыл?",
                    "Война уже идёт! Ты опоздал с объявлением.",
                    "Наши мечи уже скрестились! Не нужно повторных объявлений.",
                    "Битва продолжается. Зачем объявлять войну дважды?",
                    "Ты что, не видишь что мы уже воюем? Иди воевать, а не болтай!",
                    "На поле боя уже льется кровь! Присоединяйся или заткнись!"
                ]
                return random.choice(already_war_responses)

            # Объявляем войну
            cursor.execute("""
                UPDATE diplomacies 
                SET relationship = 'война' 
                WHERE (faction1 = ? AND faction2 = ?) OR (faction1 = ? AND faction2 = ?)
            """, (self.faction, faction, faction, self.faction))

            cursor.execute("""
                UPDATE relations 
                SET relationship = 0 
                WHERE (faction1 = ? AND faction2 = ?) OR (faction1 = ? AND faction2 = ?)
            """, (self.faction, faction, faction, self.faction))

            self.db_connection.commit()

            # Получаем фразу для фракции
            phrases = self.faction_phrases.get(faction, {})
            war_phrase = phrases.get("war_declaration", f"Война объявлена против {faction}!")

            # Дополнительные вариации в зависимости от агрессивности сообщения
            message_lower = message.lower()

            if any(word in message_lower for word in ['убью', 'уничтожу', 'сотру', 'стеру']):
                # Очень агрессивное объявление
                aggressive_responses = [
                    "Так ты хочешь смерти? Получи её!",
                    "Говорил, говорил... теперь получай!",
                    "Угрожать мне? Тебе конец!",
                    "Твои слова стали твоим смертным приговором!",
                    "Я сделаю так, что ты пожалеешь о каждом сказанном слове!",
                    "За каждое твоё оскорбление заплатишь кровью!"
                ]
                war_phrase += f" {random.choice(aggressive_responses)}"

            elif any(word in message_lower for word in ['ненавижу', 'презираю', 'отвратительно']):
                # Эмоциональное объявление
                emotional_responses = [
                    "Твоя ненависть встретит мое презрение на поле боя!",
                    "Если ненавидишь - докажи это в бою!",
                    "Ненависть - плохой советчик. Сейчас ты это поймёшь!",
                    "Пусть твоя ненависть станет твоим надгробием!"
                ]
                war_phrase += f" {random.choice(emotional_responses)}"

            # Добавляем фракционные реплики
            faction_war_responses = {
                "Эльфы": [
                    "Ты осквернил наши леса в последний раз! Стрелы уже летят в твою сторону!",
                    "Природа восстанет против тебя! Деревья станут твоими могилами!",
                    "За каждое срубленное дерево - сто твоих солдат!",
                    "Лес пропитается твоей кровью!"
                ],
                "Север": [
                    "Холодная смерть найдёт тебя! Мороз скрепит твои кости!",
                    "Ледяной ветер выдует твою жизнь! Зима пришла за тобой!",
                    "В буране твои армии замёрзнут насмерть!",
                    "Северный ветер принёс тебе смерть!"
                ],
                "Адепты": [
                    "Ересь будет сожжена! Очистим мир огнём!",
                    "Бог покарает тебя через нашу руку! Готовься к божьему суду!",
                    "Священная война началась! Смерть неверным!",
                    "Твоя душа будет гореть в аду!"
                ],
                "Элины": [
                    "Песок поглотит твои кости! Пустыня высосет твою кровь!",
                    "Зной пустыни иссушит твою армию! Солнце сожжёт тебя!",
                    "В песках похороню твои надежды!",
                    "Пустыня станет твоей могилой!"
                ],
                "Вампиры": [
                    "Твоя кровь будет нашей! Ночь вечной тьмы настала!",
                    "Мы будем пить твою кровь веками! Страшись ночи!",
                    "Ты станешь нашей вечной игрушкой!",
                    "Кровопийцы идут за тобой!"
                ]
            }

            # Добавляем случайную реплику для фракции
            faction_responses = faction_war_responses.get(faction, [])
            if faction_responses:
                additional_response = random.choice(faction_responses)
                return f"{war_phrase} {additional_response}"

            return war_phrase

        except Exception as e:
            print(f"Ошибка при объявлении войны: {e}")
            error_responses = [
                "Что-то пошло не так при объявлении войны.",
                "Моя канцелярия не смогла обработать объявление.",
                "Войну объявить не удалось. Попробуй позже.",
                "Не могу начать войну сейчас. Что-то мешает."
            ]
            return random.choice(error_responses)

    def _is_insult_or_threat(self, message):
        """Определяет, является ли сообщение оскорблением или угрозой - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
        insult_keywords = [
            'дурак', 'идиот', 'дебил', 'кретин', 'тупица', 'олух',
            'мудак', 'козел', 'сволочь', 'подонок', 'ублюдок', 'сука',
            'тварь', 'скотина', 'жмот', 'жадина', 'трус',
            'ничтожество', 'отброс', 'мусор', 'гнида', 'паразит',
            'уебок', 'пидор', 'педик', 'гомик', 'педераст',
            'задницу', 'жопу', 'хую', 'хуюшки', 'петух',
            'выебать тебя', 'выебали тебя', 'тебя выебал',
            'тебя выебать',
            'гандон', 'уебан', 'пидр', 'охуел', 'ебало',
            'шлюха', 'блядь', 'проститутка', 'шалава',
            'выродок', 'урод', 'калека', 'инвалид',
            'сучонок', 'сучий потрох', 'пёс', 'собака',
            'свинья', 'осёл', 'кобыла', 'жеребец',
            'хуй', 'пизда', 'ебать', 'блять', 'еблище', 'ебанашка',
            'хуило', 'долбоеб', 'тебе пиздец', 'ебло', 'петух', 'пидарасина',
            'ебало', 'вагина', 'ебасосина', 'пиздабол', 'петушара', 'петуш',
            'пошёл нахуй', 'иди нахуй', 'пошёл ты', 'пошла ты',
            'заткнись', 'заткни пасть', 'завались', 'отстань',
            'отъебись', 'отвали', 'проваливай', 'съеби',
            'сдохни', 'подыхай', 'сгинь', 'исчезни',
            'чтоб ты сдох', 'чтоб ты подавился', 'чтоб ты сгнил',
            'гнилой', 'прогнивший', 'вонючий', 'воняешь',
            'тупой', 'безмозглый', 'бездарность', 'неудачник',
            'жалкий', 'жалкое', 'ничтожный', 'мелкий',
            'тряпка', 'сопляк', 'молокосос', 'щенок',
            'предатель', 'изменник', 'иуда', 'Иуда',
            'вор', 'жулик', 'мошенник', 'аферист',
            'лжец', 'лгун', 'врун', 'обманщик',
            'трус', 'боязливый', 'пугливый', 'трусливый',
            'жадный', 'жадина', 'скряга', 'скупой'
        ]

        threat_keywords = [
            'убью', 'убить', 'уничтожу', 'уничтожить',
            'раздавлю', 'раздавить', 'сотру', 'стереть',
            'сожгу', 'сжечь', 'разорву', 'разорвать',
            'повешу', 'повесить', 'казню', 'казнить',
            'запорю', 'запороть', 'зарежу', 'зарезать',
            'застрелю', 'застрелить', 'задушу', 'задушить',
            'покалечу', 'покалечить', 'изувечу', 'изувечить',
            'изнасилую', 'изнасиловать', 'надругаюсь', 'надругаться',
            'опущу', 'опустить', 'унижу', 'унизить',
            'отомщу', 'отомстить', 'отплачу', 'отплатить',
            'накажу', 'наказать', 'покараю', 'покарать',
            'покончу', 'покончить', 'прикончу', 'прикончить',
            'сотру с лица земли', 'стереть с карты',
            'вырежу', 'вырезать', 'выжгу', 'выжечь',
            'превращу в пепел', 'в пыль', 'в труху',
            'не оставлю камня на камне', 'камня на камне не оставлю',
            'сотру в порошок', 'в порошок сотру',
            'сделаю из тебя фарш', 'фарш сделаю',
            'костей не соберёшь', 'не соберёшь костей'
        ]

        message_lower = message.lower()

        # Проверяем оскорбления - как отдельные слова или фразы
        has_insult = False
        words = message_lower.split()

        # Проверяем каждое слово отдельно (чтобы "дать" не считалось оскорблением)
        for word in words:
            for insult in insult_keywords:
                # Если оскорбление - одно слово, проверяем точное совпадение
                if ' ' not in insult and word == insult:
                    has_insult = True
                    break
                # Если оскорбление - фраза, проверяем вхождение
                elif ' ' in insult and insult in message_lower:
                    has_insult = True
                    break

        # Проверяем угрозы
        has_threat = any(threat in message_lower for threat in threat_keywords)

        # Проверяем агрессивные конструкции (более строгие паттерны)
        aggressive_patterns = [
            r'^я\s+теб[еяя]\s+[а-я]+у$',  # я тебя убью (отдельное предложение)
            r'^ты\s+[а-я]+ешь$',  # ты сдохнешь (отдельное предложение)
            r'^чтоб\s+ты\s+[а-я]+$',  # чтоб ты сдох (отдельное предложение)
            r'пош[её]л\s+нахуй',  # пошёл нахуй
            r'иди\s+нахуй',  # иди нахуй
            r'заткни\s+пасть',  # заткни пасть
            r'^заткнись$',  # заткнись (отдельное слово)
            r'я\s+теб[ея]\s+(убью|уничтожу|раздавлю|сотру|сожгу)',  # я тебя [угроза]
            r'ты\s+(сдохнешь|подыхаешь|сгниёшь|исчезнешь)',  # ты [угроза]
            r'чтоб\s+ты\s+(сдох|подавился|сгнил|исчез)',  # чтоб ты [угроза]
            r'\bубью\s+тебя\b',  # убью тебя
            r'\bуничтожу\s+тебя\b',  # уничтожу тебя
            r'\bраздавлю\s+тебя\b',  # раздавлю тебя
            r'\bубью\s+вас\b',  # убью вас
            r'\bуничтожу\s+вас\b',  # уничтожу вас
        ]

        import re
        has_aggressive_pattern = False
        for pattern in aggressive_patterns:
            if re.search(pattern, message_lower):
                has_aggressive_pattern = True
                break

        # Дополнительная проверка: не считать предложения типа "Ты можешь мне дать" за оскорбления
        # Проверяем, есть ли в предложении нейтральные глаголы
        neutral_verbs = ['дать', 'дать', 'могу', 'можешь', 'можно', 'хочу', 'нужно', 'нужен', 'нужно']
        has_neutral_request = any(verb in message_lower for verb in neutral_verbs)

        # Если есть нейтральный запрос и нет явных оскорблений/угроз, то это не оскорбление
        if has_neutral_request and not (has_insult or has_threat):
            # Проверяем, нет ли оскорблений рядом с глаголами
            # Разбиваем предложение на слова и проверяем соседние слова
            words_list = message_lower.split()
            for i, word in enumerate(words_list):
                if word in neutral_verbs:
                    # Проверяем соседние слова на оскорбления
                    nearby_insult = False
                    start = max(0, i - 2)
                    end = min(len(words_list), i + 3)

                    for j in range(start, end):
                        if j != i and words_list[j] in insult_keywords:
                            nearby_insult = True
                            break

                    if not nearby_insult:
                        return False

        return has_insult or has_threat or has_aggressive_pattern

    def _handle_insult_or_threat(self, message, faction, relation_level):
        """Обрабатывает оскорбления и угрозы"""
        try:
            cursor = self.db_connection.cursor()

            # Проверяем текущий ход
            cursor.execute("SELECT turn_count FROM turn")
            turn_result = cursor.fetchone()

            message_lower = message.lower()

            # Если отношения уже плохие или нейтральные
            if relation_level < 50:
                # Ухудшаем отношения
                deterioration = random.randint(10, 25)
                new_relation = max(0, relation_level - deterioration)

                cursor.execute("""
                    UPDATE relations 
                    SET relationship = ? 
                    WHERE (faction1 = ? AND faction2 = ?) OR (faction1 = ? AND faction2 = ?)
                """, (new_relation, self.faction, faction, faction, self.faction))

                self.db_connection.commit()

                # Проверяем, можно ли объявить войну
                if turn_result and turn_result[0] >= 14 and new_relation < 20:
                    war_responses = [
                        f"За такие слова я объявляю тебе войну! Отношения упали до {new_relation}/100.",
                        f"Ты перешёл черту! Война! Отношения: {new_relation}/100.",
                        f"Хватит! Между нами война! Твои оскорбления стоят тебе {deterioration}%.",
                        f"На оскорбления отвечаю войной! Отныне мы враги!"
                    ]

                    # Объявляем войну
                    cursor.execute("""
                        UPDATE diplomacies 
                        SET relationship = 'война' 
                        WHERE (faction1 = ? AND faction2 = ?) OR (faction1 = ? AND faction2 = ?)
                    """, (self.faction, faction, faction, self.faction))

                    self.db_connection.commit()

                    return random.choice(war_responses)
                else:
                    # Просто ухудшаем отношения
                    insult_responses = [
                        f"Считаешь это остроумным?! Отношения ухудшились на {deterioration}%",
                        f"Что культурно нельзя?! Ты потерял {deterioration}% доверия",
                        f"Твоё хамство дорого тебе обойдётся! -{deterioration} к отношениям.",
                        f"Я этого не забуду! Отношения упали до {new_relation}/100."
                    ]
                    return random.choice(insult_responses)
            else:
                # Если отношения были хорошими
                deterioration = random.randint(15, 30)
                new_relation = max(0, relation_level - deterioration)

                cursor.execute("""
                    UPDATE relations 
                    SET relationship = ? 
                    WHERE (faction1 = ? AND faction2 = ?) OR (faction1 = ? AND faction2 = ?)
                """, (new_relation, self.faction, faction, faction, self.faction))

                self.db_connection.commit()

                responses = [
                    f"Я думал, мы друзья... За такие слова отношения падают на {deterioration} %.",
                    f"Разочарован твоим поведением. -{deterioration} к нашим отношениям.",
                    f"Твои оскорбления ранят. Отношения теперь {new_relation}/100.",
                    f"Ответишь за слова? Наши отношения упали на {deterioration}%"
                ]

                # Если отношения упали сильно, угрожаем войной
                if new_relation < 30 and turn_result and turn_result[0] >= 14:
                    responses.append(f"Ещё одно такое слово - и будет война! Отношения: {new_relation}/100.")

                return random.choice(responses)

        except Exception as e:
            print(f"Ошибка при обработке оскорбления: {e}")
            return "Твои слова оскорбительны. Пожалуйста, веди себя прилично."

    def create_diplomacy_interface(self):
        """Создает адаптивный интерфейс дипломатического чата с полем ввода вверху окна"""
        # Создаем основной контейнер
        diplomacy_window = BoxLayout(
            orientation='vertical',
            size_hint=(1, 1),
            spacing=0,
            padding=0
        )

        # Фон (упрощенный)
        with diplomacy_window.canvas.before:
            Color(0.08, 0.08, 0.12, 1)
            self.bg_rect = Rectangle(pos=diplomacy_window.pos, size=diplomacy_window.size)

        # Обновляем фон при изменении размеров
        diplomacy_window.bind(
            pos=lambda w, v: setattr(self.bg_rect, 'pos', v),
            size=lambda w, v: setattr(self.bg_rect, 'size', v)
        )

        # 1. ПОЛЕ ВВОДА (САМОЕ ВЕРХ) - УПРОЩЕННАЯ ВЕРСИЯ
        input_panel = self.create_input_panel_safe()
        diplomacy_window.add_widget(input_panel)

        # 2. ИСТОРИЯ ЧАТА (СЕРЕДИНА) - ОСНОВНАЯ ОБЛАСТЬ
        chat_area = self.create_chat_area_safe()
        diplomacy_window.add_widget(chat_area)

        # 3. ПАНЕЛЬ УПРАВЛЕНИЯ (НИЗ)
        control_panel = self.create_control_panel_safe()
        diplomacy_window.add_widget(control_panel)

        return diplomacy_window

    def create_input_panel_safe(self):
        """Создает безопасную панель ввода для Android"""
        panel = BoxLayout(
            orientation='horizontal',
            size_hint=(1, None),
            height=dp(50),
            spacing=dp(8),
            padding=[dp(4), dp(4)]
        )

        # Упрощенное поле ввода
        self.message_input = TextInput(
            hint_text="Введите сообщение...",
            multiline=False,
            background_normal='',
            background_color=(0.18, 0.18, 0.25, 1),
            foreground_color=(1, 1, 1, 1),
            cursor_color=(0.5, 0.7, 1, 1),
            padding=[dp(8), dp(8)],
            font_size='14sp',
            size_hint=(0.8, 1)
        )

        # Упрощенная кнопка отправки
        send_btn = Button(
            text=">",
            size_hint=(0.2, 1),
            background_normal='',
            background_color=(0, 0, 0, 0),
            color=(1, 1, 1, 1),
            font_size='16sp',
            bold=True
        )
        with send_btn.canvas.before:
            send_btn._bc = Color(0.20, 0.50, 0.88, 1)
            send_btn._br = RoundedRectangle(pos=send_btn.pos, size=send_btn.size, radius=[dp(8)])
        send_btn.bind(
            pos=lambda i, v: setattr(i._br, 'pos', v),
            size=lambda i, v: setattr(i._br, 'size', v)
        )
        send_btn.bind(on_press=self.send_diplomatic_message)

        panel.add_widget(self.message_input)
        panel.add_widget(send_btn)

        # Простой фон без сложных привязок
        with panel.canvas.before:
            Color(0.14, 0.14, 0.2, 1)
            panel.bg = Rectangle(pos=panel.pos, size=panel.size)

        def update_bg(instance, value):
            instance.bg.pos = instance.pos
            instance.bg.size = instance.size

        panel.bind(pos=update_bg, size=update_bg)

        return panel

    def create_chat_area_safe(self):
        """Создает безопасную область чата для Android"""
        # Основной контейнер
        main_container = BoxLayout(orientation='vertical')

        # ScrollView с упрощенными настройками
        self.chat_scroll = ScrollView(
            size_hint=(1, 1),
            do_scroll_x=False,
            bar_width=dp(6),
            scroll_type=['bars'],
            bar_color=(0.3, 0.3, 0.5, 0.5)
        )

        # Контейнер для сообщений
        self.chat_container = BoxLayout(
            orientation='vertical',
            size_hint_y=None,
            spacing=dp(4),
            padding=[dp(4), dp(4)]
        )
        self.chat_container.bind(minimum_height=self.chat_container.setter('height'))

        self.chat_scroll.add_widget(self.chat_container)
        main_container.add_widget(self.chat_scroll)

        return main_container

    def load_factions_from_db(self):
        """Загружает список живых фракций (имеющих хотя бы 1 город)"""
        try:
            cursor = self.db_connection.cursor()
            cursor.execute("""
                SELECT DISTINCT faction FROM cities
                WHERE faction != 'Нейтрал' AND faction != 'Мятежники' AND faction != 'Нежить'
            """)
            factions = [row[0] for row in cursor.fetchall()]
            return factions
        except Exception as e:
            print(f"Ошибка при загрузке списка фракций из БД: {e}")
            return None

    def create_control_panel_safe(self):
        """Создает безопасную панель управления для Android"""
        panel = BoxLayout(
            orientation='vertical',
            size_hint=(1, None),
            height=dp(100),
            spacing=dp(4),
            padding=[dp(4), dp(4)]
        )

        # Верхняя строка: выбор фракции
        faction_row = BoxLayout(
            orientation='horizontal',
            size_hint=(1, 0.4),
            spacing=dp(4)
        )

        faction_label = Label(
            text="Фракция:",
            font_size='12sp',
            color=(0.8, 0.8, 0.9, 1),
            size_hint=(0.3, 1),
            valign='middle'
        )

        self.faction_spinner = Spinner(
            text='Выберите фракцию',
            values=[],
            size_hint=(0.7, 1),
            background_color=(0.2, 0.3, 0.5, 1),
            font_size='12sp'
        )

        # Заполняем список фракций из базы данных
        factions = self.load_factions_from_db()
        if factions:
            for faction in factions:
                if faction != self.faction:
                    self.faction_spinner.values.append(faction)

            if not self.faction_spinner.values:
                self.faction_spinner.text = "Нет доступных фракций"
                self.faction_spinner.disabled = True
        else:
            # Фолбэк — загружаем живые фракции из городов
            try:
                _cur = self.db_connection.cursor()
                _cur.execute("SELECT DISTINCT faction FROM cities WHERE faction != 'Нейтрал' AND faction != 'Мятежники' AND faction != 'Нежить'")
                for _row in _cur.fetchall():
                    if _row[0] != self.faction:
                        self.faction_spinner.values.append(_row[0])
            except Exception:
                pass

        self.faction_spinner.bind(text=self.on_faction_selected_android)

        # Автовыбор фракции если передана через уведомление
        preselect = getattr(self.advisor, 'preselect_faction', None)
        if preselect and preselect in self.faction_spinner.values:
            self.faction_spinner.text = preselect

        faction_row.add_widget(faction_label)
        faction_row.add_widget(self.faction_spinner)

        # Средняя строка: информация об отношениях
        info_row = BoxLayout(
            orientation='horizontal',
            size_hint=(1, 0.3),
            spacing=dp(4)
        )

        self.relation_info_label = Label(
            text="Выберите фракцию",
            font_size='11sp',
            color=(0.7, 0.7, 0.8, 1),
            halign='center',
            size_hint=(0.8, 1)
        )

        info_row.add_widget(self.relation_info_label)

        # Нижняя строка: кнопка
        button_row = BoxLayout(
            orientation='horizontal',
            size_hint=(1, 0.3),
            spacing=dp(4)
        )

        info_button = Button(
            text="Подробнее",
            size_hint=(1, 1),
            background_color=(0.3, 0.3, 0.5, 1),
            font_size='10sp',
            on_press=self.show_relation_info
        )
        button_row.add_widget(info_button)

        panel.add_widget(faction_row)
        panel.add_widget(info_row)
        panel.add_widget(button_row)

        # Простой фон
        with panel.canvas.before:
            Color(0.12, 0.12, 0.18, 1)
            panel.bg = Rectangle(pos=panel.pos, size=panel.size)

        def update_bg(instance, value):
            instance.bg.pos = instance.pos
            instance.bg.size = instance.size

        panel.bind(pos=update_bg, size=update_bg)

        return panel

    def create_chat_interface(self):
        """Альтернативный упрощенный интерфейс"""
        return self.create_diplomacy_interface()