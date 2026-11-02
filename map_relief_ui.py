"""Small relief foundations and readable city geography labels."""
from functools import lru_cache


def draw_city_base(widget, info, x, y, size):
    if not info or info.landform != 'highland':
        return
    from kivy.graphics import Color, Ellipse, Triangle
    # The footprint/road endpoint stays fixed. A shaded stone terrace conveys
    # height without moving hit targets or letting buildings hang over water.
    with widget.canvas:
        Color(.04,.035,.025,.38)
        Ellipse(pos=(x+size*.04,y-size*.03),size=(size*.92,size*.24))
        Color(.34,.32,.27,.9)
        Triangle(points=(x+size*.10,y+size*.08,x+size*.90,y+size*.08,x+size*.76,y-size*.01))
        Color(.57,.54,.43,.9)
        Triangle(points=(x+size*.10,y+size*.08,x+size*.76,y-size*.01,x+size*.22,y-size*.01))


@lru_cache(maxsize=12)
def _badge_texture(text):
    from kivy.core.text import Label as CoreLabel
    label=CoreLabel(text=text,font_size=12,bold=True,color=(.95,.89,.63,1),
                    outline_width=1,outline_color=(.025,.035,.035,1))
    label.refresh()
    return label.texture


def draw_city_badges(widget, info, x, y, size, label_y):
    if not info or not info.badges:
        return
    from kivy.graphics import Color, Rectangle
    names=[]
    if info.landform == 'highland':
        names.append('Горы')
    elif info.landform == 'lowland':
        names.append('Низина')
    if info.waterside:
        names.append('Берег')
    texture=_badge_texture(' · '.join(names))
    left=x+(size-texture.width)/2
    left=max(widget.map_pos[0]+3,min(left,widget.map_pos[0]+widget.base_map_width*widget.map_scale-texture.width-3))
    with widget.canvas:
        Color(1,1,1,1)
        Rectangle(texture=texture,pos=(left,label_y-texture.height-2),size=texture.size)
