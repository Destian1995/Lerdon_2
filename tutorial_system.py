from kivy.uix.modalview import ModalView
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.image import Image
from kivy.metrics import dp, sp
from kivy.animation import Animation
from kivy.clock import Clock
from ui_components import ModernButton
import json
import os

class TutorialSystem:
    """Система обучения для новичков"""

    def __init__(self):
        self.tutorial_file = 'tutorial_progress.json'
        self.current_step = 0
        self.tutorial_active = False
        self.steps = self._define_tutorial_steps()
        self._load_progress()

    def _define_tutorial_steps(self):
        """Определяет шаги обучения"""
        return [
            {
                'id': 'welcome',
                'title': 'Добро пожаловать в Lerdon Legends!',
                'message': 'Это пошаговая стратегическая игра. Вы управляете княжеством и конкурируете с другими фракциями.',
                'image': 'tutorial/welcome.png',
                'action': 'next'
            },
            {
                'id': 'resources',
                'title': 'Ресурсы',
                'message': 'У вас есть ресурсы: Кроны (деньги), Кристаллы (минералы) и Рабочие (население). Они нужны для строительства и армии.',
                'target': 'resource_panel',
                'action': 'highlight'
            },
            {
                'id': 'buildings',
                'title': 'Строительство',
                'message': 'Строите здания для развития экономики. Выберите город и нажмите кнопку строительства.',
                'target': 'build_button',
                'action': 'highlight'
            },
            {
                'id': 'army',
                'title': 'Армия',
                'message': 'Нанимайте войска для защиты и нападения. Разные юниты имеют разные сильные и слабые стороны.',
                'target': 'army_panel',
                'action': 'highlight'
            },
            {
                'id': 'diplomacy',
                'title': 'Дипломатия',
                'message': 'Общайтесь с другими фракциями. Можно заключать союзы, торговать или объявлять войны.',
                'target': 'diplomacy_button',
                'action': 'highlight'
            },
            {
                'id': 'turns',
                'title': 'Ходы',
                'message': 'Игра происходит по ходам. Каждый ход вы можете выполнять действия, затем нажмите "Завершить ход".',
                'target': 'end_turn_button',
                'action': 'highlight'
            },
            {
                'id': 'victory',
                'title': 'Цель игры',
                'message': 'Цель - стать самым могущественным правителем. Развивайте экономику, стройте армию и заключайте выгодные союзы!',
                'action': 'finish'
            }
        ]

    def _load_progress(self):
        """Загружает прогресс обучения"""
        try:
            if os.path.exists(self.tutorial_file):
                with open(self.tutorial_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.current_step = data.get('current_step', 0)
                    self.tutorial_active = data.get('active', True)
        except Exception as e:
            print(f"Ошибка загрузки прогресса туториала: {e}")

    def _save_progress(self):
        """Сохраняет прогресс обучения"""
        try:
            data = {
                'current_step': self.current_step,
                'active': self.tutorial_active,
                'completed_steps': list(range(self.current_step))
            }
            with open(self.tutorial_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Ошибка сохранения прогресса туториала: {e}")

    def start_tutorial(self):
        """Начинает обучение"""
        self.tutorial_active = True
        self.current_step = 0
        self._save_progress()
        self.show_current_step()

    def next_step(self):
        """Переходит к следующему шагу"""
        if self.current_step < len(self.steps) - 1:
            self.current_step += 1
            self._save_progress()
            self.show_current_step()
        else:
            self.finish_tutorial()

    def previous_step(self):
        """Возвращается к предыдущему шагу"""
        if self.current_step > 0:
            self.current_step -= 1
            self._save_progress()
            self.show_current_step()

    def skip_tutorial(self):
        """Пропускает обучение"""
        self.tutorial_active = False
        self._save_progress()

    def finish_tutorial(self):
        """Завершает обучение"""
        self.tutorial_active = False
        self.current_step = len(self.steps) - 1
        self._save_progress()

    def show_current_step(self):
        """Показывает текущий шаг обучения"""
        if not self.tutorial_active or self.current_step >= len(self.steps):
            return

        step = self.steps[self.current_step]
        tutorial_popup = TutorialPopup(
            title=step['title'],
            message=step['message'],
            image=step.get('image'),
            on_next=self.next_step,
            on_previous=self.previous_step if self.current_step > 0 else None,
            on_skip=self.skip_tutorial
        )
        tutorial_popup.open()

    def is_tutorial_active(self):
        """Проверяет, активно ли обучение"""
        return self.tutorial_active

    def get_current_step(self):
        """Возвращает текущий шаг"""
        return self.steps[self.current_step] if self.current_step < len(self.steps) else None


class TutorialPopup(ModalView):
    """Всплывающее окно шага обучения"""

    def __init__(self, title, message, image=None, on_next=None, on_previous=None, on_skip=None, **kwargs):
        super().__init__(**kwargs)
        self.size_hint = (0.8, 0.6)
        self.auto_dismiss = False

        layout = BoxLayout(orientation='vertical', padding=dp(20), spacing=dp(15))

        # Заголовок
        title_label = Label(
            text=title,
            font_size=sp(20),
            bold=True,
            size_hint_y=None,
            height=dp(40),
            color=(0.2, 0.4, 0.8, 1)
        )
        layout.add_widget(title_label)

        # Изображение (если есть)
        if image and os.path.exists(os.path.join('files', 'menu', 'tutorial', image)):
            img = Image(
                source=os.path.join('files', 'menu', 'tutorial', image),
                size_hint_y=None,
                height=dp(150),
                allow_stretch=True,
                keep_ratio=True
            )
            layout.add_widget(img)

        # Сообщение
        message_label = Label(
            text=message,
            font_size=sp(16),
            halign='center',
            valign='middle',
            text_size=(self.width * 0.8, None),
            size_hint_y=None,
            height=dp(80)
        )
        layout.add_widget(message_label)

        # Кнопки
        buttons_layout = BoxLayout(
            orientation='horizontal',
            size_hint_y=None,
            height=dp(50),
            spacing=dp(10)
        )

        # Кнопка "Назад"
        if on_previous:
            prev_btn = ModernButton(
                text='← Назад',
                size_hint_x=0.3,
                on_release=lambda x: self._on_previous(on_previous)
            )
            buttons_layout.add_widget(prev_btn)

        # Кнопка "Пропустить"
        skip_btn = ModernButton(
            text='Пропустить',
            size_hint_x=0.4,
            normal_color=[0.8, 0.4, 0.4, 1],
            on_release=lambda x: self._on_skip(on_skip)
        )
        buttons_layout.add_widget(skip_btn)

        # Кнопка "Далее"
        next_btn = ModernButton(
            text='Далее →',
            size_hint_x=0.3,
            on_release=lambda x: self._on_next(on_next)
        )
        buttons_layout.add_widget(next_btn)

        layout.add_widget(buttons_layout)
        self.add_widget(layout)

    def _on_next(self, callback):
        self.dismiss()
        if callback:
            callback()

    def _on_previous(self, callback):
        self.dismiss()
        if callback:
            callback()

    def _on_skip(self, callback):
        self.dismiss()
        if callback:
            callback()


class TooltipSystem:
    """Система всплывающих подсказок"""

    def __init__(self):
        self.tooltips = {
            'build_button': 'Строить здания для развития экономики',
            'army_button': 'Управление войсками и найм юнитов',
            'diplomacy_button': 'Общение с другими фракциями',
            'end_turn_button': 'Завершить ход и передать очередь ИИ',
            'resource_panel': 'Ваши текущие ресурсы',
            'map': 'Карта мира с городами и территориями'
        }

    def show_tooltip(self, widget_id, position):
        """Показывает подсказку для виджета"""
        if widget_id in self.tooltips:
            tooltip = Tooltip(
                text=self.tooltips[widget_id],
                pos=position
            )
            tooltip.open()

    def get_tooltip_text(self, widget_id):
        """Возвращает текст подсказки"""
        return self.tooltips.get(widget_id, '')


class Tooltip(ModalView):
    """Всплывающая подсказка"""

    def __init__(self, text, pos, **kwargs):
        super().__init__(**kwargs)
        self.size_hint = (None, None)
        self.size = (dp(200), dp(60))
        self.pos = pos
        self.auto_dismiss = True
        self.background_color = (0.2, 0.2, 0.2, 0.9)

        label = Label(
            text=text,
            font_size=sp(14),
            color=(1, 1, 1, 1),
            halign='center',
            valign='middle'
        )
        self.add_widget(label)

        # Автоматическое закрытие через 3 секунды
        Clock.schedule_once(lambda dt: self.dismiss(), 3)


# Глобальные экземпляры
tutorial_system = TutorialSystem()
tooltip_system = TooltipSystem()</content>
<parameter name="filePath">c:\Users\lerdo\Desktop\AI\Lerdon_2\tutorial_system.py