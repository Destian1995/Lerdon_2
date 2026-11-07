"""Morgana's optional offer, visible after a soul pact and an undead arrival."""
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.image import Image
from kivy.uix.scrollview import ScrollView
from otherworld_ui import WorldPopup,_button,_busy,_refresh_main,_screen
from mirror_readable_ui import ReadableText
from frontend_ui import NaturalList
import morgana_covenant as covenant


class MorganaOffer(WorldPopup):
    def __init__(self,conn,faction,**kwargs):
        self.conn,self.faction=conn,faction
        super().__init__('Моргана · Служение Нежити',**kwargs)
        body=BoxLayout(spacing=dp(8));self.body=body;self.root.add_widget(body)
        self.art=Image(source='files/army/death/morgana.png',fit_mode='contain',size_hint_x=.45)
        body.add_widget(self.art)
        scroll=ScrollView(do_scroll_x=False);self.copy_scroll=scroll;body.add_widget(scroll)
        copy=NaturalList(padding=dp(4),spacing=dp(8));scroll.add_widget(copy)
        from mirror_monster_quest import deadline_caption,pact
        existing=pact(conn,faction)
        text=('«Отдайте мне свою душу — и возглавьте мой легион».\n\n'
              'Вы получите войска Нежити и её найм. Ваши города станут некрополями; герои и спутник останутся с вами.\n\n'
              'Армия и лимиты ресурсов: +45% навсегда. Моргана и Низар — союзники со своими армиями. '
              'Со всеми живыми фракциями — вечная война, без мира.\n\n'+
              ('Срок прежней сделки сохранится. '+deadline_caption(conn,faction) if existing else 'На победу — 30 ходов после принятия.')+
              '\nНе успеете победить — потеряете душу и кампанию. Звание не присваивается.')
        copy.add_widget(ReadableText(text,size=15))
        self.feedback=ReadableText('',size=14);copy.add_widget(self.feedback)
        actions=BoxLayout(size_hint_y=None,height=dp(44),spacing=dp(6));self.root.add_widget(actions)
        actions.add_widget(_button('Служить Моргане' if existing else 'Продать душу Моргане',self.accept))
        actions.add_widget(_button('Отказаться',self.decline))

    def layout_content(self):
        if not hasattr(self,'body'):return
        portrait=self.root.width<dp(500) and self.root.height>self.root.width
        self.body.orientation='vertical' if portrait else 'horizontal'
        self.art.size_hint=(1,None) if portrait else (.45,1)
        if portrait:self.art.height=dp(180)
        self.copy_scroll.size_hint=(1,1) if portrait else (.55,1)

    def accept(self,*_):
        if _busy(self.conn):return
        try:covenant.accept(self.conn,self.faction)
        except ValueError as exc:self.feedback.text=str(exc);return
        screen=_screen(self.conn)
        if screen:
            screen.faction.load_buildings()
            screen.faction.resources.update(dict(self.conn.execute('SELECT resource_type,amount FROM resources WHERE faction=?',(self.faction,))))
        _refresh_main(self.conn,self.faction);self.dismiss()

    def decline(self,*_):
        if _busy(self.conn):return
        with self.conn:covenant.decline(self.conn,self.faction)
        self.dismiss()


def show_offer(conn,faction,force=False):
    screen=_screen(conn)
    if screen and getattr(screen,'_game_ended',False):return None
    if _busy(conn):return None
    with conn:row=covenant.offer(conn,faction)
    if not row or row['status']!='offered' or row['notified'] and not force:return None
    popup=MorganaOffer(conn,faction);popup.open()
    with conn:conn.execute('UPDATE morgana_covenants SET notified=1 WHERE faction=?',(faction,))
    return popup


def schedule_offer(conn,faction,attempts=120):
    """Wait for AI marches/portal travel, rather than losing the event."""
    import sqlite3
    from kivy.clock import Clock
    screen=_screen(conn)
    if screen and getattr(screen,'_game_ended',False):return
    try:
        with conn:row=covenant.offer(conn,faction)
        if not row or row['status']!='offered' or row['notified']:return
        if _busy(conn):
            if attempts:Clock.schedule_once(lambda dt:schedule_offer(conn,faction,attempts-1),.5)
        else:show_offer(conn,faction)
    except sqlite3.Error:
        return  # The campaign was closed while waiting for an animation.
