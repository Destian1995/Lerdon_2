"""Initial quote history and per-turn updates without opening the game database."""
import ast
from pathlib import Path
import random
import sqlite3
from types import SimpleNamespace
import unittest
from unittest.mock import patch


class MarketPriceHistoryTests(unittest.TestCase):
    def test_initial_history_is_generated_once_and_extends_on_next_turn(self):
        tree = ast.parse((Path(__file__).resolve().parents[1] / 'economic.py').read_text(encoding='utf-8'))
        faction = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'Faction')
        method = next(node for node in faction.body if isinstance(node, ast.FunctionDef)
                      and node.name == 'generate_raw_material_price')
        namespace = dict(random=random, sqlite3=sqlite3)
        exec(compile(ast.Module(body=[method], type_ignores=[]), 'economic.py', 'exec'), namespace)
        generate = namespace[method.name]
        with sqlite3.connect(':memory:') as db:
            db.executescript('CREATE TABLE turn(turn_count INTEGER); INSERT INTO turn VALUES (1);')
            game = SimpleNamespace(cursor=db.cursor(), raw_material_price_history=[], last_turn_loaded=-1)
            with patch.object(random, 'uniform', side_effect=[100] + [1] * 34):
                generate(game)
            self.assertEqual(game.raw_material_price_history, list(range(134, 99, -1)))
            self.assertEqual(game.current_raw_material_price, 100)
            before = list(game.raw_material_price_history)
            with patch.object(random, 'uniform', side_effect=AssertionError('Repeated generation')):
                generate(game)
            self.assertEqual(game.raw_material_price_history, before)
            db.execute('UPDATE turn SET turn_count=2')
            with patch.object(random, 'uniform', return_value=-2):
                generate(game)
            self.assertEqual(game.raw_material_price_history, before + [98])
            for turn in range(3, 80):
                db.execute('UPDATE turn SET turn_count=?', (turn,))
                generate(game)
            self.assertEqual(len(game.raw_material_price_history), 60)
            self.assertTrue(all(76.3 <= price <= 148.7 for price in game.raw_material_price_history))


if __name__ == '__main__':
    unittest.main()
