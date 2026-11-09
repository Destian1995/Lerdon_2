"""A touch-friendly two-page ability book; combat rules stay in the model."""
from pathlib import Path

from kivy.graphics import Color, Line, Rectangle, RoundedRectangle
from kivy.metrics import dp
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.image import Image
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView

from strategy_ui import StrategyButton, text_label, GOLD
from tactical_abilities import ABILITIES
from utils.helpers import format_number
from window_theme import prepare_custom_popup

ROOT=Path(__file__).resolve().parent
INK=(.20,.14,.09,1)
FADED=(.40,.32,.23,1)
READY=(.16,.37,.22,1)
AMBER=(.60,.25,.09,1)
ICONS={
    'paladin_shield':'bronya_svutogo.png','auto_burst':'mushket_markova.png',
    'blood_vortex':'posoh_diadara.png','twin_arrow':'luk_luny.png',
    'priest_shield':'amulet_vechnoy_vesny.png','vampire_raise':'koltso_dushi.png',
    'snipe':'vintovka_greynjger.png','burst':'mushket_markova.png','grenade':'artefakt_voiny.png',
    'blizzard':'amulet_zimy.png','freeze':'amulet_hlad.png','flight':'sapogi_strannika.png',
    'flame':'koltso_plameni.png','fire_shield':'bronya_aresa.png','heal':'amulet_vechnoy_vesny.png',
    'sword_throw':'mech_paladina.png','inspire':'korona_solnca.png','whirlwind':'mech_paladina.png','drain':'posoh_diadara.png',
    'vampirism':'koltso_dushi.png','dominate':'shlem_haosa.png','blood':'klinok_zabveniya.png'}
TARGETS={'enemy':'Вражеский отряд','ally':'Союзный отряд','soldier':'Союзные солдаты',
         'cell':'Клетка поля','flight':'Свободная клетка','direction':'Направление от героя',
         'self':'Вокруг героя','army':'Все союзные солдаты'}


def page_text(text='',size=13,color=INK,**kwargs):
    label=text_label(text,size,color,size_hint_y=None,**kwargs)
    label._strategy_no_theme=True
    label.unbind(size=label._strategy_text_sizer)
    label.bind(width=lambda obj,value:setattr(obj,'text_size',(max(1,value),None)))
    label.bind(texture_size=lambda obj,value:setattr(obj,'height',value[1]+dp(6)))
    label.text_size=(max(1,label.width),None)
    return label


class BookPages(BoxLayout):
    def __init__(self,**kwargs):
        super().__init__(padding=(dp(15),dp(6)),spacing=dp(28),**kwargs)
        self._strategy_no_theme=True
        self.bind(pos=self.draw,size=self.draw)
        self.draw()

    def draw(self,*_):
        x,y=self.pos;w,h=self.size;middle=x+w/2
        self.canvas.before.clear()
        with self.canvas.before:
            Color(.18,.10,.055,1)
            RoundedRectangle(pos=(x,y),size=(w,h),radius=[dp(9)])
            for left in (x+dp(4),middle+dp(3)):
                Color(.89,.81,.63,1)
                RoundedRectangle(pos=(left,y+dp(4)),size=(max(1,w/2-dp(7)),max(1,h-dp(8))),radius=[dp(4)])
                Color(.98,.91,.75,.58)
                Rectangle(pos=(left+dp(3),y+dp(8)),size=(max(1,w/2-dp(14)),max(1,h-dp(16))))
                Color(.52,.36,.17,.42)
                Line(points=(left+dp(8),y+dp(9),left+w/2-dp(15),y+dp(9)),width=.7)
                Line(points=(left+dp(8),y+h-dp(9),left+w/2-dp(15),y+h-dp(9)),width=.7)
            for step in range(7):
                Color(.28,.16,.075,.20*(1-step/7))
                Rectangle(pos=(middle-dp(2+step*1.3),y+dp(5)),size=(dp(4+step*2.6),max(1,h-dp(10))))


