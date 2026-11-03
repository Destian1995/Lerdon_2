import unittest
from types import SimpleNamespace

import test_terrain_journeys as journeys
from terrain_journeys import features,advance_journeys
from terrain_site_ui import TerrainSitePopup,waiting_groups,open_terrain_site
from strategy_ui_fixture import Window
from test_responsive_windows import settle
from window_theme import install_window_theme


class TerrainSiteTests(unittest.TestCase):
    def setUp(self):
        self.fixture=journeys.JourneyTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.conn=self.fixture.db
        self.map=SimpleNamespace(conn=self.conn)
        self.site=features(self.conn)[0]
        self.original_size=Window.size
        self.addCleanup(setattr,Window,'size',self.original_size)
        install_window_theme()

    def popup(self):
        popup=TerrainSitePopup(self.map,self.site)
        self.addCleanup(popup.dismiss,animation=False)
        return popup

    def test_identical_waits_merge_but_experience_and_destinations_stay_distinct(self):
        self.fixture.send(count=20)
        self.fixture.send(count=15)
        groups=waiting_groups(self.conn,self.site['id'])
        self.assertEqual(len(groups),1)
        self.assertEqual(groups[0]['units'][0]['count'],35)
        self.assertEqual(groups[0]['remaining'],2)
        self.conn.execute("UPDATE garrisons SET experience=7 WHERE city_name='@terrain:2'")
        groups=waiting_groups(self.conn,self.site['id'])
        self.assertEqual({u['experience'] for u in groups[0]['units']},{3,7})
        self.fixture.send('B',10)
        groups=waiting_groups(self.conn,self.site['id'])
        self.assertEqual({g['destination'] for g in groups},{'B','C'})
        self.assertEqual(sum(u['count'] for g in groups for u in g['units']),45)
        self.assertEqual(waiting_groups(self.conn,self.site['id'],{'@terrain:1','@terrain:2','@terrain:3'}),[])

    def test_popup_reads_real_camps_and_refreshes_after_departure_without_changing_troops(self):
        self.fixture.send(count=50)
        popup=self.popup()
        before=list(self.conn.iterdump())
        popup.refresh()
        self.assertEqual(list(self.conn.iterdump()),before)
        self.assertEqual(len(popup.unit_cards),1)
        self.assertIn('50',popup.garrison_heading.text)
        self.assertTrue(popup.art.source.endswith('forest_1.png'))
        self.conn.execute('UPDATE turn SET turn_count=1')
        popup.refresh()
        self.assertEqual(popup.groups[0]['remaining'],1)
        self.conn.execute('UPDATE turn SET turn_count=2')
        advance_journeys(self.conn,2)
        popup.refresh()
        self.assertEqual(popup.groups,[])
        self.assertEqual(popup.unit_cards,[])

    def test_portrait_landscape_and_resize_keep_image_list_and_close_accessible(self):
        for _ in range(5):
            self.fixture.send(count=10)
        popup=self.popup()
        popup.open(animation=False)
        for size in ((1040,640),(640,360),(390,844),(320,568)):
            Window.size=size
            # Windows applies SDL's native GL viewport asynchronously. Let it
            # settle before requesting and checking the popup's final layout.
            settle()
            popup.fit()
            settle()
            with self.subTest(size=size):
                self.assertGreater(popup.scroll.height,45)
                self.assertGreaterEqual(popup.art_panel.width,80)
                self.assertGreaterEqual(popup.header.y,popup.garrison.top-1)
                self.assertGreaterEqual(popup.garrison.y,popup.close_button.top-1)
                self.assertGreaterEqual(popup.close_button.y,popup.y)
                self.assertLessEqual(popup.right,Window.width+1)
                self.assertTrue(popup._refresh_event)
        popup.dismiss(animation=False)
        self.assertIsNone(popup._refresh_event)

    def test_map_tap_opens_illustrated_window_and_replaces_previous_inspection(self):
        from map_features_ui import inspect_waypoint
        self.map._terrain_feature_hits=[(100,100,self.site,[])]
        self.assertTrue(inspect_waypoint(self.map,SimpleNamespace(x=100,y=100)))
        first=self.map._terrain_site_popup
        self.addCleanup(first.dismiss,animation=False)
        second=open_terrain_site(self.map,features(self.conn)[1])
        self.addCleanup(second.dismiss,animation=False)
        self.assertIs(self.map._terrain_site_popup,second)
        self.assertTrue(second.art.source.endswith('swamp_1.png'))
        second.dismiss(animation=False)
        self.assertIsNone(self.map._terrain_site_popup)


if __name__=='__main__':
    unittest.main()
