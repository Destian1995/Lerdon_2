import ast
import sqlite3
import unittest
from pathlib import Path
from types import SimpleNamespace

from utils.coup_rules import coup_probabilities

ROOT = Path(__file__).resolve().parents[1]


class CoupRulesTests(unittest.TestCase):
    def test_loyalty_boundaries_and_group_risk(self):
        for loyalty, count, expected in (
            (0, 1, (1, .3)), (14.99, 1, (1, .3)), (15, 1, (0, 0)),
            (29.99, 1, (0, 0)), (30, 2, (0, 0)), (100, 2, (0, 0)),
            (29.99, 2, (1, .5)), (14, 2, (1, .5)), (None, 0, (0, 0)),
        ):
            with self.subTest(loyalty=loyalty, count=count):
                self.assertEqual(coup_probabilities(loyalty, count), expected)

    def test_turn_resolution_matches_displayed_probabilities(self):
        tree = ast.parse((ROOT / 'nobles_generator.py').read_text(encoding='utf-8'))
        function = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                        and n.name == 'check_coup_attempts')
        for loyalties in ([30, 70], [15, 70], [29, 70], [14.99, 70], [29, 29], [14, 29]):
            for roll in (.29, .3, .49, .5):
                with self.subTest(loyalties=loyalties, roll=roll):
                    conn = sqlite3.connect(':memory:')
                    self.addCleanup(conn.close)
                    conn.execute('CREATE TABLE nobles (id, loyalty, name, status)')
                    conn.executemany('INSERT INTO nobles VALUES (?, ?, ?, ?)',
                                     [(i, loyalty, str(i), 'active')
                                      for i, loyalty in enumerate(loyalties)])
                    calls = []
                    def random_roll():
                        calls.append(True)
                        return roll
                    ns = dict(coup_probabilities=coup_probabilities,
                              random=SimpleNamespace(random=random_roll, choice=lambda _: 'indifferent'),
                              record_coup_attempt=lambda *a: None,
                              get_player_faction=lambda *a: 'Север',
                              generate_new_noble=lambda *a: None,
                              show_coup_attempt_popup=lambda **kw: None)
                    exec(compile(ast.Module(body=[function], type_ignores=[]), '<coup>', 'exec'), ns)
                    attempt, success = coup_probabilities(min(loyalties), sum(v < 30 for v in loyalties))
                    self.assertEqual(ns['check_coup_attempts'](conn), bool(attempt and roll < success))
                    self.assertEqual(len(calls), int(attempt))

    def test_secret_service_text_replaces_views_and_preserves_hidden_information(self):
        tree = ast.parse((ROOT / 'nobles.py').read_text(encoding='utf-8'))
        card = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'SecretServiceCard')
        method = next(n for n in card.body if isinstance(n, ast.FunctionDef) and n.name == '_get_status_text')
        ns = {}
        exec(compile(ast.Module(body=[method], type_ignores=[]), '<status>', 'exec'), ns)
        data = dict(show_loyalty=True, calculated_loyalty=14, loyalty=14,
                    coup_attempt_chance=1, coup_success_chance=.3)
        text = ns['_get_status_text'](SimpleNamespace(noble_data=data))
        self.assertIn('Попытка переворота: 100%', text)
        self.assertIn('успех: 30%', text)
        self.assertNotIn('Взгляды', text)
        data['show_loyalty'] = False
        text = ns['_get_status_text'](SimpleNamespace(noble_data=data))
        self.assertIn('Риск переворота: скрыто', text)
        self.assertNotIn('30%', text)


if __name__ == '__main__':
    unittest.main()
