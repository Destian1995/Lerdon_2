import ast
import contextlib
import copy
import io
import os
import random
import sqlite3
import tempfile
import unittest
from pathlib import Path

from city_war import (army_strength, ensure_city_war_schema, record_battle,
                      record_capture, reconcile_city_rebuilding, read_city_war_states)


class CityWarFixture(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:')
        self.db.executescript('''
            CREATE TABLE cities(name TEXT PRIMARY KEY, faction TEXT);
            INSERT INTO cities VALUES ('Town', 'Север');
            CREATE TABLE buildings(city_name TEXT, faction TEXT, building_type TEXT, count INTEGER);
            INSERT INTO buildings VALUES ('Town', 'Север', 'Фабрика', 12);
            CREATE TABLE turn(faction TEXT, turn_count INTEGER);
            INSERT INTO turn VALUES ('Север', 5);
        ''')
        ensure_city_war_schema(self.db)

    def tearDown(self):
        self.db.close()

    def state(self):
        return read_city_war_states(self.db)['Town']


class CityWarRulesTests(CityWarFixture):
    def test_both_armies_must_reach_threshold_inclusive(self):
        record_battle(self.db, 'Town', 20_000_000, 19_999_999, 'Север')
        self.assertFalse(self.state().ruined)
        self.assertEqual(self.db.execute('SELECT SUM(count) FROM buildings').fetchone()[0], 12)
        record_battle(self.db, 'Town', 19_999_999, 90_000_000, 'Север')
        self.assertFalse(self.state().ruined)
        record_battle(self.db, 'Town', 20_000_000, 20_000_000, 'Север')
        self.assertTrue(self.state().ruined)
        self.assertEqual(self.state().kind, 'battle')  # Defender held the city.
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM buildings').fetchone()[0], 0)
        self.assertEqual(self.state().smoke_until, 7)

    def test_capture_and_small_battle_never_magically_heal_ruins(self):
        record_battle(self.db, 'Town', 20_000_000, 20_000_000, 'Север')
        self.db.execute("UPDATE cities SET faction='Эльфы'")
        record_capture(self.db, 'Town', 'Эльфы')
        self.assertTrue(self.state().ruined)
        self.assertEqual(self.state().kind, 'peace')
        record_battle(self.db, 'Town', 100, 100, 'Север')
        self.assertTrue(self.state().ruined)
        self.assertEqual(self.state().kind, 'battle_capture')

    def test_rebuild_requires_full_capacity_then_next_turn(self):
        record_battle(self.db, 'Town', 20_000_000, 20_000_000, 'Север')
        self.db.execute("INSERT INTO buildings VALUES ('Town', 'Север', 'Фабрика', 24)")
        self.db.execute('UPDATE turn SET turn_count=10')
        reconcile_city_rebuilding(self.db)
        self.assertTrue(self.state().ruined)
        self.assertIsNone(self.state().ready_turn)
        self.db.execute('UPDATE buildings SET count=25')
        reconcile_city_rebuilding(self.db)
        self.assertEqual(self.state().ready_turn, 10)
        reconcile_city_rebuilding(self.db)
        self.assertTrue(self.state().ruined)
        self.db.execute('UPDATE turn SET turn_count=11')
        reconcile_city_rebuilding(self.db)
        self.assertFalse(self.state().ruined)
        self.assertEqual(self.state().kind, 'rebuild')
        self.assertEqual(self.state().smoke_until, -1)

    def test_interrupted_reconstruction_and_new_major_battle_restart_wait(self):
        record_battle(self.db, 'Town', 20_000_000, 20_000_000, 'Север')
        self.db.execute("INSERT INTO buildings VALUES ('Town', 'Север', 'Фабрика', 25)")
        reconcile_city_rebuilding(self.db)
        self.db.execute('UPDATE buildings SET count=24')
        self.db.execute('UPDATE turn SET turn_count=6')
        reconcile_city_rebuilding(self.db)
        self.assertTrue(self.state().ruined)
        self.assertIsNone(self.state().ready_turn)
        self.db.execute('UPDATE buildings SET count=25')
        reconcile_city_rebuilding(self.db)
        record_battle(self.db, 'Town', 20_000_000, 20_000_000, 'Север')
        self.assertIsNone(self.state().ready_turn)

    def test_damage_survives_database_reopen(self):
        record_battle(self.db, 'Town', 20_000_000, 20_000_000, 'Север')
        self.db.commit()
        with tempfile.TemporaryDirectory() as folder:
            path = str(Path(folder) / 'save.db')
            saved = sqlite3.connect(path)
            self.db.backup(saved)
            saved.close()
            reopened = sqlite3.connect(path)
            self.assertTrue(read_city_war_states(reopened)['Town'].ruined)
            reopened.close()

    def test_strength_matches_ai_formula_and_counts_only_participating_stacks(self):
        army = [dict(unit_count=10, units_stats={'Урон': 100, 'Защита': 50,
                                                'Живучесть': 20, 'Класс юнита': '2 класс'})]
        self.assertEqual(army_strength(army), 2400)
        army[0]['unit_count'] = 0
        self.assertEqual(army_strength(army), 0)

    def test_actual_ai_fight_records_initial_strength_before_losses(self):
        # Execute real combat in memory; never import fight's global database.
        source = Path(__file__).resolve().parents[1] / 'fight.py'
        tree = ast.parse(source.read_text(encoding='utf-8'))
        nodes = []
        for node in tree.body:
            if isinstance(node, ast.FunctionDef):
                nodes.append(node)
            elif isinstance(node, ast.Assign):
                try:
                    ast.literal_eval(node.value)
                except (ValueError, TypeError):
                    continue
                nodes.append(node)
        namespace = dict(random=random.Random(14), sqlite3=sqlite3, copy=copy, os=os)
        from utils.faction_bonuses import NORTH_MULTIPLIER, ADEPT_MULTIPLIER, VAMPIRE_RATE, ELF_RATE, PEAK_SEASONS
        namespace.update(NORTH_MULTIPLIER=NORTH_MULTIPLIER, ADEPT_MULTIPLIER=ADEPT_MULTIPLIER,
                         VAMPIRE_RATE=VAMPIRE_RATE, ELF_RATE=ELF_RATE, FACTION_PEAK_SEASON=PEAK_SEASONS)
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(source), 'exec'), namespace)
        self.db.executescript('''
            CREATE TABLE user_faction(faction_name TEXT);
            CREATE TABLE garrisons(city_name TEXT, unit_name TEXT, unit_count INTEGER, experience INTEGER);
        ''')
        # UI and unrelated result bookkeeping are not part of this fixture.
        namespace['update_results_table'] = lambda *args, **kwargs: None
        def transfer_owner(**kwargs):
            if kwargs['winner'] == 'attacking':
                self.db.execute("UPDATE cities SET faction='Enemy' WHERE name='Town'")
        namespace['update_garrisons_after_battle'] = transfer_owner
        def army(name):
            return [dict(unit_name=name, unit_count=10_000, units_stats={
                'Урон': 1000, 'Защита': 1000, 'Живучесть': 1000, 'Класс юнита': 1})]
        with contextlib.redirect_stdout(io.StringIO()):
            result = namespace['fight']('Source', 'Town', army('D'), army('A'),
                                        'Enemy', 'Север', self.db)
        self.assertGreater(result['rounds'], 0)
        self.assertGreater(result['attacking_losses'], 0)
        self.assertGreater(result['defending_losses'], 0)
        self.assertTrue(self.state().ruined)
        strength = self.db.execute('SELECT attacker_strength, defender_strength FROM city_war_state').fetchone()
        self.assertEqual(tuple(strength), (33_000_000, 33_000_000))


