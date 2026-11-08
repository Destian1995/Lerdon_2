"""Touch-first tactical battlefield and atlas playback; combat lives in the model."""
import json
import math
from pathlib import Path

from kivy.clock import Clock
from kivy.core.image import Image as CoreImage
from kivy.core.text import Label as CoreLabel
from kivy.graphics import Color, Rectangle, Line, Ellipse
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.widget import Widget

from strategy_ui import StrategyButton, text_label, surface, GOLD, TEXT, MUTED, SURFACE
from tactical_combat import TERRAINS, RANGE, WIDTH, HEIGHT
from tactical_abilities import ABILITIES
from window_theme import prepare_custom_popup
from utils.helpers import format_number
from game_audio import get_audio, attack_sound

ROOT = Path(__file__).resolve().parent
ASSETS = ROOT/'files/army/animated'
BLUE = (.30,.67,1,1)
RED = (1,.39,.34,1)
GREEN = (.34,.87,.57,1)
TILE_COLORS = {
    'plain': (.24,.34,.23), 'road': (.43,.38,.27), 'forest': (.12,.25,.18),
    'hill': (.40,.42,.27), 'swamp': (.18,.29,.26), 'snow': (.65,.74,.79),
    'rock': (.26,.29,.34), 'water': (.09,.29,.43), 'bridge': (.45,.34,.22),
    'sand':(.69,.50,.25),'blight':(.25,.18,.31),
}


def flowing_label(text='',size=13):
    label=text_label(text,size,TEXT,size_hint_y=None)
    label.unbind(size=label._strategy_text_sizer)
    label.bind(width=lambda obj,value:setattr(obj,'text_size',(value,None)))
    label.bind(texture_size=lambda obj,value:setattr(obj,'height',value[1]+dp(12)))
    label.text_size=(label.width,None)
    return label


class SpriteLibrary:
    def __init__(self):
        self.index = json.loads((ASSETS/'index.json').read_text(encoding='utf-8'))
        self.atlases = {}
        self.fallbacks = {}

    def key(self, unit):
        ref = str(unit.get('unit_image') or unit.get('image_path') or '').replace('\\','/')
        if '/files/' in ref:
            ref = 'files/'+ref.split('/files/',1)[1]
        return self.index['references'].get(ref)

    def frame(self, unit, action, age):
        key = self.key(unit)
        if not key:
            ref = unit.get('unit_image') or unit.get('image_path')
            if not ref:
                return None, (0,0), (.5,.1)
            if ref not in self.fallbacks:
                try:
                    self.fallbacks[ref] = CoreImage(ref, nocache=True).texture
                except Exception:
                    self.fallbacks[ref] = None
            return self.fallbacks[ref], (0,0), (.5,.1)
        if key not in self.atlases:
            path = ASSETS/self.index['characters'][key]
            meta = json.loads(path.read_text(encoding='utf-8'))
            atlas = CoreImage(str(path.parent/meta['image']), nocache=True).texture
            frames = {}
            for state, clip in meta['animations'].items():
                regions = []
                for f in clip['frames']:
                    x,y,w,h = f['rect']
                    regions.append(atlas.get_region(x,atlas.height-y-h,w,h))
                frames[state] = regions
            self.atlases[key] = (meta,atlas,frames)
        meta, _, frames = self.atlases[key]
        clip = meta['animations'][action]
        n = int(age*clip['fps'])
        n = n % len(clip['frames']) if clip['loop'] else min(n,len(clip['frames'])-1)
        offset = clip['frames'][n]['offset']
        return frames[action][n], (offset[0]/meta['frame_size'][0], offset[1]/meta['frame_size'][1]), meta['ground_anchor']

    def clear(self):
        self.atlases.clear()
        self.fallbacks.clear()


