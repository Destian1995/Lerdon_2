"""One explicit decision after an army conquers an enemy town."""
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from otherworld_ui import WorldPopup,_button
from mirror_readable_ui import ReadableText
from strategy_ui import GOLD
import main_map_intrigues as plots


def pending_capture(conn,faction,city):
    if not plots.exists(conn,'map_intrigue_captures') or plots.owner(conn,city)!=faction:return None
    return next(iter(plots._dicts(conn,"SELECT * FROM map_intrigue_captures WHERE faction=? AND city=? AND status='pending' ORDER BY id DESC LIMIT 1",(faction,city))),None)


class CityCapturePopup(WorldPopup):
    def __init__(self,conn,faction,row,**kwargs):
        self.conn,self.faction,self.row=conn,faction,row
        super().__init__('ГОРОД ВЗЯТ · '+row['city'],accent=GOLD,**kwargs)
        for child in list(self.header.children):
            if child is not self.heading:self.header.remove_widget(child)
        self.heading.font_size=dp(18)
        self.body=BoxLayout(orientation='vertical',size_hint_y=None,spacing=dp(10))
        self.body.bind(minimum_height=self.body.setter('height'))
        self.scroll=ScrollView(do_scroll_x=False);self.scroll.add_widget(self.body);self.root.add_widget(self.scroll)
        self.body.add_widget(ReadableText('Ваши войска заняли вражеский город. Решите, как поступить с жителями.',size=18,color=GOLD))
        self.body.add_widget(ReadableText('Пощадить: сохранить дома и сбережения жителей; доверие спутника +10.\n\nРазграбить: до 15 000 крон и 5 000 кристаллов с учётом лимитов; доверие спутника −20. Горожане запомнят разграбление.',size=15))
        if row['offer_id']:self.body.add_widget(ReadableText('Вы обещали пощадить город. Нарушение слова закроет новые тайные предложения на 15 ходов.',size=15,color=(1,.48,.42,1)))
        self.notice=ReadableText('',size=14,height=0);self.body.add_widget(self.notice)
        self.buttons={};footer=BoxLayout(size_hint_y=None,height=dp(52),spacing=dp(8))
        for choice,label in (('spare','Пощадить'),('plunder','Разграбить')):
            button=_button(label,lambda *_,c=choice:self.choose(c),accent=GOLD)
            footer.add_widget(button);self.buttons[choice]=button
        self.root.add_widget(footer)
        self.done=False

    def choose(self,choice):
        if self.done:return
        try:
            plots.settle_capture(self.conn,self.faction,self.row['id'],choice)
            self.conn.commit()
        except ValueError as error:
            self.notice.text=str(error);return
        self.done=True
        from utils.resource_payments import sync_resources
        sync_resources(self.conn,self.faction)
        self.dismiss()
        from game_process import refresh_map
        refresh_map()
        from kivy.clock import Clock
        Clock.schedule_once(lambda dt: present_next_capture(self.conn,self.faction),.1)


def present_capture(conn,faction,city):
    row=pending_capture(conn,faction,city)
    if not row:return None
    from kivy.core.window import Window
    for popup in Window.children:
        if isinstance(popup,CityCapturePopup) and popup.conn is conn and popup.row['id']==row['id']:return popup
    popup=CityCapturePopup(conn,faction,row);popup.open();return popup


def present_next_capture(conn,faction):
    if not plots.exists(conn,'map_intrigue_captures'):return None
    row=conn.execute("""SELECT m.city FROM map_intrigue_captures m
        JOIN cities c ON c.name=m.city AND c.faction=m.faction
        WHERE m.faction=? AND m.status='pending' ORDER BY m.id LIMIT 1""",(faction,)).fetchone()
    return present_capture(conn,faction,row[0]) if row else None
