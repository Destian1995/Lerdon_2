import sqlite3
import unittest
from unittest.mock import Mock
from test_army_intelligence import fixture
import army_intelligence as intel


class PaidIntelligenceTests(unittest.TestCase):
    def setUp(self):
        self.db=fixture();self.addCleanup(self.db.close)
        self.db.executescript('''CREATE TABLE relations(faction1,faction2,relationship,UNIQUE(faction1,faction2));
            INSERT INTO relations VALUES('Север','Адепты',40),('Адепты','Север',40);
            INSERT INTO cities VALUES('Дальний','Адепты'),('Башни','Адепты');''')

    def balance(self):return self.db.execute("SELECT amount FROM resources WHERE faction='Север'").fetchone()[0]

    def test_user_example_and_empire_rate_cap(self):
        price=intel.quote(self.db,'Север','Адепты')
        self.assertEqual((price.cities,price.rate,price.relation_cost,price.total),(3,5000,300000,451000))
        self.db.executemany('INSERT INTO cities VALUES(?,?)',[(f'C{i}','Адепты') for i in range(10)])
        self.assertEqual(intel.quote(self.db,'Север','Адепты').rate,9000)

    def test_success_pays_exact_quote_and_rolls_discovery_once(self):
        rng=Mock();rng.random.return_value=.4
        before=self.balance();result=intel.gather(self.db,'Север','Адепты','Дом',rng=rng,expected_cost=451000)
        self.assertEqual(self.balance(),before-451000)
        self.assertFalse(result['detected']);self.assertEqual(intel.relation(self.db,'Север','Адепты'),40)
        with self.assertRaises(ValueError):intel.gather(self.db,'Север','Адепты','Дом',rng=rng)
        self.assertEqual(self.balance(),before-451000);rng.random.assert_called_once()

    def test_detection_immediately_lowers_both_relations_by_35(self):
        rng=Mock();rng.random.return_value=.399
        result=intel.gather(self.db,'Север','Адепты','Дом',rng=rng)
        self.assertTrue(result['detected'])
        self.assertEqual(list(self.db.execute('SELECT relationship FROM relations')),[(5,),(5,)])
        self.assertTrue(intel.visible(self.db,'Север','Адепты'))

    def test_insufficient_money_and_changed_quotes_do_not_charge_or_roll(self):
        rng=Mock();before=self.balance()
        with self.assertRaises(ValueError):intel.gather(self.db,'Север','Адепты','Дом',expected_cost=1,rng=rng)
        self.assertEqual(self.balance(),before)
        self.db.execute('UPDATE resources SET amount=450999')
        with self.assertRaises(ValueError):intel.gather(self.db,'Север','Адепты','Дом',rng=rng)
        self.assertEqual(self.balance(),450999);self.assertFalse(intel.visible(self.db,'Север','Адепты'))
        rng.random.assert_not_called()

    def test_failed_report_rolls_back_money_and_diplomatic_penalty(self):
        intel.gather(self.db,'Север','Адепты','Дом',rng=Mock(random=lambda:1))
        self.db.execute('UPDATE turn SET turn_count=7')
        self.db.execute("CREATE TRIGGER fail_intel BEFORE INSERT ON map_army_intelligence BEGIN SELECT RAISE(ABORT,'fail');END")
        before=self.balance();rng=Mock();rng.random.return_value=0
        with self.assertRaises(sqlite3.IntegrityError):intel.gather(self.db,'Север','Адепты','Дом',rng=rng)
        self.assertEqual(self.balance(),before)
        self.assertEqual(intel.relation(self.db,'Север','Адепты'),40)


if __name__=='__main__':unittest.main()
