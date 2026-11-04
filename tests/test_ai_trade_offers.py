"""Real offer generation, UI parsing and transfer of the displayed 5:6 lots."""
import ast
from pathlib import Path
import random
import re
import sqlite3
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from utils.trade_offers import resource_offer


def method(path,name):
    tree=ast.parse(Path(path).read_text(encoding='utf-8'))
    node=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name==name)
    namespace=dict(random=random,re=re)
    exec(compile(ast.Module(body=[node],type_ignores=[]),path,'exec'),namespace)
    return namespace[name]


class AITradeOfferTests(unittest.TestCase):
    def test_every_faction_and_resource_branch_requests_exactly_six_for_five(self):
        generate=method('ii.py','_generate_trade_exchange')
        parse=method('message_ui.py','trade_terms')
        for faction in ('Север','Эльфы','Вампиры','Элины','Адепты'):
            for crowns,crystals in ((20000,10000),(0,10000),(10000,0),(2500,0),(1500,0),(12345,9837)):
                for roll in (.1,.9):
                    ai=SimpleNamespace(faction=faction,resources={'Кроны':crowns,'Кристаллы':crystals})
                    with patch('random.random',return_value=roll):trade=generate(ai)
                    if faction in ('Элины','Адепты') and crowns==1500 and crystals==0:
                        self.assertIsNone(trade)
                        continue
                    self.assertIsNotNone(trade,(faction,crowns,crystals))
                    give,amount,want,requested,text=trade
                    self.assertEqual(requested*5,amount*6)
                    self.assertLessEqual(amount,ai.resources[give])
                    self.assertNotEqual(give,want)
                    terms=parse(text)
                    self.assertEqual(terms,((str(amount),give),(str(requested),want)))

    def test_allied_elins_and_adepts_use_the_same_explicit_terms(self):
        parse=method('message_ui.py','trade_terms')
        for name in ('_elins_diplomacy','_adepts_diplomacy'):
            sent=[]
            ai=SimpleNamespace(_send_diplomatic_message=lambda kind,text:sent.append(text) or True)
            with patch('random.random',return_value=0):
                method('ii.py',name)(ai,{}, {},dict(our_crystals=10489,our_cities=2),80,True,False)
            ((amount,_),(requested,_))=parse(sent[0])
            self.assertEqual(int(requested)*5,int(amount)*6)

    def test_1000_for_1200_and_exact_execution_in_both_directions(self):
        execute=method('game_process.py','_execute_trade_deal')
        for give in ('Кроны','Кристаллы'):
            _,amount,want,requested,text=resource_offer(give,1000)
            self.assertEqual((amount,requested),(1000,1200))
            db=sqlite3.connect(':memory:');self.addCleanup(db.close)
            db.executescript('CREATE TABLE resources(faction,resource_type,amount); CREATE TABLE relations(faction1,faction2,relationship);')
            db.executemany('INSERT INTO resources VALUES(?,?,?)',
                           [('Игрок',give,0),('Игрок',want,2000),('ИИ',give,2000),('ИИ',want,0)])
            db.execute("INSERT INTO relations VALUES('Игрок','ИИ',50)");db.commit()
            screen=SimpleNamespace(conn=db,selected_faction='Игрок',faction=None)
            execute(screen,'ИИ',text,db.cursor())
            balances={(f,r):a for f,r,a in db.execute('SELECT * FROM resources')}
            self.assertEqual(balances,{('Игрок',give):1000,('Игрок',want):800,('ИИ',give):1000,('ИИ',want):1200})

    def test_tiny_balance_does_not_create_unfunded_offer(self):
        self.assertIsNone(resource_offer('Кроны',4))
        ai=SimpleNamespace(faction='Север',resources={'Кроны':0,'Кристаллы':0})
        self.assertIsNone(method('ii.py','_generate_trade_exchange')(ai))
