import ast
import sqlite3
import tempfile
import unittest
from pathlib import Path
from starting_economy import reset_starting_crowns
from tools.prepare_release_data import prepare
from city_construction import CATALOG,buy_building


class StartingEconomyTests(unittest.TestCase):
    def test_new_campaign_budget_and_special_factions(self):
        with sqlite3.connect(':memory:') as db:
            db.execute('CREATE TABLE resources(faction,resource_type,amount)')
            factions=('Север','Элины','Адепты','Вампиры','Эльфы','Нежить','Мятежники','Нейтрал')
            db.executemany('INSERT INTO resources VALUES(?,?,?)',[(f,'Кроны',50) for f in factions])
            db.execute("INSERT INTO resources VALUES('Север','Кристаллы',900)")
            reset_starting_crowns(db)
            for faction,balance in db.execute("SELECT faction,amount FROM resources WHERE resource_type='Кроны'"):
                self.assertEqual(balance,100000 if faction in ('Нежить','Мятежники') else 50 if faction=='Нейтрал' else 2500)
            self.assertEqual(db.execute("SELECT amount FROM resources WHERE resource_type='Кристаллы'").fetchone()[0],900)

    def test_starting_budget_buys_both_economic_buildings(self):
        from test_main_map_intrigues import fixture
        db=fixture();self.addCleanup(db.close)
        db.execute('DELETE FROM buildings')
        reset_starting_crowns(db)
        for name in ('Больница','Фабрика'):buy_building(db,'Дом','Север',name)
        self.assertEqual(db.execute("SELECT amount FROM resources WHERE faction='Север' AND resource_type='Кроны'").fetchone()[0],0)
        self.assertEqual({n:v['cost'] for n,v in CATALOG.items()},
            {'Больница':1000,'Фабрика':1500,'Стена':4000,'Рынок':3000,'Кузница':3000,'Цитадель':5000})

    def test_release_changes_both_packaged_tables_without_touching_source(self):
        with tempfile.TemporaryDirectory() as folder:
            source,target=Path(folder)/'source.db',Path(folder)/'release.db'
            db=sqlite3.connect(source)
            db.executescript("CREATE TABLE resources(faction,resource_type,amount);"
                "CREATE TABLE resources_default(faction,resource_type,amount);"
                "CREATE TABLE campaign_stub(id INTEGER PRIMARY KEY AUTOINCREMENT);"
                "INSERT INTO resources VALUES('Север','Кроны',98765);"
                "INSERT INTO resources_default VALUES('Север','Кроны',50);")
            db.commit();db.close()
            prepare(source,target)
            db=sqlite3.connect(target)
            for table in ('resources','resources_default'):
                self.assertEqual(db.execute('SELECT amount FROM '+table).fetchone()[0],2500)
            db.close()
            db=sqlite3.connect(source)
            self.assertEqual(db.execute('SELECT amount FROM resources').fetchone()[0],98765)
            db.close()

    def test_both_new_game_restore_paths_apply_budget_after_copy(self):
        for filename in ('main.py','results_game.py'):
            tree=ast.parse(Path(filename).read_text(encoding='utf-8'))
            restore=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='restore_from_backup')
            self.assertTrue(any(isinstance(n,ast.Call) and isinstance(n.func,ast.Name)
                and n.func.id=='reset_starting_crowns' for n in ast.walk(restore)))
