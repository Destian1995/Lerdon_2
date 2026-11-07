from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from test_otherworlds import fixture
from tactical_geography import local_field,context,remember_map
from tactical_combat import TERRAINS
from map_terrain import FOREST,WATER,DESERT,SNOW


class TacticalGeographyTests(unittest.TestCase):
    def test_real_city_coordinates_choose_local_biome_and_terrain(self):
        db=fixture();self.addCleanup(db.close)
        remember_map(db,'files/map/generate/map_1.png')
        seen=[]
        def kind(x,y):seen.append((x,y));return FOREST
        mask=SimpleNamespace(kind_at=kind)
        with patch('map_terrain.load_terrain',return_value=mask):
            result=context(db,'Home','Север')
        self.assertEqual(result['biome'],'forest')
        self.assertEqual(len(result['terrain']),100)
        self.assertAlmostEqual(sum(x for x,y in seen)/len(seen),138.5)
        self.assertAlmostEqual(sum(y for x,y in seen)/len(seen),124)
        self.assertIn('forest',result['terrain'].values())

    def test_bridges_keep_local_water_fields_crossable_and_masks_match_rules(self):
        for kind,biome in ((WATER,'coast'),(DESERT,'desert'),(SNOW,'snow'),(FOREST,'forest')):
            name,field=local_field(SimpleNamespace(kind_at=lambda x,y:kind),0,0)
            self.assertEqual(name,biome)
            self.assertTrue(set(field.values())<=set(TERRAINS))
            for y in (3,6):self.assertTrue(all(not TERRAINS[field[x,y]].blocked for x in range(10)))

    def test_all_eight_painted_backgrounds_exist(self):
        for kind in ('plains','forest','snow','desert','swamp','highland','coast','corruption'):
            path=Path('files/battlefields')/(kind+'.png')
            self.assertTrue(path.is_file())
            self.assertEqual(path.read_bytes()[:8],b'\x89PNG\r\n\x1a\n')


if __name__=='__main__':unittest.main()
