"""Collapsible tutorial card. Touches outside the card reach the game."""
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.scrollview import ScrollView

from strategy_ui import StrategyButton, text_label, surface, INK, GOLD


class TutorialPanel(FloatLayout):
    def __init__(self, progress, on_next, on_back, on_skip, on_open, **kwargs):
        super().__init__(**kwargs)
        self.progress = progress
        self.collapsed = False
        self.card = surface(BoxLayout(orientation='vertical', padding=dp(10), spacing=dp(6),
                                     size_hint=(None, None)), INK, GOLD)
        self.header = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(6))
        self.title = text_label('', 14, GOLD, bold=True)
        self.header.add_widget(self.title)
        self.fold = StrategyButton(text='Свернуть', size_hint_x=None, width=dp(100))
        self.fold.bind(on_release=lambda *_: self.toggle())
        self.header.add_widget(self.fold)
        self.card.add_widget(self.header)
        self.body = BoxLayout(orientation='vertical', spacing=dp(6))
        self.scroll = ScrollView(do_scroll_x=False)
        self.message = text_label('', 14, size_hint_y=None, markup=True)
        self.message.unbind(size=self.message._strategy_text_sizer)
        self.message.bind(width=lambda w, v: setattr(w, 'text_size', (v, None)),
                          texture_size=lambda w, v: setattr(w, 'height', v[1]))
        self.scroll.add_widget(self.message)
        self.body.add_widget(self.scroll)
        self.open_btn = StrategyButton(size_hint_y=None, height=dp(48), primary=True)
        self.open_btn.bind(on_release=lambda *_: on_open())
        self.body.add_widget(self.open_btn)
        self.actions = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(6))
        self.back_btn = StrategyButton(text='Назад')
        self.next_btn = StrategyButton(text='Далее')
        self.skip_btn = StrategyButton(text='Пропустить')
        for button, callback in ((self.back_btn, on_back), (self.next_btn, on_next), (self.skip_btn, on_skip)):
            button.bind(on_release=lambda w, callback=callback: callback())
            self.actions.add_widget(button)
        self.body.add_widget(self.actions)
        self.card.add_widget(self.body)
        self.add_widget(self.card)
        self.bind(size=self._fit, pos=self._fit)
        self.refresh()

    def refresh(self):
        lesson = self.progress.lesson
        self.title.text = f'{self.progress.index + 1}/{len(self.progress.lessons)} · {lesson.title}'
        status = 'Выполнено. Можно продолжить.' if lesson.event and self.progress.can_advance else lesson.task
        self.message.text = '[b]' + status + '[/b]\n\n' + lesson.text
        self.next_btn.disabled = not self.progress.can_advance
        self.next_btn.text = 'Завершить' if self.progress.index == len(self.progress.lessons) - 1 else 'Далее'
        self.back_btn.disabled = self.progress.index == 0
        self.open_btn.text = {'map': 'К карте', 'economy': 'Открыть экономику', 'army': 'Открыть армию',
                              'politics': 'Открыть политику', 'advisor': 'Открыть Советника'}.get(lesson.section, '')
        self.open_btn.disabled = not bool(lesson.section)
        self.open_btn.opacity = 1 if lesson.section else 0
        self.open_btn.height = dp(48) if lesson.section else 0
        self.scroll.scroll_y = 1
        self._fit()

    def toggle(self):
        self.collapsed = not self.collapsed
        if self.collapsed:
            self.card.remove_widget(self.body)
        else:
            self.card.add_widget(self.body)
        self.fold.text = 'Развернуть' if self.collapsed else 'Свернуть'
        self._fit()

    def _fit(self, *args):
        # The text scrolls even on a short landscape phone screen.
        bottom = min(dp(78), self.height * .22)
        self.card.width = max(dp(1), min(dp(480), self.width - dp(20)))
        self.card.height = dp(68) if self.collapsed else max(dp(1), min(dp(350), self.height - bottom - dp(10)))
        self.card.pos = (self.x + (self.width - self.card.width) / 2, self.y + bottom)

    def on_touch_down(self, touch):
        handled = super().on_touch_down(touch)
        return handled or self.card.collide_point(*touch.pos)

    def on_touch_up(self, touch):
        handled = super().on_touch_up(touch)
        return handled or self.card.collide_point(*touch.pos)
