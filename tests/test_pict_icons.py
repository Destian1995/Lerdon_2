"""Runtime icon assets and UI fallback regressions; no game database imports."""
import os
os.environ['KIVY_NO_ARGS'] = '1'
os.environ['KIVY_NO_CONFIG'] = '1'
os.environ['KIVY_NO_FILELOG'] = '1'
os.environ['KIVY_METRICS_DENSITY'] = '1'
os.environ['KIVY_METRICS_FONTSCALE'] = '1'
import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch
from PIL import Image
from kivy.config import Config
Config.set('graphics', 'window_state', 'hidden')
from kivy.core.image import Image as CoreImage
from kivy.uix.image import Image as ImageWidget

ROOT = Path(__file__).resolve().parents[1]


class PictIconTests(unittest.TestCase):
    def test_generated_assets_are_complete_transparent_and_compact(self):
        data = json.loads((ROOT / 'assets/pict-redraw-manifest.json').read_text(encoding='utf-8'))
        self.assertEqual(len(data['entries']), 19)
        decoded_bytes = 0
        for entry in data['entries']:
            path = ROOT / entry['output']
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), entry['sha256'])
            with Image.open(path) as image:
                self.assertEqual(image.mode, 'RGBA')
                self.assertEqual(image.size, (entry['size'], entry['size']))
                self.assertEqual(image.getchannel('A').getextrema(), (0, 255))
                box = image.getchannel('A').getbbox()
                self.assertGreater(box[0], 0)
                self.assertGreater(box[1], 0)
                self.assertLess(box[2], image.width)
                self.assertLess(box[3], image.height)
                decoded_bytes += image.width * image.height * 4
            self.assertEqual(CoreImage(str(path)).texture.size, (entry['size'], entry['size']))
        self.assertLess(decoded_bytes, 4 * 1024 * 1024)

    def test_chat_header_uses_widget_and_resets_unknown_faction_icon(self):
        # Load this UI module without executing ai_models' app-level initializer.
        package = ModuleType('ai_models')
        package.__path__ = [str(ROOT / 'ai_models')]
        ui_package = ModuleType('ai_models.ui')
        ui_package.__path__ = [str(ROOT / 'ai_models/ui')]
        translation = ModuleType('ai_models.translation')
        exec(compile((ROOT / 'ai_models/translation.py').read_text(encoding='utf-8'),
                     'translation.py', 'exec'), translation.__dict__)
        with patch.dict(sys.modules, {'ai_models': package, 'ai_models.ui': ui_package,
                                      'ai_models.translation': translation}):
            spec = importlib.util.spec_from_file_location('ai_models.ui.chat_widgets',
                                                         ROOT / 'ai_models/ui/chat_widgets.py')
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            header = module.ChatHeader('Север')
            self.assertIsInstance(header.icon, ImageWidget)
            self.assertEqual(header.icon.source, 'files/sov/people.jpg')
            header.update_info('Эльфы', {})
            self.assertEqual(header.icon.source, 'files/sov/elfs.jpg')
            header.update_info('Неизвестная фракция', {})
            self.assertEqual(header.icon.source, 'files/pict/question.png')
            header.clear_widgets()

    def test_random_ideology_restores_bonus_icon(self):
        tree = ast.parse((ROOT / 'main.py').read_text(encoding='utf-8'))
        method = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
                      and n.name == 'on_ideology_selected')
        namespace = {}
        exec(compile(ast.Module(body=[method], type_ignores=[]), 'main.py', 'exec'), namespace)
        menu = SimpleNamespace(ideology_bonus_label=SimpleNamespace(text='', color=None),
                               ideology_bonus_icon=SimpleNamespace(source='files/status/resource_box/coin.png'))
        namespace['on_ideology_selected'](menu, None, 'Случайная')
        self.assertEqual(menu.ideology_bonus_icon.source, 'files/pict/menu/bonus_icon.png')
        self.assertEqual(menu.selected_ideology, 'random')


if __name__ == '__main__':
    unittest.main()
