import unittest
from unittest.mock import patch

import test_terrain_journeys as journeys
from strategy_ui_fixture import Widget
from kivy.core.text import Label as CoreLabel
from map_roads import TransportNetwork
from map_features_ui import draw_waypoints


class SwampVisibilityTests(unittest.TestCase):
    def test_swamp_has_explicit_label_even_when_its_variant_name_is_dead_peat_bog(self):
        fixture=journeys.JourneyTests();fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        fixture.db.execute("UPDATE map_features SET icon_variant=2 WHERE kind='swamp'")
        host=Widget();host.conn=fixture.db
        host.map_scale=1;host.map_pos=(0,0)
        host.base_map_width,host.base_map_height=1200,800
        host._road_geometry=TransportNetwork(land=[(1,2,[(138.5,330),(338.5,330)]),
                                                   (2,3,[(338.5,330),(538.5,330)])])
        with patch('kivy.core.text.Label',wraps=CoreLabel) as labels:
            draw_waypoints(host)
        texts=[call.kwargs['text'] for call in labels.call_args_list]
        self.assertIn('Болото · 3 х.',texts)
        self.assertEqual(sum(site['kind']=='swamp' for _,_,site,_ in host._terrain_feature_hits),1)


if __name__=='__main__':
    unittest.main()
