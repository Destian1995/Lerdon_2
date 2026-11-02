import sqlite3
import sys
import unittest
from unittest.mock import Mock
from types import SimpleNamespace

from strategy_ui_fixture import *
from test_responsive_windows import settle
import test_troop_movement as march_tests
from terrain_journeys import ensure_schema, advance_journeys
from troop_movement import play_ai_marches, rendered_leg


class PlayerTerrainTests(unittest.TestCase):
    setUp = march_tests.MovementArrivalTests.setUp
    tearDown = march_tests.MovementArrivalTests.tearDown
    count = march_tests.MovementArrivalTests.count

    def test_real_player_command_stops_midroad_then_continues_after_two_turns(self):
        selection=SimpleNamespace(dismiss=Mock())
        self.owner.current_popup=selection
        self.owner.dismiss=Mock()
        for column, definition in (('attack','REAL DEFAULT 10'),('defense','REAL DEFAULT 5'),
                                   ('durability','REAL DEFAULT 10'),('unit_class',"TEXT DEFAULT '1'")):
            self.db.execute(f'ALTER TABLE units ADD COLUMN {column} {definition}')
        ensure_schema(self.db)
        self.db.execute("INSERT INTO map_features VALUES(1,'forest',1,2,.5,238,330,2,1)")
        sys.modules['game_process'].refresh_map = lambda: None
        self.owner.move_selected_group_to_city()
        selection.dismiss.assert_called_once_with()
        self.owner.dismiss.assert_called_once_with()
        self.assertIsNone(self.owner.current_popup)
        self.assertFalse(self.errors)
        self.assertEqual(self.count('A'),50)
        self.assertEqual(self.count('C'),0)
        self.assertEqual(self.db.execute('SELECT moves_left FROM turn_check_move').fetchone()[0],0)
        self.assertEqual(self.db.execute('SELECT unit_count FROM garrisons WHERE city_name LIKE ?',('@terrain:%',)).fetchone()[0],50)
        first = self.layer.marches.marches[0].route
        self.assertLess(first.points[-1][0],338.5)
        for _ in range(180):
            self.layer.update(1/30)
        self.assertFalse(self.screen.end_turn_button.disabled)
        advance_journeys(self.db,1)
        self.assertEqual(self.count('C'),0)
        advance_journeys(self.db,2)
        self.assertEqual(self.count('C'),50)
        play_ai_marches(self.screen)
        resumed = self.layer.marches.marches[0].route
        self.assertEqual(first.points[-1],resumed.points[0])
        self.assertEqual(resumed.points[-1],(538.5,330))
        for _ in range(240):
            self.layer.update(1/30)
        self.assertFalse(self.screen.end_turn_button.disabled)

    def test_road_leg_preserves_ferry_flags_and_exact_cut_endpoints(self):
        centers={1:(138.5,330),2:(338.5,330),3:(538.5,330)}
        first=rendered_leg(self.network,[1,2,3],centers,(0,0),(0,.5))
        second=rendered_leg(self.network,[1,2,3],centers,(0,.5),(1,1))
        self.assertEqual(first.points[-1],second.points[0])
        self.assertEqual(len(first.land),len(first.points)-1)
        self.assertEqual(len(second.land),len(second.points)-1)

    def test_hero_flag_survives_forest_wait_and_departure_after_camp_is_deleted(self):
        for column,definition in (('attack','REAL DEFAULT 10'),('defense','REAL DEFAULT 5'),
                                  ('durability','REAL DEFAULT 10'),('unit_class',"TEXT DEFAULT '1'")):
            self.db.execute(f'ALTER TABLE units ADD COLUMN {column} {definition}')
        self.db.execute("INSERT INTO units(unit_name,faction,consumption,unit_class) VALUES('Герой','Север',1,'3')")
        self.db.execute("INSERT INTO garrisons VALUES('A','Герой',1,'')")
        self.owner.selected_group.append(dict(city_name='A',unit_name='Герой',unit_count=1))
        ensure_schema(self.db)
        self.db.execute("INSERT INTO map_features VALUES(1,'forest',1,2,.5,238,330,2,1)")
        sys.modules['game_process'].refresh_map=lambda:None
        self.owner.move_selected_group_to_city()
        self.assertFalse(self.errors)
        self.assertIsNotNone(self.layer.marches.marches[0].hero_flag)
        for _ in range(180):
            self.layer.update(1/30)
        advance_journeys(self.db,2)
        self.assertFalse(self.db.execute("SELECT 1 FROM garrisons WHERE city_name LIKE '@terrain:%'").fetchall())
        play_ai_marches(self.screen)
        self.assertIsNotNone(self.layer.marches.marches[0].hero_flag)

    def test_ally_wins_race_return_animation_goes_from_forest_to_source_not_target(self):
        for column,definition in (('attack','REAL DEFAULT 10'),('defense','REAL DEFAULT 5'),
                                  ('durability','REAL DEFAULT 10'),('unit_class',"TEXT DEFAULT '1'")):
            self.db.execute(f'ALTER TABLE units ADD COLUMN {column} {definition}')
        self.db.execute("INSERT INTO units(unit_name,faction,consumption,unit_class) VALUES('Герой','Север',1,'2')")
        self.db.execute("INSERT INTO garrisons VALUES('A','Герой',1,'')")
        self.owner.selected_group.append(dict(city_name='A',unit_name='Герой',unit_count=1))
        ensure_schema(self.db)
        self.db.execute("INSERT INTO map_features VALUES(1,'forest',1,2,.5,238,330,2,1)")
        sys.modules['game_process'].refresh_map=lambda:None
        self.owner.move_selected_group_to_city()
        first_end=self.layer.marches.marches[0].route.points[-1]
        for _ in range(180):
            self.layer.update(1/30)
        self.db.execute("UPDATE cities SET faction='Эльфы' WHERE name='C'")
        self.db.execute("INSERT INTO diplomacies VALUES('Север','Эльфы','союз')")
        advance_journeys(self.db,2)
        play_ai_marches(self.screen)
        returned=self.layer.marches.marches[0]
        self.assertEqual(returned.route.points[0],first_end)
        self.assertEqual(returned.route.points[-1],(138.5,330))
        self.assertIsNotNone(returned.hero_flag)
        self.assertEqual(self.db.execute("SELECT SUM(unit_count) FROM garrisons WHERE city_name='A'").fetchone()[0],101)
        self.assertEqual(self.count('C'),0)
        self.assertFalse(self.screen._ai_march_destinations)


class GarrisonHeaderTests(unittest.TestCase):
    def test_header_totals_refresh_when_troops_leave(self):
        popup,db=city_fixture(populated=True)
        self.addCleanup(db.close)
        self.addCleanup(popup.dismiss)
        before=popup.garrison_attack_total.text
        db.execute('UPDATE garrisons SET unit_count=1')
        popup.update_garrison()
        self.assertNotEqual(popup.garrison_attack_total.text,before)
        db.execute('DELETE FROM garrisons')
        popup.update_garrison()
        self.assertEqual(popup.garrison_attack_total.text,'0')
        self.assertEqual(popup.garrison_defense_total.text,'0')


if __name__ == '__main__':
    unittest.main()
