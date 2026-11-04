"""Map indicators show troops left behind throughout the real march lifecycle."""
import unittest
import ast
import sqlite3
from pathlib import Path
from unittest.mock import Mock
from test_troop_movement import MovementArrivalTests
from utils.garrison_presence import military_presence
from map_city_effects import read_hero_garrisons


class DepartingGarrisonTests(unittest.TestCase):
    setUp=MovementArrivalTests.setUp
    tearDown=MovementArrivalTests.tearDown

    def heroes(self):
        self.db.execute("ALTER TABLE units ADD COLUMN unit_class TEXT DEFAULT '1'")
        self.db.execute("INSERT INTO units VALUES('Герой','Север',10,'3')")
        self.db.execute("INSERT INTO garrisons VALUES('A','Герой',1,'')")
        self.db.commit()

    def move(self,units):
        self.owner.selected_group=[dict(city_name='A',unit_name=name,unit_count=count) for name,count in units]
        self.owner.move_selected_group_to_city()
        self.assertFalse(self.errors)

    def test_only_selected_units_disappear_and_hero_left_behind_keeps_flag(self):
        self.heroes()
        self.screen.update_army_rating=Mock()
        self.move([('Страж',50)])
        presence=military_presence(self.db)
        self.assertEqual(presence['city_consumption']['A'],60)
        self.assertEqual(presence['faction_consumption']['Север'],110)
        self.assertEqual(read_hero_garrisons(self.db),(('A','Север'),))
        self.screen.update_army_rating.assert_called_once_with()
        self.assertEqual(self.db.execute("SELECT unit_count FROM garrisons WHERE unit_name='Страж'").fetchone()[0],100)

    def test_departing_hero_removes_source_flag_and_arrival_adds_target_flag(self):
        self.heroes()
        self.move([('Герой',1)])
        self.assertEqual(read_hero_garrisons(self.db),())
        self.assertEqual(military_presence(self.db)['city_counts']['A'],100)
        for _ in range(240):self.layer.update(1/30)
        self.assertEqual(read_hero_garrisons(self.db),(('C','Север'),))
        self.assertEqual(self.screen._march_departures,{})

    def test_whole_garrison_vanishes_at_departure_and_cancel_restores_it(self):
        self.heroes()
        self.move([('Страж',100),('Герой',1)])
        self.assertEqual(military_presence(self.db)['city_counts']['A'],0)
        self.assertEqual(military_presence(self.db)['city_consumption']['A'],0)
        self.assertEqual(read_hero_garrisons(self.db),())
        self.layer.marches.cancel_all()
        self.assertEqual(military_presence(self.db)['city_counts']['A'],101)
        self.assertEqual(read_hero_garrisons(self.db),(('A','Север'),))
        self.assertFalse(self.screen._troop_movement_busy)

    def test_another_hero_still_in_the_city_keeps_its_flag(self):
        self.heroes()
        self.db.execute("INSERT INTO units VALUES('Второй герой','Север',5,'2')")
        self.db.execute("INSERT INTO garrisons VALUES('A','Второй герой',1,'')")
        self.move([('Герой',1)])
        self.assertEqual(read_hero_garrisons(self.db),(('A','Север'),))

    def test_real_city_badge_and_animated_flag_refresh_in_the_departure_frame(self):
        from utils.movement_rules import army_size_level
        self.heroes()
        self.db.execute("ALTER TABLE cities ADD COLUMN icon_coordinates TEXT DEFAULT '[100,100]'")
        self.db.execute('ALTER TABLE cities ADD COLUMN kf_crystal REAL DEFAULT 1')
        self.db.execute('CREATE TABLE political_systems(faction,system)')
        tree=ast.parse(Path('game_process.py').read_text(encoding='utf-8'))
        node=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='update_city_military_status')
        namespace=dict(sqlite3=sqlite3)
        exec(compile(ast.Module(body=[node],type_ignores=[]),'game_process.py','exec'),namespace)
        self.screen.selected_faction='Север'
        self.screen.IDEOLOGY_ICON_MAP={}
        self.screen.calculate_star_level=army_size_level
        self.screen.update_army_rating=lambda:namespace['update_city_military_status'](self.screen)
        cities=[('A',100,300,'Север'),('B',300,300,'Север'),('C',500,300,'Север')]
        self.map._sync_map_atmosphere=lambda:self.layer.city_effects.sync(cities,{},0,read_hero_garrisons(self.db))
        self.screen.update_army_rating();self.map._sync_map_atmosphere()
        self.assertEqual(self.screen.city_star_levels['A'][0],3)
        self.assertEqual(len(self.layer.city_effects.flags),1)
        self.move([('Страж',100),('Герой',1)])
        self.assertEqual(self.screen.city_star_levels['A'][0],0)
        self.assertFalse(self.screen.city_star_levels['A'][4])
        self.assertEqual(self.layer.city_effects.flags,[])
        self.assertEqual(self.screen.city_star_levels['C'][0],0)
        self.layer.marches.cancel_all()
        self.assertEqual(self.screen.city_star_levels['A'][0],3)
        self.assertTrue(self.screen.city_star_levels['A'][4])
        self.assertEqual(len(self.layer.city_effects.flags),1)
