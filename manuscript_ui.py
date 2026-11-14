"""A candlelit chronicle: fixed controls, scrollable ink, bounded canvas animation."""
import math
import random
import re
from functools import lru_cache
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, Rectangle, RoundedRectangle, Line, Mesh, RenderContext
from kivy.graphics.texture import Texture
from kivy.metrics import dp, sp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.widget import Widget
from strategy_ui import StrategyButton, GOLD

FONT='files/menu/manuscript/DejaVuSerif.ttf'
INK=(.19,.115,.065,1)
CANDLE_ART='files/menu/manuscript/realistic-candle.png'

FIRE_FRAGMENT='''
$HEADER$
uniform float u_time;
float hash(vec2 p) { return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453); }
float noise(vec2 p) {
    vec2 i=floor(p),f=fract(p); f=f*f*(3.0-2.0*f);
    return mix(mix(hash(i),hash(i+vec2(1.0,0.0)),f.x),
               mix(hash(i+vec2(0.0,1.0)),hash(i+vec2(1.0,1.0)),f.x),f.y);
}
float flow(vec2 p) {
    float v=0.0,a=0.55;
    for(int i=0;i<4;i++) { v+=a*noise(p); p=p*2.03+vec2(8.1,3.7); a*=0.5; }
    return v;
}
void main(void) {
    vec2 uv=tex_coord0;
    float n=flow(vec2(uv.x*6.0,uv.y*5.0-u_time*2.8));
    float bend=(sin(u_time*2.5+uv.y*7.0)*0.045+(n-0.5)*0.12)*uv.y;
    float width=0.26*pow(max(0.0001,sin(uv.y*3.14159265)),0.75)*(1.0-uv.y*0.60);
    float d=abs(uv.x-0.5-bend);
    float edge=1.0-smoothstep(width*0.48,width,d);
    float vertical=smoothstep(0.0,0.045,uv.y)*(1.0-smoothstep(0.80,1.0,uv.y));
    float heat=clamp((1.0-d/max(width,0.001))*1.2+(1.0-uv.y)*0.12+(n-0.5)*0.18,0.0,1.0);
    vec3 rgb=mix(vec3(1.0,0.20,0.015),vec3(1.0,0.76,0.17),smoothstep(0.18,0.75,heat));
    float core=smoothstep(0.73,0.98,heat)*(1.0-smoothstep(0.48,0.94,uv.y));
    rgb=mix(rgb,vec3(1.0,0.98,0.80),core);
    rgb=mix(vec3(0.26,0.43,1.0),rgb,smoothstep(0.01,0.13,uv.y));
    gl_FragColor=vec4(rgb,edge*vertical*0.98)*frag_color;
}
'''


class LivingFlame(Widget):
    """A small GLES2 fire surface: advected noise, soft edges and a hot core."""
    def __init__(self,**kwargs):
        super().__init__(**kwargs)
        self.canvas=RenderContext(use_parent_projection=True,use_parent_modelview=True)
        self.fallback=None
        try:
            self.canvas.shader.fs=FIRE_FRAGMENT
            if not self.canvas.shader.success:raise RuntimeError('Fire shader unavailable')
            with self.canvas:
                Color(1,1,1,1);self.rect=Rectangle(texture=texture('light'))
        except Exception:
            # Keep a flame on older GL drivers rather than fail the entire screen.
            self.canvas.shader.fs='$HEADER$\nvoid main(void){gl_FragColor=frag_color;}'
            with self.canvas:
                Color(1,.80,.28,1);self.fallback=Mesh(mode='triangle_fan')
        self.canvas['u_time']=0.0
        self.bind(pos=self.layout,size=self.layout)
        self.layout()

    def layout(self,*_):
        if self.fallback is None:self.rect.pos,self.rect.size=self.pos,self.size

    def animate(self,t):
        self.canvas['u_time']=float(t)
        if self.fallback is not None:
            Candle.flame_mesh(self.fallback,self.center_x,self.y,self.width*.20,self.height,
                              math.sin(t*3.8)*self.width*.08)


