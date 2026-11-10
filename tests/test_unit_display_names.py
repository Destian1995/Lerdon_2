import unittest
from utils.unit_names import unit_display_name
from tactical_combat import TacticalBattle
from test_tactical_combat import unit


class UnitDisplayNameTests(unittest.TestCase):
    def test_service_prefix_faction_id_and_class_are_hidden(self):
        cases={'Спутник: Ярл Астрид / Север #4':'Ярл Астрид',
               'Странник: Рунный проводник / Север':'Рунный проводник',
               'Странник: Снежный всадник / Север':'Снежный всадник',
               'Легион: Вестники Смерти / Элины':'Вестники Смерти',
               'Владислав [Чемпион]':'Владислав','Ольга':'Ольга',
               'Северный страж / Южный страж':'Северный страж / Южный страж'}
        for raw,expected in cases.items():
            with self.subTest(raw=raw):self.assertEqual(unit_display_name(raw),expected)

    def test_tactical_presentation_preserves_identity_and_hero_skills(self):
        raw='Спутник: Ярл Астрид / Север #4'
        companion=unit(raw,count=1)
        hero=unit('Владислав',count=1,cls='3')
        battle=TacticalBattle([companion,hero],[unit('Враг')])
        stack=battle.stacks['attacker:0']
        self.assertEqual(stack.name,'Ярл Астрид')
        self.assertEqual(stack.unit['unit_name'],raw)
        self.assertEqual(battle.skills(battle.stacks['attacker:1']),('snipe','burst','grenade'))


class GarrisonNameUITests(unittest.TestCase):
    def test_garrison_displays_clean_names_and_keeps_database_identifiers(self):
        from strategy_ui_fixture import city_fixture,Window,Label
        from test_dialog_layout import settle
        previous=Window.size;Window.size=(640,360)
        popup,db=city_fixture();self.addCleanup(db.close)
        names=('Владислав','Спутник: Ярл Астрид / Адепты #4','Странник: Рунный проводник / Адепты')
        try:
            for i,name in enumerate(names):
                db.execute('INSERT INTO units VALUES(?,?,?,?,?,?,?,?)',(name,'files/pict/hire/sword.png','3' if i==0 else '1',100,100,10,100,'infantry'))
                db.execute('INSERT INTO garrisons VALUES(?,?,?,?,?)',(popup.city_name,name,1 if i<2 else 1000,'files/pict/hire/sword.png',0))
            db.commit();popup.update_garrison();popup.open(animation=False);settle()
            text=' '.join(w.text for w in popup.walk() if isinstance(w,Label))
            for name in names:self.assertIn(unit_display_name(name),text)
            for unwanted in ('Спутник:','Странник:',' / Адепты','#4','[Чемпион]'):self.assertNotIn(unwanted,text)
            self.assertEqual(tuple(r[0] for r in db.execute('SELECT unit_name FROM garrisons')),names)
            popup.export_to_png('.release/garrison-clean-unit-names.png')
        finally:
            popup.dismiss(animation=False);Window.size=previous;settle()
