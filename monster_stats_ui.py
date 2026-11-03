"""Large, colour-coded monster location stats, fitted to available pixels."""
from kivy.clock import Clock
from kivy.metrics import dp,sp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.image import Image
from kivy.uix.label import Label

from strategy_ui import surface


class StatTile(BoxLayout):
    def __init__(self,caption,icon,accent,background,**kwargs):
        super().__init__(spacing=dp(10),padding=dp(10),**kwargs)
        surface(self,background,accent)
        self.icon=Image(source=icon,size_hint=(None,None),pos_hint={'center_y':.5},mipmap=True)
        self.add_widget(self.icon)
        labels=BoxLayout(orientation='vertical',spacing=dp(2))
        self.caption=Label(text=caption,markup=True,bold=True,color=accent,halign='left',valign='middle',size_hint_y=None)
        self.value=Label(markup=True,bold=True,color=accent,halign='left',valign='middle')
        labels.add_widget(self.caption);labels.add_widget(self.value);self.add_widget(labels)
        self._fit_event=Clock.create_trigger(self.fit,0)
        self.bind(size=self._fit_event)
        self.value.bind(text=self._fit_event,size=self._fit_event)
        self.caption.bind(size=self._fit_event)

    def fit(self,*_):
        inset=min(dp(10),self.height*.12)
        self.padding=inset
        self.icon.size=(min(dp(58),self.height*.65),)*2
        self.caption.font_size=max(8,min(sp(14),self.height*.16))
        self.caption.height=self.caption.font_size*1.4
        self.caption.text_size=self.caption.size
        lines=self.value.text.count('\n')+1
        font=max(9,min(sp(34),self.value.height/(lines*1.22),self.height*.43))
        for _ in range(12):
            self.value.font_size=font
            self.value.text_size=(max(1,self.value.width),None)
            self.value.texture_update()
            if self.value.texture_size[1]<=self.value.height+1 or font<=9:
                break
            font=max(9,font*.9)
        self.value.text_size=self.value.size


class MonsterStatsPanel(BoxLayout):
    def __init__(self,**kwargs):
        super().__init__(orientation='vertical',spacing=dp(8),**kwargs)
        self._responsive_keep_geometry=True
        self.defense=StatTile('ЗАЩИТА','files/pict/hire/shield.png',(.45,.82,1,1),(.045,.10,.17,1))
        self.reward=StatTile('НАГРАДА','files/status/resource_box/coin.png',(1,.80,.36,1),(.15,.105,.045,1))
        self.reward.size_hint_y=1.4
        self.training=StatTile('ВЕТЕРАНСТВО','files/pict/hire/class.png',(.42,.92,.64,1),(.045,.135,.095,1))
        self.tiles=(self.defense,self.reward,self.training)
        for tile in self.tiles:self.add_widget(tile)
        self.bind(height=lambda w,h:setattr(w,'spacing',min(dp(10),max(4,h*.025))))

    def set_prize(self,prize):
        from utils.helpers import format_number
        number=lambda n:format_number(n).replace('.0 ', ' ')
        self.defense.value.text=number(prize['defense'])
        if prize['resources']:
            self.reward.icon.source='files/status/resource_box/coin.png'
            self.reward.value.text=(f'[color=#FFD36A]+{number(prize["resources"])} крон[/color]\n'
                                    f'[color=#74DEFF]+{number(prize["resources"])} кристаллов[/color]')
            self.reward.caption.text='НАГРАДА  ·  +1 ОПЫТА'
        else:
            self.reward.icon.source='files/pict/hire/class.png'
            self.reward.value.text='+1 опыта войскам'
            self.reward.caption.text='НАГРАДА'
        if prize['legendary']:
            self.reward.caption.text+='  ·  [color=#DE92FF]ДАР +550%[/color]'
        self.training.value.text=f'{prize["duration"]} х.'
