"""Author portrait and touch-friendly community links, independent of game data."""
from kivy.graphics import Color, Rectangle
from kivy.metrics import dp, sp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.widget import Widget
from mirror_readable_ui import ReadableText
from strategy_ui import StrategyButton, surface, INK, GOLD, TEXT, MUTED
from ui_motion import enter

PORTRAIT = 'files/menu/author/developer-vladislav.png'
LINKS = (
    ('VK', 'Автор ВКонтакте', 'Связаться с разработчиком',
     'https://vk.com/destianfarbius', (.40,.66,.98,1)),
    ('TG', 'Сообщество Telegram', 'Обсуждения и новости Лэрдона',
     'https://t.me/+scOGK6ph6r03YmU6', (.32,.81,.87,1)),
)


class CommunityButton(StrategyButton):
    def __init__(self, symbol, title, subtitle, accent, **kwargs):
        super().__init__(text='', accent=accent, size_hint_y=None, height=dp(76), **kwargs)
        self._strategy_fixed_layout = True
        row = BoxLayout(padding=(dp(12),dp(8)), spacing=dp(12))
        icon = surface(Label(text=symbol, color=accent, bold=True, font_size=sp(19),
                             size_hint_x=None, width=dp(48)), (.07,.14,.20,1), accent)
        row.add_widget(icon)
        copy = BoxLayout(orientation='vertical', spacing=dp(2))
        self.title_label = Label(text=title, color=TEXT, bold=True, font_size=sp(17),
                                 halign='left', valign='middle')
        self.detail_label = Label(text=subtitle, color=MUTED, font_size=sp(12),
                                  halign='left', valign='middle')
        for label in (self.title_label, self.detail_label):
            label.bind(size=lambda w,_:setattr(w,'text_size',w.size))
            copy.add_widget(label)
        row.add_widget(copy)
        row.add_widget(Label(text='›', font_size=sp(30), color=accent, size_hint_x=None, width=dp(20)))
        self.add_widget(row)
        self.bind(pos=lambda *_:setattr(row,'pos',self.pos), size=lambda *_:setattr(row,'size',self.size))
        row.pos,row.size=self.pos,self.size


