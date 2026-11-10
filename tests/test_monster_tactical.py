import json
from pathlib import Path
import unittest
from unittest.mock import patch
from test_monster_sites import fixture
import monster_sites as hunts
from monster_tactical import armies
from tactical_combat import TacticalBattle
from utils.garrison_stats import garrison_profiles


class MonsterTacticalTests(unittest.TestCase):
    def setUp(self):
        self.db=fixture();self.addCleanup(self.db.close)
        self.site=hunts.sites(self.db)[4]
        self.eid=hunts.begin_hunt(self.db,self.site['id'],'Север')

    def resolved(self,win=True,remaining=230):
        def choose(attackers,defenders,side,city,context,type_modifiers=None,factions=('', '')):
            self.assertFalse(self.db.in_transaction)
            self.assertEqual(side,'attacker')
            self.assertEqual(city,hunts.monster_name(self.site))
            model=TacticalBattle(attackers,defenders,**context,factions=factions)
            for stack in model.stacks.values():
                if stack.side==('defender' if win else 'attacker'):
                    stack.count=0;stack.hp=0
                elif stack.unit['unit_name']=='troop':
                    stack.count=remaining;stack.hp=remaining*stack.health_per_unit
            model._check_end()
            return model
        return choose

    def test_actual_tactical_result_and_survivors_override_quick_threshold_once(self):
        self.db.execute('UPDATE monster_expeditions SET attack=0');self.db.commit()
        with patch('tactical_battle_bridge.request_battle',side_effect=self.resolved()) as request:
            result=hunts.resolve_hunt(self.db,self.eid,allow_tactical=True)
            self.assertTrue(result['won']);self.assertEqual(result['mode'],'tactical')
            self.assertEqual((result['losses'],result['survivors']),(20,231))
            before=list(self.db.execute('SELECT amount FROM resources'))
            self.assertEqual(hunts.resolve_hunt(self.db,self.eid,allow_tactical=True),result)
            self.assertEqual(request.call_count,1)
            self.assertEqual(before,list(self.db.execute('SELECT amount FROM resources')))
        hunts.finish_hunt(self.db,self.eid)
        self.assertEqual(self.db.execute("SELECT unit_count FROM garrisons WHERE city_name='Home' AND unit_name='troop'").fetchone()[0],230)
        self.assertIsNone(hunts.expedition(self.db,self.eid))

    def test_tactical_defeat_never_grants_rewards_and_dead_troops_do_not_return(self):
        before=list(self.db.execute('SELECT amount FROM resources'))
        with patch('tactical_battle_bridge.request_battle',side_effect=self.resolved(False)):
            result=hunts.resolve_hunt(self.db,self.eid,allow_tactical=True)
        self.assertFalse(result['won']);self.assertEqual(result['losses'],251)
        self.assertEqual(before,list(self.db.execute('SELECT amount FROM resources')))
        self.assertEqual(hunts.progress(self.db,'Север')['veteran_until'],0)
        hunts.finish_hunt(self.db,self.eid)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM garrisons').fetchone()[0],0)
        self.assertEqual(next(s for s in hunts.sites(self.db) if s['id']==self.site['id'])['defeats'],0)

    def test_quick_choice_keeps_existing_outcome_and_army(self):
        with patch('tactical_battle_bridge.request_battle',return_value=None):
            result=hunts.resolve_hunt(self.db,self.eid,allow_tactical=True)
        self.assertTrue(result['won']);self.assertEqual(result['mode'],'quick')
        hunts.finish_hunt(self.db,self.eid)
        self.assertEqual(self.db.execute('SELECT SUM(unit_count) FROM garrisons').fetchone()[0],251)

    def test_stacks_use_real_garrison_power_and_every_monster_animation_reference_exists(self):
        row=hunts.expedition(self.db,self.eid)
        party,enemy=armies(self.db,row,self.site)
        profiles=garrison_profiles(self.db,row['camp'],'Север')
        model=TacticalBattle(party,enemy)
        for stack in model.stacks.values():
            if stack.side=='attacker':
                self.assertEqual(stack.unit['_quick_combat_power'],(profiles[stack.unit['unit_name']]['attack'],profiles[stack.unit['unit_name']]['defense']))
        for tier in range(1,8):
            for variant in range(1,6):
                stem='monster_'+str(tier)+('' if variant==1 else '_'+str(variant))
                meta=Path('files/army/animated/monsters',stem+'.json')
                data=json.loads(meta.read_text(encoding='utf-8'))
                self.assertTrue((meta.parent/data['image']).exists())
                self.assertTrue(all(key in data['animations'] for key in ('idle','walk','attack','hit','death')))

    def test_interrupted_choice_recovers_without_auto_victory_or_reward(self):
        before=list(self.db.execute('SELECT amount FROM resources'))
        with patch('tactical_battle_bridge.request_battle',side_effect=RuntimeError('closed')):
            with self.assertRaises(RuntimeError):hunts.resolve_hunt(self.db,self.eid,allow_tactical=True)
        self.assertEqual(hunts.expedition(self.db,self.eid)['stage'],'fighting')
        hunts.recover_hunts(self.db)
        self.assertIsNone(hunts.expedition(self.db,self.eid))
        self.assertEqual(before,list(self.db.execute('SELECT amount FROM resources')))
        self.assertEqual(self.db.execute('SELECT SUM(unit_count) FROM garrisons').fetchone()[0],251)

    def test_failed_reward_rolls_back_losses_and_reward_together(self):
        self.db.execute("CREATE TRIGGER fail_reward BEFORE UPDATE ON resources BEGIN SELECT RAISE(ABORT,'reward failure'); END")
        row=hunts.expedition(self.db,self.eid)
        with patch('tactical_battle_bridge.request_battle',side_effect=self.resolved()):
            with self.assertRaises(Exception):hunts.resolve_hunt(self.db,self.eid,allow_tactical=True)
        self.assertEqual(self.db.execute('SELECT SUM(unit_count) FROM garrisons WHERE city_name=?',(row['camp'],)).fetchone()[0],251)
        self.assertEqual(hunts.expedition(self.db,self.eid)['stage'],'fighting')

    def test_ai_hunts_do_not_open_a_player_choice(self):
        with patch('tactical_battle_bridge.request_battle') as request:
            hunts.resolve_hunt(self.db,self.eid)
            request.assert_not_called()

if __name__=='__main__':unittest.main()
