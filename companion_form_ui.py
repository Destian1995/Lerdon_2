"""Change a pact companion's shape from either world's garrison card."""
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.image import Image
from otherworld_ui import WorldPopup,_button,_busy,_refresh_main
from mirror_layout import FitLabel
from utils.helpers import format_number
import mirror_monster_quest as hunt


class CompanionForms(WorldPopup):
    def __init__(self,conn,faction,callback=None,**kwargs):
        self.conn,self.faction,self.callback=conn,faction,callback
        super().__init__('Облик спутника',**kwargs)
        self.art=Image(fit_mode='contain')
        self.root.add_widget(self.art)
        self.stats=FitLabel(size_hint_y=None,height=dp(64),maximum=dp(15),minimum=dp(12),halign='center')
        self.root.add_widget(self.stats)
        actions=BoxLayout(size_hint_y=None,height=dp(44),spacing=dp(6))
        for caption,form in (('Дворянин · атака','noble'),('Монстр · защита','monster')):
            actions.add_widget(_button(caption,lambda *_,f=form:self.switch(f)))
        self.root.add_widget(actions);self.refresh()
        genders=BoxLayout(size_hint_y=None,height=dp(44),spacing=dp(6))
        for caption,gender in (('Дворянин','lord'),('Дворянка','lady')):
            genders.add_widget(_button(caption,lambda *_,g=gender:self.gender(g)))
        self.root.add_widget(genders)
        from morgana_covenant import offer
        row=offer(conn,faction)
        if row and row['status'] in ('offered','deferred'):
            from morgana_covenant_ui import show_offer
            self.root.add_widget(_button('Предложение Морганы',lambda *_:show_offer(conn,faction,force=True),size_hint_y=None,height=dp(44)))

    def refresh(self):
        data=hunt.companion_form(self.conn,self.faction)
        if not data:return
        row=self.conn.execute('SELECT attack,defense,image_path FROM units WHERE unit_name=?',(data['unit_name'],)).fetchone()
        self.art.source=row[2]
        from heart_contract import multiplier
        factor=multiplier(self.conn,self.faction)
        row=(row[0]*factor,row[1]*factor,row[2])
        self.stats.text=('Дворянин: АТК +50%, ЗАЩ −50%' if data['form']=='noble' else 'Монстр: АТК −50%, ЗАЩ +50%')
        self.stats.text+='\nАТК '+format_number(row[0])+' · ЗАЩ '+format_number(row[1])+'\n'+hunt.deadline_caption(self.conn,self.faction)

    def switch(self,form):
        if _busy(self.conn):return
        try:
            with self.conn:hunt.set_form(self.conn,self.faction,form)
        except ValueError as exc:self.stats.text=str(exc);return
        self.refresh();_refresh_main(self.conn,self.faction)
        if self.callback:self.callback()

    def gender(self,gender):
        if _busy(self.conn):return
        try:
            with self.conn:hunt.choose_gender(self.conn,self.faction,gender)
        except ValueError as exc:self.stats.text=str(exc);return
        self.refresh();_refresh_main(self.conn,self.faction)
        if self.callback:self.callback()


def form_button(conn,faction,unit_name,callback=None):
    if not unit_name.startswith(hunt.PREFIX):return None
    data=hunt.companion_form(conn,faction)
    if not data or data['unit_name']!=unit_name:return None
    def show(*_):
        if not _busy(conn):CompanionForms(conn,faction,callback).open()
    return _button('Сменить облик спутника',show,size_hint_y=None,height=dp(44))
