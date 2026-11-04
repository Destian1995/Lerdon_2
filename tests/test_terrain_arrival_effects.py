import unittest
from unittest.mock import Mock
from types import SimpleNamespace
from strategy_ui_fixture import Window
from map_atmosphere import MapAtmosphere
from map_features_ui import sync_waypoint_effects
from troop_movement import MarchRoute


class TerrainArrivalEffectTests(unittest.TestCase):
    def setUp(self):
        self.layer=MapAtmosphere();self.layer.configure((0,0),1)
        self.effects=self.layer.marches.terrain_arrivals
        self.effects.set_sites([dict(id=1,kind='forest',x=250,y=300),dict(id=2,kind='swamp',x=400,y=300)])
        self.addCleanup(self.layer.marches.cancel_all);self.addCleanup(self.layer.stop)

    def march(self,points,dry=True):
        provider=lambda:MarchRoute([(self.layer._origin[0]+x*self.layer._scale,self.layer._origin[1]+y*self.layer._scale)
                                     for x,y in points],[dry]*(len(points)-1))
        self.layer.marches.play_batch([(provider,1,'Север',100)],lambda:None,lambda:None)
        return self.layer.marches.marches[-1]

    def advance(self,seconds):
        for _ in range(round(seconds*30)):self.layer.update(1/30)

    def test_forest_then_swamp_pulse_once_per_march_and_fade_completely(self):
        entered=Mock(wraps=self.effects.enter);self.effects.enter=entered
        march=self.march([(100,300),(500,300)])
        self.advance(1.8)
        self.assertEqual(entered.call_count,1)
        self.assertEqual(entered.call_args.args[0]['kind'],'forest')
        self.assertTrue(any(p['glow'].a>0 for p in self.effects.pulses))
        self.advance(2.2)
        self.assertEqual(entered.call_count,2)
        self.assertEqual(entered.call_args.args[0]['kind'],'swamp')
        self.advance(3)
        self.assertEqual(entered.call_count,2)
        self.assertTrue(march.arrived)
        self.assertTrue(all(p['glow'].a==p['edge'].a==0 for p in self.effects.pulses))
        self.assertTrue(all(c.a==0 for p in self.effects.pulses for c,_ in p['fog']))

    def test_arrival_at_forest_pulses_but_departure_and_remote_or_water_routes_do_not(self):
        entered=Mock(wraps=self.effects.enter);self.effects.enter=entered
        self.march([(100,300),(250,300)])
        self.advance(2)
        self.assertEqual(entered.call_count,1)
        self.march([(250,300),(300,300)])
        self.march([(100,500),(500,500)])
        self.march([(100,300),(500,300)],dry=False)
        self.advance(6)
        self.assertEqual(entered.call_count,1)

    def test_pulse_follows_zoom_pan_and_cancelling_clears_it(self):
        self.effects.enter(self.effects.sites[1]);self.effects.update(.3)
        p=self.effects.pulses[0];pos=p['halo'].pos;size=p['halo'].size
        self.layer.configure((30,60),2);self.effects.update(0)
        self.assertEqual(p['halo'].pos,(30+pos[0]*2,60+pos[1]*2))
        self.assertEqual(p['halo'].size,(size[0]*2,size[1]*2))
        self.layer.marches.cancel_all()
        self.assertTrue(all(p['glow'].a==0 for p in self.effects.pulses))

    def test_real_waypoint_hit_positions_supply_the_effects_without_database_reads(self):
        widget=SimpleNamespace(_map_atmosphere=self.layer,map_pos=(30,60),map_scale=2,
                               _terrain_feature_hits=[(530,660,dict(id=1,kind='forest'),[])])
        sync_waypoint_effects(widget)
        self.assertEqual(self.effects.sites[1],dict(id=1,kind='forest',x=250,y=300))