@lru_cache(maxsize=2)
def texture(kind):
    size=128 if kind=='paper' else 64
    pixels=bytearray();rng=random.Random(512)
    for y in range(size):
        for x in range(size):
            if kind=='paper':
                grain=rng.randrange(-6,7)+2*math.sin(x*.19+y*.12)
                pixels.extend((int(225+grain),int(204+grain),int(160+grain),255))
            else:
                r=math.hypot((x-size/2)/(size/2),(y-size/2)/(size/2))
                pixels.extend((255,255,255,int(255*max(0,1-r)**2)))
    data=bytes(pixels);result=Texture.create(size=(size,size),colorfmt='rgba')
    def reload(target):target.blit_buffer(data,colorfmt='rgba',bufferfmt='ubyte')
    reload(result);result.add_reload_observer(reload)
    result.wrap='repeat' if kind=='paper' else 'clamp_to_edge'
    return result


class Candle(Widget):
    """Detailed wax/brass artwork, illuminated by a continuously moving fire."""
    def __init__(self,**kwargs):
        super().__init__(**kwargs)
        with self.canvas:
            self.halo_color=Color(1,.65,.19,.65)
            self.halo=Rectangle(texture=texture('light'))
            Color(1,1,1,1);self.body=Rectangle(source=CANDLE_ART)
        self.flame=LivingFlame(size_hint=(None,None))
        self.add_widget(self.flame)
        self.bind(pos=self.layout,size=self.layout)
        self.layout()

    def layout(self,*_):
        x,y=self.pos;w,h=self.size
        body_h=min(h*.78,w*.98*1.5);body_w=body_h*2/3
        self.body.pos=(x+(w-body_w)/2,y+h*.03);self.body.size=(body_w,body_h)
        self.flame.size=(w*.64,h*.25)
        self.flame.pos=(self.center_x-self.flame.width/2,y+h*.03+body_h*.862)
        self.halo.size=(w*3.2,h*1.05)
        self.halo.pos=(self.center_x-self.halo.size[0]/2,self.flame.center_y-self.halo.size[1]/2)
        self.animate(0)

    @staticmethod
    def flame_mesh(mesh,x,y,w,h,bend):
        vertices=[x,y+h*.40,0,0]
        # A rounded drop with a leaning tip, no random jumps between frames.
        for i in range(33):
            angle=2*math.pi*i/32
            v=(1+math.sin(angle))/2
            px=x+math.cos(angle)*w*(1-.72*v)+bend*v*v
            py=y+v*h
            vertices.extend((px,py,0,0))
        mesh.vertices=vertices;mesh.indices=list(range(34))

    def animate(self,t):
        self.flame.animate(t)
        intensity=.82+.10*math.sin(t*3.1)+.06*math.sin(t*8.3)
        self.halo_color.a=.62*intensity
        return intensity


