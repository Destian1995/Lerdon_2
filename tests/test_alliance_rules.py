import sqlite3
import unittest
import ast
from pathlib import Path
from types import SimpleNamespace
from alliance_rules import allies,support_player
from army_intelligence import visible,gather


class AllianceTests(unittest.TestCase):
    def test_same_ideology_improves_relations_each_turn_without_alliance(self):
        tree=ast.parse(Path('ii.py').read_text(encoding='utf-8-sig'))
        cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='AIController')
        method=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='update_relations_based_on_political_system')
        ns={};exec(compile(ast.Module(body=[method],type_ignores=[]),'ii.py','exec'),ns)
        relations={'Эльфы':95,'Адепты':50}
        ai=SimpleNamespace(faction='Север',turn=1,load_political_system=lambda:'Смирение',
            load_relations=lambda:dict(relations),
            load_political_system_for_faction=lambda f:'Смирение' if f=='Эльфы' else 'Борьба',
            update_relation_in_db=lambda f,v:relations.update({f:v}))
        for turn in (1,2,3,4):
            ai.turn=turn;ns[method.name](ai)
        self.assertEqual(relations,{'Эльфы':100,'Адепты':43})

    def setUp(self):
        self.db=sqlite3.connect(':memory:');self.addCleanup(self.db.close)
        self.db.executescript('''CREATE TABLE cities(name,faction);
            INSERT INTO cities VALUES('Дом','Север'),('Лес','Эльфы'),('Замок','Адепты'),('Пустыня','Элины');
            CREATE TABLE diplomacies(faction1,faction2,relationship,UNIQUE(faction1,faction2));
            INSERT INTO diplomacies VALUES('Север','Эльфы','союз'),('Эльфы','Север','союз');
            CREATE TABLE player_allies(player_faction,ally_faction);
            INSERT INTO player_allies VALUES('Север','Эльфы');
            CREATE TABLE turn(turn_count);INSERT INTO turn VALUES(40);
            CREATE TABLE truces(faction1,faction2,truce_until_turn);
            INSERT INTO truces VALUES('Эльфы','Адепты',100);''')

    def test_starting_like_minded_factions_are_not_allies(self):
        self.db.execute('DELETE FROM diplomacies')
        self.assertEqual(allies(self.db,'Север'),set())
        self.assertFalse(visible(self.db,'Север','Эльфы'))
        self.db.execute("INSERT INTO diplomacies VALUES('Север','Адепты','война')")
        self.assertEqual(support_player(self.db,'Север'),set())
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM diplomacies').fetchone()[0],1)

    def test_starting_and_negotiated_allies_have_permanent_intelligence(self):
        self.db.execute("INSERT INTO diplomacies VALUES('Элины','Север','союз')")
        before=list(self.db.iterdump())
        for turn in (1,40,500):
            self.db.execute('UPDATE turn SET turn_count=?',(turn,))
            self.assertTrue(visible(self.db,'Север','Эльфы'))
            self.assertTrue(visible(self.db,'Север','Элины'))
            self.assertFalse(visible(self.db,'Север','Адепты'))
        self.db.execute('UPDATE turn SET turn_count=40')
        self.assertEqual(list(self.db.iterdump()),before)
        with self.assertRaisesRegex(ValueError,'Разведка не требуется'):
            gather(self.db,'Север','Эльфы','Дом')

    def test_support_overrides_enemy_alliance_and_truce_even_late_game(self):
        self.db.executemany('INSERT INTO diplomacies VALUES(?,?,?)',[
            ('Адепты','Север','война'),('Адепты','Эльфы','союз')])
        self.assertEqual(support_player(self.db,'Север'),{('Эльфы','Адепты')})
        for a,b in (('Адепты','Эльфы'),('Эльфы','Адепты')):
            self.assertEqual(self.db.execute('SELECT relationship FROM diplomacies WHERE faction1=? AND faction2=?',(a,b)).fetchone()[0],'война')
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM truces').fetchone()[0],0)
        self.assertEqual(support_player(self.db,'Север'),set())
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM diplomacies WHERE relationship='союз'").fetchone()[0],2)

    def test_no_recursive_coalition_or_revival_of_broken_alliance(self):
        self.db.executemany('INSERT INTO diplomacies VALUES(?,?,?)',[
            ('Север','Адепты','война'),('Эльфы','Элины','союз')])
        support_player(self.db,'Север')
        self.assertIsNone(self.db.execute("SELECT 1 FROM diplomacies WHERE faction1='Элины' AND faction2='Адепты'").fetchone())
        self.db.execute("UPDATE diplomacies SET relationship='война' WHERE faction1='Север' AND faction2='Эльфы'")
        self.assertNotIn('Эльфы',allies(self.db,'Север'))
        self.assertFalse(visible(self.db,'Север','Эльфы'))
        self.assertEqual(support_player(self.db,'Север'),set())


if __name__=='__main__':unittest.main()