class AuthorPage(FloatLayout):
    def __init__(self, owner, **kwargs):
        super().__init__(**kwargs)
        self.art = Image(source='files/menu/choise/people.jpg', fit_mode='cover')
        self.add_widget(self.art)
        shade=FloatLayout()
        with shade.canvas:
            Color(*INK[:3],.78)
            self._shade=Rectangle()
        shade.bind(pos=lambda w,_:setattr(self._shade,'pos',w.pos),size=lambda w,_:setattr(self._shade,'size',w.size))
        self.add_widget(shade)
        self.panel=surface(BoxLayout(orientation='vertical', size_hint=(None,None),
                                    padding=dp(12), spacing=dp(10)),(*INK[:3],.97))
        self.panel._strategy_fixed_layout=True
        self.add_widget(self.panel)
        self.header=BoxLayout(orientation='vertical',size_hint_y=None,height=dp(58))
        self.header.add_widget(Label(text='LERDON / СОЗДАТЕЛЬ МИРА',font_size=sp(10),color=GOLD))
        self.header.add_widget(Label(text='Об авторе',font_size=sp(25),bold=True,color=TEXT))
        self.panel.add_widget(self.header)
        self.scroll=ScrollView(do_scroll_x=False,bar_width=dp(3),bar_color=GOLD)
        self.body=GridLayout(cols=2,size_hint_y=None,spacing=dp(18))
        self.body.bind(minimum_height=self.body.setter('height'))
        self.scroll.add_widget(self.body);self.panel.add_widget(self.scroll)
        self.portrait_card=surface(BoxLayout(orientation='vertical',padding=dp(4),spacing=dp(4),
                                            size_hint=(None,None)),(.035,.05,.065,1))
        self.portrait=Image(source=PORTRAIT,fit_mode='contain',mipmap=True)
        self.portrait_card.add_widget(self.portrait)
        self.portrait_card.add_widget(Label(text='СОЗДАТЕЛЬ ЛЭРДОНА',font_size=sp(10),color=GOLD,
                                             size_hint_y=None,height=dp(22)))
        self.body.add_widget(self.portrait_card)
        self.info=BoxLayout(orientation='vertical',size_hint_y=None,spacing=dp(10),padding=(dp(2),dp(8)))
        self.info.bind(minimum_height=self.info.setter('height'))
        self.name_label=ReadableText('Владислав',size=27,bold=True,color=TEXT)
        self.info.add_widget(self.name_label)
        self.info.add_widget(ReadableText('Автор и разработчик «Легенд Лэрдона»',size=14,color=GOLD))
        self.greeting=ReadableText('Добро пожаловать в мой мир! Желаю вам интересных открытий, '
            'неожиданных историй и достойных побед.',size=15,color=TEXT)
        self.info.add_widget(self.greeting)
        self.social_heading=ReadableText('Остаёмся на связи',size=13,color=MUTED)
        self.info.add_widget(self.social_heading)
        self.link_buttons=[]
        for symbol,title,subtitle,address,accent in LINKS:
            button=CommunityButton(symbol,title,subtitle,accent)
            button.bind(on_release=lambda widget,address=address:owner.open_link(widget,address))
            self.link_buttons.append(button);self.info.add_widget(button)
        self.info.add_widget(ReadableText('Иконки и изображения: ChatGPT',size=11,color=MUTED))
        self.info_holder=BoxLayout(orientation='vertical')
        self.top_space=Widget()
        self.bottom_space=Widget()
        self.info_holder.add_widget(self.top_space)
        self.info_holder.add_widget(self.info)
        self.info_holder.add_widget(self.bottom_space)
        self.info.bind(height=self.fit_info_holder)
        self.body.add_widget(self.info_holder)
        self.back_button=StrategyButton(text='В меню',size_hint_y=None,height=dp(48))
        self.back_button.bind(on_release=owner.go_back)
        self.panel.add_widget(self.back_button)
        self.bind(size=self.arrange,pos=self.arrange)
        self.arrange()
        enter(self.panel)

    def arrange(self,*_):
        self.panel.size=(max(1,min(dp(1100),self.width-dp(20))),max(1,self.height-dp(20)))
        self.panel.center=self.center
        wide=self.panel.width>=dp(560)
        compact=wide and self.height<dp(480)
        self.panel.padding=dp(8 if compact else 12)
        self.panel.spacing=dp(6 if compact else 10)
        self.header.height=dp(42 if compact else 58)
        self.info.spacing=dp(4 if compact else 10)
        self.info.padding=(dp(2),dp(0 if compact else 8))
        for widget in (self.greeting,self.social_heading):
            if compact and widget.parent:self.info.remove_widget(widget)
        if not compact and not self.greeting.parent:
            # Restore the greeting above the community controls after rotation.
            index=self.info.children.index(self.link_buttons[0])+1
            self.info.add_widget(self.social_heading,index=index)
            self.info.add_widget(self.greeting,index=index+1)
        for button in self.link_buttons:button.height=dp(64 if compact else 76)
        self.body.cols=2 if wide else 1
        self.body.spacing=dp(18 if wide else 10)
        self.info_holder.size_hint_y=1 if wide else None
        for spacer in (self.top_space,self.bottom_space):
            spacer.size_hint_y=1 if wide else None
            if not wide:spacer.height=0
        if not wide:self.info_holder.height=self.info.height
        if wide:
            height=max(dp(180),self.panel.height-self.header.height-dp(48)-2*self.panel.padding[1]-2*self.panel.spacing)
            self.portrait_card.size=(min(self.panel.width*.37,height*.69),height)
        else:
            self.portrait_card.size=(max(1,self.panel.width-dp(24)),dp(200))
        self.scroll.scroll_y=1

    def fit_info_holder(self,*_):
        if self.info_holder.size_hint_y is None:self.info_holder.height=self.info.height


def build_author(owner):
    page=AuthorPage(owner)
    owner.add_widget(page)
    owner._front_page=page
    return page