class ManuscriptPage(FloatLayout):
    def __init__(self,owner,story,**kwargs):
        super().__init__(**kwargs)
        self.owner=owner;self._event=None;self.age=0;self._focus_bound=False
        self.add_widget(Image(source='files/menu/lor.jpg',fit_mode='cover'))
        shade=Widget()
        with shade.canvas:
            Color(.025,.012,.005,.50);dark=Rectangle()
        shade.bind(pos=lambda w,_:setattr(dark,'pos',w.pos),size=lambda w,_:setattr(dark,'size',w.size))
        self.add_widget(shade)
        self.sheet=FloatLayout(size_hint=(None,None))
        self.sheet._strategy_fixed_layout=True
        with self.sheet.canvas.before:
            Color(.02,.009,.003,.65);self.paper_shadow=RoundedRectangle(radius=[dp(6)])
            Color(1,1,1,1);self.paper=Rectangle(texture=texture('paper'))
            Color(.43,.27,.10,.44);self.edge=Line(width=dp(1.2))
            Color(.45,.28,.12,.2);self.inner_edge=Line(width=dp(.8))
            self.light_color=Color(1,.73,.30,.16);self.light=Rectangle(texture=texture('light'))
        self.add_widget(self.sheet)
        self.column=BoxLayout(orientation='vertical',padding=dp(28),spacing=dp(14),pos_hint={'x':0,'y':0})
        self.column._strategy_fixed_layout=True
        self.sheet.add_widget(self.column)
        self.kicker=Label(text='ИЗ ЛЕТОПИСЕЙ ПЯТИ КОРОЛЕВСТВ',font_name=FONT,font_size=sp(10),color=(.43,.27,.12,1),size_hint_y=None,height=dp(18))
        self.title=Label(text='История Лэрдона',font_name=FONT,font_size=sp(28),color=INK,bold=False,
                         halign='center',valign='middle',size_hint_y=None,height=dp(46))
        self.column.add_widget(self.kicker);self.column.add_widget(self.title)
        self.scroll=ScrollView(do_scroll_x=False,bar_width=dp(4),bar_color=(.43,.25,.10,.7),bar_inactive_color=(.43,.25,.10,.25))
        story=re.sub(r'\[color=#[A-Fa-f0-9]+\]','[color=#755131]',story)
        self.ink=Label(text=story,markup=True,font_name=FONT,font_size=sp(17),color=INK,
                       halign='left',valign='top',size_hint_y=None,line_height=1.28,padding=(dp(2),dp(8)))
        self.ink.bind(width=self.wrap,texture_size=lambda w,value:setattr(w,'height',value[1]+dp(16)))
        self.scroll.add_widget(self.ink);self.column.add_widget(self.scroll)
        self.footer=BoxLayout(size_hint_y=None,height=dp(48),spacing=dp(8))
        self.back_button=StrategyButton(text='Назад',size_hint_y=None,height=dp(48))
        self.back_button.bind(on_release=owner.go_back)
        self.footer.add_widget(self.back_button);self.column.add_widget(self.footer)
        self.candle=Candle(size_hint=(None,None));self.add_widget(self.candle)
        self.bind(size=self.arrange,pos=self.arrange,parent=self.lifecycle)
        owner.bind(parent=self.lifecycle)
        if owner.is_event_type('on_leave'):owner.bind(on_leave=self.stop,on_enter=self.start)
        self.arrange()

    def wrap(self,*_):self.ink.text_size=(max(dp(20),self.ink.width-dp(8)),None)

    def arrange(self,*_):
        compact=self.width<dp(700) or self.height<dp(450)
        gutter=dp(62 if compact else 140)
        width=max(dp(160),min(dp(980),self.width-gutter-dp(22)))
        height=max(dp(140),self.height-dp(20 if compact else 42))
        self.sheet.size=(width,height)
        self.sheet.pos=(self.center_x-(width+gutter)/2,self.center_y-height/2)
        x,y=self.sheet.pos;w,h=self.sheet.size
        self.paper.pos=(x,y);self.paper.size=(w,h)
        self.paper.tex_coords=(0,0,w/dp(180),0,w/dp(180),h/dp(180),0,h/dp(180))
        self.paper_shadow.pos=(x+dp(5),y-dp(6));self.paper_shadow.size=(w,h)
        self.edge.rectangle=(x,y,w,h)
        self.inner_edge.rectangle=(x+dp(7),y+dp(7),w-dp(14),h-dp(14))
        self.column.padding=dp(14 if compact else 30)
        self.column.spacing=dp(6 if compact else 12)
        self.kicker.height=dp(16 if compact else 20)
        self.kicker.font_size=sp(8 if compact else 10)
        self.title.height=dp(35 if compact else 48);self.title.font_size=sp(20 if compact else 29)
        self.title.text_size=(max(1,w-dp(28)),None)
        self.ink.font_size=sp(16 if compact else 18)
        candle_w=gutter+dp(12)
        self.candle.size=(candle_w,min(h*.65,dp(265),candle_w*1.9))
        self.candle.pos=(self.sheet.right-dp(5),y+dp(35 if compact else 58))
        self.light.pos=(self.sheet.right-w*.65,y+h*.04);self.light.size=(w*.9,h*.95)
        self.wrap()

    def lifecycle(self,*_):
        if self.parent is not None and self.owner.parent is not None:self.start()
        else:self.stop()

    def focus(self,_window,focused):
        if focused:self.start()
        else:self.stop(unbind=False)

    def start(self,*_):
        if self.parent is None or self.owner.parent is None:return
        if not self._focus_bound:
            Window.bind(focus=self.focus);self._focus_bound=True
        if self._event is None:self._event=Clock.schedule_interval(self.update,1/24)

    def stop(self,*_,unbind=True):
        if self._event:self._event.cancel();self._event=None
        if unbind and self._focus_bound:
            Window.unbind(focus=self.focus);self._focus_bound=False

    def update(self,dt):
        self.age+=min(dt,.1)
        self.light_color.a=.14*self.candle.animate(self.age)


def build_manuscript(owner,story):
    page=ManuscriptPage(owner,story);owner.add_widget(page);owner._manuscript=page
    return page
