import ast
from pathlib import Path
import random
import sqlite3
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch
from test_otherworlds import fixture
from test_rebel_campaign import extracted_class
import otherworlds as worlds
import mirror_monster_quest as hunt


class SoulPactTests(unittest.TestCase):
    def setUp(self):
        self.db=fixture();self.addCleanup(self.db.close)
        self.db.executescript('CREATE TABLE season(id,season_index); INSERT INTO season VALUES(1,0);')
        self.party=worlds.enter(self.db,'Север','Home')
        hunt.begin(self.db,'Север',random.Random(3))
        self.db.execute('UPDATE portal_parties SET city_id=?',(hunt.state(self.db,'Север')['city_id'],))
        hunt.investigate(self.db,'Север');hunt.investigate(self.db,'Север')

    def test_deal_adds_monster_without_combat_and_cannot_be_extended(self):
        before=list(self.db.execute('SELECT * FROM garrisons'))
        prize=hunt.sell_soul(self.db,'Север','Hero')
        self.assertEqual((prize['attack'],prize['defense']),(1_040_000_000,1_240_000_000))
        self.assertEqual(hunt.pact(self.db,'Север')['deadline'],30)
        self.assertEqual(hunt.state(self.db,'Север')['stage'],3)
        for row in before:self.assertIn(row,list(self.db.execute('SELECT * FROM garrisons')))
        self.assertFalse(list(self.db.execute('SELECT * FROM portal_battles')))
        with self.assertRaises(ValueError):hunt.sell_soul(self.db,'Север','Hero')
        # A new case cannot re-sell the soul or reset its original deadline.
        self.db.execute('UPDATE turn SET turn_count=15')
        hunt.begin(self.db,'Север',random.Random(4))
        self.db.execute('UPDATE portal_parties SET city_id=?',(hunt.state(self.db,'Север')['city_id'],))
        hunt.investigate(self.db,'Север');hunt.investigate(self.db,'Север')
        with self.assertRaises(ValueError):hunt.sell_soul(self.db,'Север','Hero')
        self.assertEqual(hunt.pact(self.db,'Север')['deadline'],30)

    def test_deadline_survives_home_return_monster_loss_and_save_load(self):
        prize=hunt.sell_soul(self.db,'Север','Hero')
        self.db.execute("UPDATE portal_parties SET city_id=1")
        worlds.return_home(self.db,'Север')
        self.db.execute('DELETE FROM garrisons WHERE unit_name=?',(prize['name'],))
        self.db.commit();copy=sqlite3.connect(':memory:');self.addCleanup(copy.close);self.db.backup(copy)
        self.assertEqual(hunt.pact(copy,'Север')['deadline'],30)
        copy.execute('UPDATE turn SET turn_count=29');self.assertFalse(hunt.soul_loss_reason(copy,'Север'))
        copy.execute('UPDATE turn SET turn_count=30');self.assertIn('Поражение',hunt.soul_loss_reason(copy,'Север'))
        self.assertFalse(hunt.soul_loss_reason(copy,'Эльфы'))

    def test_invalid_deal_does_not_issue_unit_or_deadline(self):
        with self.assertRaises(ValueError):hunt.sell_soul(self.db,'Север','Absent')
        self.db.execute('UPDATE portal_parties SET city_id=1')
        with self.assertRaises(ValueError):hunt.sell_soul(self.db,'Север','Hero')
        self.assertIsNone(hunt.pact(self.db,'Север'))
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM units WHERE unit_name LIKE 'Спутник:%'").fetchone()[0],0)

    def test_failed_award_rolls_back_both_pact_and_companion(self):
        self.db.execute("CREATE TRIGGER no_companion BEFORE INSERT ON garrisons WHEN NEW.unit_name LIKE 'Спутник:%' BEGIN SELECT RAISE(ABORT,'interrupted'); END")
        before=list(self.db.iterdump())
        with self.assertRaises(sqlite3.IntegrityError):hunt.sell_soul(self.db,'Север','Hero')
        self.assertEqual(list(self.db.iterdump()),before)

    def test_campaign_deadline_defeat_and_last_turn_victory(self):
        hunt.sell_soul(self.db,'Север','Hero')
        tree=ast.parse(Path('economic.py').read_text(encoding='utf-8'))
        method=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='end_game')
        ns={};exec(compile(ast.Module(body=[method],type_ignores=[]),'economic.py','exec'),ns)
        win=False
        model=SimpleNamespace(conn=self.db,faction='Север',population=200,get_city_count=lambda:1,
                              check_all_relations_high=lambda:win,check_remaining_factions=lambda:True)
        with patch('undead_invasion.is_invasion_active',return_value=False):
            self.db.execute('UPDATE turn SET turn_count=29')
            self.assertTrue(ns['end_game'](model)[0])
            self.db.execute('UPDATE turn SET turn_count=30')
            running,reason=ns['end_game'](model)
            self.assertFalse(running);self.assertIn('душу',reason)
            win=True
            self.assertEqual(ns['end_game'](model),(False,'Мир во всем мире'))
            self.db.execute('UPDATE turn SET turn_count=31')
            self.assertIn('душу',ns['end_game'](model)[1])

    def test_new_campaign_clears_pact(self):
        hunt.sell_soul(self.db,'Север','Hero')
        tree=ast.parse(Path('main.py').read_text(encoding='utf-8'))
        method=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='clear_tables')
        ns={'sqlite3':sqlite3};exec(compile(ast.Module(body=[method],type_ignores=[]),'main.py','exec'),ns)
        ns['clear_tables'](self.db)
        self.assertIsNone(hunt.pact(self.db,'Север'))


class VictoryRankTests(unittest.TestCase):
    def test_only_victory_assigns_rank_even_on_direct_calculation(self):
        db=sqlite3.connect(':memory:');self.addCleanup(db.close)
        db.executescript('''CREATE TABLE dossier(faction,military_rank,avg_military_rating_per_faction,
            avg_soldiers_starving,battle_victories,battle_defeats);
            INSERT INTO dossier VALUES('Север','Прежнее звание',100,0,5,0);
            INSERT INTO dossier VALUES('Эльфы','Эльфийское звание',100,0,5,0);''')
        cls=extracted_class('results_game.py','ResultsGame');obj=cls('lose','',db);obj.current_faction='Север'
        for status in ('lose','unknown'):
            obj.game_status=status;obj.calculate_military_rank()
            self.assertEqual(db.execute("SELECT military_rank FROM dossier WHERE faction='Север'").fetchone()[0],'Прежнее звание')
        obj.game_status='win';obj.calculate_military_rank()
        self.assertNotEqual(db.execute("SELECT military_rank FROM dossier WHERE faction='Север'").fetchone()[0],'Прежнее звание')
        self.assertEqual(db.execute("SELECT military_rank FROM dossier WHERE faction='Эльфы'").fetchone()[0],'Эльфийское звание')

    def test_result_screen_calls_rank_assignment_only_for_win(self):
        cls=extracted_class('results_game.py','ResultsGame');obj=cls('lose','',None)
        obj.update_dossier_stats=Mock();obj.calculate_military_rank=Mock()
        obj.calculate_results=lambda:[];obj.show_results_popup=Mock()
        obj.show_results('Север','lose','Сделка истекла')
        obj.calculate_military_rank.assert_not_called()
        obj.show_results('Север','win','Мир во всем мире')
        obj.calculate_military_rank.assert_called_once()


if __name__=='__main__':unittest.main()
