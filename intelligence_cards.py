"""Responsive reconnaissance selection using the game's faction heraldry."""
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.image import Image
from strategy_ui import surface,StrategyButton,text_label,GOLD,MUTED

EMBLEMS={'Север':'people','Эльфы':'elfs','Вампиры':'vampires','Адепты':'adepts',
         'Элины':'poly','Нежить':'skull','Мятежники':'keig','Нейтрал':'default'}
GREEN=(.43,.88,.60,1)


def money(value):return f'{int(value):,}'.replace(',',' ')


class ScoutCards(GridLayout):
    def __init__(self,**kwargs):
        super().__init__(cols=1,spacing=dp(8),size_hint_y=None,**kwargs)
        self.bind(minimum_height=self.setter('height'),width=self.fit)

    def fit(self,*_):self.cols=2 if self.width>=dp(440) else 1


def scout_card(target,price,left,selected,callback):
    card=surface(BoxLayout(orientation='vertical',padding=dp(8),spacing=dp(5),
        size_hint_y=None,height=dp(126)),(.075,.095,.12,1),GREEN if selected else GOLD)
    row=BoxLayout(spacing=dp(8))
    row.add_widget(Image(source='files/status/army_in_city/standards/'+EMBLEMS.get(target,'default')+'.png',
                         fit_mode='contain',size_hint_x=None,width=dp(58)))
    info=BoxLayout(orientation='vertical',spacing=dp(2))
    info.add_widget(text_label(target,16,GREEN if selected else GOLD,bold=True))
    info.add_widget(text_label(money(price)+' крон',13,GOLD))
    info.add_widget(text_label(f'Сведения: ещё {left} х.' if left else 'Нет свежих сведений',11,GREEN if left else MUTED))
    row.add_widget(info);card.add_widget(row)
    button=StrategyButton(text='Выбрано' if selected else 'Выбрать фракцию',height=dp(44),size_hint_y=None,
                          accent=GREEN if selected else GOLD)
    button.bind(on_release=lambda *_:callback(target));card.add_widget(button)
    return card,button
