import sqlite3
import unittest
from diplomatic_gifts import city_quality,quote_gift


class GiftQuoteTests(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(':memory:');self.addCleanup(self.db.close)
        self.db.executescript('''CREATE TABLE cities(id,name,faction,kf_crystal);
            INSERT INTO cities VALUES(1,'A','Target',1.2),(2,'B','Target',2.3),(3,'C','Target',7.75),
                (4,'D','Player',1.1),(5,'E','Other',1.8),(6,'F','Нейтрал',7.75);''')
        self.power={'Target':100,'Player':200,'Other':50,'Нейтрал':100000}

    def quote(self,old=100000):return quote_gift(self.db,'Target',old,self.power.get)

    def test_three_quality_levels_and_city_count_add_to_quarter_price(self):
        q=self.quote()
        self.assertEqual(q.tiers,(1,1,1));self.assertEqual(q.cities,3);self.assertEqual(q.quality,6)
        self.assertEqual(q.base,25000);self.assertEqual(q.city_bonus,30000)
        self.assertEqual((q.army_rank,q.army_percent,q.army_bonus),(2,15,8250))
        self.assertEqual(q.total,63250)
        for value,level in ((None,1),(1,1),(1.2,1),(1.8,2),(2.3,2),(5.3,3),(7.75,3)):
            self.assertEqual(city_quality(value),level)

    def test_only_top_two_armies_have_extra_cost_and_empty_army_never_does(self):
        self.power['Target']=300
        self.assertEqual((self.quote().army_rank,self.quote().total),(1,68750))
        self.power['Target']=1
        self.assertEqual((self.quote().army_rank,self.quote().total),(3,55000))
        self.power['Target']=0
        self.assertIsNone(self.quote().army_rank);self.assertEqual(self.quote().army_bonus,0)
        self.power.update(Target=0,Player=0,Other=0)
        self.assertEqual(self.quote().total,55000)

    def test_quote_updates_after_city_quality_capture_and_army_changes(self):
        self.db.execute("UPDATE cities SET kf_crystal=5.3 WHERE id=1")
        self.assertEqual(self.quote().quality,8)
        self.db.execute("UPDATE cities SET faction='Other' WHERE id=3")
        q=self.quote();self.assertEqual(q.cities,2);self.assertEqual(q.quality,5)
        self.power['Target']=500
        self.assertEqual(self.quote().army_percent,25)

    def test_positive_ties_share_rank_and_quotes_are_read_only_whole_numbers(self):
        self.power['Target']=200
        before=self.db.total_changes;q=self.quote(100003)
        self.assertEqual(q.army_rank,1);self.assertEqual(q.total,68750)
        self.assertEqual(self.db.total_changes,before)
        self.assertIsInstance(q.total,int)

    def test_legacy_city_without_income_coefficient_uses_level_one(self):
        self.db.execute('ALTER TABLE cities DROP COLUMN kf_crystal')
        q=self.quote();self.assertEqual(q.tiers,(3,0,0));self.assertEqual(q.city_bonus,15000)


if __name__=='__main__':unittest.main()
