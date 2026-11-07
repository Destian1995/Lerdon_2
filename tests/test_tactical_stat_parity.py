"""Independent balance cases, live army scaling, and database handoff."""
import copy
import sqlite3
import unittest
from test_tactical_combat import unit
from test_tactical_abilities import arena
from test_battle_ui import combat_namespace
from tactical_combat import TacticalBattle
from combat_stats import base_power


class TacticalStatParityTests(unittest.TestCase):
    def test_northern_soldier_keeps_quick_auras_faction_xp_relief_and_spirit(self):
        soldier=unit('Солдат',100,attack=10,defense=20)
        soldier['units_stats']['Живучесть']=8
        soldier.update(_experience_multiplier=1.15,_terrain_defense_multiplier=1.3)
        hero=unit('Герой',1,attack=300,defense=200,cls=3)
        hero['units_stats']['Живучесть']=40
        legend=unit('Легенда',1,attack=9999,defense=9999,cls=4)
        m=TacticalBattle([soldier,hero,legend],[unit('Враг')],factions=('Север',''),
                          season_multipliers={'Север':2.75},spirit_factions=('Север',))
        s=m.stacks['attacker:0']
        self.assertAlmostEqual(m._power(s,True),int(310*(1.8*2.75))*1.15*1.15)
        self.assertAlmostEqual(m._power(s,False),(24+200+20)*1.15*1.3)
        self.assertAlmostEqual(base_power(soldier,(300,200,40),'Север',2.75)[0],1764.1)

    def test_adept_and_rebel_and_zombie_rules_remain_unchanged(self):
        s=unit('Воин',attack=10,defense=2)
        s['_experience_multiplier']=1.25
        atk,defense=base_power(s,(300,200,40),'Адепты',2.75)
        self.assertEqual(atk,310*1.25)
        self.assertEqual(defense,int(222*(1.55*2.75))*1.25)
        self.assertEqual(base_power(s,(300,200,40),'Мятежники'),((6+300)*1.25,(1.2+220)*1.25))
        s['unit_name']='Зомби'
        self.assertEqual(base_power(s,(300,200,40),'Нежить'),(10*1.25,2*1.25))

    def test_one_fighter_at_2_point_1_consumption_adds_2_point_1_percent(self):
        m,a,g,b,h=arena('Владислав')
        g.count=1;g.unit['consumption']=2.1
        self.assertAlmostEqual(m.army_skill_multiplier(a),1.021)
        g.count=100
        self.assertAlmostEqual(m.army_skill_multiplier(a),3.1)
        g.count=50
        self.assertAlmostEqual(m.army_skill_multiplier(a),2.05)
        g.count=0;g.hp=0
        self.assertEqual(m.army_skill_multiplier(a),1)

    def test_only_friendly_living_class_one_units_count_toward_skill_scaling(self):
        m,a,g,b,h=arena('Владислав')
        a.unit['consumption']=1000;h.unit['consumption']=1000;b.unit['consumption']=1000
        g.unit['units_stats']['Потребление']='2,1';g.count=10
        self.assertAlmostEqual(m.army_skill_multiplier(a),1.21)
        g.unit['consumption']=0
        self.assertEqual(m.army_skill_multiplier(a),1)

    def test_offensive_abilities_scale_from_hero_attack_and_current_army(self):
        results=[]
        for cost in (0,2.1):
            m,a,g,b,h=arena('Владислав');g.count=100;g.unit['consumption']=cost
            event=m.use_ability('snipe',b.pos)
            results.append(event['strikes'][0]['damage'])
        self.assertAlmostEqual(results[1]/results[0],3.1)
        m,a,g,b,h=arena('Владислав');before=m.skill_power(a,True)
        a.unit['units_stats']['Защита']*=3
        self.assertEqual(m.skill_power(a,True),before)
        a.unit['units_stats']['Урон']*=2
        self.assertEqual(m.skill_power(a,True),before*2)

    def test_shield_strength_uses_defense_not_attack_or_incoming_damage(self):
        powers=[]
        for defense,cost in ((1000,0),(2000,0),(1000,2.1)):
            m,a,g,b,h=arena('Кристол');g.count=100;g.unit['consumption']=cost
            a.unit['units_stats']['Защита']=defense
            m.use_ability('fire_shield',g.pos)
            powers.append(g.effects['fire_shield']['armor'])
        self.assertEqual(powers,[300,600,930])

    def test_drain_is_fixed_to_cast_attack_instead_of_enemy_max_health(self):
        ticks=[]
        for count in (1000,2000):
            m,a,g,b,h=arena('Валерия');b.max_hp*=count/1000;b.hp=b.max_hp
            m.use_ability('drain',b.pos)
            ticks.append(b.effects['drain']['damage'])
        self.assertEqual(ticks[0],ticks[1])

    def test_campaign_enrichment_transfers_upkeep_even_on_legacy_unit_schema(self):
        db=sqlite3.connect(':memory:');self.addCleanup(db.close)
        db.execute('CREATE TABLE units(unit_name TEXT,consumption REAL)')
        db.execute("INSERT INTO units VALUES('Воин',2.1)")
        army=[unit()]
        combat_namespace()['_enrich_with_db_stats'](army,db)
        self.assertEqual(army[0]['consumption'],2.1)

    def test_mirror_completed_profile_is_not_buffed_or_rounded_twice(self):
        s=unit();s.update(_quick_combat_power=(1234,5678),_experience_multiplier=1.25)
        m=TacticalBattle([s,unit('Герой',1,cls=3)],[unit('Враг')],morale_rules=False)
        for _ in range(3):
            self.assertEqual(m._power(m.stacks['attacker:0'],True),1234)
            self.assertEqual(m._power(m.stacks['attacker:0'],False),5678)
            m._new_round()


if __name__=='__main__':unittest.main()
