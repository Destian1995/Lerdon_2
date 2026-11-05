"""A crystal exchange board with a prominent quote and two visible trade panels."""
from kivy.graphics import Color, Mesh, Line, Ellipse
from kivy.metrics import dp
from kivy.uix.widget import Widget
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from frontend_ui import NaturalList
from mirror_readable_ui import ReadableText, ReadableButton
from strategy_ui import surface, GOLD, MUTED
import otherworlds as worlds

CYAN=(.33,.85,1,1)
GREEN=(.40,.92,.70,1)
AMBER=(1,.74,.36,1)


def number(value):
    return f'{int(value):,}'.replace(',', ' ')


class CrystalEmblem(Widget):
    def __init__(self, tint=CYAN, **kwargs):
        super().__init__(**kwargs)
        self.tint=tint
        self.bind(pos=self.draw,size=self.draw)
        self.draw()

    def draw(self,*_):
        self.canvas.clear()
        x,y=self.center;scale=min(self.size)*.44
        points=[(x,y+scale),(x+scale*.59,y+scale*.33),
                (x+scale*.48,y-scale*.37),(x,y-scale),
                (x-scale*.48,y-scale*.37),(x-scale*.59,y+scale*.33)]
        with self.canvas:
            for radius,alpha in ((1.1,.035),(.88,.06),(.68,.09)):
                Color(*self.tint[:3],alpha)
                Ellipse(pos=(x-scale*radius,y-scale*radius),size=(scale*radius*2,scale*radius*2))
            for i,point in enumerate(points):
                following=points[(i+1)%len(points)]
                shade=(.45,.80,.63,.33,.60,.90)[i]
                Color(*(min(1,c*shade+.12) for c in self.tint[:3]),1)
                Mesh(vertices=[x,y,0,0,*point,0,0,*following,0,0],indices=[0,1,2],mode='triangles')
            Color(.76,.96,1,.85)
            Line(points=[v for p in points for v in p],close=True,width=dp(1))
            Color(1,1,1,.55)
            Line(points=[*points[0],x,y,*points[3]],width=dp(.8))


class CrystalTradePanel(NaturalList):
    def __init__(self,city,buy,**kwargs):
        super().__init__(padding=dp(16),spacing=dp(9),**kwargs)
        self.buy=buy
        accent=GREEN if buy else AMBER
        surface(self,(.035,.13,.16,1) if buy else (.16,.105,.055,1),accent)
        heading=BoxLayout(size_hint_y=None,height=dp(54),spacing=dp(10))
        self.heading=heading
        self.emblem=CrystalEmblem(tint=CYAN if buy else AMBER,size_hint_x=None,width=dp(54))
        heading.add_widget(self.emblem)
        self.title=ReadableText('Купить кристаллы' if buy else 'Продать кристаллы',
                                size=18,color=accent,bold=True,pos_hint={'center_y':.5})
        self._compact=False
        self.title.bind(height=lambda _,h:setattr(heading,'height',max(dp(24 if self._compact else 54),h)))
        heading.add_widget(self.title)
        self.add_widget(heading)
        self.add_widget(ReadableText('10 000 кристаллов',size=16,bold=True))
        self.caption=ReadableText('Вы заплатите' if buy else 'Вы получите',size=13,color=MUTED)
        self.add_widget(self.caption)
        self.price=ReadableText('',size=27,bold=True,color=accent)
        self.add_widget(self.price)
        self.button=ReadableButton(text='Купить' if buy else 'Продать',accent=accent,
                                    primary=True,size_hint_y=None,height=dp(48))
        self.button.bind(on_release=lambda *_:city.act(
            lambda:worlds.trade_crystals(city.conn,city.faction,buy),
            'Кристаллы куплены' if buy else 'Кристаллы проданы'))
        self.add_widget(self.button)

    def refresh(self,city):
        self.price.text=number(worlds.crystal_trade_price(city.conn,self.buy))+' крон'
        self.button.disabled=not bool(city.present())
        self.button.height=dp(48)

    def compact(self,enabled):
        self._compact=enabled
        self.padding=dp(6 if enabled else 16)
        self.spacing=dp(3 if enabled else 9)
        self.emblem.width=0 if enabled else dp(54)
        self.emblem.opacity=0 if enabled else 1
        self.heading.spacing=0 if enabled else dp(10)
        self.title.logical_font_size=16 if enabled else 18
        self.title.update_font()
        self.heading.height=max(dp(24 if enabled else 54),self.title.height)
        if enabled and self.caption.parent:self.remove_widget(self.caption)
        elif not enabled and self.caption.parent is None:self.add_widget(self.caption,index=2)
        self.price.logical_font_size=20 if enabled else 27
        self.price.update_font()


class MirrorCrystalMarket(ScrollView):
    def __init__(self,city,**kwargs):
        super().__init__(do_scroll_x=False,bar_width=dp(4),**kwargs)
        self.city=city
        self.body=NaturalList(spacing=dp(12),padding=(0,0,dp(5),dp(5)))
        self.add_widget(self.body)
        banner=surface(BoxLayout(size_hint_y=None,padding=dp(14),spacing=dp(12)),(.04,.085,.15,1),CYAN)
        self.banner=banner
        banner.pos_hint={'top':1}
        self.emblem=CrystalEmblem(size_hint=(None,None),size=(dp(76),dp(76)),pos_hint={'center_y':.5})
        banner.add_widget(self.emblem)
        copy=NaturalList(spacing=dp(3),pos_hint={'center_y':.5})
        copy.add_widget(ReadableText('КУРС КРИСТАЛЛОВ',size=12,color=CYAN,bold=True))
        self.quote=ReadableText('',size=29,color=CYAN,bold=True)
        self.balance=ReadableText('',size=13,color=MUTED)
        copy.add_widget(self.quote);copy.add_widget(self.balance)
        banner.add_widget(copy)
        copy.bind(height=lambda _,h:setattr(banner,'height',max(dp(108),h+dp(28))))
        self.body.add_widget(banner)
        self.cards=GridLayout(cols=2,size_hint_y=None,spacing=dp(12))
        self.cards.bind(minimum_height=self.cards.setter('height'))
        self.panels=[CrystalTradePanel(city,buy) for buy in (True,False)]
        for panel in self.panels:self.cards.add_widget(panel)
        self.body.add_widget(self.cards)
        self.bind(size=self.arrange)
        self.arrange();self.refresh()

    def arrange(self,*_):
        self.cards.cols=2 if self.width>=dp(540) else 1
        compact=self.width>=dp(540) and self.height<dp(300)
        self.body.orientation='horizontal' if compact else 'vertical'
        self.banner.size_hint_x=.30 if compact else 1
        self.cards.size_hint_x=.70 if compact else 1
        self.emblem.width=0 if compact else dp(76)
        self.emblem.opacity=0 if compact else 1
        self.banner.spacing=0 if compact else dp(12)
        self.banner.padding=dp(8 if compact else 14)
        self.quote.logical_font_size=21 if compact else 29
        self.quote.update_font()
        for panel in self.panels:panel.compact(compact)

    def refresh(self):
        city=self.city
        self.quote.text=f'{worlds.crystal_quote(city.conn)/100:.3f} крон / шт.'
        balances=dict(city.conn.execute('SELECT resource_type,amount FROM resources WHERE faction=?',(city.faction,)))
        self.balance.text=f'В наличии: {number(balances.get("Кроны",0))} крон · {number(balances.get("Кристаллы",0))} кристаллов'
        for panel in self.panels:panel.refresh(city)
        city.offer_buttons=[panel.button for panel in self.panels]
        self.arrange()
