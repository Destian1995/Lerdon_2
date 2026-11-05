"""Touch-friendly selection of rebel attack targets on the current world map."""
import ast
import sys
from kivy.clock import Clock
from kivy.graphics import Color, Line
from kivy.metrics import dp,sp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.image import Image
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from strategy_ui import StrategyButton,text_label,surface,INK,GOLD,MUTED,TEXT
from window_theme import prepare_custom_popup
from rebel_orders import available_targets,issue_order

ICONS={'Север':'people','Эльфы':'elfs','Вампиры':'vampires','Адепты':'adepts',
       'Элины':'poly','Мятежники':'keig','Нежить':'castle_death'}


def current_map_source(conn):
    screen=getattr(sys.modules.get('game_process'),'_active_game_screen',None)
    if getattr(screen,'conn',None) is conn and screen.parent:
        for child in screen.parent.children:
            if getattr(child,'random_map_source',None):
                return child.random_map_source
    return ''


class RebelAttackMap(Popup):
    def __init__(self,conn,player,on_order=None,**kwargs):
        super().__init__(title='',separator_height=0,size_hint=(1,1),auto_dismiss=False,**kwargs)
        prepare_custom_popup(self)
        self.conn,self.player,self.on_order=conn,player,on_order
        self.selected=None;self.zoom=1;self.nodes={};self.positions={}
        self.targets=dict(available_targets(conn,player))
        self.layout=BoxLayout(orientation='vertical',padding=dp(6),spacing=dp(4))
        surface(self.layout,INK,GOLD);self.content=self.layout
        header=BoxLayout(size_hint_y=None,height=dp(40),spacing=dp(4))
        header.add_widget(text_label('Приказ мятежникам',sp(17),GOLD,bold=True))
        for caption,callback in [('−',lambda *_:self.set_zoom(-.5)),('+',lambda *_:self.set_zoom(.5))]:
            button=StrategyButton(text=caption,size_hint_x=None,width=dp(44))
            button.bind(on_release=callback);header.add_widget(button)
        self.layout.add_widget(header)
        self.scroll=ScrollView(do_scroll_x=True,do_scroll_y=True,scroll_type=['content','bars'],bar_width=dp(4))
        self.scroll.scroll_y=.5
        self.map=FloatLayout(size_hint=(None,None));surface(self.map,INK)
        self.map_image=Image(source=current_map_source(conn),size_hint=(None,None),fit_mode='fill')
        self.map.add_widget(self.map_image)
        self.scroll.add_widget(self.map);self.layout.add_widget(self.scroll)
        self.status=text_label('Красные города — цели · Карту можно двигать',sp(12),MUTED)
        self.status.size_hint_y=None;self.status.height=dp(36);self.layout.add_widget(self.status)
        footer=BoxLayout(size_hint_y=None,height=dp(48),spacing=dp(6))
        cancel=StrategyButton(text='Отмена');cancel.bind(on_release=lambda *_:self.dismiss())
        self.confirm=StrategyButton(text='Выберите город',disabled=True)
        self.confirm.bind(on_release=self.submit)
        footer.add_widget(cancel);footer.add_widget(self.confirm);self.layout.add_widget(footer)
        self.towns=list(conn.execute('SELECT id,name,faction,coordinates FROM cities ORDER BY id'))
        for cid,name,owner,raw in self.towns:
            try:x,y=ast.literal_eval(raw)
            except (ValueError,TypeError,SyntaxError):continue
            self.positions[cid]=(float(x),float(y))
            node=StrategyButton(text='',size_hint=(None,None),disabled=name not in self.targets)
            node.opacity=1 if name in self.targets else .55
            icon=Image(source='files/buildings/'+ICONS.get(owner,'default')+'.png',fit_mode='contain')
            node.add_widget(icon)
            node.bind(pos=lambda n,_:self.place_icon(n),size=lambda n,_:self.place_icon(n))
            node.icon=icon
            node.bind(on_release=lambda _,n=name:self.select(n))
            label=text_label(name,sp(11),TEXT,bold=True)
            label.size_hint=(None,None)
            label.shorten=True;label.shorten_from='right';label.max_lines=1
            surface(label,INK,GOLD if name in self.targets else MUTED)
            self.map.add_widget(node);self.map.add_widget(label)
            self.nodes[name]=(cid,node,label)
        self._redraw=Clock.create_trigger(self.draw,-1)
        self.scroll.bind(size=self._redraw);self.map.bind(pos=self._redraw)
        self.bind(on_open=self._redraw,on_dismiss=lambda *_:self._redraw.cancel())
        self._redraw()

    def place_icon(self,node):
        if hasattr(node,'icon'):node.icon.pos=node.pos;node.icon.size=node.size

    def set_zoom(self,delta):
        self.zoom=max(.5,min(3,self.zoom+delta));self._redraw()

    def draw(self,*_):
        width,height=max(1,self.scroll.width),max(1,self.scroll.height)
        scale=max(.02,max(max(1,width-dp(72))/1200,max(1,height-dp(80))/800))*self.zoom
        self.map.size=(max(width,1200*scale+dp(72)),max(height,800*scale+dp(80)))
        left=self.map.x+(self.map.width-1200*scale)/2
        bottom=self.map.y+(self.map.height-800*scale)/2+dp(10)
        self.map_image.pos=(left,bottom);self.map_image.size=(1200*scale,800*scale)
        self.map.canvas.after.clear()
        with self.map.canvas.after:
            Color(.85,.70,.40,.6)
            for a,b in self.conn.execute('SELECT city1,city2 FROM roads'):
                if a in self.positions and b in self.positions:
                    x,y=self.positions[a];u,v=self.positions[b]
                    Line(points=[left+x*scale,bottom+y*scale,left+u*scale,bottom+v*scale],width=dp(1))
        for name,(cid,node,label) in self.nodes.items():
            x,y=self.positions[cid];cx,cy=left+x*scale,bottom+y*scale
            side=dp(42 if self.scroll.width<dp(700) else 50)
            node.size=(side,side);node.center=(cx,cy)
            label.size=(dp(108),dp(26));label.pos=(cx-label.width/2,cy-side/2-dp(25))
            if name in self.targets:
                with self.map.canvas.after:
                    Color(*((1,.30,.18,1) if name!=self.selected else (.35,1,.5,1)))
                    Line(circle=(cx,cy,side*.64),width=dp(2.5 if name==self.selected else 1.5))

    def select(self,name):
        if name not in self.targets:return
        self.selected=name;self.confirm.disabled=False;self.confirm.text='Атаковать'
        self.status.text=f'{name} · {self.targets[name]}'
        self._redraw()

    def submit(self,*_):
        if not self.selected:return
        try:enemy=issue_order(self.conn,self.player,self.selected)
        except ValueError as exc:
            self.status.text=str(exc);self.confirm.disabled=True;return
        if self.on_order:self.on_order(self.selected,enemy)
        self.dismiss()
