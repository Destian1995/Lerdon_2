"""Deterministic 10x10 combat model. No database, UI, or global random state.

Coordinates start at the lower left. A stack keeps fractional wounds between
attacks; its displayed count is the number of living soldiers, not hit points.
Campaign writes happen only after the battle has finished.
"""
from dataclasses import dataclass,field
from heapq import heappop, heappush
import copy
import math
import random
from tactical_abilities import ABILITIES,hero_abilities


SIZE = 10


@dataclass(frozen=True)
class Terrain:
    name: str
    cost: int = 10
    cover: float = 1.0
    melee_cover: float = 1.0
    elevation: int = 0
    blocked: bool = False
    opaque: bool = False
    description: str = ''


TERRAINS = {
    'plain': Terrain('Луг', description='Свободное движение и открытый обзор.'),
    'road': Terrain('Дорога', 7, description='Движение стоит 0,7 вместо 1.'),
    'forest': Terrain('Лес', 20, 1.40, 1.15, opaque=True,
                      description='Ход: 2. Защита: +40% от стрел, +15% вблизи. Перекрывает обзор; нет натиска.'),
    'hill': Terrain('Высота', 15, elevation=1,
                    description='Ход: 1,5. +15% урона сверху. Закрывает обзор с равнины.'),
    'swamp': Terrain('Болото', 30,
                     description='Ход: 3. −15% урона, нет натиска.'),
    'snow': Terrain('Снег', 20, description='Движение стоит 2.'),
    'sand': Terrain('Песок',20,description='Рыхлый песок: движение стоит 2.'),
    'blight': Terrain('Гиблая земля',20,description='Трудная местность: движение стоит 2.'),
    'rock': Terrain('Скалы', blocked=True, opaque=True,
                    description='Непроходимы, перекрывают обзор.'),
    'water': Terrain('Вода', blocked=True, description='Непроходима. Для перехода нужен мост.'),
    'bridge': Terrain('Мост', description='Проход через воду. Без укрытия.'),
}
SPEED = {'infantry': 4, 'cavalry': 5, 'beast': 5, 'archer': 3, 'mage': 3, 'siege': 2}
RANGE = {'archer': 7, 'mage': 6, 'siege': 6}


def weapon_role(unit,kind):
    """Weapon range is independent of the faction's counter-pick type."""
    explicit=unit.get('tactical_role') or (unit.get('units_stats') or {}).get('Тактика')
    if explicit in SPEED:return explicit
    image=str(unit.get('unit_image') or unit.get('image_path') or '').replace('\\','/').lower()
    for ending,role in {
        'elfs/archer.jpg':'archer','elfs/druid.jpg':'mage','elfs/disease.jpg':'mage',
        'people/predator.jpg':'archer','death/banshi.png':'mage','death/morgana.png':'mage',
        'death/solder.png':'infantry','death/zombie.png':'beast','death/archer.png':'archer','death/king_.png':'infantry',
    }.items():
        if image.endswith(ending):return role
    return kind


def stat(unit, key, default=0):
    try:
        value=(unit.get('units_stats') or {}).get(key,default)
        return float(default if value is None or value=='' else value)
    except (TypeError, ValueError):
        return float(default)


def unit_class(unit):
    try:
        return int(str((unit.get('units_stats') or {}).get('Класс юнита', 1)).split()[0])
    except (TypeError, ValueError, IndexError):
        return 1


def distance(a, b):
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def make_field(seed=0, biome='plains'):
    """Mirrored terrain and two guaranteed crossing lanes: no trapped armies."""
    rng = random.Random(seed)
    field = {(x, y): 'plain' for x in range(SIZE) for y in range(SIZE)}
    kinds = ['plain'] * 5 + ['forest'] * 3 + ['hill'] * 2 + ['swamp', 'rock']
    if biome == 'highland':
        kinds += ['hill'] * 4 + ['rock'] * 2
    elif biome == 'lowland':
        kinds += ['swamp'] * 4 + ['water']
    elif biome == 'snow':
        kinds += ['snow'] * 5
    elif biome == 'forest':kinds += ['forest']*5
    elif biome == 'swamp':kinds += ['swamp']*5+['water']
    elif biome == 'desert':kinds = ['sand']*8+['hill','rock','plain']
    elif biome == 'corruption':kinds += ['blight']*6
    elif biome == 'coast':kinds += ['water']*3
    for x in range(2, 5):
        for y in range(SIZE):
            kind = rng.choice(kinds)
            field[x, y] = field[9-x, y] = kind
    for y in (3, 6):
        for x in range(SIZE):
            field[x, y] = 'bridge' if field[x, y] == 'water' else 'road'
    return field


