"""Real SQLite cases, combat losses, one-time rewards and season snapshots."""
import json
from pathlib import Path
import random
import sqlite3
import unittest
from test_otherworlds import fixture
import otherworlds as worlds
import otherworld_quests as quests
import mirror_monster_quest as hunt


class MonsterCaseTests(unittest.TestCase):
    def setUp(self):
        self.db=fixture();self.addCleanup(self.db.close)
        self.db.executescript('CREATE TABLE season(id PRIMARY KEY,current_season,season_index); INSERT INTO season VALUES(1,"Зима",0);')
        self.party=worlds.enter(self.db,'Север','Home')

    def accept(self,seed=3):
        hunt.begin(self.db,'Север',random.Random(seed))
        return hunt.state(self.db,'Север')

    def arrive(self):
        self.db.execute('UPDATE portal_parties SET city_id=? WHERE faction=?',(hunt.state(self.db,'Север')['city_id'],'Север'))

    def reveal(self):
        self.accept();self.arrive()
        hunt.investigate(self.db,'Север');hunt.investigate(self.db,'Север')
        story=json.loads(hunt.state(self.db,'Север')['scenario']);hunt.accuse(self.db,'Север',story['nobles'][story['culprit']]['name'])
        hunt.reject_soul(self.db,'Север')

    @staticmethod
    def win(unit,guard,*args,**kwargs):guard['unit_count']=0

    def test_accept_is_optional_persistent_and_freezes_season_and_bonuses(self):
        self.assertIsNone(quests.state(self.db,'Север'))
        resources=list(self.db.execute('SELECT * FROM resources'))
        case=self.accept()
        self.assertIn(case['city_id'],range(2,8))
        for key in ('attack_bonus','defense_bonus'):self.assertTrue(142<=case[key]<=271)
        self.db.execute('UPDATE season SET season_index=2')
        self.assertEqual(hunt.state(self.db,'Север'),case)
        self.assertEqual(hunt.monster(case)['attack'],325_000_000)
        self.assertIsNone(quests.state(self.db,'Север'))
        self.assertEqual(resources,list(self.db.execute('SELECT * FROM resources')))
        self.assertIn(case['city_id'],quests.objectives(self.db,'Север'))
        self.db.commit();saved=sqlite3.connect(':memory:');self.addCleanup(saved.close)
        self.db.backup(saved)
        self.assertEqual(hunt.state(saved,'Север'),case)
        with self.assertRaises(ValueError):hunt.begin(saved,'Север')

    def test_monster_has_requested_base_and_fixed_acceptance_season_multipliers(self):
        case=self.accept()
        strengths=[hunt.monster(dict(case,season=i))['attack'] for i in range(4)]
        self.assertEqual(strengths,[325_000_000,234_000_000,169_000_000,252_200_000])
        self.assertEqual(hunt.monster(dict(case,season=1))['defense'],279_000_000)
        self.assertEqual(hunt.monster(case)['defense'],387_500_000)

    def test_clues_and_fight_are_location_and_stage_gated(self):
        self.accept()
        with self.assertRaises(ValueError):hunt.investigate(self.db,'Север')
        with self.assertRaises(ValueError):hunt.fight(self.db,'Север','Hero',self.win)
        self.arrive();hunt.investigate(self.db,'Север')
        self.assertEqual(hunt.state(self.db,'Север')['stage'],1)
        with self.assertRaises(ValueError):hunt.fight(self.db,'Север','Hero',self.win)
        hunt.investigate(self.db,'Север')
        self.assertEqual(hunt.state(self.db,'Север')['stage'],2)
        with self.assertRaises(ValueError):hunt.fight(self.db,'Север','absent',self.win)

    def test_two_clues_identify_exactly_one_noble_in_each_random_case(self):
        culprits=set()
        for seed in range(18):
            case=self.accept(seed);story=json.loads(case['scenario'])
            culprit=story['nobles'][story['culprit']];culprits.add(story['culprit'])
            crest=[n for n in story['nobles'] if n['crest']==culprit['crest']]
            mark=[n for n in story['nobles'] if n['mark']==culprit['mark']]
            self.assertEqual(len(crest),2);self.assertEqual(len(mark),2)
            self.assertEqual([n for n in crest if n in mark],[culprit])
            self.assertIn(culprit['crest'],story['witness']);self.assertIn(culprit['mark'],story['clue'])
            self.assertFalse(hunt.revealed(case))
            self.db.execute('UPDATE portal_monster_cases SET stage=3,finished_turn=0 WHERE id=?',(case['id'],))
            self.db.execute('UPDATE turn SET turn_count=15')
        self.assertEqual(culprits,{0,1,2})

    def test_accusation_is_required_and_wrong_guess_does_not_unlock_monster(self):
        self.accept();self.arrive();case=hunt.state(self.db,'Север');story=json.loads(case['scenario'])
        culprit=story['nobles'][story['culprit']]['name']
        with self.assertRaises(ValueError):hunt.accuse(self.db,'Север',culprit)
        first=hunt.investigate(self.db,'Север');second=hunt.investigate(self.db,'Север')
        self.assertNotIn(story['monster'],first+second)
        with self.assertRaises(ValueError):hunt.fight(self.db,'Север','Hero',self.win)
        with self.assertRaises(ValueError):hunt.sell_soul(self.db,'Север','Hero')
        wrong=story['nobles'][(story['culprit']+1)%3]['name']
        self.assertIn('ошибочно',hunt.accuse(self.db,'Север',wrong))
        self.assertFalse(hunt.revealed(hunt.state(self.db,'Север')))
        self.assertIsNone(hunt.pact(self.db,'Север'))
        with self.assertRaises(ValueError):hunt.fight(self.db,'Север','Hero',self.win)
        self.assertNotIn(story['monster'],hunt.accuse(self.db,'Север',culprit))
        self.assertFalse(hunt.revealed(hunt.state(self.db,'Север')))
        with self.assertRaises(ValueError):hunt.fight(self.db,'Север','Hero',self.win)
        hunt.reject_soul(self.db,'Север')
        exposed=hunt.state(self.db,'Север')
        self.assertTrue(hunt.revealed(exposed))
        self.assertEqual((exposed['attack_bonus'],exposed['defense_bonus']),(case['attack_bonus'],case['defense_bonus']))
        with self.assertRaises(ValueError):hunt.accuse(self.db,'Север',culprit)
        self.assertTrue(hunt.fight(self.db,'Север','Hero',self.win)['won'])

    def test_every_faction_uses_shared_season_rules_for_attack_and_defense(self):
        from faction_seasons import FACTION_EFFECTS
        from test_rebel_campaign import extracted_class
        season_manager=extracted_class('seasons.py','SeasonManager')
        self.assertIs(season_manager.FACTION_EFFECTS,FACTION_EFFECTS)
        case=self.accept()
        for faction in hunt.NOBLES:
            for season,effects in enumerate(FACTION_EFFECTS):
                profile=hunt.monster(dict(case,faction=faction,season=season))
                percent=round(effects[faction]['stat']*100)
                self.assertEqual(profile['attack'],260_000_000*percent//100)
                self.assertEqual(profile['defense'],310_000_000*percent//100)
        self.assertEqual(hunt.monster(dict(case,faction='Элины',season=2))['attack'],455_000_000)

    def test_already_revealed_legacy_case_keeps_access_to_battle(self):
        self.reveal();case=hunt.state(self.db,'Север');story=json.loads(case['scenario'])
        for key in ('nobles','culprit','revealed','cleared'):story.pop(key)
        self.db.execute('UPDATE portal_monster_cases SET scenario=? WHERE id=?',(json.dumps(story),case['id']))
        self.assertTrue(hunt.revealed(hunt.state(self.db,'Север')))
        self.assertTrue(hunt.fight(self.db,'Север','Hero',self.win)['won'])

    def test_victory_awards_exactly_one_ordinary_companion_to_winning_party(self):
        self.reveal();case=hunt.state(self.db,'Север')
        before=list(self.db.execute('SELECT * FROM resources'))
        result=hunt.fight(self.db,'Север','Hero',self.win)
        self.assertTrue(result['won']);prize=result['companion']
        self.assertEqual(prize['attack'],100_000_000*(1000+case['attack_bonus'])//1000)
        self.assertEqual(prize['defense'],100_000_000*(1000+case['defense_bonus'])//1000)
        for key in ('attack','defense'):self.assertTrue(114_200_000<=prize[key]<=127_100_000)
        self.assertEqual(self.db.execute('SELECT city_name,unit_count FROM garrisons WHERE unit_name=?',(prize['name'],)).fetchone(),(self.party['camp'],1))
        self.assertEqual(self.db.execute('SELECT unit_class,unit_type FROM units WHERE unit_name=?',(prize['name'],)).fetchone(),('1','archer'))
        self.assertEqual(hunt.state(self.db,'Север')['hero'],'Hero')
        self.assertEqual(hunt.state(self.db,'Север')['stage'],3)
        self.assertEqual(before,list(self.db.execute('SELECT * FROM resources')))
        self.assertEqual(list(self.db.execute('SELECT * FROM portal_guard_buffs')),[])
        self.assertEqual(list(self.db.execute('SELECT * FROM portal_battles')),[])
        self.assertIsNone(quests.state(self.db,'Север'))
        self.assertEqual(quests.pending(self.db,'Север'),[])
        with self.assertRaises(ValueError):hunt.fight(self.db,'Север','Hero',self.win)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM units WHERE unit_name LIKE 'Спутник:%'").fetchone()[0],1)
        self.db.execute("UPDATE portal_parties SET city_id=1 WHERE faction='Север'")
        worlds.return_home(self.db,'Север')
        self.assertEqual(self.db.execute('SELECT city_name,unit_count FROM garrisons WHERE unit_name=?',(prize['name'],)).fetchone(),('Home',1))
        self.assertEqual(self.db.execute('SELECT attack,defense FROM units WHERE unit_name=?',(prize['name'],)).fetchone(),(prize['attack'],prize['defense']))

    def test_loss_does_not_issue_reward_or_complete_case(self):
        self.reveal()
        def lose(unit,guard,*args,**kwargs):unit['unit_count']=0
        result=hunt.fight(self.db,'Север','Hero',lose)
        self.assertFalse(result['won']);self.assertIsNone(result['companion'])
        self.assertEqual(hunt.state(self.db,'Север')['stage'],2)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM units WHERE unit_name LIKE 'Спутник:%'").fetchone()[0],0)

    def test_monster_victory_cannot_complete_war_in_same_city(self):
        quests.begin(self.db,'Север',random.Random(4))
        self.reveal()
        run=quests.state(self.db,'Север');scenario=quests.details(run)
        scenario['war']['target']=hunt.state(self.db,'Север')['city_id']
        self.db.execute('UPDATE portal_quest_runs SET war=2,side=?,scenario=?',
                        (scenario['war']['sides'][0],json.dumps(scenario)))
        result=hunt.fight(self.db,'Север','Hero',self.win)
        self.assertTrue(result['won']);self.assertFalse(result['quest_win'])
        self.assertEqual(quests.state(self.db,'Север')['war'],2)
        self.assertFalse(quests.pending(self.db,'Север'))

    def test_companions_are_excluded_from_recruitment_and_direct_hire(self):
        import ast
        from test_rebel_campaign import extracted_class
        self.reveal();result=hunt.fight(self.db,'Север','Hero',self.win)
        name=result['companion']['name']
        ai_class=extracted_class('ii.py','AIController');ai=ai_class.__new__(ai_class)
        ai.cursor=self.db.cursor();ai.faction='Север'
        self.assertNotIn(name,ai.load_army())
        tree=ast.parse(Path('army.py').read_text(encoding='utf-8'))
        node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='load_unit_data')
        ns={};exec(compile(ast.Module(body=[node],type_ignores=[]),'army.py','exec'),ns)
        self.assertNotIn(name,ns['load_unit_data']('Север',self.db))
        cls=extracted_class('army.py','ArmyCash')
        self.assertFalse(cls.hire_unit(object(),name,(0,0),1,{},''))

    def test_combat_error_rolls_back_losses_and_case(self):
        self.reveal();before=list(self.db.iterdump())
        def fail(unit,guard,*args,**kwargs):
            unit['unit_count']=0;raise RuntimeError('interrupted')
        with self.assertRaises(RuntimeError):hunt.fight(self.db,'Север','Hero',fail)
        self.assertEqual(list(self.db.iterdump()),before)

    def test_new_stories_do_not_repeat_until_pool_exhausted_and_art_exists(self):
        keys=set();pictures=set()
        for i in range(len(hunt.STORIES)):
            case=self.accept(i);story=json.loads(case['scenario'])
            keys.add(story['key']);pictures.add(hunt.monster(case)['unit_image'])
            self.assertTrue(Path(hunt.monster(case)['unit_image']).is_file())
            self.db.execute('UPDATE portal_monster_cases SET stage=3,finished_turn=0 WHERE id=?',(case['id'],))
            self.db.execute('UPDATE turn SET turn_count=?',(hunt.COOLDOWN,))
        self.assertEqual(len(keys),len(hunt.STORIES));self.assertGreater(len(pictures),1)

    def test_cooldown_and_missing_hero_block_new_cases(self):
        case=self.accept()
        self.db.execute('UPDATE portal_monster_cases SET stage=3,finished_turn=0 WHERE id=?',(case['id'],))
        with self.assertRaises(ValueError):self.accept()
        self.db.execute('UPDATE turn SET turn_count=?',(hunt.COOLDOWN,))
        self.db.execute("DELETE FROM garrisons WHERE unit_name='Hero'")
        with self.assertRaises(ValueError):self.accept()

    def test_new_game_clears_case_and_history(self):
        import ast
        self.accept()
        tree=ast.parse(Path('main.py').read_text(encoding='utf-8'))
        method=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='clear_tables')
        ns={'sqlite3':sqlite3};exec(compile(ast.Module(body=[method],type_ignores=[]),'main.py','exec'),ns)
        ns['clear_tables'](self.db)
        self.assertIsNone(hunt.state(self.db,'Север'))


if __name__=='__main__':unittest.main()
