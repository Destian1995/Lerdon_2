import sqlite3
import unittest
from pathlib import Path
from campaign_endings import epilogue,FACTIONS


class EndingsTests(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(':memory:');self.addCleanup(self.db.close)
        self.db.executescript('''CREATE TABLE portal_soul_pacts(faction);
            CREATE TABLE morgana_covenants(faction,status);
            CREATE TABLE portal_monster_cases(faction,reward_unit);''')

    def test_every_faction_has_its_own_victory_and_defeat(self):
        images=set();stories=set()
        for faction in FACTIONS:
            for status in ('win','lose'):
                data=epilogue(self.db,faction,status,'Все фракции были уничтожены' if status=='win' else 'Противник завоевал все ваши города. Поражение!')
                images.add(data['image']);stories.add(data['story'])
                self.assertTrue(data['consequence'])
                self.assertTrue(Path(data['image']).is_file())
        self.assertEqual(len(images),14);self.assertEqual(len(stories),14)

    def test_every_actual_loss_reason_has_a_distinct_epilogue(self):
        for reason,kind in (('Города опустели....','population'),('Вас свергли нелояльные члены совета','coup'),
                            ('Город входа в портал захвачен. Путь домой потерян.','portal'),
                            ('Срок сделки за душу истёк','soul'),('Противник завоевал все ваши города','cities'),
                            ('Ошибка при проверке завершения игры: test','error')):
            self.assertEqual(epilogue(self.db,'Элины','lose',reason)['kind'],kind)

    def test_choices_change_winning_epilogue_without_writing_campaign(self):
        self.assertEqual(epilogue(self.db,'Север','win','Мир во всем мире')['kind'],'peace')
        self.db.execute("INSERT INTO portal_monster_cases VALUES('Север','Companion')")
        self.assertIn('сохранив свою душу',epilogue(self.db,'Север','win','Все фракции были уничтожены')['story'])
        self.db.execute("INSERT INTO portal_soul_pacts VALUES('Север')")
        self.assertIn('до истечения',epilogue(self.db,'Север','win','Все фракции были уничтожены')['story'])
        self.db.execute("INSERT INTO morgana_covenants VALUES('Север','accepted')")
        before=self.db.total_changes
        data=epilogue(self.db,'Север','win','Все фракции были уничтожены')
        self.assertEqual(data['kind'],'morgana');self.assertIn('Морган',data['title'])
        self.assertEqual(self.db.total_changes,before)

    def test_old_saves_without_optional_tables_still_work(self):
        db=sqlite3.connect(':memory:')
        try:self.assertEqual(epilogue(db,'Адепты','win','Мир во всем мире')['kind'],'peace')
        finally:db.close()
