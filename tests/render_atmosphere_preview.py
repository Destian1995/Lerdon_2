"""Render weather previews without starting the game or opening its database.

Run from project root: py -3.12 tests/render_atmosphere_preview.py
"""
import os
os.environ['KIVY_NO_ARGS'] = '1'
os.environ['KIVY_NO_CONFIG'] = '1'
os.environ['KIVY_NO_FILELOG'] = '1'

import sys
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from kivy.config import Config
Config.set('graphics', 'window_state', 'hidden')
Config.set('graphics', 'width', '1200')
Config.set('graphics', 'height', '800')
from kivy.core.image import Image as CoreImage
from kivy.core.text import Label as CoreLabel
from kivy.graphics import Color, Rectangle
from kivy.uix.widget import Widget
from PIL import Image, ImageDraw
from map_atmosphere import MapAtmosphere


def render(output, season):
    root = Widget(size=(1200, 800), size_hint=(None, None))
    with root.canvas:
        Color(1, 1, 1, 1)
        Rectangle(texture=CoreImage('files/map/generate/map_2.png').texture,
                  pos=(0, 0), size=(1200, 800))
        for x, y, image, name in (
            (470, 350, 'castle_death.png', 'Некрополь'),
            (635, 390, 'default.png', 'Город под чумой'),
            (750, 250, 'castle_death.png', 'Морготар'),
        ):
            Rectangle(texture=CoreImage('files/buildings/' + image).texture,
                      pos=(x, y), size=(77, 77))
            label = CoreLabel(text=name, font_size=17, color=(1, 1, 1, 1))
            label.refresh()
            Rectangle(texture=label.texture, pos=(x + 38 - label.texture.size[0] / 2, y - 20),
                      size=label.texture.size)
    layer = MapAtmosphere()
    layer.configure((0, 0), 1)
    layer.set_season(season)
    layer.set_storms([(508.5, 388.5, False), (788.5, 288.5, True)])
    layer.set_plague([('Некрополь', 0, 470, 350), ('Цель', 32, 635, 390)],
                     [('Некрополь', 470, 350)])
    root.add_widget(layer)
    layer._time = 1.2
    layer._strike(layer._storms[0])
    layer.update(0)
    root.export_to_png(str(output))
    layer.stop()
    root.remove_widget(layer)


if __name__ == '__main__':
    sheet = Image.new('RGB', (1200, 1175), '#19212c')
    draw = ImageDraw.Draw(sheet)
    with tempfile.TemporaryDirectory() as directory:
        for index, (season, title) in enumerate((('Зима', 'WINTER / SNOW'), ('Весна', 'SPRING / RAIN FRONT'),
                                                ('Лето', 'SUMMER / CLOUD SHADOWS'), ('Осень', 'AUTUMN / DRIZZLE'))):
            path = Path(directory) / f'{index}.png'
            render(path, season)
            preview = Image.open(path).convert('RGB').resize((600, 400), Image.Resampling.LANCZOS)
            x, y = index % 2 * 600, index // 2 * 425
            draw.text((x + 12, y + 6), title, fill='white')
            sheet.paste(preview, (x, y + 25))
            if season == 'Лето':
                detail = Image.open(path).convert('RGB').crop((410, 300, 730, 470))
                detail = detail.resize((600, 319), Image.Resampling.LANCZOS)
                draw.text((12, 858), 'UNDEAD STORM AND PLAGUE / DETAIL', fill='white')
                for row, text in enumerate(('Cloud banks with internal lightning flashes',
                                            'Travelling spores from a real undead source',
                                            'Ground mist and a short outbreak wave',
                                            'One reusable, map-clipped graphics layer')):
                    draw.text((20, 905 + row * 26), text, fill='#bccad4')
                sheet.paste(detail, (600, 850))
    destination = Path('assets/atmosphere-preview.jpg')
    destination.parent.mkdir(exist_ok=True)
    sheet.save(destination, quality=94)
    print(destination.resolve())
