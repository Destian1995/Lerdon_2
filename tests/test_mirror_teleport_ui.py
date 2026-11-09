import unittest
from unittest.mock import patch
from strategy_ui_fixture import Window
from test_dialog_layout import settle
from test_otherworlds import fixture
from kivy.uix.popup import Popup
from otherworld_ui import OtherworldMap
from mirror_army_transfer import send_from_map,depart
import otherworlds as worlds


class MirrorTeleportTests(unittest.TestCase):
    def setUp(self):
        self.db=fixture();self.size=Window.size;Window.size=(1000,700)
        worlds.enter(self.db,'Север','Home')
        with patch('map_roads.build_transport_network') as build,patch('map_roads.draw_transport_layer') as draw:
            self.owner=OtherworldMap(self.db,'Север');self.owner.open(animation=False);settle()
            build.assert_not_called();draw.assert_not_called()

    def tearDown(self):
        for p in list(Window.children):
            if isinstance(p,Popup):p.dismiss(animation=False)
        settle();self.db.close();Window.size=self.size;settle()

    def test_drag_to_unconnected_city_teleports_once_without_crossing_the_map(self):
        target=next(row[0] for row in self.db.execute('SELECT id FROM portal_cities WHERE id<>1')
                    if not self.db.execute('SELECT 1 FROM portal_roads WHERE city1=1 AND city2=?',row).fetchone())
        before=self.db.execute('SELECT moves_left FROM turn_check_move').fetchone()[0]
        selection=send_from_map(self.owner,1,target)
        if selection:
            names=[r[0] for r in worlds._camp_units(self.db,worlds.party(self.db,'Север')['camp'])]
            depart(self.owner,1,target,names,selection)
        beam=self.owner.map.beam
        self.assertEqual(worlds.beam(self.db,'Север'),(1,target))
        self.assertEqual(self.db.execute('SELECT moves_left FROM turn_check_move').fetchone()[0],before-1)
        self.assertEqual(len(beam.portals),2)
        for _ in range(6):
            beam.update(.1)
            self.assertIn(beam.position,(beam.points[0],beam.points[-1]))
        self.owner.export_to_png('.release/mirror-teleport-no-roads.png')
        for _ in range(20):beam.update(.1)
        self.assertTrue(beam.finished)
        self.assertIsNone(worlds.beam(self.db,'Север'))
        self.assertEqual(worlds.party(self.db,'Север')['city_id'],target)
        beam.finish()
        self.assertEqual(self.db.execute('SELECT moves_left FROM turn_check_move').fetchone()[0],before-1)
        self.assertFalse(self.owner.map.network.land or self.owner.map.network.sea)

    def test_legacy_road_rows_are_irrelevant_to_teleportation(self):
        self.db.execute('DELETE FROM portal_roads')
        target=self.db.execute('SELECT id FROM portal_cities WHERE id<>1 LIMIT 1').fetchone()[0]
        source=worlds.party(self.db,'Север')['city_id']
        worlds.begin_beam(self.db,'Север',target)
        self.owner.play_beam(source,target)
        self.owner.close_beam();self.owner.close_beam()
        self.assertEqual(worlds.party(self.db,'Север')['city_id'],target)
        self.assertIsNone(worlds.beam(self.db,'Север'))


if __name__=='__main__':unittest.main()
