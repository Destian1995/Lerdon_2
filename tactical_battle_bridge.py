"""Bridge synchronous campaign turns to a main-thread tactical decision.

Only the worker waits. The Kivy thread owns the popup/model; SQLite stays on
the campaign worker. No campaign tables are written by the battlefield.
"""
import hashlib
import threading

_operation_connections=set()


def operation_busy(conn):
    return id(conn) in _operation_connections


def battle_context(conn, city, faction):
    try:
        row = conn.execute('SELECT turn_count FROM turn LIMIT 1').fetchone()
        turn = row[0] if row else 0
    except Exception:
        turn = 0
    from tactical_geography import context
    seed = int.from_bytes(hashlib.sha256(f'{city}:{turn}'.encode()).digest()[:8],'big')
    return dict(seed=seed,**context(conn,city,faction))


def request_battle(attackers,defenders,player_side,city='',context=None,type_modifiers=None,factions=('', '')):
    """Return None for existing quick combat, or a finished tactical model.

    A missing App means a headless simulation/test, which always stays quick.
    Main-thread callers must use launch_campaign_battle, never wait here.
    """
    if threading.current_thread() is threading.main_thread():
        return None
    from kivy.app import App
    from background_tasks import raise_if_stopping,tasks
    raise_if_stopping()
    app = App.get_running_app()
    if app is None:
        return None
    from kivy.clock import Clock
    done = threading.Event()
    answer = {}

    def display(_dt):
        if tasks.stopping.is_set():return
        try:
            from kivy.metrics import dp
            from kivy.uix.boxlayout import BoxLayout
            from kivy.uix.popup import Popup
            from strategy_ui import StrategyButton,text_label,GOLD,TEXT
            from window_theme import prepare_custom_popup
            from tactical_combat import TacticalBattle, WIDTH, HEIGHT
            from tactical_battle_ui import TacticalBattlePopup
            box = BoxLayout(orientation='vertical',padding=dp(12),spacing=dp(10))
            box._strategy_fixed_layout=True
            box.add_widget(text_label('Бой за '+city,18,GOLD,bold=True))
            box.add_widget(text_label('Тактический: поле 10×6, местность и управление отрядами.\n'
                'Быстрый: привычный автоматический расчёт.',14,TEXT))
            buttons = BoxLayout(size_hint_y=None,height=dp(52),spacing=dp(10))
            quick = StrategyButton(text='Быстрый бой')
            tactical = StrategyButton(text='Тактический бой',primary=True)
            if max(sum(u.get('unit_count',0)>0 for u in army) for army in (attackers,defenders))>WIDTH//2*HEIGHT:
                tactical.disabled = True
                tactical.text = 'Слишком много отрядов'
            buttons.add_widget(quick)
            buttons.add_widget(tactical)
            box.add_widget(buttons)
            chooser = Popup(title='Выберите режим боя',content=box,size_hint=(.9,.72),auto_dismiss=False)
            prepare_custom_popup(chooser)

            def finish(result=None):
                answer['battle'] = result
                done.set()

            def choose_quick(*_):
                chooser.dismiss()
                finish()

            def choose_tactical(*_):
                from premium_access import require
                if not require('tactical'):return
                try:
                    model = TacticalBattle(attackers,defenders,**(context or {}),
                        type_modifiers=type_modifiers,factions=factions)
                    popup = TacticalBattlePopup(model,player_side,finish,city)
                    popup.open()
                    chooser.dismiss()
                except Exception as error:
                    # Keep the choice available; never silently simulate a
                    # battle after the player selected manual control.
                    tactical.text = 'Ошибка: '+str(error)
            quick.bind(on_release=choose_quick)
            tactical.bind(on_release=choose_tactical)
            from premium_access import allowed
            if not allowed('tactical'):
                from premium_options_ui import FullVersionNotice
                can_tactical=not tactical.disabled
                tactical.disabled=True
                def refresh_access():
                    if allowed('tactical'):
                        tactical.disabled=not can_tactical
                        if notice.parent:notice.parent.remove_widget(notice)
                notice=FullVersionNotice(compact=True,on_change=refresh_access)
                box.add_widget(notice,index=1)
            chooser.open()
        except Exception as error:
            answer['error'] = error
            done.set()
    Clock.schedule_once(display,0)
    while not done.wait(.25):
        raise_if_stopping()
        if App.get_running_app() is not app:
            raise RuntimeError('Игра закрыта до завершения боя; результат не записан.')
    if 'error' in answer:
        raise answer['error']
    return answer.get('battle')


def launch_campaign_battle(conn,on_complete,**arguments):
    """Main-thread city attack. A private connection avoids UI SQLite sharing."""
    def operation(db):
        from fight import fight
        return fight(conn=db,ui_conn=conn,**arguments)
    return launch_operation(conn,operation,on_complete)


def launch_operation(conn,operation,on_complete,on_error=None):
    """Run a campaign encounter with its own connection, blocking other input."""
    from kivy.clock import Clock
    from kivy.uix.popup import Popup
    from strategy_ui import text_label
    import sqlite3
    from background_tasks import tasks,raise_if_stopping,WorkerCancelled
    raise_if_stopping()
    if operation_busy(conn):raise ValueError('Сражение уже выполняется.')
    path = next((r[2] for r in conn.execute('PRAGMA database_list') if r[1]=='main'),None)
    if not path:
        raise ValueError('Для боя нужна сохранённая база кампании.')
    conn.commit()
    blocker = Popup(title='Сражение',content=text_label('Подготовка армий…'),size_hint=(.7,.35),auto_dismiss=False)
    blocker.open()
    _operation_connections.add(id(conn))

    def work():
        result,error = None,None
        db = None
        try:
            db = sqlite3.connect(path,timeout=30)
            result = operation(db)
        except Exception as exc:
            if isinstance(exc,WorkerCancelled):return
            error = str(exc)
        finally:
            if db is not None:
                db.close()
            if tasks.stopping.is_set():_operation_connections.discard(id(conn))
        def finish(_dt):
            _operation_connections.discard(id(conn))
            if tasks.stopping.is_set():return
            blocker.dismiss()
            if error:
                if on_error:
                    on_error(error)
                    return
                from strategy_ui import StrategyButton
                from kivy.uix.boxlayout import BoxLayout
                box = BoxLayout(orientation='vertical')
                box.add_widget(text_label(error))
                close = StrategyButton(text='Закрыть',size_hint_y=.3)
                box.add_widget(close)
                popup = Popup(title='Бой не завершён',content=box,size_hint=(.9,.65))
                close.bind(on_release=popup.dismiss)
                popup.open()
                return
            on_complete(result)
        if not tasks.stopping.is_set():Clock.schedule_once(finish,0)
    try:return tasks.start(work,'player-battle')
    except BaseException:
        _operation_connections.discard(id(conn));blocker.dismiss();raise
