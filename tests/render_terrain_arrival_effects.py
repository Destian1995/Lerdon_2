"""Preview the real short-lived waypoint pulses and march without a game DB."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from strategy_ui_fixture import Window,Widget,Color,Rectangle
from test_frontend_ui import settle
from kivy.core.text import Label as CoreLabel
from PIL import Image
from map_atmosphere import MapAtmosphere
from map_roads import TransportNetwork,draw_transport_layer
from terrain_icons import icon_texture
from troop_movement import MarchRoute

Window.size=(1000,600)
root=Widget(size_hint=(None,None),size=(1000,600))
with root.canvas:
    Color(1,1,1,1);Rectangle(source='files/map/generate/map_1.png',size=root.size)
path=[(100,300),(900,300)]
root.canvas.add(draw_transport_layer(TransportNetwork(land=[(1,2,path)]),1))
sites=[dict(id=1,kind='forest',x=360,y=300),dict(id=2,kind='swamp',x=650,y=300)]
for site,name in zip(sites,('Лес','Болото')):
    with root.canvas:
        Color(1,1,1,1)
        Rectangle(texture=icon_texture(site['kind'],1),pos=(site['x']-34,site['y']-26),size=(68,68))
    label=CoreLabel(text=name,font_size=20,bold=True,outline_width=1,outline_color=(0,0,0,1));label.refresh()
    with root.canvas:
        Color(1,1,1,1);Rectangle(texture=label.texture,pos=(site['x']-label.texture.width/2,350),size=label.texture.size)
layer=MapAtmosphere();layer.configure((0,0),1,(1000,600))
root.add_widget(layer);Window.add_widget(root);settle();layer.stop()
layer.marches.terrain_arrivals.set_sites(sites)
layer.marches.play_batch([(lambda:MarchRoute(path,[True]),1,'Север',100)],lambda:None,lambda:None)
frames=[]
for _ in range(105):
    layer.update(1/20)
    texture=root.export_as_image().texture
    frames.append(Image.frombytes('RGBA',texture.size,texture.pixels).convert('RGB'))
out=Path('assets/terrain-arrival');out.mkdir(exist_ok=True)
frames[39].save(out/'forest-pulse.png')
frames[75].save(out/'swamp-pulse.png')
palette=frames[39].quantize(colors=128)
indexed=[frame.quantize(palette=palette,dither=Image.Dither.NONE) for frame in frames]
indexed[0].save(out/'arrival.gif',save_all=True,append_images=indexed[1:],duration=50,loop=0,optimize=True)
Window.remove_widget(root)
