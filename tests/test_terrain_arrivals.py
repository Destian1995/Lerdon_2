import sqlite3
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock,patch

import test_terrain_journeys as journeys
from terrain_journeys import start_journey,advance_journeys,waiting_armies


class ArrivalRaceTests(unittest.TestCase):
    def setUp(self):
        self.fixture=journeys.JourneyTests();self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.db=self.fixture.db

    def send(self,target='B',mode='attack'):
        return start_journey(self.db,'Север','A',target,[dict(unit_name='soldier',unit_count=50)],mode)

    def owner(self,city,faction):
        self.db.execute('UPDATE cities SET faction=? WHERE name=?',(faction,city))

    def relation(self,status,faction='Эльфы'):
        self.db.execute('DELETE FROM diplomacies')
        self.db.execute('INSERT INTO diplomacies VALUES(?,?,?)',('Север',faction,status))

    def test_rival_takes_neutral_target_return_instead_of_reinforcing_neutral_or_ally(self):
        for status in ('нейтралитет','союз'):
            with self.subTest(status=status):
                self.db.execute('UPDATE turn SET turn_count=0')
                self.owner('B','Нейтрал');self.relation(status)
                self.send()
                self.owner('B','Эльфы')
                self.fixture.advance(2)
                self.assertEqual(self.fixture.count('A'),100)
                self.assertEqual(self.fixture.count('B'),0)
                self.assertEqual(self.db.execute("SELECT faction FROM cities WHERE name='B'").fetchone()[0],'Эльфы')
                self.assertEqual(waiting_armies(self.db),[])
                self.fixture.advance(3)
                self.assertEqual(self.fixture.count('A'),100)

    def test_same_enemy_becoming_ally_also_returns_and_unclaimed_neutral_is_still_captured(self):
        self.owner('B','Эльфы');self.relation('война')
        self.send(mode='move')
        self.relation('союз')
        self.fixture.advance(2)
        self.assertEqual(self.fixture.count('A'),100)
        self.assertEqual(self.fixture.count('B'),0)
        self.owner('B','Нейтрал')
        self.send()
        self.fixture.advance(4)
        self.assertEqual(self.db.execute("SELECT faction FROM cities WHERE name='B'").fetchone()[0],'Север')
        self.assertEqual(self.fixture.count('B'),50)

    def test_late_army_attacks_new_enemy_owner_with_defenders_after_wait(self):
        self.owner('B','Нейтрал');self.relation('война')
        self.send()
        self.owner('B','Эльфы')
        self.db.execute("INSERT INTO garrisons VALUES('B','soldier',20,'',0)")
        fight=Mock()
        with patch.dict(sys.modules,fight=SimpleNamespace(fight=fight)):
            self.fixture.advance(1);fight.assert_not_called()
            self.fixture.advance(2);fight.assert_called_once()
            args=fight.call_args.args
            self.assertTrue(args[0].startswith('@terrain:'))
            self.assertEqual(args[1],'B')
            self.assertEqual(args[3][0]['unit_count'],50)
            self.assertEqual(args[4:6],('Север','Эльфы'))

    def test_captured_source_uses_another_reachable_owned_city(self):
        self.relation('нейтралитет')
        self.send('C')
        self.owner('C','Эльфы');self.owner('A','Вампиры')
        self.fixture.advance(2)
        self.assertEqual(self.fixture.count('A'),50)
        self.assertEqual(self.fixture.count('B'),50)
        self.assertEqual(self.fixture.count('C'),0)
        self.assertEqual(waiting_armies(self.db),[])

    def test_cut_off_return_stays_in_camp_and_resumes_when_a_safe_city_exists(self):
        self.owner('B','Нейтрал');self.relation('нейтралитет')
        self.send()
        self.owner('B','Эльфы');self.owner('A','Вампиры');self.owner('C','Вампиры')
        self.fixture.advance(2)
        self.assertEqual(waiting_armies(self.db)[0]['count'],50)
        self.assertEqual(self.fixture.count('B'),0)
        self.owner('A','Север')
        self.fixture.advance(3)
        self.assertEqual(self.fixture.count('A'),100)
        self.assertEqual(waiting_armies(self.db),[])

    def test_original_allied_reinforcement_still_arrives_but_new_ally_owner_does_not(self):
        self.owner('B','Эльфы');self.relation('союз')
        self.send(mode='move')
        self.fixture.advance(2)
        self.assertEqual(self.fixture.count('B'),50)
        self.assertEqual(self.fixture.count('A'),50)
        self.send(mode='gift')
        self.owner('B','Вампиры');self.relation('союз','Вампиры')
        self.fixture.advance(4)
        self.assertEqual(self.fixture.count('A'),50)
        self.assertEqual(self.fixture.count('B'),50)

    def test_own_faction_winning_race_receives_the_reinforcement(self):
        self.owner('B','Нейтрал');self.send()
        self.owner('B','Север')
        self.fixture.advance(2)
        self.assertEqual(self.fixture.count('B'),50)

    def test_two_real_armies_forest_arrives_first_and_swamp_army_returns_to_its_owner(self):
        self.owner('B','Нейтрал');self.owner('C','Эльфы');self.relation('союз')
        self.db.execute("INSERT INTO units VALUES('elf','Эльфы','1',10,5,10,2,'')")
        self.db.execute("INSERT INTO garrisons VALUES('C','elf',30,'',0)")
        self.send()
        start_journey(self.db,'Эльфы','C','B',[dict(unit_name='elf',unit_count=30)],'attack')
        self.fixture.advance(2)
        self.assertEqual(self.db.execute("SELECT faction FROM cities WHERE name='B'").fetchone()[0],'Север')
        self.assertEqual(self.fixture.count('B'),50)
        self.assertEqual(self.fixture.count('C'),0)
        self.fixture.advance(3)
        self.assertEqual(self.fixture.count('B'),50)
        self.assertEqual(self.fixture.count('C'),30)
        self.assertEqual(waiting_armies(self.db),[])

    def test_legacy_attack_order_and_original_allied_gift_are_distinguished(self):
        self.owner('B','Нейтрал');self.relation('союз')
        self.send()
        self.db.execute('UPDATE terrain_journeys SET destination_owner=NULL')
        self.owner('B','Эльфы')
        self.fixture.advance(2)
        self.assertEqual(self.fixture.count('A'),100)
        self.db.execute("INSERT INTO units VALUES('elf','Эльфы','1',10,5,10,2,'')")
        self.send(mode='gift')
        self.fixture.advance(4)
        self.assertEqual(self.fixture.count('A'),50)
        self.assertEqual(self.db.execute("SELECT unit_name,unit_count FROM garrisons WHERE city_name='B'").fetchone(),('elf',50))

    def test_return_via_previous_swamp_waits_again_and_survives_reload(self):
        self.db.execute("UPDATE map_features SET kind='swamp',delay=3 WHERE id=1")
        self.db.execute("UPDATE map_features SET kind='forest',delay=2 WHERE id=2")
        self.relation('союз')
        self.send('C')
        self.fixture.advance(3)
        self.owner('C','Эльфы')
        self.fixture.advance(5)
        camp=waiting_armies(self.db)[0]
        self.assertTrue(camp['returning'])
        self.assertEqual(camp['destination'],'A')
        self.assertEqual(camp['remaining'],3)
        self.assertEqual(camp['feature']['kind'],'swamp')
        copy=sqlite3.connect(':memory:');self.addCleanup(copy.close)
        self.db.backup(copy)
        self.assertEqual(waiting_armies(copy),waiting_armies(self.db))
        self.fixture.advance(8)
        self.assertEqual(self.fixture.count('A'),100)
        self.assertEqual(self.fixture.count('C'),0)
        self.assertEqual(waiting_armies(self.db),[])


if __name__=='__main__':
    unittest.main()
