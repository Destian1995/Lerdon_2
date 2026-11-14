"""Small-screen controls for voluntary ads and safe access expiration."""
from kivy.app import App
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.popup import Popup
from strategy_ui import StrategyButton, GOLD, MUTED
from mirror_readable_ui import ReadableText
from window_theme import prepare_custom_popup


class RewardedButton(StrategyButton):
    def __init__(self, compact=False, **kwargs):
        self.compact = compact
        super().__init__(text='Смотреть рекламу · +15 минут', **kwargs)
        self.bind(on_release=self.open_access)
        self._poll = Clock.schedule_interval(self.refresh, 1)
        self.bind(parent=self._parent_changed)
        self.refresh()

    def _parent_changed(self, _widget, parent):
        if parent is None and self._poll:
            self._poll.cancel()
            self._poll = None

    def refresh(self, *_):
        from rewarded_access import get_rewarded, paid_access
        controller = get_rewarded()
        if paid_access():
            self.text = 'Полный доступ открыт'
        elif controller and controller.available:
            self.text = controller.bank.caption+' · +15 мин' if self.compact else 'Продлить доступ · '+controller.bank.caption
        else:
            self.text = '+15 мин · Реклама' if self.compact else 'Смотреть рекламу · +15 минут'

    def open_access(self, *_):
        from premium_options_ui import show_full_access
        show_full_access()


class ExpiredAccessPopup(Popup):
    def __init__(self, controller, locked, **kwargs):
        root = BoxLayout(orientation='vertical', padding=dp(12), spacing=dp(8))
        root._strategy_fixed_layout = True
        super().__init__(title='', content=root, size_hint=(.94,.94),
                         size_hint_max=(dp(520),dp(330)), auto_dismiss=False, **kwargs)
        root.add_widget(ReadableText('Время полного доступа закончилось', size=19, bold=True, color=GOLD))
        root.add_widget(ReadableText('Прогресс сохранён. Посмотрите рекламу, чтобы продолжить ещё 15 минут, '
                                    'или откройте полную версию навсегда.', size=14, color=MUTED))
        button = StrategyButton(text='Продлить доступ', primary=True, size_hint_y=None, height=dp(48))
        from premium_options_ui import show_full_access
        button.bind(on_release=lambda *_:show_full_access())
        root.add_widget(button)
        if not locked:
            free = StrategyButton(text='Продолжить с бесплатными возможностями', size_hint_y=None, height=dp(48))
            free.bind(on_release=self.dismiss)
            root.add_widget(free)
        exit_button = StrategyButton(text='Сохранить и выйти', size_hint_y=None, height=dp(48))
        exit_button.bind(on_release=lambda *_:App.get_running_app().stop())
        root.add_widget(exit_button)
        self.bind(on_dismiss=lambda *_:setattr(controller, 'expiry_popup', None))
        prepare_custom_popup(self)
