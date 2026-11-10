import hashlib
import json
from pathlib import Path
import sqlite3
import unittest
from PIL import Image
from test_main_map_intrigues import fixture
import main_map_intrigues as plots
from tavern_art import tavern_path,city_tavern
from town_art import THEMES,city_variant


class TavernPoliciesTests(unittest.TestCase):
    def setUp(self):self.db=fixture();self.addCleanup(self.db.close)

    def ready(self,kind,city='Дом'):
        self.db.execute('INSERT INTO map_city_secrets(faction,city,kind,stage,economy_version) VALUES(?,?,?,2,2)',('Север',city,kind))

    def stock(self):return self.db.execute("SELECT amount FROM resources WHERE faction='Север' AND resource_type='Кроны'").fetchone()[0]

    def test_caravan_reward_uses_current_stock_once_and_all_relations_both_directions(self):
        self.db.executescript("CREATE TABLE relations(faction1,faction2,relationship,UNIQUE(faction1,faction2));"
            "INSERT INTO relations VALUES('Север','Адепты',10),('Адепты','Север',10),('Север','Эльфы',80),('Эльфы','Север',80),('Адепты','Эльфы',65);")
        self.ready('tribute','Нейтральный')
        plots.resolve_secret(self.db,'Север','Нейтральный','exploit')
        self.assertEqual(self.stock(),135000)
        rows={(a,b):v for a,b,v in self.db.execute('SELECT * FROM relations')}
        self.assertEqual(rows[('Север','Адепты')],0);self.assertEqual(rows[('Адепты','Север')],0)
        self.assertEqual(rows[('Север','Эльфы')],55);self.assertEqual(rows[('Эльфы','Север')],55)
        self.assertEqual(rows[('Адепты','Эльфы')],65)
        with self.assertRaises(ValueError):plots.resolve_secret(self.db,'Север','Нейтральный','exploit')
        self.assertEqual(self.stock(),135000)

    def test_arrest_debits_ten_percent_of_live_stock_and_caps_relation_at_100(self):
        self.ready('tribute','Нейтральный')
        self.db.executescript("CREATE TABLE relations(faction1,faction2,relationship,UNIQUE(faction1,faction2)); INSERT INTO relations VALUES('Север','Эльфы',99);")
        self.db.execute("UPDATE resources SET amount=123456 WHERE resource_type='Кроны'")
        plots.resolve_secret(self.db,'Север','Нейтральный','expose')
        self.assertEqual(self.stock(),111111)
        self.assertEqual(self.db.execute("SELECT relationship FROM relations WHERE faction1='Север' AND faction2='Эльфы'").fetchone()[0],100)

    def test_caravan_quote_respects_storage_limit_and_transaction_failure_rolls_back_reward(self):
        self.ready('tribute','Нейтральный')
        self.db.execute("UPDATE resources SET amount=9999999 WHERE resource_type='Кроны'")
        self.assertEqual(plots.caravan_quote(self.db,'Север','exploit')['actual'],1)
        self.db.executescript("CREATE TABLE relations(faction1,faction2,relationship); INSERT INTO relations VALUES('Север','Адепты',50);"
            "CREATE TRIGGER reject_relation BEFORE UPDATE ON relations BEGIN SELECT RAISE(ABORT,'failure'); END;")
        with self.assertRaises(sqlite3.DatabaseError):plots.resolve_secret(self.db,'Север','Нейтральный','exploit')
        self.assertEqual(self.stock(),9999999)
        self.assertEqual(plots.secret(self.db,'Север','Нейтральный')['stage'],2)

    def test_city_quality_weights_only_that_city_and_disconnected_city_has_no_effect(self):
        self.db.execute('ALTER TABLE cities ADD COLUMN kf_crystal REAL DEFAULT 0')
        self.db.execute("INSERT INTO cities VALUES(6,'Второй','Север',3)")
        self.db.execute("INSERT INTO buildings VALUES('Второй','Север','Фабрика',1)")
        self.db.execute("INSERT INTO buildings VALUES('Второй','Север','Больница',1)")
        self.db.execute('INSERT INTO roads VALUES(1,6)')
        self.ready('factory');plots.resolve_secret(self.db,'Север','Дом','exploit')
        self.assertEqual(plots.economy_adjustments(self.db,'Север',crystals=10000,growth=400,tax_growth=100),
                         dict(crowns=0,crystals=300,population=-37))
        self.db.execute("INSERT INTO cities VALUES(7,'Третий','Север',0)")
        self.db.execute('DELETE FROM roads');self.db.execute('INSERT INTO roads VALUES(6,7)')
        self.assertEqual(plots.economy_adjustments(self.db,'Север',crystals=10000,growth=400),dict(crowns=0,crystals=0,population=0))

    def test_old_save_is_upgraded_without_repeating_historical_rewards_or_reactivating_after_capture(self):
        self.db.execute('DROP TRIGGER intrigue_policy_capture_reset');self.db.execute('DROP TABLE map_city_secrets')
        self.db.executescript("CREATE TABLE map_city_secrets(faction,city,kind,stage,last_turn,resolution,until_turn,PRIMARY KEY(faction,city));"
            "INSERT INTO map_city_secrets VALUES('Север','Дом','factory',3,0,'exploit',5);")
        stock=self.stock()
        self.assertEqual(plots.economy_adjustments(self.db,'Север',crystals=10000)['crystals'],1500)
        plots.ensure_schema(self.db);self.assertEqual(self.stock(),stock)
        self.db.execute("UPDATE cities SET faction='Адепты' WHERE name='Дом'")
        self.db.execute("UPDATE cities SET faction='Север' WHERE name='Дом'")
        plots.ensure_schema(self.db)
        self.assertEqual(plots.economy_adjustments(self.db,'Север',crystals=10000)['crystals'],0)

    def test_companion_leaves_all_camps_at_zero_and_cannot_reappear_after_load_or_form_switch(self):
        from test_soul_pact import SoulPactTests
        import mirror_monster_quest as hunt
        case=SoulPactTests();case.setUp();self.addCleanup(case.doCleanups)
        db=case.db;prize=hunt.claim_heart(db,'Север','Hero');plots.ensure_schema(db)
        db.execute("INSERT INTO garrisons(city_name,unit_name,unit_count,unit_image) VALUES('OtherCamp',?,1,'')",(prize['name'],))
        for _ in range(3):plots.react(db,'Север',False)
        self.assertFalse(db.execute('SELECT 1 FROM garrisons WHERE unit_name=?',(prize['name'],)).fetchone())
        self.assertEqual(db.execute('SELECT loyalty,departed FROM map_companion_temper').fetchone(),(0,1))
        self.assertTrue(db.execute("SELECT 1 FROM garrisons WHERE unit_name='Hero'").fetchone())
        with self.assertRaises(ValueError):hunt.set_form(db,'Север','monster')
        db.commit();saved=sqlite3.connect(':memory:');self.addCleanup(saved.close);db.backup(saved)
        plots.advance(saved,'Север');plots.react(saved,'Север',True)
        self.assertFalse(saved.execute('SELECT 1 FROM garrisons WHERE unit_name=?',(prize['name'],)).fetchone())

    def test_monster_won_in_battle_also_reacts_and_leaves_without_a_shape_contract(self):
        from test_soul_pact import SoulPactTests
        import mirror_monster_quest as hunt
        case=SoulPactTests();case.setUp();self.addCleanup(case.doCleanups)
        db=case.db;hunt.reject_soul(db,'Север')
        def win(army,guard,*args,**kwargs):guard['unit_count']=0
        prize=hunt.fight(db,'Север','Hero',win)['companion'];plots.ensure_schema(db)
        self.assertFalse(db.execute('SELECT 1 FROM portal_companion_forms').fetchone())
        plots.react(db,'Север',False)
        attack=db.execute('SELECT attack FROM units WHERE unit_name=?',(prize['name'],)).fetchone()[0]
        self.assertEqual(attack,int(prize['attack']*1.05))
        plots.react(db,'Север',False);plots.react(db,'Север',False)
        self.assertFalse(db.execute('SELECT 1 FROM garrisons WHERE unit_name=?',(prize['name'],)).fetchone())
        self.assertEqual(db.execute('SELECT departed FROM map_companion_temper').fetchone()[0],1)


class TavernArtTests(unittest.TestCase):
    def test_all_24_taverns_are_unique_valid_and_follow_the_city_panorama_variant(self):
        paths=set()
        names={city_variant('Town'+str(i)):'Town'+str(i) for i in range(100)}
        self.assertEqual(set(names),{1,2,3})
        for faction in THEMES:
            for variant,city in names.items():
                path=Path(tavern_path(faction,city));self.assertTrue(path.is_file(),path);paths.add(path)
                self.assertEqual(path.name,'tavern-'+str(variant)+'.png')
                with Image.open(path) as image:
                    self.assertGreater(image.width,image.height);self.assertLessEqual(max(image.size),2048)
        self.assertEqual(len(paths),24)
        self.assertEqual(len({hashlib.sha256(p.read_bytes()).digest() for p in paths}),24)


if __name__=='__main__':unittest.main()
