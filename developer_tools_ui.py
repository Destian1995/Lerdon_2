"""Source-only campaign tools. Never edit licenses, turns or other factions."""
from developer_access import unlimited_actions

RESOURCES=('Кроны','Кристаллы','Рабочие','Население')


def busy(conn):
    import sys
    from turn_ui_guard import database_busy
    from tactical_battle_bridge import operation_busy
    screen=getattr(sys.modules.get('game_process'),'_active_game_screen',None)
    return (database_busy(conn) or operation_busy(conn) or
            bool(screen and getattr(screen,'conn',None) is conn and getattr(screen,'_troop_movement_busy',False)))


def set_resources(conn,faction,values):
    from utils.resource_caps import caps
    from utils.resource_payments import ensure_resource_schema,sync_resources
    if busy(conn):raise ValueError('Дождитесь завершения хода, перемещения или боя.')
    if not unlimited_actions(conn,faction):raise ValueError('Включите DEV-режим в главном меню.')
    limits=caps(conn,faction)
    amounts={}
    if set(values)!=set(RESOURCES):raise ValueError('Заполните все четыре ресурса.')
    for resource in RESOURCES:
        text=str(values[resource]).strip().replace(' ','').replace('\u00a0','')
        if not text.isascii() or not text.isdecimal():raise ValueError(resource+': введите целое неотрицательное число.')
        amount=int(text)
        if amount>limits[resource]:raise ValueError(resource+': максимум '+f'{limits[resource]:,}'.replace(',',' '))
        amounts[resource]=amount
    with conn:
        ensure_resource_schema(conn)
        for resource,amount in amounts.items():
            conn.execute('''INSERT INTO resources(faction,resource_type,amount) VALUES(?,?,?)
                ON CONFLICT(faction,resource_type) DO UPDATE SET amount=excluded.amount''',(faction,resource,amount))
    sync_resources(conn,faction)
    return amounts


def show_tools(conn,faction,on_change=None):
    from kivy.metrics import dp,sp
    from kivy.uix.boxlayout import BoxLayout
    from kivy.uix.label import Label
    from kivy.uix.popup import Popup
    from kivy.uix.scrollview import ScrollView
    from kivy.uix.textinput import TextInput
    from strategy_ui import StrategyButton,GOLD
    from window_theme import prepare_custom_popup
    if busy(conn) or not unlimited_actions(conn,faction):return
    from utils.resource_caps import caps
    limits=caps(conn,faction)
    balances=dict(conn.execute('SELECT resource_type,amount FROM resources WHERE faction=?',(faction,)))
    root=BoxLayout(orientation='vertical',padding=dp(12),spacing=dp(8))
    root._strategy_fixed_layout=True
    popup=Popup(title='',content=root,size_hint=(.94,.94),size_hint_max=(dp(620),dp(510)),auto_dismiss=False)
    prepare_custom_popup(popup)
    scroll=ScrollView(do_scroll_x=False)
    form=BoxLayout(orientation='vertical',size_hint_y=None,spacing=dp(6))
    form.bind(minimum_height=form.setter('height'));scroll.add_widget(form);root.add_widget(scroll)
    def label(text,height=40):
        item=Label(text=text,color=GOLD,font_size=sp(14),size_hint_y=None,height=dp(height))
        item.bind(size=lambda widget,_:setattr(widget,'text_size',widget.size))
        form.add_widget(item);return item
    label('DEV · Ресурсы игрока',32)
    label('Перемещения и атаки не расходуют действия.\n«Завершить ход» работает обычно.',48)
    popup.fields={}
    for resource in RESOURCES:
        row=BoxLayout(size_hint_y=None,height=dp(54),spacing=dp(8))
        row.add_widget(Label(text=resource+'\nЛимит: '+f'{limits[resource]:,}'.replace(',',' '),font_size=sp(13)))
        field=TextInput(text=str(max(0,int(balances.get(resource,0)))),multiline=False,input_filter='int',font_size=sp(19))
        popup.fields[resource]=field;row.add_widget(field);form.add_widget(row)
    popup.status=label('Указанные суммы заменят текущие запасы.',48)
    buttons=BoxLayout(size_hint_y=None,height=dp(48),spacing=dp(8))
    apply=StrategyButton(text='Установить',primary=True)
    close=StrategyButton(text='Закрыть')
    def save(*_):
        try:set_resources(conn,faction,{key:field.text for key,field in popup.fields.items()})
        except ValueError as error:popup.status.text=str(error);return
        popup.status.text='Ресурсы обновлены.'
        if on_change:on_change()
    apply.bind(on_release=save);close.bind(on_release=popup.dismiss)
    buttons.add_widget(apply);buttons.add_widget(close);root.add_widget(buttons)
    popup.open();return popup
