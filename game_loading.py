"""Frame-separated game startup; Kivy and SQLite stay on the UI thread."""
from kivy.clock import Clock
from kivy.graphics import Color, RoundedRectangle
from kivy.metrics import dp, sp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.modalview import ModalView
from kivy.uix.progressbar import ProgressBar


class GameLoadingPanel(ModalView):
    def __init__(self, steps, on_complete=None, on_error=None, **kwargs):
        super().__init__(auto_dismiss=False, size_hint=(1, 1),
                         background='', background_color=(0, 0, 0, 0),
                         overlay_color=(0.025, 0.035, 0.06, 0.96), **kwargs)
        self._anim_duration = 0
        self.steps = list(steps)
        self.completed = 0
        self._on_complete = on_complete
        self._on_error = on_error
        self._event = None
        self._started = False
        self.card = BoxLayout(orientation='vertical', padding=dp(24), spacing=dp(14),
                              size_hint=(None, None), height=dp(230))
        from strategy_ui import frame
        frame(self.card)
        with self.card.canvas.before:
            Color(0.075, 0.095, 0.15, 1)
            self._background = RoundedRectangle(radius=[dp(16)])
        self.card.bind(pos=self._layout_card, size=self._layout_card)
        self.bind(size=self._resize_card)
        self.card.add_widget(Label(text='Загрузка карты', bold=True, font_size=sp(24),
                                   color=(0.96, 0.85, 0.59, 1),
                                   size_hint_y=None, height=dp(36)))
        self.status = Label(text='Подготавливаем мир…', font_size=sp(16),
                            halign='center', valign='middle',
                            size_hint_y=None, height=dp(56))
        self.status.bind(size=lambda widget, size: setattr(widget, 'text_size', size))
        self.card.add_widget(self.status)
        self.progress = ProgressBar(max=max(1, len(self.steps)), value=0,
                                    size_hint_y=None, height=dp(12))
        self.card.add_widget(self.progress)
        self.hint = Label(text='Это может занять несколько секунд', font_size=sp(12),
                          color=(0.65, 0.71, 0.8, 1),
                          size_hint_y=None, height=dp(36))
        self.card.add_widget(self.hint)
        from responsive_ui import WindowFlow
        self.flow = WindowFlow(self.card, size_hint=(None, None))
        self.add_widget(self.flow)
        self._resize_card()

    def _resize_card(self, *args):
        self.flow.size = (max(1, min(dp(460), self.width - dp(16))),
                          max(1, min(dp(230), self.height - dp(16))))

    def _layout_card(self, *args):
        self._background.pos = self.card.pos
        self._background.size = self.card.size

    def start(self):
        if self._started:
            return
        self._started = True
        self.open(animation=False)
        # Let the modal reach the screen before any expensive game work.
        self._event = Clock.schedule_once(self._prepare_step, 0.1)

    def _prepare_step(self, dt):
        if self.completed == len(self.steps):
            self.status.text = 'Карта готова'
            self._event = Clock.schedule_once(self._finish, 0.1)
            return
        self.status.text = self.steps[self.completed][0]
        # Draw the stage label before executing its synchronous work.
        self._event = Clock.schedule_once(self._run_step, 0.05)

    def _run_step(self, dt):
        try:
            self.steps[self.completed][1]()
        except Exception as error:
            from kivy.logger import Logger
            Logger.exception('Game startup failed')
            self._event = None
            self.status.text = 'Не удалось загрузить карту'
            self.hint.text = 'Закройте панель и попробуйте снова'
            from strategy_ui import StrategyButton
            button = StrategyButton(text='Закрыть', size_hint_y=None, height=dp(48))
            button.bind(on_release=lambda *_: self.dismiss())
            self.card.add_widget(button)
            if self._on_error:
                self._on_error(error)
            return
        self.completed += 1
        self.progress.value = self.completed
        self._event = Clock.schedule_once(self._prepare_step, 0.05)

    def _finish(self, dt):
        self._event = None
        self.dismiss(animation=False)
        if self._on_complete:
            self._on_complete()

    def on_dismiss(self):
        if self._event:
            self._event.cancel()
            self._event = None