class SpellTile(ButtonBehavior,BoxLayout):
    def __init__(self,book,key,**kwargs):
        super().__init__(size_hint_y=None,height=dp(72),padding=dp(7),spacing=dp(7),**kwargs)
        self._strategy_no_theme=True
        self.book,self.key=book,key
        self.icon=Image(source=str(ROOT/'files/pict/artifacts'/ICONS[key]),
                        size_hint_x=None,width=dp(42),mipmap=True)
        self.add_widget(self.icon)
        words=BoxLayout(orientation='vertical')
        self.name=text_label(ABILITIES[key].name,13,INK,bold=True)
        self.name._strategy_no_theme=True
        left=book.cooldown(key)
        self.status=text_label('Готово' if not left else f'Ещё {left} р.',11,READY if not left else AMBER)
        self.status._strategy_no_theme=True
        self.status.size_hint_y=None;self.status.height=dp(18)
        words.add_widget(self.name);words.add_widget(self.status);self.add_widget(words)
        self.bind(pos=self.draw,size=self.draw,on_release=lambda *_:book.select_skill(key))
        self.draw()

    def draw(self,*_):
        selected=getattr(self.book,'selected',None)==self.key
        self.canvas.before.clear()
        with self.canvas.before:
            Color(*((.72,.79,.58,.72) if selected else (.96,.90,.77,.45)))
            RoundedRectangle(pos=self.pos,size=self.size,radius=[dp(5)])
            Color(*((.25,.44,.25,1) if selected else (.59,.44,.26,.40)))
            Line(rounded_rectangle=(*self.pos,*self.size,dp(5)),width=dp(1.2 if selected else .7))


