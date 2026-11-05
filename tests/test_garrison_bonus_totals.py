import ast
import unittest
from pathlib import Path

from test_monster_sites import fixture
from utils.garrison_stats import garrison_profiles,garrison_totals


class EffectiveGarrisonTests(unittest.TestCase):
    def setUp(self):
        self.db=fixture();self.addCleanup(self.db.close)
        self.db.execute("UPDATE units SET attack=22,defense=14,durability=4 WHERE unit_name='troop'")
        self.db.execute("UPDATE units SET attack=13753,defense=202,durability=5 WHERE unit_name='hero'")
        self.db.execute("UPDATE garrisons SET unit_count=6163 WHERE unit_name='troop'")
        self.db.execute('UPDATE season SET season_index=1')
        self.db.execute("INSERT INTO monster_progress(faction,veteran_until) VALUES('Север',9)")
        self.db.commit()

    def test_forge_does_not_change_garrison_attack_or_hero_aura(self):
        before=garrison_profiles(self.db,'Home')
        self.db.execute("INSERT INTO buildings VALUES('Home','Север','Кузница',1)")
        self.assertEqual(garrison_profiles(self.db,'Home'),before)

    def test_screenshot_regression_training_includes_aura_and_shkval_without_writing_database(self):
        snapshot=list(self.db.iterdump())
        profile=garrison_profiles(self.db,'Home')['troop']
        expected=(22+13753)*1.8*1.15
        self.assertAlmostEqual(profile['attack'],expected)
        self.assertAlmostEqual(profile['defense'],(14+4/2+202+5/2)*1.15)
        self.assertTrue(profile['bonus_active'])
        totals=garrison_totals(self.db,'Home')
        self.assertEqual(totals['attack'],int(expected*6163+13753))
        self.assertGreater(totals['attack'],175_000_000)
        self.assertEqual(list(self.db.iterdump()),snapshot)

    def test_elite_extra_and_expiry_change_whole_aura_without_strengthening_hero(self):
        self.db.execute("UPDATE garrisons SET experience=7 WHERE unit_name='troop'")
        profiles=garrison_profiles(self.db,'Home')
        self.assertAlmostEqual(profiles['troop']['attack'],(22+13753)*1.8*1.25*1.15)
        self.assertEqual(profiles['hero']['attack'],13753)
        self.db.execute('UPDATE turn SET turn_count=9')
        profiles=garrison_profiles(self.db,'Home')
        self.assertAlmostEqual(profiles['troop']['attack'],(22+13753)*1.8*1.25)

    def test_live_battle_applies_same_experience_to_attack_and_combat_defense(self):
        from test_battle_ui import combat_namespace
        ns=combat_namespace()
        chain=next(n for n in ast.parse(Path('fight.py').read_text(encoding='utf-8')).body
                   if isinstance(n,ast.FunctionDef) and n.name=='battle_chain')
        # Execute actual power preparation, stopping before opponent modifiers.
        stop=next(i for i,n in enumerate(chain.body) if isinstance(n,ast.Assign)
                  and any(isinstance(t,ast.Name) and t.id=='_COUNTER_PICKS' for t in n.targets))
        chain.body=chain.body[:stop]+[ast.Return(value=ast.Tuple(elts=[
            ast.Name(id='atk_attack',ctx=ast.Load()),ast.Name(id='atk_defense',ctx=ast.Load())],ctx=ast.Load()))]
        exec(compile(ast.fix_missing_locations(ast.Module(body=[chain],type_ignores=[])),'fight.py','exec'),ns)
        attacker=dict(unit_name='troop',unit_count=6163,_experience_multiplier=1.15,
                      units_stats={'Класс юнита':'1','Урон':22,'Защита':14,'Живучесть':4})
        defender=dict(unit_name='other',unit_count=1,units_stats={'Класс юнита':'1','Урон':1,'Защита':1})
        attack,defense=ns['battle_chain'](attacker,defender,'Home','Север',self.db,
                                        atk_hero_bonus=(13753,202,5),atk_fraction='Север')
        profile=garrison_profiles(self.db,'Home')['troop']
        self.assertAlmostEqual(attack,profile['attack'])
        self.assertAlmostEqual(defense,profile['defense'])

    def test_adept_building_aura_and_relief_are_applied_to_same_profile(self):
        from utils.city_terrain import ensure_schema
        self.db.execute("UPDATE cities SET faction='Адепты' WHERE name='Home'")
        self.db.execute("INSERT INTO monster_progress(faction,veteran_until) VALUES('Адепты',9)")
        self.db.execute("UPDATE units SET defense=1000,durability=0 WHERE unit_name='hero'")
        self.db.execute("UPDATE units SET defense=10,durability=0 WHERE unit_name='troop'")
        self.db.execute("INSERT INTO buildings VALUES('Home','Адепты','Стена',2)")
        ensure_schema(self.db)
        self.db.execute("INSERT INTO city_terrain VALUES('Home','lowland',0,0,NULL)")
        profile=garrison_profiles(self.db,'Home')['troop']
        self.assertTrue(profile['bonus_active'])
        self.assertAlmostEqual(profile['defense'],int((13+1300)*1.55)*1.15*.8)

    def test_battle_spirit_is_included_in_header_and_expires_with_recorded_victories(self):
        before=garrison_profiles(self.db,'Home')
        self.db.executescript("""CREATE TABLE faction_victories(faction,defeated,turn);
            INSERT INTO faction_victories VALUES('Север','Вампиры',0),('Север','Эльфы',0);""")
        after=garrison_profiles(self.db,'Home')
        self.assertAlmostEqual(after['troop']['attack'],before['troop']['attack']*1.15)
        self.assertAlmostEqual(after['hero']['attack'],before['hero']['attack']*1.15)
        self.assertEqual(after['troop']['defense'],before['troop']['defense'])
        self.db.execute('UPDATE turn SET turn_count=5')
        self.assertEqual(garrison_profiles(self.db,'Home'),before)


if __name__=='__main__':unittest.main()
