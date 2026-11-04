"""The shared faction battle arena, with a monster reward report."""
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.image import Image
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView

from battle_ui import BattleViewer,exact_count,GREEN,RED
from monster_sites import art_path,monster_name
from strategy_ui import surface,text_label,StrategyButton,INK,SURFACE,GOLD,MUTED
from window_theme import prepare_custom_popup,center_after_resize


def strike_frames(result,count,steps=6):
    """Present the resolved single strike in phases; never roll new combat."""
    damage=min(result['attack'],result['defense'])
    return [dict(round=i,atk_max=count,def_max=result['defense'],atk_total=count,
                 def_total=max(0,result['defense']-int(damage*i/steps))) for i in range(1,steps+1)]


def reward_rows(result):
    if not result['won']:
        return [('Награды','0','files/pict/hire/class.png')]
    return [('Кроны',('+' if result['resources'] else '')+exact_count(result['resources']),
             'files/status/resource_box/coin.png'),
            ('Кристаллы',('+' if result['resources'] else '')+exact_count(result['resources']),
             'files/status/resource_box/crystal.png'),
            ('Опыт участвовавших войск',f'+{result.get("experience",1)}','files/pict/hire/class.png'),
            ('Усиление войск',f'{result["duration"]} х.'+(
                f' · всего {result["training_remaining"]} х.' if result.get('training_remaining',0)>result['duration'] else ''),
             'files/pict/hire/strong.png')]+(
            [('Дар бездны','1 улучшение · +550%','files/pict/hire/sword.png')] if result.get('new_relic') else [])


class MonsterRewardReport(Popup):
    def __init__(self,result,done,**kwargs):
        self.result,self.done=result,done
        self.callback_sent=False
        self.rows=reward_rows(result)
        self.reward_cards=[]
        root=surface(BoxLayout(orientation='vertical',padding=dp(12),spacing=dp(10)),INK)
        root._strategy_fixed_layout=True
        header=BoxLayout(size_hint_y=None,height=dp(56),spacing=dp(8))
        heading=BoxLayout(orientation='vertical')
        heading.add_widget(text_label('ИТОГИ ОХОТЫ  /  '+result['name'],10,MUTED))
        heading.add_widget(text_label('ПОЛУЧЕННЫЕ НАГРАДЫ' if result['won'] else 'ОТСТУПЛЕНИЕ',22,
                                      GOLD if result['won'] else RED,bold=True))
        header.add_widget(heading)
        close=StrategyButton(text='×',size_hint_x=None,width=dp(48))
        close._strategy_close=True;close.bind(on_release=self.dismiss)
        header.add_widget(close);root.add_widget(header)
        scroll=ScrollView(do_scroll_x=False,bar_width=dp(3))
        cards=BoxLayout(orientation='vertical',size_hint_y=None,spacing=dp(8))
        cards.bind(minimum_height=cards.setter('height'))
        for caption,value,icon in self.rows:
            card=surface(BoxLayout(size_hint_y=None,height=dp(68),padding=dp(8),spacing=dp(12)),SURFACE)
            card.add_widget(Image(source=icon,size_hint_x=None,width=dp(42),mipmap=True))
            card.add_widget(text_label(caption,15))
            amount=text_label(value,19,GREEN if result['won'] else MUTED,bold=True,size_hint_x=.65)
            amount.halign='right';card.add_widget(amount)
            cards.add_widget(card);self.reward_cards.append(card)
        scroll.add_widget(cards);root.add_widget(scroll)
        button=StrategyButton(text='Вернуться на карту',size_hint_y=None,height=dp(48),primary=True)
        button.bind(on_release=self.dismiss);root.add_widget(button)
        self.return_button=button
        super().__init__(title='',content=root,size_hint=(None,None),auto_dismiss=False,**kwargs)
        prepare_custom_popup(self)
        self.bind(on_open=self.opened,on_dismiss=self.closed)
        self.fit()

    def opened(self,*_):
        Window.bind(on_resize=self.fit);self.fit()

    def fit(self,*_):
        self.size=(min(dp(940),Window.width-dp(16)),min(dp(720),Window.height-dp(16)))
        center_after_resize(self)

    def closed(self,*_):
        Window.unbind(on_resize=self.fit)
        if not self.callback_sent:
            self.callback_sent=True;self.done()


class MonsterClashPopup(BattleViewer):
    def __init__(self,widget,site,result,done,**kwargs):
        self.result,self.done=result,done
        self.reward_report=None
        row=widget.conn.execute('SELECT camp,source,faction FROM monster_expeditions WHERE site_id=?',
                                (site['id'],)).fetchone()
        camp,source,faction=row
        count=widget.conn.execute('SELECT COALESCE(SUM(unit_count),0) FROM garrisons WHERE city_name=?',(camp,)).fetchone()[0]
        image_column="COALESCE(NULLIF(g.unit_image,''),u.image_path,'')" if 'image_path' in {
            r[1] for r in widget.conn.execute('PRAGMA table_info(units)')} else 'g.unit_image'
        hero=widget.conn.execute(f'''SELECT {image_column} FROM garrisons g JOIN units u ON u.unit_name=g.unit_name
            WHERE g.city_name=? AND CAST(u.unit_class AS INTEGER)>=2 AND g.unit_count>0
            ORDER BY CAST(u.unit_class AS INTEGER) DESC LIMIT 1''',(camp,)).fetchone()
        self.army_count=count
        name=monster_name(site)
        super().__init__(strike_frames(result,count),faction,name,'attacker' if result['won'] else 'defender',
                         faction,source,name,callback=self.open_rewards,
                         attacker_image=hero[0] if hero and hero[0] else None,
                         defender_image=str(art_path(site['tier'],site.get('variant',1))),**kwargs)
        self.finish_button.text='Награды'
        self.event_label.text='Герой атакует монстра…'
        self._counts(result['defense'])

    def _counts(self,defense):
        self.attacker_panel.count.text='Войска: '+exact_count(self.army_count)
        self.defender_panel.count.text='Защита: '+exact_count(defense)

    def show_frame(self,index):
        super().show_frame(index)
        record=self.frames[index]
        self._counts(record['def_total'])
        self.round_label.text=f'Удар по защите · {index+1} / {len(self.frames)}'
        self.event_label.text='Урон защите: '+exact_count(record['def_loss'])

    def reveal_result(self):
        super().reveal_result()
        self.result_detail.text='Монстр повержен' if self.result['won'] else 'Отряд отступает без наград'
        self.finish_button.text='Награды'
        self.event_label.text='Полученные бонусы — в окне наград.'

    def open_rewards(self):
        if self.reward_report is None:
            self.reward_report=MonsterRewardReport(self.result,self.done)
            self.reward_report.open()
