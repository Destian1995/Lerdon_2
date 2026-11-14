"""Rewarded access controller. Ads are requested only by a player's button."""
import sys
import time
import uuid
import weakref
from pathlib import Path
from rewarded_time import PlayTime, AD_UNIT_ID


def game_screen():
    screen = getattr(sys.modules.get('game_process'), '_active_game_screen', None)
    return screen if screen and screen.parent and not getattr(screen, '_cleaned_up', False) else None


def paid_access():
    from developer_access import enabled
    if enabled():
        return True
    try:
        from billing_flow import get_billing_controller
        return bool(get_billing_controller().client.access())
    except Exception:
        return False


def battle_or_turn_busy(screen):
    from turn_ui_guard import database_busy
    from tactical_battle_bridge import operation_busy
    if database_busy(screen=screen) or operation_busy(screen.conn):
        return True
    from kivy.core.window import Window
    # Also covers quick battles/monster encounters not owned by the turn worker.
    return any('battle' in base.__name__.lower()
               for widget in Window.children for base in type(widget).__mro__)


def requires_full_access(screen):
    from premium_access import FREE_FACTIONS
    from kivy.core.window import Window
    return screen.selected_faction not in FREE_FACTIONS or any(
        type(widget).__name__ == 'OtherworldMap' for widget in Window.children)


class RewardedAccess:
    def __init__(self, bank, native=None):
        self.bank = bank
        self.native = native
        self.views = weakref.WeakSet()
        self.pauses = set()
        self.session = None
        self.started = 0
        self.shown = False
        self.message = ''
        self.expiry_popup = None
        self.expired_notice = False
        self._ticks = 0
        self.storage_error = False

    @property
    def available(self):
        return not self.storage_error and self.bank.remaining > 0

    def pause(self, reason, paused):
        self.bank.tick(False)
        self.pauses.add(reason) if paused else self.pauses.discard(reason)
        self.checkpoint()

    def checkpoint(self):
        try:
            self.bank.save()
            self.storage_error = False
        except OSError:
            self.storage_error = True
            self.message = 'Не удалось сохранить время доступа. Освободите место на устройстве.'

    def watch(self, *_):
        if self.session:
            return
        if not self.native:
            self.message = 'Просмотр рекламы доступен в Android-сборке с рекламным SDK.'
            self.notify()
            return
        self.bank.tick(False)
        session = uuid.uuid4().hex
        try:
            self.bank.issue(session)
            self.session = session
            self.started = time.monotonic()
            self.message = 'Загружаем рекламу…'
            self.native.show(session, AD_UNIT_ID)
        except Exception:
            self.session = None
            self.message = 'Не удалось загрузить рекламу. Попробуйте ещё раз.'
        self.notify()

    def event(self, event):
        session = event.get('session', '')
        kind = event.get('type')
        if kind == 'reward':
            # Persist first, acknowledge second. Replayed callbacks never add time twice.
            if session not in self.bank.issued:
                self.native.acknowledge(session)
                return
            if self.bank.grant(session):
                self.storage_error = False
                self.message = 'Добавлено 15 минут полного доступа. Осталось ' + self.bank.caption
                self.expired_notice = False
            self.native.acknowledge(session)
        elif session == self.session:
            if kind == 'shown':
                self.shown = True
                from game_audio import get_audio
                get_audio().pause('rewarded-ad')
            elif kind in ('closed', 'error'):
                self.shown = False
                self.session = None
                from game_audio import get_audio
                get_audio().resume('rewarded-ad')
                if kind == 'error':
                    self.message = 'Реклама сейчас недоступна. Проверьте интернет и повторите позже.'
                elif session not in self.bank.claimed:
                    self.message = 'Просмотр не подтверждён — время не добавлено.'
        self.notify()

    def tick(self, _dt=0):
        if self.native:
            try:
                for event in self.native.poll():
                    self.event(event)
            except Exception:
                self.message = 'Не удалось обработать рекламу. Повторите проверку позже.'
        if self.session and not self.shown and time.monotonic() - self.started > 60:
            self.native.cancel(self.session)
            self.session = None
            self.message = 'Реклама не загрузилась. Можно попробовать ещё раз.'
        screen = game_screen()
        licensed = paid_access() if screen or self.views else False
        running = bool(screen and not licensed and not self.pauses and not self.session
                       and self.expiry_popup is None and not self.views)
        expired = self.bank.tick(running)
        self._ticks += 1
        if self._ticks % 5 == 0 or expired:
            self.checkpoint()
        if self.available or licensed:
            if self.expiry_popup:
                self.expiry_popup.dismiss()
                self.expiry_popup = None
        elif screen and self.expiry_popup is None and not self.views and not self.session and not self.pauses:
            if self.expired_notice and not requires_full_access(screen):
                self.notify()
                return
            if not battle_or_turn_busy(screen):
                self.show_expired(screen)
        self.notify()

    def show_expired(self, screen):
        # A paid campaign or open Mirror cannot continue until access is renewed.
        locked = requires_full_access(screen)
        if not locked and self.bank.remaining == 0 and not self.bank.claimed:
            return  # Never interrupt an ordinary free campaign that has not watched an ad.
        from rewarded_access_ui import ExpiredAccessPopup
        self.expired_notice = True
        self.expiry_popup = ExpiredAccessPopup(self, locked)
        self.expiry_popup.open()

    def notify(self):
        for view in list(self.views):
            view.sync_rewarded(self)

    def close(self):
        self.bank.tick(False)
        self.checkpoint()
        if self.native and self.session and not self.shown:
            self.native.cancel(self.session)


def get_rewarded():
    from kivy.app import App
    app = App.get_running_app()
    if app is None:
        return None
    controller = getattr(app, '_rewarded_access', None)
    if controller is None:
        native = None
        from kivy.utils import platform
        if platform == 'android':
            try:
                from rewarded_android import AndroidRewarded
                native = AndroidRewarded()
            except Exception:
                pass  # An older APK without the bridge cannot grant rewarded access.
        controller = RewardedAccess(PlayTime(Path(app.user_data_dir) / 'rewarded' / 'time.json'), native)
        app._rewarded_access = controller
        from kivy.clock import Clock
        controller._event = Clock.schedule_interval(controller.tick, 1)
    return controller
