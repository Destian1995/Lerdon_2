"""Mirror Realm typography: fixed readable sp text, content grows by scrolling."""
from kivy.metrics import dp,sp,Metrics
from kivy.uix.label import Label
from strategy_ui import StrategyButton,TEXT
from mirror_layout import compact_frame
from utils.ui_text import bind_plain_text


def compact_number(value):
    from utils.helpers import format_number
    return format_number(value).replace(' тыс.','т').replace(' млн.','м').replace(' млрд.','млрд')


class ReadableText(Label):
    def __init__(self,text='',size=15,**kwargs):
        kwargs.setdefault('color',TEXT)
        kwargs.setdefault('halign','left');kwargs.setdefault('valign','middle')
        kwargs.setdefault('size_hint_y',None)
        kwargs.setdefault('height',dp(20))
        self.logical_font_size=size
        super().__init__(text=text,font_size=sp(size),**kwargs)
        self._strategy_fixed_font=True
        bind_plain_text(self)
        self.bind(width=self.wrap,texture_size=self.measure)
        Metrics.bind(density=self.update_font,fontscale=self.update_font)
        self.wrap()

    def update_font(self,*_):self.font_size=sp(self.logical_font_size)
    def wrap(self,*_):self.text_size=(max(1,self.width),None)
    def measure(self,*_):self.height=max(dp(20),self.texture_size[1]+dp(2)) if self.text.strip() else 0


class ReadableButton(StrategyButton):
    def __init__(self,**kwargs):
        kwargs.setdefault('font_size',sp(24 if kwargs.get('text')=='×' else 15))
        self.logical_font_size=kwargs['font_size']/sp(1)
        super().__init__(**kwargs)
        self._strategy_fixed_font=True
        Metrics.bind(density=self.update_font,fontscale=self.update_font)
        compact_frame(self)

    def update_font(self,*_):self.font_size=sp(self.logical_font_size)
