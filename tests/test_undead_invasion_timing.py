import sqlite3
import unittest
from undead_invasion import _upgrade_invasion_timing,INVASION_TURN_MIN,INVASION_TURN_MAX


class InvasionTimingTests(unittest.TestCase):
    def test_window_shift_preserves_width(self):
        self.assertEqual((INVASION_TURN_MIN,INVASION_TURN_MAX),(22,30))
        self.assertEqual(INVASION_TURN_MAX-INVASION_TURN_MIN,26-18)

    def test_saved_dates_delayed_exactly_once_and_started_invasions_untouched(self):
        db=sqlite3.connect(':memory:');self.addCleanup(db.close)
        db.executescript('''CREATE TABLE undead_invasion(id,invasion_turn,invasion_started);
            INSERT INTO undead_invasion VALUES(1,18,0),(2,26,0),(3,23,1);''')
        _upgrade_invasion_timing(db.cursor())
        self.assertEqual(list(db.execute('SELECT invasion_turn FROM undead_invasion ORDER BY id')),[(22,),(30,),(23,)])
        _upgrade_invasion_timing(db.cursor())
        self.assertEqual(list(db.execute('SELECT invasion_turn FROM undead_invasion ORDER BY id')),[(22,),(30,),(23,)])
        db.execute('INSERT INTO undead_invasion(id,invasion_turn,invasion_started) VALUES(4,25,0)')
        _upgrade_invasion_timing(db.cursor())
        self.assertEqual(db.execute('SELECT invasion_turn,timing_version FROM undead_invasion WHERE id=4').fetchone(),(25,1))
