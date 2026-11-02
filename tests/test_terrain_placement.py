import ast
import contextlib
import io
import math
import os
from pathlib import Path
import random
import sqlite3
import unittest

from strategy_ui_fixture import Widget
from kivy.core.text import Label as CoreLabel
from map_terrain import load_terrain,city_sprite_size
from terrain_journeys import generate_features
from terrain_placement import feature_rect,separated,FeaturePlacementError,FEATURE_SIZE
from troop_movement import rendered_route
import test_terrain_journeys as journeys


class PlacementTests(unittest.TestCase):
    def test_failure_keeps_existing_camps_and_saved_features(self):
        fixture=journeys.JourneyTests();fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        fixture.send()
        before=list(fixture.db.iterdump())
        with self.assertRaises(FeaturePlacementError):
            generate_features(fixture.db,rng=random.Random(3))
        self.assertEqual(list(fixture.db.iterdump()),before)

    def test_real_generation_and_renderer_use_clear_road_midpoints_on_all_maps(self):
        tree=ast.parse(Path('generate_map.py').read_text(encoding='utf-8'))
        gen_nodes=[n for n in tree.body if isinstance(n,(ast.Assign,ast.FunctionDef))]
        tree=ast.parse(Path('main.py').read_text(encoding='utf-8'))
        cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='MapWidget')
        nodes=[n for n in cls.body if isinstance(n,ast.FunctionDef) and
               n.name in ('draw_roads','_get_city_label_texture')]
        namespace=dict(ast=ast,sqlite3=sqlite3,CoreLabel=CoreLabel)
        exec(compile(ast.Module(body=nodes,type_ignores=[]),'main.py','exec'),namespace)
        host_type=type('PlacementMap',(Widget,),{n.name:namespace[n.name] for n in nodes})
        for number in range(1,11):
            for scale in (1,.45):
                with self.subTest(map=number,scale=scale),contextlib.redirect_stdout(io.StringIO()):
                    conn=sqlite3.connect(':memory:')
                    try:
                        conn.executescript('''CREATE TABLE cities(id,name,coordinates,faction,icon_coordinates,label_coordinates,color_faction,is_undead,kf_crystal);
                            CREATE TABLE roads(id,city1,city2);CREATE TABLE garrisons(city_name,unit_name,unit_count,unit_image);''')
                        terrain=load_terrain(f'files/map/generate/map_{number}.png')
                        host=host_type()
                        host.conn=conn;host.map_scale=scale;host.map_pos=(17,23)
                        host.base_map_width,host.base_map_height=1200,800
                        host._map_terrain=terrain;host._city_label_cache={}
                        host._road_geometry_key=None;host._road_group=None
                        host.draw_terrain_features=lambda:None
                        ns=dict(os=os,math=math,random=random.Random(number),sqlite3=sqlite3,MANHATTAN_MOVE_LIMIT=280)
                        exec(compile(ast.Module(body=gen_nodes,type_ignores=[]),'generate_map.py','exec'),ns)
                        original_save=ns['save_to_database']
                        baseline=set()
                        def save_layout(*args):
                            original_save(*args)
                            baseline.clear()
                            baseline.update(tuple(sorted(r)) for r in conn.execute('SELECT city1,city2 FROM roads'))
                        ns['save_to_database']=save_layout
                        ns['generate_map_and_cities'](conn,terrain,sprite_scale=scale,
                            label_size_provider=lambda text:host._get_city_label_texture(text).size)
                        from utils.movement_rules import MAX_MOVE_DISTANCE
                        raw_cities={cid:ast.literal_eval(raw) for cid,raw in conn.execute('SELECT id,coordinates FROM cities')}
                        for a,b in conn.execute('SELECT city1,city2 FROM roads'):
                            self.assertLessEqual(sum(abs(raw_cities[a][i]-raw_cities[b][i]) for i in (0,1)),MAX_MOVE_DISTANCE)
                        roads=list(conn.execute('SELECT city1,city2 FROM roads'))
                        owners=dict(conn.execute('SELECT id,faction FROM cities'))
                        for a,b in roads:
                            if tuple(sorted((a,b))) not in baseline:
                                self.assertTrue(owners[a]=='Нейтрал' or owners[b]=='Нейтрал')
                                self.assertLessEqual(sum(a in r for r in roads),5)
                                self.assertLessEqual(sum(b in r for r in roads),5)
                        host.draw_roads()
                        from map_features_ui import draw_waypoints
                        draw_waypoints(host)
                        cities={cid:ast.literal_eval(raw) for cid,raw in conn.execute('SELECT id,coordinates FROM cities')}
                        size=city_sprite_size(scale)
                        centers={cid:(17+x*scale+size/2,23+y*scale+size*30/77) for cid,(x,y) in cities.items()}
                        rects=[(17+x*scale,23+y*scale,17+x*scale+size,23+y*scale+size) for x,y in cities.values()]
                        placed=[]
                        self.assertGreaterEqual(len(host._terrain_feature_hits),4)
                        kinds=[hit[2]['kind'] for hit in host._terrain_feature_hits]
                        self.assertIn(kinds.count('swamp'),(1,2))
                        self.assertIn(kinds.count('forest'),(3,4,5))
                        for x,y,site,_ in host._terrain_feature_hits:
                            self.assertEqual(site['fraction'],.5)
                            midpoint=rendered_route(host._road_geometry,[site['city1'],site['city2']],centers).sample(.5)
                            self.assertAlmostEqual(x,midpoint[0]);self.assertAlmostEqual(y,midpoint[1])
                            self.assertAlmostEqual(x,17+site['x']*scale)
                            self.assertAlmostEqual(y,23+site['y']*scale)
                            rect=feature_rect(x,y,FEATURE_SIZE*scale)
                            self.assertTrue(all(separated(rect,r,10*scale-.001) for r in rects))
                            self.assertTrue(all(separated(rect,r,10*scale-.001) for r in placed))
                            placed.append(rect)
                    finally:
                        conn.close()


if __name__=='__main__':
    unittest.main()
