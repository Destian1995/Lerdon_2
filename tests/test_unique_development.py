import ast
from pathlib import Path
import sqlite3
from types import SimpleNamespace
import unittest
from city_construction import CATALOG,ensure_unique_buildings,building_counts,buy_building
from city_development import auto_develop,average_loyalty
from ai_resource_requests import request_amount,accept_request


def fixture():
    db=sqlite3.connect(':memory:')
    db.executescript('''CREATE TABLE cities(id,name,faction,coordinates,is_undead);
        INSERT INTO cities VALUES(1,'A','Север','[100,100]',0),(2,'B','Север','[200,100]',0);
        CREATE TABLE buildings(city_name,faction,building_type,count);
        CREATE TABLE resources(faction,resource_type,amount);
        INSERT INTO resources VALUES('Север','Кроны',1000000),('Север','Кристаллы',1234567),('Эльфы','Кроны',100);
        CREATE TABLE nobles(loyalty,status);
        INSERT INTO nobles VALUES(81,'active'),(79,'active'),(100,'eliminated');
        CREATE TABLE turn(turn_count);INSERT INTO turn VALUES(0);
        CREATE TABLE negotiation_history(id INTEGER PRIMARY KEY,faction1,faction2,message,is_player);''')
    db.commit();return db


def methods(file,cls,names):
    source=ast.parse(Path(file).read_text(encoding='utf-8'))
    base=next(n for n in source.body if isinstance(n,ast.ClassDef) and n.name==cls)
    nodes=[n for n in base.body if isinstance(n,ast.FunctionDef) and n.name in names]
    namespace={'sqlite3':sqlite3}
    exec(compile(ast.Module(body=nodes,type_ignores=[]),file,'exec'),namespace)
    return {n.name:namespace[n.name] for n in nodes}


class UniqueDevelopmentTests(unittest.TestCase):
    def setUp(self):self.db=fixture();self.addCleanup(self.db.close)

    def money(self):return self.db.execute("SELECT amount FROM resources WHERE faction='Север' AND resource_type='Кроны'").fetchone()[0]

    def test_legacy_duplicates_collapse_and_future_counts_stay_unique(self):
        self.db.executemany('INSERT INTO buildings VALUES(?,?,?,?)',[('A','Север','Больница',12),('A','Север','Больница',3),('B','Север','Фабрика',11)])
        ensure_unique_buildings(self.db)
        self.assertEqual(building_counts(self.db,'A','Север'),{'Больница':1})
        self.assertEqual(building_counts(self.db,'B','Север'),{'Фабрика':1})
        self.db.execute('UPDATE buildings SET count=9')
        self.assertEqual(self.db.execute('SELECT SUM(count) FROM buildings').fetchone()[0],2)
        with self.assertRaises(sqlite3.IntegrityError):self.db.execute("INSERT INTO buildings VALUES('A','Север','Больница',1)")

    def test_exactly_80_is_manual_then_above_80_builds_all_six_in_each_city_once(self):
        self.assertEqual(average_loyalty(self.db),80)
        self.assertEqual(auto_develop(self.db,'Север'),[]);self.assertEqual(self.money(),1000000)
        self.db.execute("UPDATE nobles SET loyalty=81 WHERE status='active'")
        self.assertEqual(len(auto_develop(self.db,'Север')),12)
        expected=1000000-2*sum(x['cost'] for x in CATALOG.values())
        self.assertEqual(self.money(),expected)
        for city in ('A','B'):self.assertEqual(building_counts(self.db,city,'Север'),dict.fromkeys(CATALOG,1))
        self.assertEqual(auto_develop(self.db,'Север'),[]);self.assertEqual(self.money(),expected)

    def test_no_council_and_falling_loyalty_pause_auto_but_manual_is_available(self):
        self.db.execute('DELETE FROM nobles')
        self.assertFalse(auto_develop(self.db,'Север'))
        buy_building(self.db,'A','Север','Больница')
        self.db.execute("INSERT INTO nobles VALUES(90,'active')")
        auto_develop(self.db,'Север')
        self.db.execute("INSERT INTO cities VALUES(3,'C','Север','[300,100]',0)")
        self.db.execute('UPDATE nobles SET loyalty=80')
        self.assertFalse(auto_develop(self.db,'Север'))
        self.assertFalse(building_counts(self.db,'C','Север'))

    def test_low_budget_builds_affordable_missing_types_without_duplicate_charges(self):
        self.db.execute("UPDATE nobles SET loyalty=90")
        self.db.execute("UPDATE resources SET amount=100 WHERE faction='Север' AND resource_type='Кроны'")
        built=auto_develop(self.db,'Север');self.assertEqual(len(built),4);self.assertEqual(self.money(),0)
        self.assertFalse(auto_develop(self.db,'Север'))
        with self.assertRaises(ValueError):buy_building(self.db,'A','Север','Больница')

    def test_real_player_auto_method_does_not_require_obsolete_ratio_setting(self):
        self.db.execute('UPDATE nobles SET loyalty=90')
        cls=type('Player',(),methods('economic.py','Faction',['auto_build']))
        model=cls();model.conn=self.db;model.faction='Север';model.auto_build_enabled=False
        model.resources={};model.load_buildings=lambda:None
        self.assertEqual(len(model.auto_build()),12)
        self.assertTrue(model.auto_build_enabled);self.assertEqual(model.money,self.money())

    def test_real_ai_uses_all_six_buildings_and_persists_same_price(self):
        names=['load_cities','load_buildings','load_resources','update_buildings_for_current_cities',
               'save_resources_to_db','manage_buildings','build_in_city','save_buildings']
        cls=type('AI',(),methods('ii.py','AIController',names))
        ai=cls();ai.db_connection=self.db;ai.cursor=self.db.cursor();ai.faction='Север'
        ai.resources={'Кроны':1000000,'Кристаллы':1234567};ai.buildings={};ai.cities_buildings={}
        self.assertEqual(len(ai.manage_buildings()),12)
        self.assertEqual(ai.resources['Кроны'],self.money())
        self.assertTrue(all(len(v['Здания'])==6 for v in ai.buildings.values()))
        ai.save_buildings();before=self.money();self.assertFalse(ai.manage_buildings())
        self.assertEqual(self.money(),before)


