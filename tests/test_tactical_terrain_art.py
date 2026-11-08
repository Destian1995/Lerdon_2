"""Terrain paintings must agree with combat cells and stay inside touch targets."""
import unittest
from strategy_ui_fixture import Window  # Initialize the real Kivy image provider.
from tactical_terrain_art import ROOT, TerrainArt, landmark_rect, terrain_path


class TacticalTerrainArtTests(unittest.TestCase):
    def test_every_landmark_loads_once_and_cleanup_releases_cache(self):
        art = TerrainArt()
        for biome in ('plains', 'forest', 'snow', 'desert', 'corruption'):
            for kind in ('forest', 'swamp', 'hill', 'rock', 'water', 'bridge'):
                for pos in ((0, 0), (1, 0)):
                    texture = art.texture(kind, pos, biome)
                    self.assertIs(texture, art.texture(kind, pos, biome))
                    self.assertGreater(texture.width, 0)
                    self.assertGreater(texture.height, 0)
        self.assertIsNone(art.texture('plain', (0, 0), 'plains'))
        art.clear()
        self.assertFalse(art.textures)

    def test_forest_and_marsh_reuse_world_map_art_with_biome_variants(self):
        self.assertIn('files/map/features', terrain_path('forest', (0, 0), 'forest').relative_to(ROOT).as_posix())
        self.assertEqual(terrain_path('forest', (0, 0), 'snow').name, 'forest_2.png')
        self.assertEqual(terrain_path('swamp', (0, 0), 'corruption').name, 'swamp_1_dead.png')
        self.assertNotEqual(terrain_path('forest', (0, 0), 'plains'),
                            terrain_path('forest', (1, 0), 'plains'))

    def test_landmarks_fit_cells_at_phone_sizes_without_distortion(self):
        for cell in (25, 42, 60, 100):
            for dimensions in ((1000, 600), (600, 1000), (1280, 1280)):
                (x, y), (w, h) = landmark_rect(dimensions, 13, 17, cell)
                self.assertGreaterEqual(x, 13)
                self.assertGreaterEqual(y, 17)
                self.assertLessEqual(x + w, 13 + cell)
                self.assertLessEqual(y + h, 17 + cell)
                self.assertAlmostEqual(w / h, dimensions[0] / dimensions[1])


if __name__ == '__main__':
    unittest.main()
