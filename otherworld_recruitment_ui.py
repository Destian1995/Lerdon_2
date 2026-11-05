"""The main-map recruitment mixer, backed by the expedition market."""
from types import SimpleNamespace
from kivy.metrics import dp
from kivy.uix.scrollview import ScrollView
from recruitment_ui import RecruitmentSession
from strategy_ui import text_label, GOLD
import otherworlds as worlds


class MirrorRecruitment(RecruitmentSession):
    def __init__(self,city_popup):
        self.city_popup=city_popup
        self.conn,self.faction=city_popup.conn,city_popup.faction
        self.templates=worlds.unit_offers(self.conn,self.faction)
        units={u['unit_name']:dict(image=u['image_path'],show_hire_total=True,role_label=u.get('role_label','Рекрут'),
            cost=(worlds.price(city_popup.city,u['cost_money']),0),
            stats={'Класс юнита':'1','Урон':u['attack'],'Защита':u['defense'],
                   'Живучесть':u['durability'],'Потребление Кристаллов':u['consumption']})
            for u in self.templates}
        super().__init__(self.faction,SimpleNamespace(),units,self.hire)
        self.notice=text_label('',13,GOLD,size_hint_y=None,height=0)
        self.notice.bind(text=lambda *_:setattr(self.notice,'height',dp(32) if self.notice.text else 0))
        self.popup.content.add_widget(self.notice,index=len(self.popup.content.children)-1)
        self.popup.bind(on_dismiss=lambda *_:city_popup.refresh())

    def maximum(self,info):
        unit=next(u for u in self.templates if u['image_path']==info['image'])
        try:return worlds.recruitment_limit(self.conn,self.faction,unit['id'])
        except ValueError:return 0

    def build_card(self,index):
        super().build_card(index)
        card=self.cards[index]
        display=card.children[-1]
        card.remove_widget(display)
        display.padding=dp(6)
        display.size_hint_y=None
        display.height=dp(280)
        scroll=ScrollView(do_scroll_x=False)
        scroll.add_widget(display)
        card.add_widget(scroll,index=len(card.children))
        card.mirror_scroll=scroll
        scroll.bind(size=self.fit)
        self.fit()

    def fit(self,*args):
        super().fit(*args)
        narrow=self.popup.width<self.popup.height
        for card in self.cards.values():
            scroll=getattr(card,'mirror_scroll',None)
            if not scroll:continue
            display=scroll.children[0];details=display.children[-1]
            display.orientation='vertical' if narrow else 'horizontal'
            details.size_hint=(1,None) if narrow else (.56,1)
            if narrow:details.height=dp(280)
            card.portrait.size_hint=(1,1) if narrow else (.44,1)
            display.height=max(dp(540 if narrow else 280),scroll.height)

    def hire(self,name,cost,quantity,*_):
        from otherworld_ui import _busy,_refresh_main
        if _busy(self.conn):return
        if not self.city_popup.present():
            self.notice.text='Отряд должен находиться в этом городе.';return
        unit=next(u for u in self.templates if u['unit_name']==name)
        try:
            count=int(quantity.text)
            worlds.recruit(self.conn,self.faction,unit['id'],count)
        except ValueError as exc:
            self.notice.text=str(exc);return
        self.notice.text=''
        _refresh_main(self.conn,self.faction)
        self.city_popup.refresh();self.city_popup.owner.refresh()