class Battlefield(Widget):
    def __init__(self, owner, **kwargs):
        super().__init__(**kwargs)
        self.owner = owner
        self.cell = 1
        self.origin = (0,0)
        self.labels = {}
        self.library = SpriteLibrary()
        backdrop=ROOT/'files/battlefields'/(owner.battle.biome+'.png')
        self.backdrop=CoreImage(str(backdrop),nocache=True).texture if backdrop.is_file() else None
        self.bind(pos=self.draw,size=self.draw)

    def label(self, text, x, y, size, color=TEXT):
        key = (text,round(size,1),color)
        if key not in self.labels:
            if len(self.labels)>240:
                self.labels.clear()
            label = CoreLabel(text=text,font_size=size,color=color,bold=True)
            label.refresh()
            self.labels[key] = label.texture
        texture = self.labels[key]
        Color(1,1,1,1)
        Rectangle(texture=texture,pos=(x-texture.width/2,y-texture.height/2),size=texture.size)

    def cell_center(self, pos):
        return self.origin[0]+(pos[0]+.5)*self.cell, self.origin[1]+(pos[1]+.5)*self.cell

    def draw(self, *args):
        if not hasattr(self,'library'):
            return
        battle = self.owner.battle
        self.cell = max(1,min(self.width/WIDTH,self.height/HEIGHT))
        c = self.cell
        self.origin = (self.center_x-c*WIDTH/2,self.center_y-c*HEIGHT/2)
        reachable = battle.reachable() if self.owner.can_control else {}
        deployment = battle.deployment_cells(self.owner.player_side) if self.owner.deploying else set()
        selected = self.owner.selection
        affected=set(battle.ability_cells(self.owner.selected_skill,selected)) if self.owner.selected_skill and selected in battle.terrain else set()
        active = battle.active
        self.canvas.clear()
        with self.canvas:
            if self.backdrop:
                Color(1,1,1,1)
                # Crop the square illustration, preserving landscape proportions.
                Rectangle(texture=self.backdrop,pos=self.origin,size=(c*WIDTH,c*HEIGHT),
                          tex_coords=(0,.2,1,.2,1,.8,0,.8))
            for (x,y), kind in battle.terrain.items():
                px,py = self.origin[0]+x*c,self.origin[1]+y*c
                col = TILE_COLORS[kind]
                shade = 1 if (x+y)%2 else .93
                alpha=(.03 if kind=='plain' else .23 if kind in ('forest','hill','snow','sand','blight') else .5) if self.backdrop else 1
                Color(*(v*shade for v in col),alpha)
                Rectangle(pos=(px,py),size=(c,c))
                # Small drawn landmarks keep the tactical cells legible.
                if kind == 'forest':
                    for ox,oy in ((.25,.3),(.65,.6),(.3,.76)):
                        Color(.07,.16,.10,.30)
                        Ellipse(pos=(px+c*ox-c*.06,py+c*oy-c*.06),size=(c*.17,c*.17))
                elif kind in ('water','swamp'):
                    Color(.40,.66,.67,.4)
                    for level in (.3,.65):
                        Line(points=(px+c*.15,py+c*level,px+c*.7,py+c*(level+.08)),width=1)
                elif kind in ('hill','rock'):
                    Color(.68,.70,.58,.5)
                    Line(points=(px+c*.15,py+c*.3,px+c*.5,py+c*.75,px+c*.8,py+c*.3),width=1.2)
                elif kind == 'bridge':
                    Color(.74,.59,.39,.7)
                    for level in (.2,.4,.6,.8):
                        Line(points=(px+c*.1,py+c*level,px+c*.9,py+c*level),width=1)
                if (x,y) in reachable or (x,y) in deployment:
                    Color(.36,.85,.63,.12)
                    Rectangle(pos=(px,py),size=(c,c))
                    Color(.41,.96,.66,.55)
                    Ellipse(pos=(px+c*.46,py+c*.46),size=(c*.08,c*.08))
                if active and self.owner.can_control:
                    target = battle.at((x,y))
                    if target and battle.can_attack(active,target):
                        Color(1,.35,.25,.25)
                        Rectangle(pos=(px,py),size=(c,c))
                if (x,y) in affected:
                    Color(1,.51,.18,.28)
                    Rectangle(pos=(px,py),size=(c,c))
                Color(.02,.05,.07,.38)
                Line(rectangle=(px,py,c,c),width=.65)
            if selected in reachable:
                Color(.55,1,.72,.9)
                points = [v for p in reachable[selected][1] for v in self.cell_center(p)]
                Line(points=points,width=1.6)
            if selected in battle.terrain:
                px,py = self.cell_center(selected)
                Color(1,.88,.42,1)
                Line(rectangle=(px-c/2+1,py-c/2+1,c-2,c-2),width=1.8)
            # Far rows before near rows; dead bodies behind living figures.
            for s in sorted(battle.stacks.values(),key=lambda s:(s.alive,-s.pos[1])):
                state,age,p = self.owner.visual(s)
                pending=next((hit for when,hit in self.owner.pending_strikes
                              if when>self.owner.age and hit.get('grenade') and hit['target']==s.id),None)
                visible_alive=s.alive or pending is not None
                px,py = self.cell_center(p)
                accent = BLUE if s.side=='attacker' else RED
                if visible_alive:
                    Color(*accent[:3],.32)
                    Ellipse(pos=(px-c*.37,py-c*.38),size=(c*.74,c*.26))
                    if battle.protected(s):
                        Color(.54,.84,1,.8)
                        Line(ellipse=(px-c*.32,py-c*.25,c*.64,c*.75),width=1)
                if (s.id==self.owner.deployment_actor if self.owner.deploying else s is active):
                    Color(*GOLD)
                    Line(ellipse=(px-c*.39,py-c*.4,c*.78,c*.30),width=1.5)
                texture,offset,anchor = self.library.frame(s.unit,state,age)
                size = c*1.4
                if texture:
                    coords = list(texture.tex_coords)
                    if s.side=='defender':
                        coords = coords[2:4]+coords[:2]+coords[6:8]+coords[4:6]
                    Color(1,1,1,1 if visible_alive or state=='death' else .5)
                    Rectangle(texture=texture,tex_coords=coords,
                              pos=(px-size*.5-offset[0]*size,py-c*.26-size*anchor[1]+offset[1]*size),
                              size=(size,size))
                else:
                    Color(*accent)
                    Ellipse(pos=(px-c*.2,py-c*.16),size=(c*.4,c*.5))
                if visible_alive:
                    Color(.03,.04,.06,.95)
                    Rectangle(pos=(px-c*.36,py-c*.47),size=(c*.72,c*.22))
                    self.label(format_number(s.count+(pending['killed'] if pending else 0)),px,py-c*.36,max(9,min(13,c*.25)))
                    Color(.10,.12,.14,1)
                    Rectangle(pos=(px-c*.32,py-c*.49),size=(c*.64,c*.04))
                    Color(*GREEN[:3],1)
                    Rectangle(pos=(px-c*.32,py-c*.49),size=(c*.64*min(1,(s.hp+(pending['damage'] if pending else 0))/s.max_hp),c*.04))
            for strike,age in self.owner.damage_labels:
                if age < 1.4:
                    target = battle.stacks[strike['target']]
                    px,py = self.cell_center(target.pos)
                    text = ('КРИТ ' if strike['critical'] else '')+'−'+format_number(strike['killed'] or strike['damage'])
                    self.label(text,px,py+c*(.55+age*.25),max(11,c*.28),(1,.86,.38,1))
            for strike,start in self.owner.projectiles:
                t=(self.owner.age-start)/.22
                if 0<=t<=1:
                    actor,target=battle.stacks[strike['actor']],battle.stacks[strike['target']]
                    ax,ay=self.cell_center(actor.pos)
                    tx,ty=self.cell_center(target.pos)
                    if max(abs(actor.pos[0]-target.pos[0]),abs(actor.pos[1]-target.pos[1]))>1:
                        Color(.70,.88,1,.9)
                        tail=max(0,t-.2)
                        Line(points=(ax+(tx-ax)*tail,ay+(ty-ay)*tail,
                                     ax+(tx-ax)*t,ay+(ty-ay)*t),width=1.7)
                    else:
                        Color(1,.86,.47,1-t)
                        Line(points=(tx-c*.2,ty-c*.1,tx+c*.2,ty+c*.35),width=2)
            for cells,start,key in self.owner.ability_fx:
                age=self.owner.age-start
                if 0<=age<.8 and key!='grenade':
                    hue=(.45,.83,1) if key in ('freeze','blizzard') else (.4,1,.6) if key in ('heal','inspire','vampirism') else (1,.35,.17)
                    Color(*hue,(1-age/.8)*.7)
                    for pos in cells:
                        px,py=self.cell_center(pos)
                        radius=c*(.18+age*.65)
                        Line(ellipse=(px-radius,py-radius,radius*2,radius*2),width=2)
            for origin,impact,start in self.owner.grenades:
                age=self.owner.age-start
                ax,ay=self.cell_center(origin);tx,ty=self.cell_center(impact)
                if 0<=age<.65:
                    t=age/.65
                    # Ballistic arc with a short curved trail and spinning fuse.
                    arc=min(c*1.5,max(c*.15,self.origin[1]+HEIGHT*c-max(ay,ty)-c*.15))
                    def point(v):return ax+(tx-ax)*v,ay+(ty-ay)*v+math.sin(math.pi*v)*arc
                    points=[v for i in range(9) for v in point(max(0,t-.2+i*.025))]
                    Color(.9,.78,.45,.65);Line(points=points,width=1.3)
                    px,py=point(t)
                    Color(.13,.19,.12,1);Ellipse(pos=(px-c*.075,py-c*.075),size=(c*.15,c*.15))
                    Color(1,.85,.38,1)
                    Line(points=(px,py,px+math.cos(t*20)*c*.13,py+math.sin(t*20)*c*.13),width=1.4)
                elif .65<=age<1.55:
                    t=(age-.65)/.9
                    # Expanding shockwave, hot core, sparks, then drifting smoke.
                    Color(1,.78,.3,(1-t)*.8)
                    radius=c*(.15+t*1.5)
                    Line(ellipse=(tx-radius,ty-radius,2*radius,2*radius),width=max(1,c*.035*(1-t)))
                    for i in range(12):
                        angle=i*math.tau/12
                        travel=c*t*(.65+(i%3)*.25)
                        px=tx+math.cos(angle)*travel;py=ty+math.sin(angle)*travel
                        r=c*(.10+.18*t)
                        Color(.22,.23,.24,(1-t)*.5)
                        Ellipse(pos=(px-r,py-r+c*t*.4),size=(r*2,r*2))
                        Color(1,.4+.04*(i%4),.08,(1-t)**2)
                        Line(points=(px,py,px+math.cos(angle)*c*.14,py+math.sin(angle)*c*.14),width=1.5)
                    for scale,color in ((1,(1,.28,.03)),(.65,(1,.68,.12)),(.3,(1,.97,.72))):
                        r=c*scale*(.12+.48*math.sin(math.pi*min(1,t*2)))
                        Color(*color,max(0,1-t*2))
                        Ellipse(pos=(tx-r,ty-r),size=(r*2,r*2))

    def on_touch_down(self,touch):
        if not self.collide_point(*touch.pos):
            return super().on_touch_down(touch)
        x = int((touch.x-self.origin[0])/self.cell)
        y = int((touch.y-self.origin[1])/self.cell)
        if (x,y) in self.owner.battle.terrain:
            self.owner.select((x,y))
        return True


