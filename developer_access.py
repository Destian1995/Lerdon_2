"""Local source-checkout access switch, never a payment or a license."""
import json
import os
from pathlib import Path

SOURCE_ROOT=Path(__file__).resolve().parent
STATE_FILE=SOURCE_ROOT/'developer_access.local.json'
_state=None


def available():
    # Android release packages must never honor a copied local settings file.
    if 'ANDROID_ARGUMENT' in os.environ or 'ANDROID_PRIVATE' in os.environ:
        return False
    return (SOURCE_ROOT/'.git').exists()


def enabled():
    global _state
    if not available():return False
    if _state is None:
        try:_state=json.loads(STATE_FILE.read_text(encoding='utf-8')).get('full_access') is True
        except (OSError,ValueError,AttributeError):_state=False
    return _state


def set_enabled(value):
    global _state
    if not available():raise ValueError('Режим разработчика доступен только при запуске исходников на ПК.')
    value=bool(value)
    temporary=STATE_FILE.with_suffix('.json.tmp')
    temporary.write_text(json.dumps({'full_access':value},indent=2)+'\n',encoding='utf-8')
    temporary.replace(STATE_FILE)
    _state=value


def create_toggle():
    from kivy.metrics import dp
    from strategy_ui import StrategyButton
    button=StrategyButton(size_hint_y=None,height=dp(48))
    def refresh():
        button.text='DEV · Полный доступ: '+('ВКЛЮЧЁН' if enabled() else 'выключен')
        button.primary=enabled()
    def switch(*_):
        try:set_enabled(not enabled())
        except (OSError,ValueError) as error:
            from ui_components import show_message
            show_message('Режим разработчика',str(error));return
        refresh()
    button.bind(on_release=switch)
    refresh()
    return button


def unlimited_actions(conn,faction):
    """Only the human player's campaign actions; never AI or tactical rounds."""
    if not enabled():return False
    from army_intelligence import player_faction
    return faction == player_faction(conn) and bool(faction)


def consume_action(conn,faction):
    if not unlimited_actions(conn,faction):
        conn.execute('UPDATE turn_check_move SET moves_left=MAX(0,moves_left-1) WHERE faction=?',(faction,))