@dataclass
class Stack:
    id: str
    side: str
    unit: dict
    pos: tuple
    initial: int
    count: int
    kind: str
    role: str
    initiative: float
    speed: int
    hp: float
    max_hp: float
    health_per_unit: float
    mp: int = 0
    moved: int = 0
    guarding: bool = False
    retaliated: bool = False
    waited: bool = False
    effects: dict = field(default_factory=dict)
    cooldowns: dict = field(default_factory=dict)

    @property
    def alive(self):
        return self.count > 0

    @property
    def name(self):
        return self.unit['unit_name']


class TacticalBattle:
    def __init__(self, attackers, defenders, seed=0, terrain=None,
                 biome='plains', type_modifiers=None, factions=('', ''),
                 season_multipliers=None, spirit_factions=(), capital_bonus=False,morale_rules=True):
        self.rng = random.Random(seed)
        self.biome=biome
        self.terrain = dict(terrain if terrain is not None else make_field(seed, biome))
        if set(self.terrain) != {(x, y) for x in range(10) for y in range(10)}:
            raise ValueError('Поле должно содержать ровно 10×10 клеток.')
        if any(t not in TERRAINS for t in self.terrain.values()):
            raise ValueError('Неизвестная местность.')
        self.type_modifiers = type_modifiers or {}
        self.factions = dict(zip(('attacker', 'defender'), factions))
        self.season_multipliers = season_multipliers or {}
        self.spirit_factions = spirit_factions
        self.capital_bonus = capital_bonus
        self.morale_rules=morale_rules
        self.stacks = {}
        self.round = 0
        self.queue = []
        self.delayed = []
        self.events = []
        self.bonus_activations=set()
        self.frames = []
        self.winner = None
        self.reason = ''
        for side, army in (('attacker', attackers), ('defender', defenders)):
            alive = [copy.deepcopy(u) for u in army if u.get('unit_count', 0) > 0]
            if len(alive) > 40:
                raise ValueError('На стороне может быть не больше 40 разных отрядов.')
            # Spread small armies vertically, then fill additional columns.
            rows = [4, 6, 2, 8, 0, 5, 3, 7, 1, 9]
            for i, unit in enumerate(alive):
                x = i // 10 if side == 'attacker' else 9-i//10
                pos = (x, rows[i % 10])
                self.terrain[pos] = 'plain'
                kind = str((unit.get('units_stats') or {}).get('Тип', 'infantry'))
                role = weapon_role(unit,kind)
                count = int(unit['unit_count'])
                resistance = max(1, stat(unit, 'Защита') + stat(unit, 'Живучесть') / 2)
                # Wounds use base resistance; auras/cover reduce incoming damage
                # dynamically, so losing a hero removes its aura immediately.
                hp_per = resistance * 6
                key = f'{side}:{i}'
                self.stacks[key] = Stack(key, side, unit, pos, count, count, kind, role,
                    stat(unit, 'Инициатива', 50 + 10*unit_class(unit)),
                    SPEED.get(role, 4), hp_per*count, hp_per*count, hp_per)
        for s in self.stacks.values():
            if unit_class(s.unit)==1:
                has_hero=any(h.alive and h.side==s.side and unit_class(h.unit)>=2 for h in self.stacks.values())
                s.unit.setdefault('_battle_morale',max(0,min(100,stat(s.unit,'Мораль',100)-(0 if has_hero else 30))))
        if not self._check_end():
            self._new_round()

    @property
    def active(self):
        return self.stacks[self.queue[0]] if self.queue and not self.winner else None

    def at(self, pos):
        return next((s for s in self.stacks.values() if s.alive and s.pos == pos), None)

    def tile(self, pos):
        return TERRAINS[self.terrain[pos]]

    def deployment_cells(self,side):
        columns = max(2,math.ceil(sum(s.side==side for s in self.stacks.values())/10))
        return {p for p in self.terrain if (p[0]<columns if side=='attacker' else p[0]>=10-columns)
                and not self.tile(p).blocked}

    def deploy(self,stack_id,pos):
        s = self.stacks.get(stack_id)
        if self.events or self.round!=1 or not s or pos not in self.deployment_cells(s.side):
            raise ValueError('Расстановка доступна только до боя, в своей зоне.')
        occupant=self.at(pos)
        if occupant and occupant.side!=s.side:
            raise ValueError('Клетка занята врагом.')
        if occupant:
            occupant.pos=s.pos
        s.pos=pos

    def enemies(self, stack):
        return [s for s in self.stacks.values() if s.alive and s.side != stack.side]

    def protected(self,stack):
        return unit_class(stack.unit)>=2 and any(s.alive and s.side==stack.side and unit_class(s.unit)==1
                                                for s in self.stacks.values())

    def engaged(self, stack, pos=None):
        # Protected heroes cannot be attacked yet. Letting them pin shooters
        # would leave no legal target and make an invulnerable firing blockade.
        return any(not self.protected(enemy) and distance(pos or stack.pos, enemy.pos) == 1
                   for enemy in self.enemies(stack))

    def _new_round(self):
        self.round += 1
        if self.round > 80:
            self.winner, self.reason = 'defender', 'Защитники удержали поле за 80 раундов.'
            return
        self.bonus_activations.clear()
        if self.round>1 and self.morale_rules:
            for s in self.stacks.values():
                if not s.alive or unit_class(s.unit)!=1:continue
                army=[t for t in self.stacks.values() if t.side==s.side]
                initial=sum(t.initial for t in army)
                loss_pct=(initial-sum(t.count for t in army))/max(1,initial)*100
                hero_died=any(not t.alive and unit_class(t.unit)>=2 for t in army)
                morale=max(0,min(100,s.unit['_battle_morale']-int(loss_pct/5)*2-(40 if hero_died else 0)))
                s.unit['_battle_morale']=morale
                s.unit['_tactical_morale_modifier']=1.10 if morale>80 else .8 if morale<40 else 1
        for s in self.stacks.values():
            s.effects={k:v for k,v in s.effects.items() if v['expires']>self.round}
        # Ongoing damage is applied once per round, never per animation frame.
        for s in list(self.stacks.values()):
            effect=s.effects.get('drain')
            if effect and s.alive:
                hit=self._hurt(s,effect.get('damage',0),effect['source'])
                hit['periodic']=True
                self.events.append(dict(action='status',actor=effect['source'],strikes=[hit]))
        if self._check_end():return
        self.queue = [s.id for s in sorted(self.stacks.values(),
                      key=lambda s: (-s.initiative, (self.round + (s.side == 'attacker')) % 2, s.id)) if s.alive]
        self.delayed = []
        for s in self.stacks.values():
            s.retaliated = s.waited = False
        self._activate()

    def _activate(self):
        while self.queue and not self.stacks[self.queue[0]].alive:
            self.queue.pop(0)
        if not self.queue:
            if self.delayed:
                # Waiting fast units act last, after slow waiting units.
                self.queue = sorted(self.delayed, key=lambda k: self.stacks[k].initiative)
                self.delayed = []
                self._activate()
            elif not self._check_end():
                self._snapshot()
                self._new_round()
            return
        s = self.active
        if s:
            skip=next((effect for effect in s.effects.values() if effect.get('skip',0)>0),None)
            if skip:
                skip['skip']-=1
                self.events.append(dict(action='skip',actor=s.id))
                self.queue.pop(0)
                self._activate()
                return
            s.mp, s.moved, s.guarding = s.speed*(5 if 'slow' in s.effects else 10), 0, False

    def _snapshot(self):
        row = dict(round=self.round, atk_crits=0, def_crits=0, heroes=[])
        for side, short in (('attacker', 'atk'), ('defender', 'def')):
            row[short+'_total'] = sum(s.count for s in self.stacks.values() if s.side == side)
            row[short+'_max'] = sum(s.initial for s in self.stacks.values() if s.side == side)
        self.frames.append(row)

    def _check_end(self):
        alive = {s.side for s in self.stacks.values() if s.alive}
        if len(alive) < 2:
            self.winner = 'attacker' if alive == {'attacker'} else 'defender'
            self.reason = 'Армия противника разбита.'
            self.queue = []
            return True
        return False

    def _finish(self):
        self.queue.pop(0)
        if self._check_end():
            self._snapshot()
        else:
            self._activate()

    def _neighbors(self, pos, stack=None):
        x, y = pos
        for dx, dy in ((-1,0),(1,0),(0,-1),(0,1),(-1,-1),(-1,1),(1,-1),(1,1)):
            p = (x+dx, y+dy)
            def occupied(q):
                occupant=self.at(q)
                return occupant is not None and occupant is not stack
            if p not in self.terrain or self.tile(p).blocked or occupied(p):
                continue
            if dx and dy and any(self.tile(q).blocked or occupied(q)
                                for q in ((x+dx,y), (x,y+dy))):
                continue  # no squeezing diagonally through units/rocks
            yield p, math.ceil(self.tile(p).cost * (1.4 if dx and dy else 1))

    def reachable(self, stack=None):
        s = stack or self.active
        if not s or not s.alive:
            return {}
        costs, parents = {s.pos: 0}, {s.pos: None}
        heap = [(0, s.pos)]
        while heap:
            cost, p = heappop(heap)
            if costs[p] != cost:
                continue
            # Enemy zones stop travel upon entry; leaving is allowed next turn.
            if p != s.pos and self.engaged(s, p):
                continue
            for q, step in self._neighbors(p):
                total = cost+step
                if total <= s.mp and total < costs.get(q, float('inf')):
                    costs[q], parents[q] = total, p
                    heappush(heap, (total, q))
        return {p: (costs[p], self._path(parents, p)) for p in costs if p != s.pos}

    @staticmethod
    def _path(parents, p):
        route = [p]
        while parents[p] is not None:
            p = parents[p]
            route.append(p)
        return list(reversed(route))

    def move(self, pos):
        s = self.active
        routes = self.reachable(s)
        if pos not in routes:
            raise ValueError('Эта клетка недоступна.')
        cost, path = routes[pos]
        s.mp -= cost
        s.moved += len(path)-1
        s.pos = pos
        if self.engaged(s):
            s.mp = 0
        event = dict(action='walk', actor=s.id, path=path)
        self.events.append(event)
        return event

    def line_of_sight(self, a, b):
        """Supercover sampling: diagonal rays cannot cut an opaque corner."""
        dx, dy = b[0]-a[0], b[1]-a[1]
        steps = max(abs(dx), abs(dy))*8
        height = max(self.tile(a).elevation, self.tile(b).elevation)
        for i in range(1, steps):
            x, y = a[0]+dx*i/steps, a[1]+dy*i/steps
            # Test both cells when the ray lies exactly along a corner.
            for ox, oy in ((-.00001,-.00001),(.00001,.00001),(-.00001,.00001),(.00001,-.00001)):
                p = (math.floor(x+.5+ox), math.floor(y+.5+oy))
                if p in (a,b):
                    continue
                t = self.tile(p)
                if t.opaque or t.elevation > height:
                    return False
        return True

    def can_attack(self, s, target, pos=None):
        return self.attack_block_reason(s,target,pos) is None

    def attack_block_reason(self,s,target,pos=None):
        if not s or not target or not s.alive or not target.alive or s.side == target.side:
            return 'Выберите живой вражеский отряд.'
        if self.protected(target):return 'Герой защищён: сначала уничтожьте его солдат 1 класса.'
        p = pos or s.pos
        d = distance(p, target.pos)
        if d == 1:
            return None
        reach = RANGE.get(s.role, 1)
        if s.role not in RANGE:return 'Этот отряд атакует только соседнюю клетку.'
        if d>reach:return f'До цели {d} клеток. Дальность стрельбы: {reach}.'
        if self.engaged(s,p):return 'Стрельбу связывает соседний вражеский отряд: атакуйте его или смените позицию.'
        if not self.line_of_sight(p,target.pos):return 'Линию выстрела перекрывает лес, скала или высота.'
        return None

    def _power(self, s, attack):
        from combat_stats import base_power,integer_stat
        faction=self.factions[s.side]
        heroes=[h for h in self.stacks.values() if h.alive and h.side==s.side and unit_class(h.unit) in (2,3)]
        bonus=tuple(sum(integer_stat(h.unit,key) for h in heroes) for key in ('Урон','Защита','Живучесть'))
        if self.capital_bonus and s.side=='defender':bonus=(bonus[0]+100,bonus[1]+850,bonus[2])
        atk,defense=base_power(s.unit,bonus,faction,self.season_multipliers.get(faction,1))
        if '_quick_combat_power' in s.unit:
            atk,defense=s.unit['_quick_combat_power']
        value=atk if attack else defense
        if attack:
            if faction in self.spirit_factions:value*=1.15
            value*=s.unit.get('_tactical_morale_modifier',1)
            if 'blood' in s.effects:value*=.65
            if 'inspire' in s.effects:value*=1.15
        if not attack and 'fire_shield' in s.effects:
            value+=s.effects['fire_shield'].get('armor',0)
        return value*s.unit.get('_encounter_attack_multiplier' if attack else '_encounter_defense_multiplier',1)

    def army_skill_multiplier(self,source):
        total=0.0
        for soldier in self.stacks.values():
            if not soldier.alive or soldier.side!=source.side or unit_class(soldier.unit)!=1:continue
            raw=soldier.unit.get('consumption',(soldier.unit.get('units_stats') or {}).get('Потребление',0))
            try:cost=float(str(raw).replace(',','.'))
            except (TypeError,ValueError):cost=0
            if math.isfinite(cost):total+=soldier.count*max(0,cost)
        return 1+total/100

    def skill_power(self,source,attack=True):
        return self._power(source,attack)*source.count*self.army_skill_multiplier(source)

    def _resistance(self,target):
        return max(.01,self._power(target,False)/(target.health_per_unit/6))

    def _reflection(self,source,target,damage):
        shield=target.effects.get('fire_shield')
        if not shield or not source.alive or damage<=0:return None
        hit=self._hurt(source,shield.get('burn',0)/self._resistance(source),target.id)
        hit['reflection']=True
        return hit

    def _damage(self, s, target, counter=False, pos=None):
        p = pos or s.pos
        d = distance(p, target.pos)
        ranged = d > 1
        own, enemy = self.tile(p), self.tile(target.pos)
        factor = self.type_modifiers.get(s.kind, {}).get(target.kind,1)
        opposing = self.type_modifiers.get(target.kind, {}).get(s.kind,1)
        resistance = self._power(target,False) / (target.health_per_unit/6)
        resistance *= enemy.cover if ranged else enemy.melee_cover
        resistance *= 1.30 if target.guarding else 1
        resistance *= 1.35 if opposing > 1 else 1
        if own.elevation > enemy.elevation:
            factor *= 1.15
        if self.terrain[p] == 'swamp':
            factor *= .85
        if ranged:
            if s.moved:
                factor *= .75
        elif s.role in RANGE:
            factor *= .5
        elif s.role == 'cavalry' and s.moved >= 3 and self.terrain[p] not in ('swamp','forest') and self.terrain[target.pos] not in ('swamp','forest'):
            factor *= 1.25
        if counter:
            factor *= .65
        return self._power(s,True)*s.count*factor/max(.01,resistance)

    def preview(self, target, stack=None):
        s = stack or self.active
        if not self.can_attack(s,target):
            return None
        damage = self._damage(s,target)
        def lost(amount):
            remaining = max(0, math.ceil(max(0,target.hp-amount)/target.health_per_unit-1e-10))
            return target.count-remaining
        return dict(min_damage=damage*.9, max_damage=damage*1.1,
                    min_kills=lost(damage*.9), max_kills=lost(damage*1.1),
                    critical_chance=min(100,max(0,stat(s.unit,'Крит',5))),
                    retaliation=distance(s.pos,target.pos)==1 and self.can_attack(target,s) and not target.retaliated and target.hp>damage*.9)

    def _strike(self, s, target, counter=False):
        critical = self.rng.random()*100 < min(100,max(0,stat(s.unit,'Крит',5)))
        damage = self._damage(s,target,counter)*self.rng.uniform(.9,1.1)*(1.5 if critical else 1)
        hit=self._hurt(target,damage,s.id,critical,counter)
        self._leech(s,hit['damage'])
        reflection=self._reflection(s,target,hit['damage'])
        if reflection:hit['reflected']=reflection
        return hit

    def _hurt(self,target,damage,source,critical=False,counter=False):
        before=target.count
        actual=0 if self.protected(target) else min(target.hp,max(0,damage))
        target.hp=max(0,target.hp-actual)
        target.count=max(0,math.ceil(target.hp/target.health_per_unit-1e-10))
        return dict(actor=source,target=target.id,damage=actual,killed=before-target.count,
                    critical=critical,counter=counter,dead=not target.alive)

    def _heal(self,target,amount):
        if target.alive:
            target.hp=min(target.max_hp,target.hp+max(0,amount))
            target.count=min(target.initial,math.ceil(target.hp/target.health_per_unit-1e-10))

    def _leech(self,source,damage):
        if source.alive and unit_class(source.unit)==1 and 'vampirism' in source.effects:
            cap=source.effects['vampirism'].get('healing',0)/self._resistance(source)
            self._heal(source,min(damage*.25,cap))

    def attack(self, target_id):
        s, target = self.active, self.stacks.get(target_id)
        if not self.can_attack(s,target):
            raise ValueError(self.attack_block_reason(s,target))
        strikes = [self._strike(s,target)]
        if strikes[0].get('reflected'):strikes.append(strikes[0]['reflected'])
        if s.alive and target.alive and self.can_attack(target,s) and distance(s.pos,target.pos)==1 and not target.retaliated:
            target.retaliated = True
            strikes.append(self._strike(target,s,True))
            if strikes[-1].get('reflected'):strikes.append(strikes[-1]['reflected'])
        event = dict(action='attack',actor=s.id,target=target.id,strikes=strikes)
        self.events.append(event)
        self._finish()
        return event

    def defend(self):
        s = self.active
        if not s:
            raise ValueError('Бой уже закончен.')
        s.guarding = True
        event = dict(action='defend',actor=s.id)
        self.events.append(event)
        self._finish()
        return event

    def wait(self):
        s = self.active
        if not s or s.waited or s.moved:
            raise ValueError('Ожидать можно один раз, до движения.')
        s.waited = True
        self.delayed.append(self.queue.pop(0))
        event = dict(action='wait',actor=s.id)
        self.events.append(event)
        self._activate()
        return event

    def skills(self,stack=None):
        s=stack or self.active
        return hero_abilities(s.name) if s and unit_class(s.unit)>=2 else ()

    def ability_cells(self,key,pos,stack=None):
        s=stack or self.active
        if not s or pos not in self.terrain:return []
        spec=ABILITIES[key]
        if spec.target=='army':return [t.pos for t in self.stacks.values() if t.alive and t.side==s.side and unit_class(t.unit)==1]
        if spec.target=='direction':
            dx=(pos[0]>s.pos[0])-(pos[0]<s.pos[0]);dy=(pos[1]>s.pos[1])-(pos[1]<s.pos[1])
            if not dx and not dy:return []
            result=[]
            for step in range(1,5):
                p=(s.pos[0]+dx*step,s.pos[1]+dy*step)
                if p not in self.terrain or self.terrain[p]=='rock':break
                result.append(p)
            return result
        center=s.pos if spec.target=='self' else pos
        return [p for p in self.terrain if distance(p,center)<=spec.radius]

    def ability_valid(self,key,pos,stack=None):
        s=stack or self.active
        if not s or key not in self.skills(s) or s.cooldowns.get(key,0)>self.round or pos not in self.terrain:return False
        spec=ABILITIES[key]
        target=self.at(pos)
        if spec.target=='army':return any(t.alive and t.side==s.side and unit_class(t.unit)==1 for t in self.stacks.values())
        if spec.target=='self':return pos==s.pos
        if spec.target=='flight':return target is None
        if distance(s.pos,pos)>spec.reach:return False
        if spec.target=='direction':return distance(s.pos,pos)==1 and bool(self.ability_cells(key,pos,s))
        if not self.line_of_sight(s.pos,pos):return False
        if spec.target=='cell':return True
        if not target or not target.alive:return False
        if spec.target in ('ally','soldier'):
            return target.side==s.side and (spec.target!='soldier' or unit_class(target.unit)==1)
        return target.side!=s.side and not self.protected(target)

    def _effect(self,target,key,duration,source,**extra):
        target.effects[key]=dict(expires=self.round+duration+(1 if key=='drain' else 0),source=source.id,**extra)

    def _ability_damage(self,source,target,multiplier,cast_power=None):
        resistance=self._power(target,False)/(target.health_per_unit/6)
        factor=self.type_modifiers.get(source.kind,{}).get(target.kind,1)
        power=self.skill_power(source,True) if cast_power is None else cast_power
        hit=self._hurt(target,power*multiplier*factor/max(.01,resistance),source.id)
        self._leech(source,hit['damage'])
        reflection=self._reflection(source,target,hit['damage'])
        if reflection:hit['reflected']=reflection
        return hit

    def use_ability(self,key,pos):
        s=self.active
        if not self.ability_valid(key,pos,s):raise ValueError('Способность недоступна: проверьте цель, дальность и перезарядку.')
        spec=ABILITIES[key];target=self.at(pos)
        cells=self.ability_cells(key,pos,s)
        affected=[t for t in self.stacks.values() if t.alive and t.pos in cells]
        strikes=[];old=s.pos
        if key=='flight':
            s.pos=pos;s.mp=0;s.moved+=distance(old,pos)
        elif key=='heal':self._heal(target,self.skill_power(s,False)*.25/self._resistance(target))
        elif key=='inspire':
            for t in self.stacks.values():
                if t.alive and t.side==s.side and unit_class(t.unit)==1:self._effect(t,'inspire',2,s)
            if target.id not in self.bonus_activations:
                self.queue.append(target.id);self.bonus_activations.add(target.id)
        elif key=='vampirism':
            for t in self.stacks.values():
                if t.alive and t.side==s.side and unit_class(t.unit)==1:self._effect(t,'vampirism',3,s,healing=self.skill_power(s,False)*.25)
        elif key=='fire_shield':
            power=self.skill_power(s,False)*.30
            self._effect(target,key,3,s,armor=power,burn=power)
        elif key in ('freeze','dominate'):self._effect(target,key,2,s,skip=1)
        elif key=='blood':self._effect(target,key,3,s)
        elif key=='drain':
            strikes.append(self._ability_damage(s,target,.7))
            if target.alive:self._effect(target,key,3,s,damage=self.skill_power(s,True)*.08/self._resistance(target))
        elif key in ('snipe','burst'):
            for _ in range(3 if key=='burst' else 1):
                if not target.alive or not s.alive:break
                strikes.append(self._ability_damage(s,target,.65 if key=='burst' else 2.2))
        else:
            # An area hit never bypasses the hero's bodyguards by killing them
            # earlier in the same simultaneous blast.
            affected=[t for t in affected if not self.protected(t) and (key!='whirlwind' or t.side!=s.side)]
            cast_power=self.skill_power(s,True)
            for t in affected:
                strikes.append(self._ability_damage(s,t,{'grenade':1.2,'blizzard':.9,'flame':1.3,'whirlwind':1}[key],cast_power))
                if key=='blizzard' and t.alive:self._effect(t,'slow',2,s)
        s.cooldowns[key]=self.round+spec.cooldown
        strikes=[part for hit in strikes for part in ([hit,hit['reflected']] if hit.get('reflected') else [hit])]
        event=dict(action='ability',ability=key,actor=s.id,target=target.id if target else None,
                   cells=cells,strikes=strikes)
        if key=='flight':
            n=max(1,distance(old,pos))
            event['path']=[(old[0]+(pos[0]-old[0])*i/n,old[1]+(pos[1]-old[1])*i/n) for i in range(n+1)]
        self.events.append(event)
        if key=='flight':self._check_end()
        else:self._finish()
        return event

    def _ai_ability(self,s):
        enemies=[t for t in self.enemies(s) if not self.protected(t)]
        allies=[t for t in self.stacks.values() if t.alive and t.side==s.side]
        for key in self.skills(s):
            spec=ABILITIES[key]
            if s.cooldowns.get(key,0)>self.round:continue
            candidates=[]
            if key=='heal':candidates=[t.pos for t in sorted(allies,key=lambda t:t.hp/t.max_hp) if t.hp<t.max_hp*.8]
            elif key in ('fire_shield','inspire'):
                candidates=[t.pos for t in allies if unit_class(t.unit)==1 and key not in t.effects]
            elif spec.target=='army':
                if not any('vampirism' in t.effects for t in allies):candidates=[s.pos]
            elif key=='flight':
                if enemies and min(distance(s.pos,t.pos) for t in enemies)>2:
                    candidates=[p for p in self.terrain if not self.at(p) and any(distance(p,t.pos)==1 for t in enemies)]
            elif key=='whirlwind':
                if any(distance(s.pos,t.pos)==1 for t in enemies):candidates=[s.pos]
            elif key=='flame':
                candidates=[p for p in self.terrain if distance(s.pos,p)==1]
            else:candidates=[t.pos for t in sorted(enemies,key=lambda t:-self._power(t,True)*t.count)]
            for pos in candidates:
                if not self.ability_valid(key,pos,s):continue
                if spec.target in ('cell','direction'):
                    cells=self.ability_cells(key,pos,s)
                    if not any(t.pos in cells for t in enemies) or any(t.pos in cells and not self.protected(t) for t in allies):continue
                return key,pos
        return None

    def ai_step(self):
        """One legal action; same movement/visibility rules as the player."""
        s = self.active
        if not s:
            return None
        ability=self._ai_ability(s)
        if ability:return self.use_ability(*ability)
        targets = [t for t in self.enemies(s) if self.can_attack(s,t)]
        if targets:
            target = max(targets, key=lambda t: min(t.hp,self._damage(s,t))/max(1,t.max_hp)
                         + .2*self._power(t,True)*t.count/max(1,t.max_hp))
            return self.attack(target.id)
        routes = self.reachable(s)
        if not routes:
            return self.defend()
        enemies = self.enemies(s)
        # Plan across the whole field, so a detour around a lake or cliff is
        # preferred to repeatedly walking into its nearest dead end.
        cells=[p for p in self.terrain if not self.tile(p).blocked and self.at(p) in (None,s)]
        reverse={p:[] for p in cells}
        goals=[p for p in cells if any(self.can_attack(s,t,p) for t in enemies)]
        for p in cells:
            if p!=s.pos and self.engaged(s,p):
                continue
            for q,cost in self._neighbors(p,stack=s):
                reverse[q].append((p,cost))
        costs={p:0 for p in goals}
        heap=[(0,p) for p in goals]
        from heapq import heapify
        heapify(heap)
        while heap:
            cost,p=heappop(heap)
            if costs[p]!=cost:continue
            for q,step in reverse[p]:
                if cost+step<costs.get(q,float('inf')):
                    costs[q]=cost+step
                    heappush(heap,(cost+step,q))
        def score(p):
            can = [t for t in enemies if self.can_attack(s,t,p)]
            cover = self.tile(p).cover
            return (bool(can), -costs.get(p,float('inf')), cover, self.tile(p).elevation, -routes[p][0])
        best = max(routes,key=score)
        # Never shuffle away from a firing position just to spend movement.
        if not any(self.can_attack(s,t,best) for t in enemies) and costs.get(best,float('inf')) >= costs.get(s.pos,float('inf')):
            return self.defend()
        return self.move(best)

    def apply_to(self, attackers, defenders):
        if not self.winner:
            raise ValueError('Нельзя записать незавершённый бой.')
        for side, army in (('attacker',attackers),('defender',defenders)):
            living_input = [u for u in army if u.get('unit_count',0)>0]
            stacks = [s for s in self.stacks.values() if s.side == side]
            for unit, s in zip(living_input,stacks):
                unit['unit_count'] = s.count
                unit['killed_count'] = s.initial-s.count
                unit['hero_engaged'] = unit_class(unit)>=2