os.environ['KIVY_NO_ARGS'] = '1'
os.environ['KIVY_NO_CONFIG'] = '1'
os.environ['KIVY_NO_FILELOG'] = '1'
os.environ['KIVY_METRICS_DENSITY'] = '1'
os.environ['KIVY_METRICS_FONTSCALE'] = '1'
from kivy.config import Config
Config.set('graphics', 'window_state', 'hidden')
from map_atmosphere import MapAtmosphere
from kivy.core.text import Label as CoreLabel
from kivy.graphics import Color, Rectangle, Mesh
from kivy.uix.image import Image
from kivy.uix.modalview import ModalView
from kivy.uix.widget import Widget


class CityWarEffectsTests(CityWarFixture):
    def setUp(self):
        super().setUp()
        self.layer = MapAtmosphere()
        self.layer.configure((0, 0), 1)
        self.fx = self.layer.city_effects
        self.cities = [('Town', 300, 300, 'Север')]
        self.fx.sync(self.cities, {}, 5)

    def tearDown(self):
        self.layer.stop()
        super().tearDown()

    def test_capture_replays_once_and_smoke_reuses_graphics(self):
        record_battle(self.db, 'Town', 20_000_000, 20_000_000, 'Эльфы')
        self.fx.sync(self.cities, read_city_war_states(self.db), 5)
        self.assertEqual(self.fx.captures[0]['kind'], 'battle_capture')
        particles = [id(p['shape']) for p in self.fx.smoke]
        self.fx.sync(self.cities, read_city_war_states(self.db), 5)
        self.assertEqual(len(self.fx.captures), 1)
        for _ in range(150):
            self.layer.update(1 / 30)
        self.assertEqual(self.fx.captures, [])
        self.assertEqual(particles, [id(p['shape']) for p in self.fx.smoke])
        self.fx.sync(self.cities, read_city_war_states(self.db), 20)
        self.assertTrue(self.fx.smoke)  # Ruins still smolder after ordinary smoke expires.

    def test_peace_has_no_smoke_and_normal_battle_smoke_expires(self):
        self.fx.sync([('Town', 300, 300, 'Эльфы')], {}, 5)
        self.assertEqual(self.fx.captures[0]['kind'], 'peace')
        self.assertEqual(self.fx.smoke, [])
        record_battle(self.db, 'Town', 10, 10, 'Север')
        self.fx.sync(self.cities, read_city_war_states(self.db), 5)
        self.assertTrue(self.fx.smoke)
        self.fx.sync(self.cities, read_city_war_states(self.db), 8)
        self.assertEqual(self.fx.smoke, [])

    def test_battle_smoke_comes_from_combat_and_peace_does_not_extend_it(self):
        record_capture(self.db, 'Town', 'Север')
        self.fx.sync(self.cities, read_city_war_states(self.db), 5)
        self.assertEqual(self.fx.battle_clouds, [])
        record_battle(self.db, 'Town', 10, 10, 'Север')
        self.fx.sync(self.cities, read_city_war_states(self.db), 5)
        self.assertEqual(len(self.fx.battle_clouds), 1)  # Even when defenders held.
        instructions = tuple(self.fx.battle_group.children)
        for _ in range(120):
            self.layer.update(1 / 30)
        self.assertEqual(instructions, tuple(self.fx.battle_group.children))
        self.db.execute('UPDATE turn SET turn_count=6')
        record_capture(self.db, 'Town', 'Эльфы')
        for turn in (6, 7):
            self.fx.sync(self.cities, read_city_war_states(self.db), turn)
            self.assertEqual(len(self.fx.battle_clouds), 1)
        self.fx.sync(self.cities, read_city_war_states(self.db), 8)
        self.assertEqual(self.fx.battle_clouds, [])
        self.assertEqual(self.fx.battle_group.children, [])

    def test_smoke_has_brief_quiet_flashes_without_flame_geometry(self):
        record_battle(self.db, 'Town', 10, 10, 'Север')
        self.fx.sync(self.cities, read_city_war_states(self.db), 5)
        self.assertFalse(any(isinstance(item, Mesh) for item in self.fx.battle_group.children))
        instructions = tuple(self.fx.battle_group.children)
        smoke = tuple(self.fx.smoke_group.children)
        intensities = []
        for _ in range(300):
            self.layer.update(1 / 30)
            intensities.append(self.fx.battle_clouds[0]['intensity'])
        self.assertGreater(max(intensities), .2)
        self.assertGreater(sum(value < .001 for value in intensities), 240)
        self.assertEqual(instructions, tuple(self.fx.battle_group.children))
        self.assertEqual(smoke, tuple(self.fx.smoke_group.children))

    def test_hero_flags_wave_reproject_and_follow_garrisons(self):
        cities = self.cities + [('Other', 600, 400, 'Эльфы')]
        self.fx.sync(cities, {}, 5, [('Town', 'Север')])
        flag = self.fx.flags[0]
        self.layer.update(.1)
        first = list(flag['cloth'].vertices)
        instructions = tuple(self.fx.flag_group.children)
        self.layer.update(.2)
        self.assertNotEqual(first, list(flag['cloth'].vertices))
        self.assertEqual(instructions, tuple(self.fx.flag_group.children))
        self.layer.configure((100, 50), .5)
        self.layer.update(.1)
        self.assertNotEqual(first[:2], list(flag['cloth'].vertices)[:2])
        self.fx.sync(cities, {}, 5, [('Other', 'Север')])
        self.assertEqual(self.fx.flags[0]['city'], 'Other')
        self.assertEqual(self.fx.flags[0]['faction'], 'Север')
        self.fx.sync(cities, {}, 5)
        self.assertEqual(self.fx.flags, [])

    def test_faction_standards_use_distinct_symbols_and_clear_the_badge(self):
        from map_city_effects import FACTION_EMBLEMS, faction_emblem, standard_layout
        from map_terrain import city_sprite_size
        for faction in FACTION_EMBLEMS:
            self.fx.sync(self.cities, {}, 5, [('Town', faction)])
            self.layer.update(.1)
            self.assertIs(self.fx.flags[0]['emblem'].texture, faction_emblem(faction))
        self.assertEqual(len({id(faction_emblem(faction)) for faction in FACTION_EMBLEMS}),
                         len(FACTION_EMBLEMS))
        for scale in (.45, .8, 1., 1.5):
            center = (300, 300)
            x, bottom, width, height = standard_layout(center, scale)
            badge_top = center[1] + 77 - city_sprite_size(scale) / 2 + 30
            self.assertGreaterEqual(bottom - 5, badge_top)
            self.assertGreaterEqual(width, 40)
            self.assertGreaterEqual(height, 27)
        x, y, w, h = standard_layout((300, 740), 1., bounds=(26, 26, 1148, 748))
        self.assertLessEqual(y + h + 4, 774)

    def test_real_military_overlay_keeps_shield_and_removes_helmet(self):
        from types import SimpleNamespace
        from strategy_ui_fixture import __dict__ as fixture_globals
        tree = ast.parse((Path(__file__).resolve().parents[1] / 'game_process.py').read_text(encoding='utf-8'))
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'GameScreen')
        method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'draw_army_stars_on_map')
        namespace = dict(fixture_globals)
        exec(compile(ast.Module(body=[method], type_ignores=[]), 'game_process.py', 'exec'), namespace)
        host = SimpleNamespace(city_star_levels={'Town': (2, 300, 300, 'Town', True, None, 0, False)},
                               _prev_star_levels=None, game_area=Widget(), _check_file=lambda path: True)
        namespace[method.name](host)
        sources = [item.source for item in host.game_area.canvas.before.children if isinstance(item, Rectangle)]
        self.assertTrue(any(source and source.endswith('garrison_shield.png') for source in sources))
        self.assertFalse(any(source and source.endswith('hero_helm.png') for source in sources))

    def test_flags_render_above_map_symbols_but_below_panel_children(self):
        from kivy.graphics import Fbo, ClearColor, ClearBuffers
        from map_city_effects import standard_layout
        self.fx.sync(self.cities, {}, 5, [('Town', 'Север')])
        self.layer.update(.1)
        center = self.layer.project((300, 300))
        x, y, width, height = standard_layout(center, 1, bounds=self.layer._bounds)
        root, overlay, panel = Widget(), Widget(), Widget()
        root.add_widget(self.layer)
        root.add_widget(overlay)
        with overlay.canvas.before:
            Color(1, 0, 0, 1)
            Rectangle(pos=(x - 10, y - 10), size=(width + 20, height + 20))
        with panel.canvas:
            Color(0, 0, 1, 1)
            Rectangle(pos=(x, y), size=(width, height))
        overlay.add_widget(panel)
        self.fx.attach_standards(overlay)
        canvas = self.fx._standard_canvas
        self.assertLess(overlay.canvas.children.index(canvas), overlay.canvas.children.index(panel.canvas))
        fbo = Fbo(size=(1200, 800), with_stencilbuffer=True)
        with fbo:
            ClearColor(0, 0, 0, 1)
            ClearBuffers()
        fbo.add(root.canvas)

        def sample():
            fbo.draw()
            offset = (int(y + 5) * 1200 + int(x + 5)) * 4
            return tuple(fbo.pixels[offset:offset + 3])

        try:
            self.assertEqual(sample(), (0, 0, 255))  # The panel covers the flag.
            overlay.remove_widget(panel)
            self.assertNotEqual(sample(), (255, 0, 0))  # The flag covers the symbol.
            self.assertNotEqual(sample(), (0, 0, 0))
            for _ in range(3):
                self.fx.attach_standards(None)
                self.assertNotIn(canvas, overlay.canvas.children)
                self.assertIn(self.fx.flag_group, self.fx.group.children)
                self.fx.attach_standards(overlay)
                self.assertEqual(overlay.canvas.children.count(canvas), 1)
        finally:
            fbo.remove(root.canvas)
            self.fx.attach_standards(None)
            root.remove_widget(self.layer)

    def test_hud_stays_above_later_map_badges_and_flags_for_pixels_and_touches(self):
        from types import SimpleNamespace
        from kivy.graphics import Fbo,ClearColor,ClearBuffers
        from map_city_effects import standard_layout
        self.fx.sync(self.cities,{},5,[('Town','Север')]);self.layer.update(.1)
        x,y,width,height=standard_layout(self.layer.project((300,300)),1,bounds=self.layer._bounds)
        hits=[]
        class HitLayer(Widget):
            def on_touch_down(layer,touch):
                if layer.collide_point(*touch.pos):
                    hits.append(layer.kind);return True
                return False
        root=Widget(size=(1200,800))
        badges=HitLayer(size=(1200,800));badges.kind='map'
        hud=HitLayer(pos=(x,y),size=(width,height));hud.kind='hud'
        with badges.canvas.before:
            Color(1,0,0,1);Rectangle(pos=(x,y),size=(width,height))
        with hud.canvas:
            Color(0,0,1,1);Rectangle(pos=(x,y),size=(width,height))
        root.add_widget(self.layer);root.add_widget(hud)
        # Exercise the actual insertion from GameScreen.init_ui, with an
        # already constructed HUD, rather than importing the player's DB.
        tree=ast.parse(Path('game_process.py').read_text(encoding='utf-8'))
        screen=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='GameScreen')
        method=next(n for n in screen.body if isinstance(n,ast.FunctionDef) and n.name=='init_ui')
        insertion=next(n for n in method.body if isinstance(n,ast.Expr) and isinstance(n.value,ast.Call)
            and isinstance(n.value.func,ast.Attribute) and n.value.func.attr=='add_widget'
            and n.value.args and isinstance(n.value.args[0],ast.Attribute) and n.value.args[0].attr=='game_area')
        exec(compile(ast.Module(body=[insertion],type_ignores=[]),'game_process.py','exec'),
             {'self':SimpleNamespace(root_overlay=root,game_area=badges)})
        self.fx.attach_standards(badges)
        fbo=Fbo(size=(1200,800),with_stencilbuffer=True)
        with fbo:ClearColor(0,0,0,1);ClearBuffers()
        fbo.add(root.canvas)
        try:
            for _ in range(3):
                self.layer.update(.1)
                fbo.draw();offset=(int(y+5)*1200+int(x+5))*4
                self.assertEqual(tuple(fbo.pixels[offset:offset+3]),(0,0,255))
                root.on_touch_down(SimpleNamespace(pos=(x+5,y+5)))
                self.assertEqual(hits.pop(),'hud')
        finally:
            fbo.remove(root.canvas);self.fx.attach_standards(None)
            root.remove_widget(self.layer)

    def test_opening_saved_state_does_not_replay_old_capture(self):
        record_battle(self.db, 'Town', 20_000_000, 20_000_000, 'Эльфы')
        new_layer = MapAtmosphere()
        new_layer.configure((0, 0), 1)
        new_layer.city_effects.sync(self.cities, read_city_war_states(self.db), 5)
        self.assertTrue(new_layer.city_effects.smoke)
        self.assertTrue(new_layer.city_effects.battle_clouds)
        self.assertEqual(new_layer.city_effects.captures, [])

    def test_capture_waits_until_battle_report_is_closed(self):
        modal = ModalView()
        modal.open(animation=False)
        try:
            self.fx.play('Town', 'battle_capture', 'Север')
            for _ in range(150):
                self.layer.update(0.1)
            self.assertEqual(len(self.fx.captures), 1)
            self.assertEqual(self.fx.capture_time, 0)
        finally:
            modal.dismiss(animation=False)
        for _ in range(40):
            self.layer.update(0.1)
        self.assertEqual(self.fx.captures, [])

    def test_resize_reprojects_active_effect_and_bounds_instruction_count(self):
        self.fx.play('Town', 'peace', 'Север')
        self.layer.update(0.1)
        before = self.fx.captures[0]['glow'][1].pos
        self.layer.configure((100, 50), 0.5)
        self.fx.sync(self.cities, {}, 5)
        self.layer.update(0.01)
        self.assertNotEqual(before, self.fx.captures[0]['glow'][1].pos)
        for _ in range(50):
            self.fx.play('Town', 'peace', 'Север')
        self.assertEqual(len(self.fx.captures), 8)
        self.assertEqual(len(self.fx.group.children), 11)

    def test_real_city_renderer_switches_ruins_back_to_faction_icon(self):
        path = Path(__file__).resolve().parents[1] / 'main.py'
        cls = next(n for n in ast.parse(path.read_text(encoding='utf-8')).body
                   if isinstance(n, ast.ClassDef) and n.name == 'MapWidget')
        method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'draw_fortresses')
        namespace = dict(ast=ast, sqlite3=sqlite3, os=os, Image=Image, Color=Color, Rectangle=Rectangle)
        exec(compile(ast.Module(body=[method], type_ignores=[]), str(path), 'exec'), namespace)
        host = type('CityMapHost', (Widget,), {'draw_fortresses': namespace['draw_fortresses']})()
        host.conn, host.map_scale, host.map_pos = self.db, 1, (0, 0)
        host.previous_city_factions = {}
        host.fortress_icon_widgets, host.fortress_data_for_canvas = {}, []
        host._sync_map_atmosphere = lambda: None
        label = CoreLabel(text='Town')
        label.refresh()
        host._get_city_label_texture = lambda text: label.texture
        self.db.execute("ALTER TABLE cities ADD COLUMN coordinates TEXT DEFAULT '[300, 300]'")
        self.db.execute('ALTER TABLE cities ADD COLUMN is_undead INTEGER DEFAULT 0')
        record_battle(self.db, 'Town', 20_000_000, 20_000_000, 'Север')
        host.draw_fortresses()
        self.assertTrue(host.fortress_icon_widgets['Town'].source.endswith('ruined/town.png'))
        self.db.execute("INSERT INTO buildings VALUES ('Town', 'Север', 'Фабрика', 25)")
        reconcile_city_rebuilding(self.db)
        self.db.execute('UPDATE turn SET turn_count=6')
        reconcile_city_rebuilding(self.db)
        host.draw_fortresses()
        self.assertTrue(host.fortress_icon_widgets['Town'].source.endswith('people.png'))
        self.assertEqual(tuple(host.fortress_icon_widgets['Town'].pos), (300, 300))
        self.assertEqual(tuple(host.fortress_icon_widgets['Town'].size), (77, 77))