class AbilityBook(Popup):
    def __init__(self,owner,**kwargs):
        self.owner=owner;self.actor=owner.battle.active;self.selected=None
        super().__init__(title=self.actor.name+' · Способности',size_hint=(.98,.97),
                         auto_dismiss=False,**kwargs)
        prepare_custom_popup(self)
        root=BoxLayout(orientation='vertical',padding=dp(6),spacing=dp(4))
        root._strategy_fixed_layout=True
        root._strategy_no_theme=True
        with root.canvas.before:
            Color(.085,.052,.035,1)
            cover=RoundedRectangle(pos=root.pos,size=root.size,radius=[dp(9)])
        root.bind(pos=lambda *_:setattr(cover,'pos',root.pos),size=lambda *_:setattr(cover,'size',root.size))
        header=BoxLayout(size_hint_y=None,height=dp(44),spacing=dp(8))
        title=BoxLayout(orientation='vertical')
        title.add_widget(text_label('Книга способностей',17,GOLD,bold=True))
        title.add_widget(text_label(self.actor.name+' · раунд '+str(owner.battle.round),12,(.76,.68,.54,1)))
        header.add_widget(title)
        close=StrategyButton(text='×',size_hint_x=None,width=dp(44))
        close.bind(on_release=self.dismiss);header.add_widget(close);root.add_widget(header)
        self.pages=BookPages();root.add_widget(self.pages)
        left=BoxLayout(orientation='vertical',spacing=dp(6))
        left.add_widget(page_text('Умения героя',14,bold=True))
        self.list_scroll=ScrollView(do_scroll_x=False,bar_width=dp(3))
        rows=BoxLayout(orientation='vertical',size_hint_y=None,spacing=dp(6))
        rows.bind(minimum_height=rows.setter('height'));self.list_scroll.add_widget(rows)
        left.add_widget(self.list_scroll);self.pages.add_widget(left)
        self.detail_scroll=ScrollView(do_scroll_x=False,bar_width=dp(3))
        detail=BoxLayout(orientation='vertical',size_hint_y=None,spacing=dp(6))
        detail.bind(minimum_height=detail.setter('height'))
        self.detail_title=page_text('',16,bold=True)
        self.availability=page_text('',12,READY,bold=True)
        self.description=page_text('',13)
        self.target_info=page_text('',12,FADED)
        self.power=page_text('',12,INK)
        self.warning=page_text('',12,AMBER,bold=True)
        for widget in (self.detail_title,self.availability,self.warning,self.description,self.target_info,self.power):
            detail.add_widget(widget)
        self.detail_scroll.add_widget(detail);self.pages.add_widget(self.detail_scroll)
        footer=BoxLayout(size_hint_y=None,height=dp(46),spacing=dp(7))
        self.cancel=StrategyButton(text='Обычная атака')
        self.cancel.bind(on_release=lambda *_:self.choose(None))
        self.cast=StrategyButton(text='Выбрать цель',accent=(.45,.78,.51,1),primary=True)
        self.cast.bind(on_release=lambda *_:self.choose(self.selected))
        footer.add_widget(self.cancel);footer.add_widget(self.cast);root.add_widget(footer)
        self.content=root
        self.tiles={}
        for key in owner.battle.skills(self.actor):
            tile=SpellTile(self,key);self.tiles[key]=tile;rows.add_widget(tile)
        def fit_tiles(*_):
            count=max(1,len(self.tiles))
            height=max(dp(62),min(dp(86),(self.list_scroll.height-dp(6)*(count-1))/count))
            for tile in self.tiles.values():tile.height=height
        self.list_scroll.bind(height=fit_tiles)
        fit_tiles()
        chosen=owner.selected_skill if owner.selected_skill in self.tiles else next(
            (key for key in self.tiles if not self.cooldown(key)),next(iter(self.tiles),None))
        if chosen:self.select_skill(chosen)
        else:self.cast.disabled=True
        owner.help_open=True
        owner.bind(on_dismiss=self.owner_closed)
        self.bind(on_dismiss=self.closed)

    def owner_closed(self,*_):
        self.dismiss(animation=False)

    def closed(self,*_):
        self.owner.help_open=False
        self.owner.unbind(on_dismiss=self.owner_closed)

    def cooldown(self,key):
        return max(0,self.actor.cooldowns.get(key,0)-self.owner.battle.round)

    def select_skill(self,key):
        self.selected=key;spec=ABILITIES[key];left=self.cooldown(key)
        for tile in self.tiles.values():tile.draw()
        self.detail_title.text=spec.name
        self.availability.text=f'Перезарядка: ещё {left} р.' if left else 'Готово к применению'
        self.availability.color=AMBER if left else READY
        self.description.text=spec.description.replace(' Задевает своих!','')
        self.target_info.text=TARGETS[spec.target]+(f' · дальность {spec.reach}' if spec.reach else '')+(
            f'\nРадиус: {spec.radius} кл.' if spec.radius else '')+f'\nПерезарядка: {spec.cooldown} р.'
        battle=self.owner.battle
        offensive=key in ('snipe','burst','grenade','blizzard','flame','whirlwind','sword_throw','drain','auto_burst','blood_vortex','twin_arrow','vampire_raise')
        if offensive:
            self.power.text='Сила: '+format_number(battle.ability_power(key,self.actor))+'\nДо учёта защиты цели'
        elif key=='heal':
            self.power.text='Лечение: '+format_number(battle.skill_power(self.actor,False)*.25)+'\nДо учёта стойкости цели'
        elif key=='fire_shield':
            self.power.text='Сила щита: '+format_number(battle.skill_power(self.actor,False)*.30)+\
                '\nОжог: '+format_number(battle.skill_power(self.actor,True))
        elif key=='vampirism':
            self.power.text='Предел лечения: '+format_number(battle.skill_power(self.actor,False)*.25)
        else:
            self.power.text=''
        self.warning.text='Задевает союзников — проверьте область на карте.' if key in ('grenade','blizzard','flame') else ''
        self.cast.text='Подготовить' if spec.target in ('self','army') else 'Выбрать цель'
        self.cast.disabled=left>0
        self.detail_scroll.scroll_y=1

    def choose(self,key):
        if key is not None and (key not in self.tiles or self.cooldown(key)):return
        # A turn can be externally finished while a popup is open; never arm another hero's spell.
        if self.owner.battle.active is not self.actor or not self.actor.alive:
            self.dismiss();return
        self.owner.selected_skill=key
        self.owner.selection=self.actor.pos if key and ABILITIES[key].target in ('self','army') else None
        self.dismiss();self.owner.refresh()
