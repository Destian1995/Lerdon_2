import ast
import sqlite3
import unittest
from pathlib import Path
from types import SimpleNamespace

from utils.coup_rules import coup_probabilities, council_coup_probabilities

ROOT = Path(__file__).resolve().parents[1]


class CoupRulesTests(unittest.TestCase):
    def test_loyalty_boundaries_and_group_risk(self):
        for loyalty, count, expected in (
            (0, 1, (1, .3)), (10, 1, (1 / 3, .3)), (14.99, 1, (.01 / 15, .3)), (15, 1, (0, 0)),
            (29.99, 1, (0, 0)), (30, 2, (0, 0)), (100, 2, (0, 0)),
            (29.99, 2, (.01 / 30, .5)), (14, 2, (16 / 30, .5)), (None, 0, (0, 0)),
            (-5, 1, (1, .3)), (0, 0, (0, 0)),
        ):
            with self.subTest(loyalty=loyalty, count=count):
                actual = coup_probabilities(loyalty, count)
                self.assertAlmostEqual(actual[0], expected[0])
                self.assertAlmostEqual(actual[1], expected[1])

    def test_lower_loyalty_increases_attempt_risk_within_eligible_range(self):
        for count, threshold in ((1, 15), (2, 30), (3, 30)):
            risks = [coup_probabilities(loyalty / 10, count)[0] for loyalty in range(threshold * 10 + 1)]
            self.assertEqual(risks[0], 1)
            self.assertEqual(risks[-1], 0)
            self.assertTrue(all(first > second for first, second in zip(risks, risks[1:])))

    def test_council_risk_combines_personal_attempt_probabilities(self):
        self.assertEqual(council_coup_probabilities([None, 30, 90]), (0, 0))
        self.assertEqual(council_coup_probabilities([25]), (0, 0))
        chance, success = council_coup_probabilities([10, 20, 80])
        self.assertAlmostEqual(chance, 7 / 9)
        self.assertEqual(success, .5)
        self.assertLess(council_coup_probabilities([25, 25])[0], chance)
        self.assertEqual(council_coup_probabilities([0])[0], 1)

    def test_turn_resolution_matches_displayed_probabilities(self):
        tree = ast.parse((ROOT / 'nobles_generator.py').read_text(encoding='utf-8'))
        function = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                        and n.name == 'check_coup_attempts')
        for loyalties in ([30, 70], [15, 70], [29, 70], [10, 70], [14.99, 70], [29, 29], [14, 29]):
            for attempt_roll, success_roll in ((0, .29), (0, .3), (.25, .49), (.25, .5), (.75, .29), (.999, .49)):
                with self.subTest(loyalties=loyalties, attempt_roll=attempt_roll, success_roll=success_roll):
                    conn = sqlite3.connect(':memory:')
                    self.addCleanup(conn.close)
                    conn.execute('CREATE TABLE nobles (id, loyalty, name, status)')
                    conn.executemany('INSERT INTO nobles VALUES (?, ?, ?, ?)',
                                     [(i, loyalty, str(i), 'active')
                                      for i, loyalty in enumerate(loyalties)])
                    calls = []
                    rolls = iter((attempt_roll, success_roll))
                    def random_roll():
                        calls.append(True)
                        return next(rolls)
                    ns = dict(council_coup_probabilities=council_coup_probabilities,
                              random=SimpleNamespace(random=random_roll, choice=lambda _: 'indifferent'),
                              record_coup_attempt=lambda *a: None,
                              get_player_faction=lambda *a: 'Север',
                              generate_new_noble=lambda *a: None,
                              show_coup_attempt_popup=lambda **kw: None)
                    exec(compile(ast.Module(body=[function], type_ignores=[]), '<coup>', 'exec'), ns)
                    attempt, success = council_coup_probabilities(loyalties)
                    attempted = attempt > 0 and attempt_roll < attempt
                    self.assertEqual(ns['check_coup_attempts'](conn), bool(attempted and success_roll < success))
                    self.assertEqual(len(calls), int(attempt > 0) + int(attempted))
                    eliminated = conn.execute("SELECT COUNT(*) FROM nobles WHERE status='eliminated'").fetchone()[0]
                    self.assertEqual(eliminated, sum(v < 30 for v in loyalties) if attempted else 0)

    def test_secret_service_text_replaces_views_and_preserves_hidden_information(self):
        tree = ast.parse((ROOT / 'nobles.py').read_text(encoding='utf-8'))
        card = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'SecretServiceCard')
        method = next(n for n in card.body if isinstance(n, ast.FunctionDef) and n.name == '_get_status_text')
        ns = {}
        exec(compile(ast.Module(body=[method], type_ignores=[]), '<status>', 'exec'), ns)
        data = dict(show_loyalty=True, calculated_loyalty=14, loyalty=14,
                    coup_attempt_chance=1 / 3, coup_success_chance=.3)
        text = ns['_get_status_text'](SimpleNamespace(noble_data=data))
        self.assertIn('Попытка переворота: 33.3% за ход', text)
        self.assertIn('успех: 30%', text)
        self.assertNotIn('Взгляды', text)
        data['show_loyalty'] = False
        text = ns['_get_status_text'](SimpleNamespace(noble_data=data))
        self.assertIn('Риск переворота: скрыто', text)
        self.assertNotIn('30%', text)


if __name__ == '__main__':
    unittest.main()
