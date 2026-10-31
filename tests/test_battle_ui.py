import ast
import copy
import os
import random
import sqlite3
import time
import unittest
from pathlib import Path

from battle_presentation import replay_frames, result_caption, army_summary, report_result


def combat_namespace():
    source = Path(__file__).resolve().parents[1] / 'fight.py'
    nodes = []
    for node in ast.parse(source.read_text(encoding='utf-8')).body:
        if isinstance(node, ast.FunctionDef):
            nodes.append(node)
        elif isinstance(node, ast.Assign):
            try:
                ast.literal_eval(node.value)
            except (ValueError, TypeError):
                continue
            nodes.append(node)
    namespace = dict(random=random.Random(8), sqlite3=sqlite3, copy=copy, os=os)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(source), 'exec'), namespace)
    namespace['damage_to_infrastructure'] = lambda *args: None
    namespace['_get_season_mult'] = lambda *args: 1
    return namespace


class BattlePresentationTests(unittest.TestCase):
    def test_sampling_keeps_first_final_and_true_aggregated_critical_events(self):
        rounds = [dict(round=i + 1, atk_max=1000, def_max=1000,
                       atk_total=1000 - (i + 1) * 5, def_total=1000 - (i + 1) * 8,
                       atk_crits=1, def_crits=2, heroes=[]) for i in range(100)]
        original = copy.deepcopy(rounds)
        frames = replay_frames(rounds, 16)
        self.assertEqual(len(frames), 16)
        self.assertEqual((frames[0]['round'], frames[-1]['round']), (1, 100))
        self.assertEqual(sum(f['atk_crits'] for f in frames), 100)
        self.assertEqual(sum(f['def_crits'] for f in frames), 200)
        self.assertEqual(sum(f['atk_loss'] for f in frames), 500)
        self.assertEqual(rounds, original)

    def test_defender_winning_is_defeat_for_attacking_player(self):
        self.assertEqual(result_caption('defender', 'Север', 'Север', 'Эльфы'), ('ПОРАЖЕНИЕ', False))
        self.assertEqual(result_caption('defender', 'Эльфы', 'Север', 'Эльфы'), ('ПОБЕДА', True))
        self.assertIsNone(result_caption('defender', None, 'Север', 'Эльфы')[1])

    def test_report_preserves_real_losses_recovery_and_growth(self):
        namespace = combat_namespace()
        army = [dict(unit_name='Воин', initial_count=100, unit_count=85, killed_count=20,
                     healed_count=5, units_stats={'Класс юнита': 1})]
        rows = namespace['generate_battle_report'](army, [], 'attacker', 'Север', 'Эльфы', 'Север', 'Town')
        summary = army_summary(rows)
        self.assertEqual((summary['battle_losses'], summary['net_losses'], summary['recovered']), (20, 15, 5))
        self.assertEqual(report_result(rows, 'Север', 'Север', 'Эльфы'), ('ПОБЕДА', True))
        army[0].update(unit_count=110, killed_count=0, healed_count=0)
        growth = namespace['generate_battle_report'](army, [], 'attacker', 'Север', 'Эльфы', 'Север', 'Town')[0]
        self.assertEqual((growth['losses'], growth['reinforcements']), (0, 10))
        army[0].update(unit_count=110, killed_count=20, healed_count=0)
        recruited = namespace['generate_battle_report'](army, [], 'attacker', 'Север', 'Эльфы', 'Север', 'Town')
        summary = army_summary(recruited)
        self.assertEqual((summary['net_losses'], summary['reinforcements']), (20, 30))

    def test_critical_event_logging_does_not_change_combat_or_random_sequence(self):
        unit = dict(unit_name='Воин', unit_count=1000, units_stats={
            'Урон': 150, 'Защита': 90, 'Живучесть': 100, 'Класс юнита': 1, 'Крит': 100})
        results = []
        for logging in (False, True):
            namespace = combat_namespace()
            attacker, defender = copy.deepcopy(unit), copy.deepcopy(unit)
            events = []
            namespace['battle_chain'](attacker, defender, 'Town', None, None,
                                       event_log=events if logging else None)
            results.append((attacker['unit_count'], defender['unit_count'], namespace['random'].random()))
            if logging:
                self.assertEqual(events, [(True, True)])
        self.assertEqual(results[0], results[1])


