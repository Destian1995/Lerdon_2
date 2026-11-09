import ast
import json
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
        story=json.loads(hunt.state(self.db,'Север')['scenario']);hunt.accuse(self.db,'Север',story['nobles'][story['culprit']]['name'])

    def test_deal_adds_monster_without_combat_and_cannot_be_extended(self):
        before=list(self.db.execute('SELECT * FROM garrisons'))
        prize=hunt.sell_soul(self.db,'Север','Hero')
        self.assertEqual((prize['attack'],prize['defense']),(487_500_000,193_750_000))
        self.assertEqual(hunt.pact(self.db,'Север')['deadline'],20)
        self.assertEqual(hunt.state(self.db,'Север')['stage'],3)
        for row in before:self.assertIn(row,list(self.db.execute('SELECT * FROM garrisons')))
        self.assertFalse(list(self.db.execute('SELECT * FROM portal_battles')))
        with self.assertRaises(ValueError):hunt.sell_soul(self.db,'Север','Hero')
        # A new case cannot re-sell the soul or reset its original deadline.
        self.db.execute('UPDATE turn SET turn_count=15')
        hunt.begin(self.db,'Север',random.Random(4))
        self.db.execute('UPDATE portal_parties SET city_id=?',(hunt.state(self.db,'Север')['city_id'],))
        hunt.investigate(self.db,'Север');hunt.investigate(self.db,'Север')
        story=json.loads(hunt.state(self.db,'Север')['scenario']);hunt.accuse(self.db,'Север',story['nobles'][story['culprit']]['name'])
        with self.assertRaises(ValueError):hunt.sell_soul(self.db,'Север','Hero')
        self.assertEqual(hunt.pact(self.db,'Север')['deadline'],20)

    def test_deadline_survives_home_return_monster_loss_and_save_load(self):
        prize=hunt.sell_soul(self.db,'Север','Hero')
        self.db.execute("UPDATE portal_parties SET city_id=1")
        worlds.return_home(self.db,'Север')
        self.db.execute('DELETE FROM garrisons WHERE unit_name=?',(prize['name'],))
        self.db.commit();copy=sqlite3.connect(':memory:');self.addCleanup(copy.close);self.db.backup(copy)
        self.assertEqual(hunt.pact(copy,'Север')['deadline'],20)
        copy.execute('UPDATE turn SET turn_count=19');self.assertFalse(hunt.soul_loss_reason(copy,'Север'))
        copy.execute('UPDATE turn SET turn_count=20');self.assertFalse(hunt.soul_loss_reason(copy,'Север'))
        from heart_contract import expire,multiplier
        expire(copy,'Север');self.assertEqual(multiplier(copy,'Север'),.5)
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

    def test_heart_expiry_curses_army_but_campaign_and_victory_remain_available(self):
        hunt.sell_soul(self.db,'Север','Hero')
        tree=ast.parse(Path('economic.py').read_text(encoding='utf-8'))
        method=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='end_game')
        ns={};exec(compile(ast.Module(body=[method],type_ignores=[]),'economic.py','exec'),ns)
        win=False
        model=SimpleNamespace(conn=self.db,faction='Север',population=200,get_city_count=lambda:1,
                              check_all_relations_high=lambda:win,check_remaining_factions=lambda:True)
        with patch('undead_invasion.is_invasion_active',return_value=False):
            self.db.execute('UPDATE turn SET turn_count=19')
            self.assertTrue(ns['end_game'](model)[0])
            self.db.execute('UPDATE turn SET turn_count=20')
            running,reason=ns['end_game'](model)
            self.assertTrue(running)
            from heart_contract import multiplier
            self.assertEqual(multiplier(self.db,'Север'),.5)
            win=True
            self.assertEqual(ns['end_game'](model),(False,'Мир во всем мире'))
            self.db.execute('UPDATE turn SET turn_count=21')
            self.assertEqual(ns['end_game'](model),(False,'Мир во всем мире'))

    def test_new_campaign_clears_pact(self):
        hunt.sell_soul(self.db,'Север','Hero')
        tree=ast.parse(Path('main.py').read_text(encoding='utf-8'))
        method=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='clear_tables')
        ns={'sqlite3':sqlite3};exec(compile(ast.Module(body=[method],type_ignores=[]),'main.py','exec'),ns)
        ns['clear_tables'](self.db)
        self.assertIsNone(hunt.pact(self.db,'Север'))

    def test_correct_accusation_offers_deal_while_noble_keeps_human_appearance(self):
        from PIL import Image
        case=hunt.state(self.db,'Север')
        self.assertTrue(hunt.identified(case));self.assertFalse(hunt.revealed(case))
        self.assertTrue(Path(hunt.noble_image(case)).is_file())
        for gender in ('lord','lady'):
            with Image.open('files/otherworld/companions/noble-'+gender+'.jpg') as art:
                self.assertEqual(art.size,(960,640))
        with self.assertRaises(ValueError):hunt.fight(self.db,'Север','Hero',lambda *a,**k:None)
        hunt.sell_soul(self.db,'Север','Hero')
        self.assertFalse(hunt.revealed(hunt.state(self.db,'Север')))

    def test_refusal_reveals_monster_and_closes_deal(self):
        self.assertIn('сбрасывает',hunt.reject_soul(self.db,'Север'))
        self.assertTrue(hunt.revealed(hunt.state(self.db,'Север')))
        with self.assertRaises(ValueError):hunt.sell_soul(self.db,'Север','Hero')
        def win(unit,guard,*a,**k):guard['unit_count']=0
        self.assertTrue(hunt.fight(self.db,'Север','Hero',win)['won'])
        self.assertIsNone(hunt.pact(self.db,'Север'))

    def test_shapes_recalculate_from_base_without_stacking_and_work_after_return(self):
        prize=hunt.sell_soul(self.db,'Север','Hero')
        for _ in range(8):
            monster=hunt.set_form(self.db,'Север','monster')
            self.assertEqual((monster['attack'],monster['defense']),(162_500_000,581_250_000))
            noble=hunt.set_form(self.db,'Север','noble')
            self.assertEqual((noble['attack'],noble['defense']),(487_500_000,193_750_000))
        self.assertEqual(hunt.pact(self.db,'Север')['deadline'],20)
        self.db.execute('UPDATE portal_parties SET city_id=1');worlds.return_home(self.db,'Север')
        shape=hunt.set_form(self.db,'Север','monster')
        self.assertEqual(self.db.execute('SELECT unit_image FROM garrisons WHERE unit_name=?',(prize['name'],)).fetchone()[0],shape['image'])
        self.db.commit();saved=sqlite3.connect(':memory:');self.addCleanup(saved.close);self.db.backup(saved)
        self.assertEqual(hunt.companion_form(saved,'Север')['form'],'monster')
        self.assertEqual(hunt.companion_form(saved,'Север')['base_attack'],325_000_000)
        self.db.execute('DELETE FROM garrisons WHERE unit_name=?',(prize['name'],))
        with self.assertRaises(ValueError):hunt.set_form(self.db,'Север','noble')
        self.assertEqual(hunt.pact(self.db,'Север')['deadline'],20)

    def test_old_pact_gains_shapes_once_without_moving_deadline(self):
        prize=hunt.sell_soul(self.db,'Север','Hero')
        self.db.execute('DELETE FROM portal_companion_forms')
        self.db.execute('UPDATE units SET attack=325000000,defense=387500000 WHERE unit_name=?',(prize['name'],))
        data=hunt.companion_form(self.db,'Север')
        self.assertEqual(data['base_attack'],325_000_000)
        before=list(self.db.iterdump());hunt.companion_form(self.db,'Север')
        self.assertEqual(list(self.db.iterdump()),before)
        self.assertEqual(hunt.pact(self.db,'Север')['deadline'],20)

    def test_each_faction_has_distinct_lord_and_lady_army_portraits(self):
        from PIL import Image
        import hashlib
        paths=[];hashes=[]
        for faction,names in hunt.NOBLES.items():
            for name in names[:2]:
                case=dict(faction=faction,scenario=json.dumps(dict(nobles=[dict(name=name)],culprit=0)))
                path=Path(hunt.noble_image(case));paths.append(path)
                with Image.open(path) as art:self.assertEqual(art.size,(960,640))
                hashes.append(hashlib.sha256(path.read_bytes()).hexdigest())
        self.assertEqual(len(set(paths)),10);self.assertEqual(len(set(hashes)),10)
        manifest=json.loads(Path('assets/noble-faction-art-prompts.json').read_text(encoding='utf-8'))
        self.assertEqual({Path(a['file']) for a in manifest['assets']},set(paths))
        for asset in manifest['assets']:
            self.assertEqual(hashlib.sha256(Path(asset['file']).read_bytes()).hexdigest(),asset['sha256'])

    def test_existing_noble_portrait_refreshes_without_changing_stats_or_pact(self):
        prize=hunt.sell_soul(self.db,'Север','Hero')
        before=self.db.execute('SELECT attack,defense FROM units WHERE unit_name=?',(prize['name'],)).fetchone()
        pact=hunt.pact(self.db,'Север').copy()
        self.db.execute('UPDATE units SET image_path=? WHERE unit_name=?',('old-lady.jpg',prize['name']))
        self.db.execute('UPDATE garrisons SET unit_image=? WHERE unit_name=?',('old-lady.jpg',prize['name']))
        hunt.companion_form(self.db,'Север')
        image=hunt.noble_image(hunt.state(self.db,'Север'))
        self.assertEqual(self.db.execute('SELECT attack,defense,image_path FROM units WHERE unit_name=?',(prize['name'],)).fetchone(),(*before,image))
        self.assertEqual(self.db.execute('SELECT unit_image FROM garrisons WHERE unit_name=?',(prize['name'],)).fetchone()[0],image)
        self.assertEqual(hunt.pact(self.db,'Север'),pact)


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
