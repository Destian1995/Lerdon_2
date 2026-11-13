"""Keep periodic HUD reads off the connection owned by the turn worker."""
import sys


def database_busy(conn=None, screen=None):
    if screen is None:
        screen=getattr(sys.modules.get('game_process'),'_active_game_screen',None)
    if screen is None:return False
    if conn is not None and getattr(screen,'conn',None) is not conn:return False
    worker=getattr(screen,'_turn_thread',None)
    return bool(getattr(screen,'_turn_overlay',None) is not None
                or getattr(screen,'_turn_failed',False)
                or (worker is not None and worker.is_alive()))
