import ast
import sqlite3
from pathlib import Path
from types import SimpleNamespace
import unittest

from utils.resource_payments import spend_resources, sync_resources, exchange_resources, ensure_resource_schema


class ResourcePaymentTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:')
        self.db.executescript('''CREATE TABLE resources(faction,resource_type,amount);
            INSERT INTO resources VALUES('Север','Кроны',2000000),('Север','Рабочие',200),
            ('Север','Кристаллы',500),('Эльфы','Кроны',100),('Эльфы','Кристаллы',1000);''')
        self.model = SimpleNamespace(conn=self.db, resources={}, money=0, free_peoples=0)
        sync_resources(self.db, 'Север', self.model)

    def tearDown(self):
        self.db.close()

    def test_paid_operation_persists_and_refreshes_memory(self):
        tree = ast.parse(Path('diversion.py').read_text(encoding='utf-8'))
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'CalculateCash')
        namespace = {}
        exec(compile(ast.Module(body=[cls], type_ignores=[]), 'diversion.py', 'exec'), namespace)
        cash = namespace['CalculateCash']('Север', self.model)
        for amount in (700000, 1000000, 100000):
            self.assertTrue(cash.deduct_resources(amount))
        self.assertEqual(self.model.money, 200000)
        self.assertEqual(cash.load_resources()['Кроны'], 200000)
        self.assertFalse(cash.deduct_resources(700000))
        self.assertEqual(cash.load_resources()['Кроны'], 200000)

    def test_insufficient_second_resource_rolls_back_first(self):
        self.assertFalse(spend_resources(self.db, 'Север', {'Кроны': 500, 'Рабочие': 201}))
        self.assertEqual(sync_resources(self.db, 'Север')['Кроны'], 2000000)

    def test_legacy_duplicate_crowns_do_not_block_or_multiply_event_payment(self):
        self.db.execute('DROP INDEX resources_faction_type')
        self.db.execute("INSERT INTO resources VALUES('Север','Кроны',2000000)")
        self.assertTrue(spend_resources(self.db, 'Север', {'Кроны': 18200 + 4431}))
        rows = self.db.execute("SELECT amount FROM resources WHERE faction='Север' AND resource_type='Кроны'").fetchall()
        self.assertEqual(rows, [(2000000 - 22631,)])
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("INSERT INTO resources VALUES('Север','Кроны',2000000)")

    def test_migration_keeps_latest_displayed_balance_instead_of_summing(self):
        self.db.execute('DROP INDEX resources_faction_type')
        self.db.execute("INSERT INTO resources VALUES('Север','Кроны',2400000)")
        ensure_resource_schema(self.db)
        ensure_resource_schema(self.db)
        self.assertEqual(sync_resources(self.db, 'Север')['Кроны'], 2400000)
        self.assertEqual(sync_resources(self.db, 'Эльфы')['Кроны'], 100)

    def test_duplicate_legacy_rows_do_not_allow_unaffordable_payment(self):
        self.db.execute('DROP INDEX resources_faction_type')
        self.db.execute("INSERT INTO resources VALUES('Север','Кроны',100)")
        self.assertFalse(spend_resources(self.db, 'Север', {'Кроны': 101}))
        self.assertEqual(sync_resources(self.db, 'Север')['Кроны'], 100)

    def test_schema_repair_does_not_commit_the_callers_transaction(self):
        self.db.execute('DROP INDEX resources_faction_type')
        self.db.execute("UPDATE resources SET amount=123 WHERE faction='Север' AND resource_type='Кроны'")
        ensure_resource_schema(self.db)
        self.assertTrue(self.db.in_transaction)
        self.db.rollback()
        amount = self.db.execute("SELECT amount FROM resources WHERE faction='Север' AND resource_type='Кроны'").fetchone()[0]
        self.assertEqual(amount, 2000000)

    def test_invalid_amounts_cannot_credit_or_corrupt_balance(self):
        for amount in (-100, float('nan'), float('inf')):
            self.assertFalse(spend_resources(self.db, 'Север', {'Кроны': amount}))
        self.assertEqual(sync_resources(self.db, 'Север')['Кроны'], 2000000)

    def test_exchange_checks_both_parties_and_is_atomic(self):
        self.assertFalse(exchange_resources(self.db, 'Север', 'Эльфы', 'Кроны', 100, 'Кристаллы', 1001))
        self.assertEqual(sync_resources(self.db, 'Север')['Кроны'], 2000000)
        self.assertTrue(exchange_resources(self.db, 'Север', 'Эльфы', 'Кроны', 100, 'Кристаллы', 300))
        self.assertEqual(sync_resources(self.db, 'Север')['Кроны'], 1999900)
        self.assertEqual(sync_resources(self.db, 'Север')['Кристаллы'], 800)
        self.assertEqual(sync_resources(self.db, 'Эльфы')['Кроны'], 200)
        self.assertEqual(sync_resources(self.db, 'Эльфы')['Кристаллы'], 700)

    def test_rebellion_revalidates_current_city_owner_before_payment(self):
        tree = ast.parse(Path('diversion.py').read_text(encoding='utf-8'))
        node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'validate_operation_target')
        ns = {}
        exec(compile(ast.Module(body=[node], type_ignores=[]), 'diversion.py', 'exec'), ns)
        self.db.executescript('''CREATE TABLE cities(name,faction); CREATE TABLE garrisons(city_name,unit_count);
            CREATE TABLE units(unit_name); INSERT INTO units VALUES('Кейдж'),('Мятежники');
            INSERT INTO cities VALUES('Цель','Эльфы');''')
        info = {'Эльфы': {'cities_without_garrison': ['Старая цель']}}
        check = ns[node.name]
        self.assertIsNone(check(self.db, 'Север', 'Мятеж', {}, 'Эльфы', info))
        self.assertEqual(info['Эльфы']['cities_without_garrison'], ['Цель'])
        self.db.execute("UPDATE cities SET faction='Север'")
        self.assertIsNotNone(check(self.db, 'Север', 'Мятеж', {}, 'Эльфы', info))
        self.assertEqual(sync_resources(self.db, 'Север')['Кроны'], 2000000)


if __name__ == '__main__':
    unittest.main()
