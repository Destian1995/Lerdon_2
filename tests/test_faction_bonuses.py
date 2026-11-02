"""Run the combat bonus blocks without importing the game or opening its DB."""
import ast
from pathlib import Path
import unittest
from utils.faction_bonuses import NORTH_MULTIPLIER, ADEPT_MULTIPLIER, VAMPIRE_RATE, ELF_RATE


TREE = ast.parse((Path(__file__).resolve().parents[1] / 'fight.py').read_text(encoding='utf-8'))


def bonus_namespace(season_multiplier=1):
    assignments = {'elf_heal_rate', 'vamp_rate', 'shkval_mult', 'oplot_mult'}
    functions = {'_apply_elf_healing', '_apply_vampirism'}
    nodes = [node for node in ast.walk(TREE)
             if (isinstance(node, ast.Assign) and any(
                 isinstance(target, ast.Name) and target.id in assignments for target in node.targets))
             or (isinstance(node, ast.FunctionDef) and node.name in functions)]
    namespace = dict(NORTH_MULTIPLIER=NORTH_MULTIPLIER, ADEPT_MULTIPLIER=ADEPT_MULTIPLIER,
                     VAMPIRE_RATE=VAMPIRE_RATE, ELF_RATE=ELF_RATE,
                     _season_mult=lambda _: season_multiplier,
                     _get_season_mult=lambda *_: season_multiplier,
                     atk_fraction='Север', def_fraction='Адепты', conn=None,
                     get_unit_class=lambda unit: unit['unit_class'],
                     _faction_bonus_messages=[])
    exec(compile(ast.Module(body=nodes, type_ignores=[]), 'fight.py', 'exec'), namespace)
    return namespace


class FactionBonusTests(unittest.TestCase):
    def test_elves_restore_sixty_percent_and_all_losses_in_summer(self):
        for season, expected in ((1, 60), (2.75, 100)):
            with self.subTest(season=season):
                ns = bonus_namespace(season)
                soldier = dict(unit_class=1, unit_count=10, killed_count=100, unit_name='Стрелок')
                hero = dict(unit_class=2, unit_count=0, killed_count=1, unit_name='Герой')
                ns['_apply_elf_healing']([soldier, hero], 'Эльфы')
                self.assertEqual(soldier['unit_count'], 10 + expected)
                self.assertEqual(soldier['killed_count'], 100 - expected)
                self.assertEqual(hero['unit_count'], 0)

    def test_vampires_raise_fifteen_percent_with_existing_season_amplification(self):
        for season, expected in ((1, 60), (2.75, 165)):
            with self.subTest(season=season):
                ns = bonus_namespace(season)
                soldier = dict(unit_class=1, unit_count=10)
                enemy = [dict(unit_class=1, killed_count=400), dict(unit_class=2, killed_count=10)]
                ns['_apply_vampirism']([soldier], enemy, 'Вампиры')
                self.assertEqual(soldier['unit_count'], 10 + expected)

    def test_north_and_adepts_use_new_multipliers(self):
        for season in (1, 2.75):
            ns = bonus_namespace(season)
            self.assertAlmostEqual(ns['shkval_mult'], 1.8 * season)
            self.assertAlmostEqual(ns['oplot_mult'], 1.55 * season)


if __name__ == '__main__':
    unittest.main()
