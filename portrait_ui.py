"""Opt-in frames for large portraits; map and menu icons stay undecorated."""
from kivy.graphics import Color, InstructionGroup, Line
from kivy.metrics import dp
from kivy.clock import Clock

from strategy_ui import GOLD, FACTIONS

FACTION_PATHS = {'people': 'Север', 'elfs': 'Эльфы', 'elf': 'Эльфы',
                 'vampires': 'Вампиры', 'vampire': 'Вампиры', 'adepts': 'Адепты',
                 'adept': 'Адепты', 'poly': 'Элины', 'death': 'Нежить', 'rebellion': 'Мятежники'}


def portrait_accent(source):
    path = (source or '').replace('\\', '/').lower()
    if 'otherworld/' in path:
        for key, faction in (('north', 'Север'), ('elves', 'Эльфы'),
                             ('vampires', 'Вампиры'), ('adepts', 'Адепты'), ('elines', 'Элины')):
            if '/'+key+'/' in path:
                return FACTIONS.get(faction, GOLD)
        return GOLD
    if '/files/' in path:
        path = path.split('/files/', 1)[1]
    elif path.startswith('files/'):
        path = path[6:]
    else:
        return None
    pieces = path.split('/')
    if len(pieces) >= 3 and pieces[0] == 'army':
        return FACTIONS.get(FACTION_PATHS.get(pieces[1]), GOLD)
    if path.startswith('pict/hero/'):
        return GOLD
    if path.startswith('sov/'):
        key = pieces[-1].rsplit('.', 1)[0]
        return FACTIONS.get(FACTION_PATHS.get(key), GOLD)
    if len(pieces) == 2 and pieces[0] == 'buildings':
        key = pieces[1].rsplit('.', 1)[0]
        if key in FACTION_PATHS:
            return FACTIONS.get(FACTION_PATHS[key], GOLD)
    return None


class PortraitFrame:
    def __init__(self, widget):
        self.widget = widget
        self.group = InstructionGroup()
        self.accent = Color(*GOLD)
        self.outer = Line(width=dp(1.1))
        self.inner_color = Color(*GOLD[:3], .4)
        self.inner = Line(width=dp(.7))
        self.gold = Color(*GOLD)
        self.corners = [Line(width=dp(1.8)) for _ in range(4)]
        for instruction in (self.accent, self.outer, self.inner_color, self.inner, self.gold, *self.corners):
            self.group.add(instruction)
        widget.canvas.after.add(self.group)
        self._update_event=Clock.create_trigger(self.update,-1)
        widget.bind(pos=self._update_event, size=self._update_event, texture=self._update_event,
                    texture_size=self._update_event, norm_image_size=self._update_event,
                    color=self._update_event, fit_mode=self._update_event)
        self.update()

    def update(self, *args):
        widget = self.widget
        accent = portrait_accent(widget.source)
        visible = (getattr(widget, '_portrait_frame_enabled', False) and accent is not None
                   and widget.texture is not None and not getattr(widget, '_portrait_frame_disabled', False))
        self.visible = visible
        alpha = widget.color[3] if visible else 0
        self.accent.rgba = (*(accent or GOLD)[:3], alpha)
        self.inner_color.a = alpha * .4
        self.gold.a = alpha
        if not visible:
            return
        if self.group not in widget.canvas.after.children:
            widget.canvas.after.add(self.group)
        # Use raw geometry: center/norm_image_size aliases can still contain the
        # previous layout's cached values while Image is moving/loading an atlas.
        tw,th=widget.texture.size
        w,h=max(0,widget.width),max(0,widget.height)
        scale=min(w/max(1,tw),h/max(1,th))
        if widget.fit_mode=='scale-down':scale=min(1,scale)
        if widget.fit_mode=='cover':scale=max(w/max(1,tw),h/max(1,th))
        width,height=(w,h) if widget.fit_mode=='fill' else (min(w,tw*scale),min(h,th*scale))
        x,y=widget.x+(w-width)/2,widget.y+(h-height)/2
        self.image_bounds = (x, y, width, height)
        padding = dp(4)
        x, y, width, height = x - padding, y - padding, width + 2 * padding, height + 2 * padding
        self.bounds = (x, y, width, height)
        inset = min(dp(1), width / 30, height / 30)
        radius = min(dp(8), width / 8, height / 8)
        self.outer.rounded_rectangle = (x + inset, y + inset, max(0, width - inset * 2),
                                        max(0, height - inset * 2), radius)
        self.inner.rounded_rectangle = (x + inset * 2, y + inset * 2, max(0, width - inset * 4),
                                        max(0, height - inset * 4), max(0, radius - inset))
        length = min(dp(15), width / 5, height / 5)
        for line, (cx, cy, sx, sy) in zip(self.corners, (
                (x + inset, y + inset, 1, 1), (x + width - inset, y + inset, -1, 1),
                (x + inset, y + height - inset, 1, -1), (x + width - inset, y + height - inset, -1, -1))):
            line.points = (cx, cy + length * sy, cx, cy, cx + length * sx, cy)


def style_portrait_image(widget, *args, enabled=None):
    if enabled is not None:
        widget._portrait_frame_enabled = enabled
    decoration = getattr(widget, '_portrait_frame', None)
    if not getattr(widget, '_portrait_frame_enabled', False):
        if decoration:
            decoration.update()
        return
    if not getattr(widget, '_portrait_source_bound', False):
        widget.bind(source=style_portrait_image)
        widget._portrait_source_bound = True
    if decoration is None and portrait_accent(widget.source) is not None:
        widget._portrait_frame = PortraitFrame(widget)
    elif decoration:
        decoration.update()
