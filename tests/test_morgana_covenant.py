import ast
import json
from pathlib import Path
import sqlite3
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch
import test_soul_pact as pact_tests
from test_rebel_campaign import extracted_class
import mirror_monster_quest as hunt
import morgana_covenant as covenant
from utils.resource_caps import caps


class LegacyCovenantTests(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(':memory:');self.addCleanup(self.db.close)
        self.db.executescript('''CREATE TABLE cities(name,faction);
            INSERT INTO cities VALUES('Home','Север');
            CREATE TABLE resources(faction,resource_type,amount);
            INSERT INTO resources VALUES('Север','Кроны',12345);''')

    def test_pact_read_before_first_mirror_visit_is_safe_and_read_only(self):
        before=list(self.db.iterdump())
        self.assertIsNone(hunt.pact(self.db,'Север'))
        self.assertEqual(hunt.deadline_caption(self.db,'Север'),'')
        self.assertEqual(list(self.db.iterdump()),before)

    def test_turn_initializes_dependencies_without_resetting_legacy_campaign(self):
        before_cities=list(self.db.execute('SELECT * FROM cities'))
        before_resources=list(self.db.execute('SELECT * FROM resources'))
        covenant.turn(self.db,'Север');covenant.turn(self.db,'Север')
        self.assertIsNotNone(self.db.execute("SELECT 1 FROM sqlite_master WHERE name='portal_soul_pacts'").fetchone())
        self.assertIsNone(hunt.pact(self.db,'Север'))
        self.assertIsNone(covenant.state(self.db,'Север'))
        self.assertEqual(list(self.db.execute('SELECT * FROM cities')),before_cities)
        self.assertEqual(list(self.db.execute('SELECT * FROM resources')),before_resources)

    def test_existing_pact_survives_schema_initialization(self):
        hunt.ensure_schema(self.db)
        self.db.execute("INSERT INTO portal_soul_pacts VALUES('Север',7,3,33)")
        covenant.ensure_schema(self.db);covenant.ensure_schema(self.db)
        self.assertEqual(hunt.pact(self.db,'Север'),dict(case_id=7,signed_turn=3,deadline=23))


class MorganaCovenantTests(unittest.TestCase):
    def setUp(self):
        seed=pact_tests.SoulPactTests();seed.setUp();self.addCleanup(seed.doCleanups)
        self.db=seed.db;self.party=seed.party
        self.prize=hunt.sell_soul(self.db,'Север','Hero')
        self.db.executescript('''INSERT INTO cities(id,name,faction,coordinates) VALUES
            (3,'Crypt','Нежить','[800,100]'),(4,'Enemy','Эльфы','[900,100]');
            INSERT INTO units(id,faction,unit_name,cost_money,cost_time,image_path,attack,defense,durability,unit_class,consumption,unit_type) VALUES
            (90,'Нежить','Призрак',3,1,'files/army/death/solder.png',29,7,3,'1',0.8,'infantry'),
            (91,'Нежить','Низар',0,0,'files/army/death/king_.png',800,950,80,'3',0,'mage'),
            (92,'Нежить','Моргана',0,0,'files/army/death/morgana.png',208,800,50,'2',0,'mage');
            INSERT INTO garrisons VALUES('Crypt','Призрак',24000,'files/army/death/solder.png',0);
            INSERT INTO garrisons VALUES('Crypt','Низар',1,'files/army/death/king_.png',0);
            INSERT INTO garrisons VALUES('Crypt','Моргана',1,'files/army/death/morgana.png',0);''')

    def test_offer_requires_both_sold_soul_and_undead_on_main_map(self):
        self.db.execute("UPDATE cities SET faction='Нейтрал' WHERE name='Crypt'")
        self.assertIsNone(covenant.offer(self.db,'Север'))
        self.db.execute("UPDATE cities SET faction='Нежить' WHERE name='Crypt'")
        self.assertEqual(covenant.offer(self.db,'Север')['status'],'offered')
        self.assertIsNone(covenant.offer(self.db,'Элины'))

    def test_accept_preserves_armies_and_starts_new_fifteen_turn_deadline(self):
        self.db.execute('UPDATE turn SET turn_count=7')
        hero=self.db.execute("SELECT * FROM garrisons WHERE unit_name='Hero'").fetchone()
        prize=self.db.execute('SELECT * FROM garrisons WHERE unit_name=?',(self.prize['name'],)).fetchone()
        transferred=covenant.accept(self.db,'Север')
        self.assertGreater(transferred,0)
        self.assertEqual(hunt.pact(self.db,'Север')['deadline'],22)
        self.assertEqual(hero,self.db.execute("SELECT * FROM garrisons WHERE unit_name='Hero'").fetchone())
        self.assertEqual(prize,self.db.execute('SELECT * FROM garrisons WHERE unit_name=?',(self.prize['name'],)).fetchone())
        self.assertEqual(self.db.execute("SELECT unit_count FROM garrisons WHERE unit_name='Низар'").fetchone()[0],1)
        self.assertEqual(self.db.execute("SELECT unit_count FROM garrisons WHERE unit_name='Моргана'").fetchone()[0],1)
        player=self.db.execute("SELECT SUM(g.unit_count) FROM garrisons g WHERE g.unit_name LIKE 'Легион:%'").fetchone()[0]
        remaining=self.db.execute("SELECT unit_count FROM garrisons WHERE unit_name='Призрак'").fetchone()[0]
        self.assertEqual(player+remaining,24000)
        self.assertEqual(self.db.execute("SELECT city_name FROM garrisons WHERE unit_name LIKE 'Легион:%'").fetchone()[0],self.party['camp'])
        with self.assertRaises(ValueError):covenant.accept(self.db,'Север')
        self.assertEqual(self.db.execute("SELECT SUM(g.unit_count) FROM garrisons g WHERE g.unit_name LIKE 'Легион:%'").fetchone()[0],player)

    def test_city_necropolis_and_new_captures_keep_player_control(self):
        covenant.accept(self.db,'Север')
        self.assertEqual(set(self.db.execute("SELECT faction,is_undead FROM cities WHERE name IN ('Home','Safe')")),{('Север',1)})
        self.assertEqual(covenant.presentation_faction(self.db,'Home','Север'),'Нежить')
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM buildings WHERE faction='Север'").fetchone()[0],12)
        self.db.execute("DELETE FROM buildings WHERE city_name='Home'")
        covenant.turn(self.db,'Север')
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM buildings WHERE city_name='Home'").fetchone()[0],6)
        self.db.execute("UPDATE cities SET faction='Север' WHERE name='Enemy'")
        self.assertEqual(self.db.execute("SELECT is_undead FROM cities WHERE name='Enemy'").fetchone()[0],1)

    def test_caps_permanent_and_army_limit_boosts_exactly_once(self):
        before=caps(self.db,'Север');covenant.accept(self.db,'Север')
        for kind,value in before.items():self.assertEqual(caps(self.db,'Север')[kind],round(value*1.45))
        cls=extracted_class('economic.py','Faction')
        obj=SimpleNamespace(conn=self.db,faction='Север',city_count=2,towers=2)
        self.assertEqual(cls.max_army_limit.fget(obj),10150)
        self.db.execute('UPDATE turn SET turn_count=25');covenant.turn(self.db,'Север')
        self.assertEqual(caps(self.db,'Север'),{k:round(v*1.45) for k,v in before.items()})
        self.assertEqual(caps(self.db,'Эльфы')['Кроны'],10_000_000)

    def test_living_diplomacy_is_locked_but_undead_are_allies(self):
        covenant.accept(self.db,'Север')
        for a,b in (('Север','Эльфы'),('Эльфы','Север')):
            self.assertEqual(self.db.execute('SELECT relationship FROM diplomacies WHERE faction1=? AND faction2=?',(a,b)).fetchone()[0],'война')
        self.db.execute("UPDATE diplomacies SET relationship='союз' WHERE faction1='Север' AND faction2='Эльфы'")
        self.assertEqual(self.db.execute("SELECT relationship FROM diplomacies WHERE faction1='Север' AND faction2='Эльфы'").fetchone()[0],'война')
        self.db.execute("UPDATE relations SET relationship=100 WHERE faction1='Север' AND faction2='Эльфы'")
        self.assertEqual(self.db.execute("SELECT relationship FROM relations WHERE faction1='Север' AND faction2='Эльфы'").fetchone()[0],0)
        self.db.execute("UPDATE diplomacies SET relationship='война' WHERE faction1='Нежить' AND faction2='Север'")
        self.assertEqual(self.db.execute("SELECT relationship FROM diplomacies WHERE faction1='Нежить' AND faction2='Север'").fetchone()[0],'союз')
        self.assertTrue(covenant.peace_locked(self.db,'Север','Эльфы'))
        self.assertFalse(covenant.peace_locked(self.db,'Север','Нежить'))
        self.db.execute("DELETE FROM diplomacies WHERE faction1='Север' AND faction2='Эльфы'")
        self.assertEqual(self.db.execute("SELECT relationship FROM diplomacies WHERE faction1='Север' AND faction2='Эльфы'").fetchone()[0],'война')
        self.db.execute("INSERT INTO truces(faction1,faction2,truce_until_turn) VALUES('Север','Эльфы',500)")
        self.assertFalse(list(self.db.execute('SELECT * FROM truces')))

    def test_decline_has_no_effect_and_offer_does_not_repeat(self):
        before=caps(self.db,'Север');covenant.offer(self.db,'Север');covenant.decline(self.db,'Север')
        self.assertFalse(covenant.serving(self.db,'Север'))
        self.assertEqual(caps(self.db,'Север'),before)
        self.assertEqual(covenant.offer(self.db,'Север')['status'],'declined')
        self.assertEqual(hunt.pact(self.db,'Север')['deadline'],20)

    def test_gender_choice_after_pact_changes_portrait_only(self):
        before=self.db.execute('SELECT attack,defense FROM units WHERE unit_name=?',(self.prize['name'],)).fetchone()
        for gender in ('lord','lady'):
            result=hunt.choose_gender(self.db,'Север',gender)
            case=hunt.state(self.db,'Север')
            self.assertEqual(result['image'],hunt.noble_portrait(case,hunt.noble_name(case),gender=gender))
            self.assertEqual((result['attack'],result['defense']),before)
            self.assertEqual(hunt.pact(self.db,'Север')['deadline'],20)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM units WHERE unit_name LIKE 'Спутник:%'").fetchone()[0],1)

    def test_nizar_and_morgana_attack_separately_and_do_not_target_player(self):
        covenant.accept(self.db,'Север')
        ai=SimpleNamespace(db_connection=self.db,cursor=self.db.cursor(),_undead_direct_attack=Mock())
        covenant.ally_attacks(ai)
        calls=ai._undead_direct_attack.call_args_list
        self.assertEqual({c.kwargs['hero'] for c in calls},{'Низар','Моргана'})
        self.assertTrue(all(c.args[1]=='Enemy' and c.args[2]=='Эльфы' for c in calls))

    def test_royal_capture_moves_only_selected_hero_and_detachment(self):
        covenant.accept(self.db,'Север')
        ai=SimpleNamespace(db_connection=self.db,get_defending_army=lambda city:[])
        guards=self.db.execute("SELECT unit_count FROM garrisons WHERE city_name='Crypt' AND unit_name='Призрак'").fetchone()[0]
        party=[dict(unit_name='Низар',unit_count=1,unit_image='king.png'),dict(unit_name='Призрак',unit_count=1000,unit_image='ghost.png')]
        covenant.resolve_royal_attack(ai,'Crypt','Enemy','Эльфы',party)
        self.assertEqual(self.db.execute("SELECT city_name FROM garrisons WHERE unit_name='Моргана'").fetchone()[0],'Crypt')
        self.assertEqual(self.db.execute("SELECT city_name FROM garrisons WHERE unit_name='Низар'").fetchone()[0],'Enemy')
        self.assertEqual(self.db.execute("SELECT unit_count FROM garrisons WHERE city_name='Crypt' AND unit_name='Призрак'").fetchone()[0],guards-1000)

    def test_accepted_service_survives_save_and_new_game_clears_it(self):
        covenant.accept(self.db,'Север');self.db.commit()
        saved=sqlite3.connect(':memory:');self.addCleanup(saved.close);self.db.backup(saved)
        self.assertTrue(covenant.serving(saved,'Север'))
        tree=ast.parse(Path('main.py').read_text(encoding='utf-8'));method=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='clear_tables')
        ns={'sqlite3':sqlite3};exec(compile(ast.Module(body=[method],type_ignores=[]),'main.py','exec'),ns)
        ns['clear_tables'](saved)
        self.assertFalse(covenant.serving(saved,'Север'))
        self.assertEqual(list(saved.execute('SELECT * FROM diplomacies')),[])

    def test_conquest_victory_with_allied_undead_and_deadline_priority(self):
        covenant.accept(self.db,'Север')
        self.assertFalse(covenant.won(self.db,'Север'))
        self.db.execute("UPDATE cities SET faction='Нежить' WHERE name='Enemy'")
        self.assertTrue(covenant.won(self.db,'Север'))
        tree=ast.parse(Path('economic.py').read_text(encoding='utf-8'));method=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='end_game')
        ns={};exec(compile(ast.Module(body=[method],type_ignores=[]),'economic.py','exec'),ns)
        obj=SimpleNamespace(conn=self.db,faction='Север',population=100,get_city_count=lambda:2)
        self.db.execute('UPDATE turn SET turn_count=15')
        self.assertIn('Все фракции были уничтожены',ns['end_game'](obj)[1])
        self.db.execute('UPDATE turn SET turn_count=16')
        self.assertIn('Поражение',ns['end_game'](obj)[1])


if __name__=='__main__':unittest.main()
