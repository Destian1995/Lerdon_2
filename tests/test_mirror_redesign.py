"""Real persistence and economy checks for the new investigation and mixer."""
import random
import sqlite3
import unittest
from test_otherworlds import fixture
import otherworlds as w
import otherworld_quests as q


class InvestigationTests(unittest.TestCase):
    def setUp(self):
        self.db=fixture();self.addCleanup(self.db.close)
        w.enter(self.db,'Север','Home')
        q.begin(self.db,'Север',random.Random(42))
        self.run=q.state(self.db,'Север');self.d=q.details(self.run)['detective']

    def at(self,index):
        self.db.execute('UPDATE portal_parties SET city_id=?',(self.d['cities'][index],))

    def collect(self):
        self.at(0);q.action(self.db,'Север','witness')
        self.at(1);q.action(self.db,'Север','ledger',self.d['search_sites'][self.d['search_answer']])
        self.at(2)

    def crowns(self):
        return self.db.execute("SELECT amount FROM resources WHERE faction='Север' AND resource_type='Кроны'").fetchone()[0]

    def test_wrong_search_loses_crowns_but_preserves_other_resources(self):
        self.at(0);q.action(self.db,'Север','witness');self.at(1)
        q.action(self.db,'Север','ledger',self.d['search_sites'][(self.d['search_answer']+1)%3])
        self.assertEqual(self.crowns(),0)
        self.assertEqual(self.db.execute("SELECT amount FROM resources WHERE resource_type='Кристаллы'").fetchone()[0],100000)
        self.assertEqual(q.evidence(self.db,'Север'),([],[]))
        self.assertEqual(q.pending(self.db,'Север'),[])

    def test_missing_board_blocks_but_pinning_order_does_not_reject_correct_suspect(self):
        self.collect();culprit=self.d['suspects'][self.run['culprit']]
        with self.assertRaises(ValueError):q.action(self.db,'Север','accuse',culprit)
        self.assertGreater(self.crowns(),0)
        collected,_=q.evidence(self.db,'Север')
        for clue in reversed(collected):q.action(self.db,'Север','arrange',clue)
        q.action(self.db,'Север','accuse',culprit)
        self.assertGreater(self.crowns(),0)
        self.assertEqual(q.state(self.db,'Север')['detective'],3)

    def test_board_survives_reload_and_can_be_rearranged(self):
        self.collect();collected,_=q.evidence(self.db,'Север')
        q.action(self.db,'Север','arrange',collected[-1])
        q.action(self.db,'Север','reset_board')
        for clue in collected:q.action(self.db,'Север','arrange',clue)
        self.db.commit()
        restored=sqlite3.connect(':memory:');self.addCleanup(restored.close)
        self.db.backup(restored)
        self.assertEqual(q.evidence(restored,'Север'),(collected,collected))
        q.action(restored,'Север','accuse',self.d['suspects'][self.run['culprit']])
        self.assertEqual(q.pending(restored,'Север'),[101])
        self.assertGreater(self.crowns(),0)

    def test_availability_tracks_stock_cash_and_army_capacity(self):
        initial=w.recruitment_limit(self.db,'Север',1)
        self.assertGreater(initial,0)
        before=self.crowns();cost=w.recruit(self.db,'Север',1,7)
        self.assertEqual(self.crowns(),before-cost)
        self.assertLessEqual(w.recruitment_limit(self.db,'Север',1),initial-7)
        self.db.execute("UPDATE resources SET amount=0 WHERE resource_type='Кроны'")
        self.assertEqual(w.recruitment_limit(self.db,'Север',1),0)
