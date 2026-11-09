"""Choose whole expedition stacks after dropping one city onto another."""
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from otherworld_ui import WorldPopup, _button, _busy
from strategy_ui import text_label, GOLD
from utils.helpers import format_number
import otherworlds as worlds


def send_from_map(owner, source, destination):
    if _busy(owner.conn):return
    if source==destination or not owner.conn.execute('SELECT 1 FROM portal_cities WHERE id=?',(destination,)).fetchone():
        owner.message.text='Выберите другой город Зазеркалья.'
        return
    units=worlds._camp_units(owner.conn,worlds.city_camp(owner.conn,owner.faction,source))
    if not units:return
    if len(units)==1:
        return depart(owner,source,destination,[units[0][0]])
    popup=MirrorArmySelection(owner,source,destination,units)
    owner.army_selection=popup
    popup.open()
    return popup


def depart(owner,source,destination,names,popup=None):
    if _busy(owner.conn):return
    try:worlds.begin_beam(owner.conn,owner.faction,destination,names,source=source)
    except ValueError as exc:
        (popup.notice if popup else owner.message).text=str(exc)
        return
    if popup:popup.dismiss()
    owner.map.draw()
    owner.play_beam(source,destination)


class MirrorArmySelection(WorldPopup):
    def __init__(self,owner,source,destination,units):
        super().__init__('Отправить войска',accent=owner.accent)
        self.selected=set()
        city=next(c for c in owner.map.nodes if c['id']==destination)
        self.root.add_widget(text_label('Назначение: '+city['name'],16,GOLD,
                                       size_hint_y=None,height=dp(32)))
        scroll=ScrollView(do_scroll_x=False)
        rows=BoxLayout(orientation='vertical',size_hint_y=None,spacing=dp(8))
        rows.bind(minimum_height=rows.setter('height'))
        self.unit_buttons={}
        for row in units:
            name,count=row[:2]
            caption=name+(' · '+format_number(count) if str(row[7]).split()[0]=='1' else '')
            button=_button(caption,lambda *_:None,
                           size_hint_y=None,height=dp(56),accent=owner.accent)
            def toggle(btn,n=name):
                if n in self.selected:self.selected.remove(n)
                else:self.selected.add(n)
                btn.set_selected(n in self.selected)
                self.send.disabled=not self.selected
            button.bind(on_release=toggle)
            self.unit_buttons[name]=button;rows.add_widget(button)
        scroll.add_widget(rows);self.root.add_widget(scroll)
        self.notice=text_label('Выберите отряды. Остальные останутся в городе.',14,
                               size_hint_y=None,height=dp(38))
        self.root.add_widget(self.notice)
        self.send=_button('Отправить',lambda *_:depart(owner,source,destination,self.selected,self),
                          size_hint_y=None,height=dp(48),disabled=True)
        self.root.add_widget(self.send)
