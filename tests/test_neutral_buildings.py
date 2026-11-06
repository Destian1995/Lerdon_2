import unittest
from city_construction import CATALOG,ensure_neutral_buildings,building_counts
from test_unique_development import fixture


class NeutralBuildingsTests(unittest.TestCase):
    def setUp(self):
        self.db=fixture();self.addCleanup(self.db.close)
        self.db.execute("UPDATE cities SET faction='Нейтрал' WHERE name='B'")

    def test_full_catalogue_is_free_unique_and_preserves_player_buildings(self):
        self.db.executemany('INSERT INTO buildings VALUES(?,?,?,?)',[
            ('A','Север','Рынок',1),('B','Север','Больница',4),('B','Нейтрал','Больница',2)])
        resources=list(self.db.execute('SELECT * FROM resources'))
        for _ in range(3):ensure_neutral_buildings(self.db)
        self.assertEqual(building_counts(self.db,'B','Нейтрал'),dict.fromkeys(CATALOG,1))
        self.assertEqual(building_counts(self.db,'A','Север'),{'Рынок':1})
        self.assertEqual(list(self.db.execute('SELECT * FROM resources')),resources)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM buildings WHERE city_name='B'").fetchone()[0],6)

    def test_captured_town_loses_all_buildings_and_does_not_get_free_repairs(self):
        ensure_neutral_buildings(self.db)
        self.db.execute("UPDATE cities SET faction='Север' WHERE name='B'")
        ensure_neutral_buildings(self.db)
        self.assertEqual(building_counts(self.db,'B','Север'),{})
        ensure_neutral_buildings(self.db)
        self.assertEqual(building_counts(self.db,'B','Север'),{})

    def test_every_conqueror_demolishes_only_captured_town_in_same_transaction(self):
        self.db.execute("INSERT INTO buildings VALUES('A','Север','Рынок',1)")
        ensure_neutral_buildings(self.db)
        self.db.commit()
        for conqueror in ('Север','Эльфы','Вампиры','Адепты','Элины','Мятежники','Нежить'):
            with self.subTest(conqueror=conqueror):
                self.db.execute('SAVEPOINT capture')
                self.db.execute("UPDATE cities SET faction=? WHERE name='B'",(conqueror,))
                self.assertEqual(self.db.execute("SELECT COUNT(*) FROM buildings WHERE city_name='B'").fetchone()[0],0)
                self.assertEqual(building_counts(self.db,'A','Север'),{'Рынок':1})
                self.db.execute('ROLLBACK TO capture');self.db.execute('RELEASE capture')
                self.assertEqual(building_counts(self.db,'B','Нейтрал'),dict.fromkeys(CATALOG,1))

    def test_same_owner_update_preserves_buildings_and_old_saves_receive_trigger(self):
        from city_construction import ensure_unique_buildings
        ensure_neutral_buildings(self.db)
        self.db.execute('DROP TRIGGER demolish_captured_city_buildings')
        ensure_unique_buildings(self.db)  # Existing uniqueness index must not skip the new migration.
        self.db.execute("UPDATE cities SET faction='Нейтрал' WHERE name='B'")
        self.assertEqual(building_counts(self.db,'B','Нейтрал'),dict.fromkeys(CATALOG,1))
        self.db.execute("UPDATE cities SET faction='Север' WHERE name='B'")
        self.assertEqual(building_counts(self.db,'B','Север'),{})


if __name__=='__main__':unittest.main()
