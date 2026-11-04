"""Quest master/detail layout with readable text and independent scroll areas."""
import math
from kivy.clock import Clock
from kivy.core.text import Label as CoreLabel
from kivy.metrics import dp,sp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from frontend_ui import NaturalList
from mirror_readable_ui import ReadableText
from strategy_ui import surface,INK,SURFACE,GOLD,MUTED
from otherworld_ui import _button
from mirror_layout import compact_frame


class QuestActions(GridLayout):
    def __init__(self,choices,accent,**kwargs):
        super().__init__(cols=1,size_hint_y=None,spacing=dp(6),**kwargs)
        for caption,callback,enabled in choices:
            button=_button(caption,callback,accent=accent)
            button.disabled=not enabled
            self.add_widget(button)
        self._fit=Clock.create_trigger(self.fit,-1)
        for button in self.children:button.bind(font_size=self._fit,text=self._fit)
        self.bind(width=self._fit);self._fit()

    def fit(self,*_):
        self.cols=2 if self.width>=dp(580) else 1
        width=(self.width-dp(6)*(self.cols-1))/self.cols
        row=dp(44)
        for button in self.children:
            text=CoreLabel(text=button.text,font_size=sp(15),bold=True,
                           text_size=(max(1,width-dp(16)),None))
            text.refresh();row=max(row,text.texture.height+dp(12))
        self.row_default_height=row;self.row_force_default=True
        rows=math.ceil(len(self.children)/self.cols)
        self.height=rows*row+max(0,rows-1)*dp(6)


class QuestDetail(BoxLayout):
    def __init__(self,title,copy,buttons,accent,details='',**kwargs):
        super().__init__(orientation='vertical',spacing=dp(6),**kwargs)
        self.title=title
        header=surface(NaturalList(padding=dp(8),spacing=dp(2)),SURFACE,accent)
        compact_frame(header)
        self.heading=ReadableText(title,size=17,bold=True,color=accent)
        self.defense_copy=ReadableText(details,size=14,color=GOLD)
        header.add_widget(self.heading)
        if details:header.add_widget(self.defense_copy)
        self.add_widget(header)
        self.scroll=ScrollView(do_scroll_x=False,bar_width=dp(4))
        self.content=NaturalList(padding=dp(8),spacing=dp(10))
        self.scroll.add_widget(self.content)
        surface(self.scroll,INK,accent);compact_frame(self.scroll)
        self.sections=[]
        for line in copy.split('\n'):
            if not line.strip():continue
            color=(1,.48,.43,1) if line.startswith('Риск:') else GOLD if line.startswith(('Награда','За каждое','За оба')) else (.4,.88,.65,1) if line.startswith(('Опросите','Изучите','Предъявите','Соберите','Посольство','Ваш союзник','Сразитесь')) else None
            kwargs={'color':color} if color else {}
            label=ReadableText(line,size=15,**kwargs)
            self.sections.append(label);self.content.add_widget(label)
        self.copy=self.sections[0] if self.sections else self.heading
        self.buttons=QuestActions(buttons,accent)
        if buttons:self.content.add_widget(self.buttons)
        self.add_widget(self.scroll)


class QuestSplitView(BoxLayout):
    def __init__(self,back,accent,**kwargs):
        super().__init__(spacing=dp(8),**kwargs)
        self.accent=accent;self.pages=[];self.page_index=0;self.selectors=[]
        self.back=back
        self.sidebar=BoxLayout(orientation='vertical',spacing=dp(6))
        self.sidebar_scroll=ScrollView(do_scroll_x=False,bar_width=dp(3))
        self.list=NaturalList(spacing=dp(8))
        self.sidebar_scroll.add_widget(self.list);self.sidebar.add_widget(self.sidebar_scroll)
        back.height=dp(44);back.size_hint_y=None
        self.sidebar.add_widget(back)
        self.detail_host=BoxLayout()
        self.add_widget(self.sidebar);self.add_widget(self.detail_host)
        self.bind(size=self.fit);self.fit()

    def fit(self,*_):
        portrait=self.width<dp(500) and self.height>self.width
        self.orientation='vertical' if portrait else 'horizontal'
        self.sidebar.size_hint=(1,None) if portrait else (.34,1)
        if portrait:self.sidebar.height=dp(164)
        self.detail_host.size_hint=(1,1) if portrait else (.66,1)
        self.back.height=dp(44)
        for button in self.selectors:button.height=dp(48)

    def clear_cards(self):
        self.pages.clear();self.selectors.clear();self.list.clear_widgets();self.detail_host.clear_widgets()

    def add_card(self,card):
        index=len(self.pages);self.pages.append(card)
        button=_button(card.title,lambda *_,i=index:self.select(i),accent=self.accent,
                       size_hint_y=None,height=dp(48),font_size=sp(14))
        self.selectors.append(button);self.list.add_widget(button)
        if len(self.pages)==1:self.select(0)

    def select(self,index):
        if not self.pages:return
        self.page_index=max(0,min(index,len(self.pages)-1))
        self.detail_host.clear_widgets();self.detail_host.add_widget(self.pages[self.page_index])
        for i,button in enumerate(self.selectors):button.set_selected(i==self.page_index)
