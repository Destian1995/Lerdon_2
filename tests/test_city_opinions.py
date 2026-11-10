import unittest
from city_opinions import conversations
from test_main_map_intrigues import fixture
from city_war import record_capture,record_battle

class CityOpinionTests(unittest.TestCase):
    def setUp(self):
        self.db=fixture();self.addCleanup(self.db.close)
    def text(self,rate,city='Дом'):
        return ' '.join(text for _,text in conversations(self.db,city,{'Север':rate,'Адепты':34,'Эльфы':10}))
    def test_tax_boundaries_match_population_effect(self):
        for rate in (0,10,24):self.assertIn('родным',self.text(str(rate)+'%'))
        for rate in (25,30,34):self.assertIn('перспективы',self.text(rate))
        for rate in (35,45,90,100):
            text=self.text(rate)
            self.assertIn('уехать',text);self.assertIn('Союзный',text)
        self.assertIn('перспективы',self.text(None))
    def test_plunder_and_mercy_remain_in_conversations(self):
        self.db.execute("UPDATE cities SET faction='Север' WHERE name='Вражеский'")
        import main_map_intrigues as plots
        plots.captured(self.db,'Вражеский','Север',1)
        row=plots.journal(self.db,'Север')['captures'][0]
        plots.settle_capture(self.db,'Север',row['id'],'plunder')
        self.assertIn('После разграбления',self.text(10,'Вражеский'))
        self.assertIn('доверие после грабежа',self.text(10,'Вражеский'))
        plots.captured(self.db,'Вражеский','Север',2)
        row=plots.journal(self.db,'Север')['captures'][0]
        plots.settle_capture(self.db,'Север',row['id'],'spare')
        self.assertIn('запретил грабить',self.text(30,'Вражеский'))
    def test_peaceful_and_neutral_captures_do_not_ask_to_plunder(self):
        self.db.execute("UPDATE cities SET faction='Север' WHERE name='Нейтральный'")
        record_capture(self.db,'Нейтральный','Север')
        record_battle(self.db,'Нейтральный',100,10,'Нейтрал')
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM map_intrigue_captures').fetchone()[0],0)
        self.db.execute("UPDATE cities SET faction='Север' WHERE name='Вражеский'")
        record_battle(self.db,'Вражеский',100,10,'Адепты')
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM map_intrigue_captures').fetchone()[0],1)

if __name__=='__main__':unittest.main()
