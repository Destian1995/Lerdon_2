"""An illustrated, responsive allegiance choice within the quest journal."""
from kivy.metrics import sp,dp
from kivy.properties import NumericProperty,StringProperty
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.image import Image
from mirror_layout import QuestCard,FitLabel,compact_frame
from otherworld_themes import image_path
from otherworlds import QUEST_GARRISON_DEFENSE
from strategy_ui import surface,GOLD,MUTED
from utils.helpers import format_number

BLUE=(.46,.79,1,1)
ROSE=(1,.54,.66,1)


class AllegianceChoice(ButtonBehavior,BoxLayout):
    text=StringProperty('')
    maximum=NumericProperty(16)

    def __init__(self,caption,callback,enabled,portrait,accent,**kwargs):
        super().__init__(spacing=5,**kwargs)
        self.text=caption
        surface(self,tuple(.035+c*.075 for c in accent[:3])+(1,),accent)
        compact_frame(self)
        self.art=Image(source=portrait,size_hint_x=None,mipmap=True)
        labels=BoxLayout(orientation='vertical')
        self.name=FitLabel(text=caption.removeprefix('Поддержать: '),color=accent,bold=True,minimum=sp(12))
        self.hint=FitLabel(text='ЗАКЛЮЧИТЬ СОЮЗ',color=MUTED,size_hint_y=None,maximum=10)
        labels.add_widget(self.name);labels.add_widget(self.hint)
        self.add_widget(self.art);self.add_widget(labels)
        self.disabled=not enabled;self.bind(on_release=callback)
        self.bind(size=self.fit,maximum=self.fit,disabled=self.fit,state=self.fit)
        self.fit()

    def fit(self,*_):
        self.padding=min(6,self.height*.09)
        self.art.width=min(48,self.height*.78,self.width*.23)
        self.name.maximum=max(sp(12),min(sp(18),self.height*.34,self.maximum))
        self.hint.height=12 if self.height>=48 else 0
        self.hint.opacity=1 if self.hint.height else 0
        self.opacity=.42 if self.disabled else 1
        self._strategy_frame.outer_color.a=1 if self.state=='down' else .85


class AllegianceCard(QuestCard):
    def __init__(self,title,copy,buttons,accent,faction,stage,compact_copy,**kwargs):
        self.stage=stage;self.full_copy=copy;self.compact_copy=compact_copy
        self.defense_text='ЗАЩИТА ГАРНИЗОНА\n'+format_number(QUEST_GARRISON_DEFENSE).replace('.0 ',' ')
        self.summary=None
        super().__init__(title,copy,buttons,accent,**kwargs)
        if stage==0:
            self.buttons.clear_widgets()
            for i,(caption,callback,enabled) in enumerate(buttons):
                self.buttons.add_widget(AllegianceChoice(caption,callback,enabled,
                    image_path(faction,'cities','city_'+str(4 if i==0 else 7)),BLUE if i==0 else ROSE))
        self.summary=BoxLayout(size_hint_y=None,spacing=5)
        self.defense_tile=surface(BoxLayout(padding=5,spacing=4),(.14,.055,.075,1),ROSE)
        compact_frame(self.defense_tile)
        self.defense_icon=Image(source='files/pict/hire/shield.png',size_hint_x=None,mipmap=True)
        self.defense_copy=FitLabel(text=self.defense_text,color=ROSE,bold=True,maximum=sp(20))
        self.defense_tile.add_widget(self.defense_icon);self.defense_tile.add_widget(self.defense_copy)
        self.reward_tile=surface(BoxLayout(padding=5),(.13,.105,.05,1),GOLD)
        compact_frame(self.reward_tile)
        self.reward_copy=FitLabel(text='НАГРАДА\nАртефакт · 25 ходов',color=GOLD,bold=True,maximum=sp(17))
        self.reward_tile.add_widget(self.reward_copy)
        self.summary.add_widget(self.defense_tile);self.summary.add_widget(self.reward_tile)
        self.content.add_widget(self.summary,index=1 if buttons else 0)
        self.bind(size=self.fit)
        self.fit()

    def button_height(self):
        return dp(64) if self.stage==0 else super().button_height()

    def fit(self,*_):
        super().fit()
        if self.summary is None:return
        self.summary.height=dp(68)
        self.summary.opacity=1
        for child in (self.defense_copy,self.reward_copy):
            child.text=self.defense_text if child is self.defense_copy else 'НАГРАДА\nАртефакт · 25 ходов'
        self.defense_icon.width=min(38,self.summary.height*.60)
        if self.stage==0:
            for button in self.buttons.children:button.maximum=min(sp(18),max(10,self.buttons.width/24))
