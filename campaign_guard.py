"""Bring a portal defeat above Mirror windows, exactly once on the UI thread."""
def finish_portal_campaign(conn,faction,screen,force=False):
    from portal_home import loss_reason
    if conn is None or not faction or not screen or getattr(screen,'_game_ended',False):return False
    overlay=getattr(screen,'_turn_overlay',None)
    if not force and overlay is not None and overlay.parent:return False
    reason=loss_reason(conn,faction)
    if not reason:return False
    return finish_campaign(conn,faction,screen,'lose',reason)


def finish_campaign(conn,faction,screen,status,reason):
    if not screen or getattr(screen,'_game_ended',False):return False
    screen._game_ended=True
    if hasattr(screen,'end_turn_button'):screen.end_turn_button.disabled=True
    from kivy.core.window import Window
    from kivy.uix.popup import Popup
    for widget in list(Window.children):
        if isinstance(widget,Popup):widget.dismiss(animation=False)
    from results_game import ResultsGame
    ResultsGame(status,reason,conn).show_results(faction,status,reason)
    return True