class AidRequestTests(unittest.TestCase):
    def setUp(self):self.db=fixture();self.addCleanup(self.db.close)

    def letter(self):
        kind,amount,text=request_amount(self.db,'Север',{'Кроны':1000,'Кристаллы':0})
        message='[ПРОСЬБА] '+text
        self.db.execute('INSERT INTO negotiation_history VALUES(1,?,?,?,0)',('Эльфы','Север',message));self.db.commit()
        return kind,amount,message

    def test_full_actual_balance_is_quoted_exactly_and_transferred_once(self):
        kind,amount,message=self.letter()
        self.assertEqual((kind,amount),('Кристаллы',1234567));self.assertIn('1234567',message)
        self.assertTrue(accept_request(self.db,'Север','Эльфы',message)[0])
        self.assertEqual(self.db.execute("SELECT amount FROM resources WHERE faction='Север' AND resource_type='Кристаллы'").fetchone()[0],0)
        self.assertFalse(accept_request(self.db,'Север','Эльфы',message)[0])
        self.assertEqual(self.db.execute("SELECT amount FROM resources WHERE faction='Эльфы' AND resource_type='Кристаллы'").fetchone()[0],1234567)

    def test_stale_request_cannot_overdraw_or_claim_payment(self):
        kind,amount,message=self.letter()
        self.db.execute("UPDATE resources SET amount=100 WHERE faction='Север' AND resource_type='Кристаллы'")
        self.assertFalse(accept_request(self.db,'Север','Эльфы',message)[0])
        self.assertFalse(self.db.execute('SELECT 1 FROM resource_aid_payments').fetchone())
        self.db.execute('UPDATE resources SET amount=0')
        self.assertIsNone(request_amount(self.db,'Север',{}))

    def test_real_ai_letter_quotes_live_player_stock_without_abbreviation(self):
        sent=[]
        ai=SimpleNamespace(db_connection=self.db,resources={'Кроны':1000,'Кристаллы':0},turn=12,
            _get_game_context=lambda:{'our_cities':2,'our_strength':1},
            _get_player_faction_name=lambda:'Север',
            _send_diplomatic_message=lambda kind,text:sent.append((kind,text)) or True)
        send=methods('ii.py','AIController',['_try_send_resource_request'])['_try_send_resource_request']
        self.assertTrue(send(ai,{},50))
        self.assertEqual(sent[0][0],'ПРОСЬБА')
        self.assertIn('Просим передать 1234567 кристаллов.',sent[0][1])
