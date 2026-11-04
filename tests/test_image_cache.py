import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from strategy_ui_fixture import Widget
from image_cache import refresh_image_cache,IMAGE_CACHE_DIRS,IMAGE_CACHE_VERSION


class ImageCacheTests(unittest.TestCase):
    def test_visual_update_clears_every_image_cache_without_touching_saves(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            save=root/'game_data.db';save.write_bytes(b'player-progress')
            art=root/'files'/'city.png';art.parent.mkdir();art.write_bytes(b'asset')
            for name in IMAGE_CACHE_DIRS:
                target=root/name;target.mkdir(parents=True,exist_ok=True)
                (target/'old.png').write_bytes(b'cached')
            with patch('kivy.cache.Cache.remove') as clear:
                self.assertTrue(refresh_image_cache(root))
                self.assertEqual(clear.call_count,4)
            self.assertTrue(all(not (root/name).exists() for name in IMAGE_CACHE_DIRS))
            self.assertEqual(save.read_bytes(),b'player-progress')
            self.assertEqual(art.read_bytes(),b'asset')
            self.assertEqual(json.loads((root/'image-cache-version.json').read_text())['version'],IMAGE_CACHE_VERSION)
            self.assertFalse(refresh_image_cache(root))
