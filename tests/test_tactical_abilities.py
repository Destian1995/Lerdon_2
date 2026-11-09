import unittest
from test_tactical_combat import unit
from tactical_combat import TacticalBattle,unit_class
from tactical_abilities import HEROES,ABILITIES


def arena(name):
    hero=unit(name,1,attack=1000,defense=1000,initiative=100,cls=3)
    guard=unit('Солдаты',200,initiative=10)
    m=TacticalBattle([hero,guard],[unit('Враг',1000,initiative=50),unit('Чужой герой',1,cls=3)])
    a,g,b,h=list(m.stacks.values())
    a.pos=(3,4);g.pos=(1,1);b.pos=(5,4);h.pos=(8,5)
    m.terrain={p:'plain' for p in m.terrain}
    return m,a,g,b,h


class HeroAbilityTests(unittest.TestCase):
    def test_every_requested_hero_and_all_abilities_are_available(self):
        expected={'Владислав':3,'Ольга':2,'Арн-гот':2,'Кристол':1,'Сестра Милосердия':2,
                  'Агилар':2,'Валерия':1,'Изабэлл':2,'Дитрих Фрост':1}
        keys=set()
        for name,count in expected.items():
            m,*_=arena(name);self.assertEqual(len(m.skills()),count);keys.update(m.skills())
        from tactical_abilities import TROOPS
        self.assertEqual(keys,set(ABILITIES)-set(TROOPS))

    def test_bodyguards_protect_heroes_from_shots_counters_area_and_dot(self):
        m,a,g,b,h=arena('Владислав')
        self.assertTrue(m.protected(a));self.assertTrue(m.protected(h))
        a.pos=(7,5)
        self.assertFalse(m.can_attack(a,h))
        self.assertFalse(m.ability_valid('snipe',h.pos))
        old=a.hp
        m._hurt(a,1e12,b.id)
        self.assertEqual(a.hp,old)
        m._effect(a,'drain',3,b);m._new_round()
        self.assertEqual(a.hp,old)
        g.count=0;g.hp=0
        m._hurt(a,200,b.id)
        self.assertEqual(a.hp,old-200)
        self.assertFalse(m.protected(a))

    def test_snipe_and_burst_damage_and_cooldowns(self):
        for key in ('snipe','burst'):
            m,a,g,b,h=arena('Владислав');old=b.hp
            event=m.use_ability(key,b.pos)
            self.assertLess(b.hp,old)
            self.assertEqual(len(event['strikes']),3 if key=='burst' else 1)
            self.assertEqual(a.cooldowns[key],1+ABILITIES[key].cooldown)
            m.queue.insert(0,a.id)
            with self.assertRaises(ValueError):m.use_ability(key,b.pos)

    def test_grenade_and_blizzard_have_friendly_fire_and_preserve_hero_shield(self):
        for name,key in (('Владислав','grenade'),('Ольга','blizzard')):
            m,a,g,b,h=arena(name);g.pos=(4,4);h.pos=(5,5)
            old=(a.hp,g.hp,b.hp,h.hp)
            m.use_ability(key,b.pos)
            self.assertLess(g.hp,old[1]);self.assertLess(b.hp,old[2])
            self.assertEqual(a.hp,old[0]);self.assertEqual(h.hp,old[3])
            if key=='blizzard':self.assertIn('slow',b.effects)

    def test_freeze_and_dominate_skip_exactly_one_activation(self):
        for name,key in (('Ольга','freeze'),('Изабэлл','dominate')):
            m,a,g,b,h=arena(name)
            m.use_ability(key,b.pos)
            self.assertTrue(any(e['action']=='skip' and e['actor']==b.id for e in m.events))
            self.assertEqual(b.effects[key]['skip'],0)
            m._new_round()
            self.assertEqual(b.effects[key]['skip'],0)

    def test_area_blast_still_hits_all_targets_if_caster_dies_in_the_same_blast(self):
        m,a,g,b,h=arena('Владислав')
        g.count=0;g.hp=0;a.hp=1;b.pos=(4,4)
        old=b.hp
        m.use_ability('grenade',b.pos)
        self.assertFalse(a.alive)
        self.assertLess(b.hp,old)

    def test_dragon_flight_ignores_obstacles_and_allows_attack_after_landing(self):
        m,a,g,b,h=arena('Арн-гот');m.terrain[4,4]='water'
        event=m.use_ability('flight',(4,4))
        self.assertEqual(a.pos,(4,4));self.assertIs(m.active,a);self.assertEqual(a.mp,0)
        self.assertTrue(m.can_attack(a,b));self.assertGreater(len(event['path']),1)
        self.assertFalse(m.ability_valid('flight',g.pos))

    def test_fire_is_four_cells_in_selected_direction(self):
        m,a,g,b,h=arena('Арн-гот')
        self.assertEqual(m.ability_cells('flame',(4,4)),[(4,4),(5,4),(6,4),(7,4)])
        self.assertFalse(m.ability_valid('flame',(6,4)))
        old=b.hp;m.use_ability('flame',(4,4));self.assertLess(b.hp,old)

    def test_fire_shield_reflects_actual_damage_without_recursion(self):
        m,a,g,b,h=arena('Кристол');m.use_ability('fire_shield',g.pos)
        g.pos=(4,4);old=b.hp
        hit=m._strike(b,g)
        self.assertIn('reflected',hit);self.assertLess(b.hp,old)
        self.assertAlmostEqual(hit['reflected']['damage'],g.effects['fire_shield']['burn']/m._resistance(b))
        self.assertGreater(m._power(g,False),1100)

    def test_sister_heals_and_inspiration_grants_one_extra_soldier_turn(self):
        m,a,g,b,h=arena('Сестра Милосердия')
        g.hp*=.5;g.count=100
        expected=g.hp+m.skill_power(a,False)*.25/m._resistance(g)
        m.use_ability('heal',g.pos)
        self.assertAlmostEqual(g.hp,expected)
        m,a,g,b,h=arena('Сестра Милосердия')
        m.use_ability('inspire',g.pos)
        self.assertEqual(m.queue.count(g.id),2)
        self.assertIn(g.id,m.bonus_activations)
        self.assertIn('inspire',g.effects)

    def test_whirlwind_hits_neighbors_only_and_does_not_hit_friends(self):
        m,a,g,b,h=arena('Агилар');b.pos=(4,4);g.pos=(3,5)
        old=(g.hp,b.hp,h.hp)
        m.use_ability('whirlwind',a.pos)
        self.assertEqual(g.hp,old[0]);self.assertLess(b.hp,old[1]);self.assertEqual(h.hp,old[2])

    def test_drain_ticks_three_rounds_and_expires(self):
        m,a,g,b,h=arena('Валерия')
        m.use_ability('drain',b.pos);start=b.hp
        tick=b.effects['drain']['damage']
        for _ in range(3):m._new_round()
        self.assertAlmostEqual(b.hp,start-tick*3)
        m._new_round();self.assertNotIn('drain',b.effects)

    def test_army_vampirism_heals_only_regular_troops_from_actual_damage(self):
        m,a,g,b,h=arena('Изабэлл')
        m.use_ability('vampirism',a.pos)
        self.assertIn('vampirism',g.effects);self.assertNotIn('vampirism',a.effects)
        g.hp*=.5;g.count=100;before=g.hp
        cap=g.effects['vampirism']['healing']/m._resistance(g)
        hit=m._strike(g,b)
        self.assertAlmostEqual(g.hp,min(g.max_hp,before+min(hit['damage']*.25,cap)))

    def test_blood_reduces_enemy_attack_and_expires(self):
        m,a,g,b,h=arena('Дитрих Фрост');before=m._power(b,True)
        m.use_ability('blood',b.pos)
        self.assertAlmostEqual(m._power(b,True),before*.65)
        for _ in range(4):m._new_round()
        self.assertNotIn('blood',b.effects)

    def test_ai_uses_hero_abilities_with_the_same_validation(self):
        m,a,g,b,h=arena('Владислав')
        event=m.ai_step()
        self.assertEqual(event['action'],'ability');self.assertEqual(event['ability'],'snipe')


if __name__=='__main__':unittest.main()
