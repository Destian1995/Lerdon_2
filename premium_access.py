"""Content gates: verified licenses or the local source-only developer switch."""
FREE_FACTIONS=frozenset(('Эльфы','Вампиры','Адепты'))
PAID_FEATURES=frozenset(('mirror','tactical','tavern_quests','sabotage','no_ads'))


def full_access():
    from developer_access import enabled
    if enabled():return True
    from kivy.app import App
    if App.get_running_app() is None:return False
    from rewarded_access import get_rewarded
    reward=get_rewarded()
    if reward and reward.available:return True
    try:
        from billing_flow import get_billing_controller
        return bool(get_billing_controller().client.access())
    except Exception:return False


def allowed(feature,faction=None):
    if feature=='faction' and faction in FREE_FACTIONS:return True
    if feature not in PAID_FEATURES and feature!='faction':return True
    return full_access()


def require(feature,faction=None):
    if allowed(feature,faction):return True
    from premium_options_ui import show_locked_content
    show_locked_content()
    return False


def return_from_mirror(conn,faction):
    """An existing expedition can leave without paying or losing its army."""
    from kivy.uix.boxlayout import BoxLayout
    from kivy.uix.popup import Popup
    from strategy_ui import StrategyButton,text_label,GOLD
    from premium_options_ui import show_full_access
    root=BoxLayout(orientation='vertical',spacing=8,padding=12)
    root.add_widget(text_label('Зазеркалье доступно в полной версии.\nВаш отряд можно бесплатно вернуть домой.',16,GOLD))
    popup=Popup(title='Возвращение отряда',content=root,size_hint=(.94,.8),auto_dismiss=False)
    def leave(*_):
        import otherworlds as worlds
        try:worlds.return_home(conn,faction)
        except ValueError as exc:
            from ui_components import show_message
            show_message('Возвращение',str(exc));return
        from otherworld_ui import _refresh_main
        _refresh_main(conn,faction);popup.dismiss()
    for title,callback in (('Вернуться домой',leave),('Полная версия',lambda *_:show_full_access()),('Закрыть',popup.dismiss)):
        button=StrategyButton(text=title,size_hint_y=None,height=48)
        button.bind(on_release=callback);root.add_widget(button)
    popup.open();return popup