os.environ.update(KIVY_NO_ARGS='1', KIVY_NO_CONFIG='1', KIVY_NO_FILELOG='1',
                  KIVY_METRICS_DENSITY='1', KIVY_METRICS_FONTSCALE='1')
from kivy.config import Config
Config.set('graphics', 'window_state', 'hidden')
from kivy.base import EventLoop
from kivy.clock import Clock
from kivy.core.window import Window
from battle_ui import BattleViewer, BattleReport


class BattleUITests(unittest.TestCase):
    def setUp(self):
        self.original_size = Window.size
        Window.size = (640, 360)
        self.settle()
        self.popups = []
        self.rounds = [dict(round=i + 1, atk_max=1000, def_max=1000,
                            atk_total=900 - i * 50, def_total=800 - i * 100) for i in range(3)]

    def settle(self):
        for _ in range(4):
            time.sleep(0.02)
            EventLoop.idle()

    def viewer(self, **kwargs):
        view = BattleViewer(self.rounds, 'Север', 'Эльфы', 'defender', 'Север', 'Source', 'Town', **kwargs)
        self.popups.append(view)
        view.open(animation=False)
        self.settle()
        if view.clock_event:
            view.clock_event.cancel()
            view.clock_event = None
        return view

    def tearDown(self):
        for view in self.popups:
            view.dismiss(animation=False)
        Window.size = self.original_size
        self.settle()

    def test_phone_bounds_pause_speed_and_real_losses(self):
        view = self.viewer()
        view.show_frame(0)
        self.assertEqual(view.attacker_panel.damage.text, '−100')
        self.assertNotIn('крит', view.event_label.text.lower())
        view.toggle_pause()
        index = view.index
        for _ in range(20):
            view.update(0.1)
        self.assertEqual(view.index, index)
        view.change_speed()
        self.assertEqual(view.speed, 2)
        self.assertGreaterEqual(view.attacker_panel.y, view.arena.y)
        self.assertEqual(tuple(view.fx.pos), tuple(view.arena.pos))
        self.assertLessEqual(view.defender_panel.right, view.defender_panel.parent.right + 0.1)

    def test_skip_and_dismiss_deliver_one_report_and_cancel_clock(self):
        calls = []
        view = self.viewer(callback=lambda: calls.append('report'))
        view.close_to_report()
        view.close_to_report()
        Clock.tick()
        self.assertEqual(calls, ['report'])
        self.assertIsNone(view.clock_event)
        self.assertTrue(view.closed)

    def test_particle_pool_is_reused_and_result_has_correct_player_outcome(self):
        view = self.viewer()
        particles = [id(p['shape']) for p in view.fx.particles]
        for i in range(60):
            view.update(0.1)
        self.assertTrue(view.finished)
        self.assertEqual(view.result_label.text, 'ПОРАЖЕНИЕ')
        self.assertEqual(particles, [id(p['shape']) for p in view.fx.particles])

    def test_report_supports_observer_and_single_healed_hero(self):
        rows = [dict(unit_name='Герой', initial_count=1, final_count=1, losses=1,
                     healed=1, side='attacking', result='Победа', city='Town')]
        report = BattleReport(rows, None, 'Север', 'Эльфы')
        self.popups.append(report)
        report.open(animation=False)
        self.settle()
        self.assertEqual(report.summaries['attacking']['recovered'], 1)
        self.assertLessEqual(report.right, Window.width)
        self.assertGreaterEqual(report.x, 0)