class TacticalBattlePopup(Popup):
    def __init__(self,battle,player_side,callback,city='',**kwargs):
        super().__init__(title='',size_hint=(1,1),auto_dismiss=False,**kwargs)
        prepare_custom_popup(self)
        self.battle,self.player_side,self.callback = battle,player_side,callback
        self.audio=get_audio()
        self.sound_queue=[]
        self.result_sound_played=False
        self.selection = None
        self.selected_skill=None
        self.deploying = True
        self.deployment_actor = next((s.id for s in battle.stacks.values() if s.side==player_side),None)
        self.autoplay = False
        self.finished = False
        self.age = 0
        self.busy = 0
        self.animations = {}
        self.walk = None
        self.pending_strikes = []
        self.damage_labels = []
        self.projectiles=[]
        self.ability_fx=[]
        self.grenades=[]
        self.seen_events=0
        self.help_open=False
        self.notified = False
        self.clock_event=None
        self.root_box = BoxLayout(orientation='vertical',padding=dp(2),spacing=dp(2))
        self.root_box._strategy_fixed_layout=True
        surface(self.root_box)
        header = BoxLayout(size_hint_y=None,height=dp(40))
        self.heading = text_label(city,13,GOLD,bold=True)
        help_button = StrategyButton(text='?',size_hint_x=None,width=dp(44))
        help_button.bind(on_release=self.show_rules)
        header.add_widget(help_button)
        self.root_box.add_widget(header)
        self.body = BoxLayout(spacing=dp(2))
        self.board = Battlefield(self)
        self.panel = BoxLayout(orientation='vertical',spacing=dp(4),padding=dp(2))
        surface(self.panel,SURFACE)
        self.compact_info=text_label('',11,GOLD,bold=True)
        self.turn_label = text_label('',13,GOLD,bold=True)
        header.add_widget(self.turn_label,index=len(header.children))
        scroller = self.info_scroll = ScrollView(do_scroll_x=False)
        self.info = flowing_label()
        scroller.add_widget(self.info)
        self.panel.add_widget(scroller)
        self.action = StrategyButton(text='Выберите клетку',primary=True,size_hint_y=None,height=dp(48))
        self.action.bind(on_release=self.confirm)
        self.panel.add_widget(self.action)
        buttons = self.buttons = GridLayout(cols=2,size_hint_y=None,height=dp(88),spacing=dp(4))
        self.guard = StrategyButton(text='Защита +30%')
        self.wait_button = StrategyButton(text='Ожидать')
        self.auto_button = StrategyButton(text='Автобой')
        self.speed_button = StrategyButton(text='Скорость ×1')
        self.speed_button.size_hint_x=None;self.speed_button.width=dp(85)
        header.add_widget(self.speed_button,index=1)
        self.skill_button=StrategyButton(text='Способности')
        self.speed = 1
        self.guard.bind(on_release=lambda *_:self.perform(self.battle.defend))
        self.wait_button.bind(on_release=lambda *_:self.perform(self.battle.wait))
        self.auto_button.bind(on_release=self.toggle_auto)
        self.speed_button.bind(on_release=self.toggle_speed)
        self.skill_button.bind(on_release=self.show_skills)
        for button in (self.guard,self.wait_button,self.auto_button,self.skill_button):
            buttons.add_widget(button)
        self.panel.add_widget(buttons)
        self.log_label = text_label('Зелёные клетки — движение. Красные — доступные цели.',11,MUTED,
                                    size_hint_y=None,height=dp(42))
        self.panel.add_widget(self.log_label)
        self.info_button=StrategyButton(text='Инфо',size_hint_y=None,height=dp(44))
        self.info_button.size_hint=(None,1);self.info_button.width=dp(58)
        self.info_button.bind(on_release=self.show_info)
        header.add_widget(self.info_button,index=1)
        self.root_box.add_widget(self.body)
        self.content = self.root_box
        self.bind(size=self.layout_battle,on_open=self.begin,on_dismiss=self.cleanup)
        self.layout_battle()
        self.refresh()

    @property
    def can_control(self):
        return bool(self.battle.active and self.battle.active.side==self.player_side
                    and not self.deploying and not self.autoplay and self.busy<=0 and not self.battle.winner)

    def layout_battle(self,*args):
        self.body.clear_widgets()
        landscape = self.width > self.height*1.15
        self.body.orientation = 'horizontal' if landscape else 'vertical'
        self.board.size_hint = (1,1) if landscape else (1,None)
        self.panel.size_hint = (None,1) if landscape else (1,1)
        self.panel.clear_widgets()
        self.buttons.cols=1 if landscape else 2
        self.buttons.height=dp(188 if landscape else 92)
        if landscape:
            self.panel.width = max(dp(100),min(dp(124),self.width*.17))
            if self.height>=dp(350):self.panel.add_widget(self.compact_info)
        else:
            self.board.height=max(1,(self.width-dp(28))*HEIGHT/WIDTH)
            self.panel.add_widget(self.info_scroll)
        for widget in (self.action,self.buttons):self.panel.add_widget(widget)
        self.body.add_widget(self.board)
        self.body.add_widget(self.panel)

    def show_info(self,*args):
        self.help_open=True
        box=BoxLayout(orientation='vertical',spacing=dp(6),padding=dp(8))
        box._strategy_fixed_layout=True
        scroll=ScrollView(do_scroll_x=False)
        scroll.add_widget(flowing_label(self.info.text+'\n\n'+self.log_label.text,14))
        box.add_widget(scroll)
        close=StrategyButton(text='К бою',size_hint_y=None,height=dp(44))
        sound=StrategyButton(text='Настройки звука',size_hint_y=None,height=dp(44))
        def sound_settings(*_):
            from audio_settings_ui import show_audio_settings
            show_audio_settings(manager=self.audio)
        sound.bind(on_release=sound_settings)
        box.add_widget(sound)
        box.add_widget(close)
        popup=Popup(title='Отряд и выбранная клетка',content=box,size_hint=(.92,.92))
        prepare_custom_popup(popup)
        close.bind(on_release=popup.dismiss)
        popup.bind(on_dismiss=lambda *_:setattr(self,'help_open',False))
        popup.open()

    def begin(self,*args):
        if self.parent and self.clock_event is None:
            self.audio.start_music(self,self.battle.factions.get(self.player_side))
            self.refresh()
            self.clock_event = Clock.schedule_interval(self.tick,1/30)

    def cleanup(self,*args):
        self.sound_queue.clear()
        self.audio.stop_owner(self)
        if getattr(self,'clock_event',None):
            self.clock_event.cancel()
            self.clock_event = None
        self.board.library.clear()
        self.board.backdrop=None

    def show_rules(self,*args):
        self.help_open=True
        box = BoxLayout(orientation='vertical',padding=dp(12),spacing=dp(6))
        box._strategy_fixed_layout=True
        box.add_widget(text_label('Правила и местность',16,GOLD,size_hint_y=None,height=dp(30)))
        scroll = ScrollView(do_scroll_x=False)
        label = flowing_label('Каждый отряд двигается и атакует один раз за активацию. Очередь — по инициативе. '
            'Движение можно разбить на несколько шагов. После атаки ход заканчивается.\n\n'
            'Стрелки, маги и осадные отряды стреляют. Дальность: 7 / 6 / 6 клеток. '
            'На открытой линии стрелки бьют на 7 клеток без штрафа за дальность. После движения урон ×0,75. Вблизи их урон ×0,5. '
            'Соседний враг блокирует стрельбу по дальним целям.\n\n'
            'В ближнем бою выживший враг отвечает с 65% урона, один раз за раунд. '
            'Конница после 3 шагов получает +25% урона натиска на открытом месте. '
            'Вход в зону рядом с врагом останавливает движение. Диагональ стоит ×1,4.\n\n'
            'Защита даёт +30% до следующей активации. Ожидание переносит ход в конец раунда, '
            'один раз и до движения. Все герои участвуют с начала боя; ауры 2–3 классов действуют на солдат. '
            'Пока жив хотя бы один союзный отряд 1 класса, герои не получают урон. '
            'Защищённые герои не блокируют стрельбу соседних отрядов.\n\n'
            'Способности выбираются отдельной кнопкой: у каждой есть цель, дальность и перезарядка в раундах. '
            'Граната, вьюга и огненная полоса задевают своих; оранжевые клетки показывают область действия.\n\n'
            'Предпросмотр показывает обычный урон без критического удара. Крит даёт ×1,5. '
            'Ранения сохраняются между ударами. За 80 раундов атакующий должен победить, иначе защитники удерживают город.\n\n'+
            '\n\n'.join(t.name+': '+t.description for t in TERRAINS.values()),13)
        scroll.add_widget(label)
        box.add_widget(scroll)
        close = StrategyButton(text='Понятно',size_hint_y=None,height=dp(44))
        box.add_widget(close)
        popup = Popup(title='Правила и местность',content=box,size_hint=(.90,.90))
        prepare_custom_popup(popup)
        close.bind(on_release=popup.dismiss)
        popup.bind(on_dismiss=lambda *_:setattr(self,'help_open',False))
        popup.open()

    def select(self,pos):
        self.selection = pos
        if self.deploying:
            stack=self.battle.at(pos)
            if stack and stack.side==self.player_side:
                self.deployment_actor=stack.id
        self.refresh()

    def show_skills(self,*args):
        if not self.can_control:return
        actor=self.battle.active
        box=BoxLayout(orientation='vertical',padding=dp(10),spacing=dp(6))
        box._strategy_fixed_layout=True
        box.add_widget(text_label(actor.name+' · Способности',16,GOLD,size_hint_y=None,height=dp(30)))
        scroll=ScrollView(do_scroll_x=False)
        rows=BoxLayout(orientation='vertical',size_hint_y=None,spacing=dp(8))
        rows.bind(minimum_height=rows.setter('height'))
        scroll.add_widget(rows);box.add_widget(scroll)
        popup=Popup(title=actor.name+' · Способности',content=box,size_hint=(.94,.9))
        prepare_custom_popup(popup)
        def choose(key):
            self.selected_skill=key
            self.selection=actor.pos if key and ABILITIES[key].target in ('self','army') else None
            popup.dismiss();self.refresh()
        for key in self.battle.skills(actor):
            spec=ABILITIES[key];left=max(0,actor.cooldowns.get(key,0)-self.battle.round)
            button=StrategyButton(text=spec.name+(' · '+str(left)+' р.' if left else ''),size_hint_y=None,height=dp(44))
            button.disabled=left>0
            button.bind(on_release=lambda *_,key=key:choose(key))
            rows.add_widget(button)
            rows.add_widget(flowing_label(spec.description+' Перезарядка: '+str(spec.cooldown)+' раунда.',13))
        bonus=self.battle.army_skill_multiplier(actor)
        rows.add_widget(flowing_label('Урон умений: 15% текущей атаки всех живых союзных отрядов, с учётом защиты цели.\n'
            f'Усиление защитных умений армией: +{(bonus-1)*100:g}%.\n'
            f'Атакующая сила умений: {format_number(self.battle.skill_power(actor,True))}. '
            f'Защитная: {format_number(self.battle.skill_power(actor,False))}.',13))
        close=StrategyButton(text='Обычная атака / отмена',size_hint_y=None,height=dp(44))
        close.bind(on_release=lambda *_:choose(None));box.add_widget(close)
        self.help_open=True
        popup.bind(on_dismiss=lambda *_:setattr(self,'help_open',False))
        popup.open()

    def refresh(self):
        s = self.battle.active
        actor=self.battle.stacks.get(self.deployment_actor) if self.deploying else s
        self.compact_info.text=(actor.name+'\n'+format_number(actor.count)) if actor else ''
        if self.battle.winner:
            if self.busy<=0 and not self.result_sound_played:
                self.audio.play('victory' if self.battle.winner==self.player_side else 'defeat',owner=self)
                self.result_sound_played=True
            self.turn_label.text = 'ПОБЕДА' if self.battle.winner==self.player_side else 'ПОРАЖЕНИЕ'
            self.info.text = self.battle.reason
            self.action.text = 'Завершить бой'
            self.action.disabled = self.busy>0
        elif self.deploying:
            self.turn_label.text='Расстановка · ваша армия'
            actor=self.battle.stacks.get(self.deployment_actor)
            self.info.text=('Выберите свой отряд, затем свободную зелёную клетку. '
                            'Расстановка бесплатна.\n\n'+(actor.name if actor else ''))
            self.action.text='Начать бой'
            self.action.disabled=False
            if self.selection in self.battle.deployment_cells(self.player_side) and actor and self.selection!=actor.pos:
                self.action.text='Поставить отряд'
        else:
            self.turn_label.text = f'Раунд {self.battle.round} · '+('Ваш ход' if s.side==self.player_side else 'Ход противника')
            queue = self.battle.queue[:5]
            self.info.text = (f'{s.name} · {format_number(s.count)}\n'
                f'Ход: {s.mp/10:g} · Инициатива: {s.initiative:g}\n'
                f'Дальность: {RANGE.get(s.role,1)}\n'
                f'На бойца · АТК {format_number(self.battle._power(s,True))} · ЗАЩ {format_number(self.battle._power(s,False))}\n'
                'Очередь: '+' → '.join(self.battle.stacks[k].name for k in queue))
            self.action.text = 'Выберите клетку'
            self.action.disabled = True
        if self.selection in self.battle.terrain:
            t = self.battle.tile(self.selection)
            self.info.text += '\n\n'+t.name+' · '+t.description
            target = self.battle.at(self.selection)
            if target:
                self.info.text += f'\n{target.name} · {format_number(target.count)}\nЗдоровье: {target.hp/target.max_hp:.0%}'
                self.info.text+=f'\nНа бойца · АТК {format_number(self.battle._power(target,True))} · ЗАЩ {format_number(self.battle._power(target,False))}'
                if self.battle.protected(target):self.info.text+='\nГерой защищён, пока живы союзные солдаты 1 класса.'
                if target.effects:self.info.text+='\nЭффекты: '+', '.join(ABILITIES[k].name if k in ABILITIES else 'Замедление' for k in target.effects)
                if self.can_control and not self.selected_skill and target.side!=s.side:
                    preview = self.battle.preview(target)
                    if preview:
                        self.info.text += (f"\nУрон: {format_number(preview['min_damage'])}–{format_number(preview['max_damage'])}"
                            f"\nПотери: {format_number(preview['min_kills'])}–{format_number(preview['max_kills'])}"
                            f"\nКрит: {preview['critical_chance']:g}% · "+('Возможен ответный удар' if preview['retaliation'] else 'Без ответного удара'))
                        self.action.text,self.action.disabled = 'Атаковать',False
                    else:
                        self.info.text += '\n'+self.battle.attack_block_reason(s,target)
            elif self.can_control:
                route = self.battle.reachable().get(self.selection)
                if route:
                    self.action.text,self.action.disabled = f'Идти · {route[0]/10:g} ОД',False
        self.guard.disabled = not self.can_control
        self.wait_button.disabled = not self.can_control or bool(s and (s.waited or s.moved))
        self.auto_button.disabled = bool(self.battle.winner)
        self.skill_button.disabled=not self.can_control or not self.battle.skills()
        if self.selected_skill and self.can_control:
            spec=ABILITIES[self.selected_skill]
            self.info.text+='\n\n'+spec.name+': '+spec.description+'\nВыберите цель на поле.'
            self.info.text+='\nУрон: 15% текущей атаки живого гарнизона. '
            self.info.text+=f'Сила · АТК {format_number(self.battle.skill_power(s,True))} · ЗАЩ {format_number(self.battle.skill_power(s,False))}'
            self.action.text='Применить: '+spec.name
            self.action.disabled=not self.battle.ability_valid(self.selected_skill,self.selection)
        self.board.draw()

    def confirm(self,*args):
        if self.battle.winner:
            if self.busy<=0 and not self.notified:
                self.notified = True
                self.dismiss()
                self.callback(self.battle)
            return
        if self.deploying:
            actor=self.battle.stacks.get(self.deployment_actor)
            if self.action.text=='Поставить отряд' and actor:
                self.battle.deploy(actor.id,self.selection)
                self.selection=None
            else:
                self.deploying=False
                self.selection=None
            self.refresh()
            return
        if not self.can_control or self.selection is None:
            return
        if self.selected_skill:
            key=self.selected_skill;pos=self.selection
            self.selected_skill=None
            self.perform(lambda:self.battle.use_ability(key,pos))
            return
        target = self.battle.at(self.selection)
        if target:
            self.perform(lambda:self.battle.attack(target.id))
        else:
            self.perform(lambda:self.battle.move(self.selection))

    def perform(self,action):
        if not self.can_control:
            return
        try:
            self.animate(action())
        except ValueError as error:
            self.log_label.text = str(error)
        self.refresh()

    def animate(self,event):
        if not event:
            return
        self.selection = None
        self.selected_skill=None
        actor = self.battle.stacks[event['actor']]
        action = event['action']
        grenade=action=='ability' and event['ability']=='grenade'
        if action=='ability':
            key=event['ability']
            sound=('throw' if grenade else 'rifle' if key=='snipe' else None if key=='burst'
                   else 'frost' if key in ('freeze','blizzard') else 'heal' if key in ('heal','inspire','vampirism')
                   else 'sword' if key=='whirlwind' else 'magic')
            if sound:self.audio.play(sound,owner=self)
        if action=='ability':self.ability_fx.append((event['cells'],self.age+(.65 if grenade else 0),event['ability']))
        if grenade:
            self.grenades.append((event['origin'],event['impact'],self.age))
            self.sound_queue.append((self.age+.65,'explosion'))
            self.animations[actor.id]=('attack',self.age,self.age+.65)
            self.busy=1.6
            for strike in event.get('strikes',[]):
                self.pending_strikes.append((self.age+.65,dict(strike,grenade=True)))
            self.log_label.text=actor.name+' · Граната'
        elif action=='walk':
            self.audio.play('step',owner=self)
            self.walk = (actor.id,event['path'],self.age)
            self.busy = max(.2,(len(event['path'])-1)*.13)
            self.animations[actor.id] = ('walk',self.age,self.age+self.busy)
            self.log_label.text = actor.name+' меняет позицию.'
        elif action in ('attack','ability') and event.get('path'):
            self.walk=(actor.id,event['path'],self.age)
            self.busy=max(.3,(len(event['path'])-1)*.13)
            self.animations[actor.id]=('walk',self.age,self.age+self.busy)
        elif action in ('attack','ability') and event.get('strikes'):
            self.busy = .72*len(event['strikes'])+.65
            for i,strike in enumerate(event['strikes']):
                self.pending_strikes.append((self.age+i*.72,dict(strike,ability=event.get('ability'))))
            self.log_label.text = actor.name+' · '+(ABILITIES[event['ability']].name if action=='ability' else 'Атака')
        else:
            self.busy = .65 if action=='ability' else .25
            if action=='ability':self.animations[actor.id]=('attack',self.age,self.age+.6)
            self.log_label.text = actor.name+(' · '+ABILITIES[event['ability']].name if action=='ability' else ' занял защиту.' if action=='defend' else ' ожидает.')
        for extra in self.battle.events[self.seen_events:]:
            if extra['action']=='status':
                when=self.age+self.busy
                for hit in extra['strikes']:self.pending_strikes.append((when,hit))
                self.busy+=.7
            elif extra['action']=='skip':
                self.ability_fx.append(([self.battle.stacks[extra['actor']].pos],self.age,'freeze'))
        self.seen_events=len(self.battle.events)

    def visual(self,s):
        p = s.pos
        animation = self.animations.get(s.id)
        state, age = ('idle',self.age) if s.alive else ('death',10)
        if any(when>self.age and hit.get('grenade') and hit['target']==s.id for when,hit in self.pending_strikes):
            state,age='idle',self.age
        if animation:
            name,start,end = animation
            if self.age >= start and (self.age < end or name=='death'):
                state,age = name,self.age-start
            elif self.age<start:
                state,age='idle',self.age
        if self.walk and self.walk[0]==s.id:
            _,path,start = self.walk
            step = min(len(path)-1,(self.age-start)/.13)
            i = min(len(path)-2,int(step))
            fraction = min(1,step-i)
            p = (path[i][0]+(path[i+1][0]-path[i][0])*fraction,
                 path[i][1]+(path[i+1][1]-path[i][1])*fraction)
        return state,age,p

    def tick(self,dt):
        if self.help_open:return
        dt = min(dt,.1)*self.speed
        self.age += dt
        old_busy = self.busy
        self.busy = max(0,self.busy-dt)
        if self.walk and self.age-self.walk[2]>=(len(self.walk[1])-1)*.13:
            self.walk = None
        for when,strike in list(self.pending_strikes):
            if self.age>=when:
                if not any(strike.get(key) for key in ('periodic','reflection','grenade')):
                    actor=self.battle.stacks[strike['actor']]
                    target=self.battle.stacks[strike['target']]
                    if strike.get('ability')=='burst':self.audio.play('rifle',owner=self)
                    elif not strike.get('ability'):
                        ranged=max(abs(actor.pos[0]-target.pos[0]),abs(actor.pos[1]-target.pos[1]))>1
                        self.audio.play(attack_sound(actor.unit,actor.role,ranged),owner=self)
                    self.sound_queue.append((when+.22,'hit'))
                if not strike.get('periodic') and not strike.get('reflection') and not strike.get('grenade'):
                    self.animations[strike['actor']] = ('attack',when,when+.6)
                state = 'death' if strike['dead'] else 'hit'
                self.animations[strike['target']] = (state,when+(0 if strike.get('grenade') else .22),when+1.05)
                self.damage_labels.append((strike,0))
                if not strike.get('periodic') and not strike.get('grenade'):self.projectiles.append((strike,when))
                self.pending_strikes.remove((when,strike))
                self.log_label.text = ('Ответный удар. ' if strike['counter'] else '')+'Урон: '+format_number(strike['damage'])+' · Потери: '+format_number(strike['killed'])
        for when,key in list(self.sound_queue):
            if self.age>=when:
                self.audio.play(key,owner=self)
                self.sound_queue.remove((when,key))
        self.projectiles=[(strike,start) for strike,start in self.projectiles if self.age-start<.3]
        self.ability_fx=[item for item in self.ability_fx if self.age-item[1]<.8]
        self.grenades=[item for item in self.grenades if self.age-item[2]<1.6]
        self.damage_labels = [(strike,age+dt) for strike,age in self.damage_labels if age<1.4]
        if self.busy<=0:
            if old_busy>0:
                self.refresh()
            if not self.deploying and self.battle.active and (self.autoplay or self.battle.active.side!=self.player_side):
                self.animate(self.battle.ai_step())
                self.refresh()
        self.board.draw()

    def toggle_auto(self,*args):
        self.deploying=False
        self.selected_skill=None
        self.autoplay = not self.autoplay
        self.auto_button.text = 'Ручной бой' if self.autoplay else 'Автобой'
        self.refresh()

    def toggle_speed(self,*args):
        self.speed = {1:2,2:4,4:1}[self.speed]
        self.speed_button.text = f'Скорость ×{self.speed}'
