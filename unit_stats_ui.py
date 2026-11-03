"""Stat rows sized from the space available in a unit detail card."""
from kivy.clock import Clock
from kivy.metrics import dp, sp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.image import Image
from kivy.uix.label import Label


class UnitStatsPanel(BoxLayout):
    def __init__(self, stats, hero=False, **kwargs):
        super().__init__(orientation='vertical', padding=dp(8), **kwargs)
        self._responsive_keep_geometry = True
        self.hero = hero
        self.rows = []
        for caption, source, value in stats:
            row = BoxLayout(size_hint_y=None, spacing=dp(10))
            icon = Image(source=source, size_hint=(None, None),
                         pos_hint={'center_y': .5}, allow_stretch=True,
                         keep_ratio=True, mipmap=True)
            label = Label(text=f'[color=#CCCCCC]{caption}:[/color] [b]{value}[/b]',
                          markup=True, halign='left', valign='middle')
            row.add_widget(icon)
            row.add_widget(label)
            self.add_widget(row)
            self.rows.append((row, icon, label))
        self._resize = Clock.create_trigger(self._fit, 0)
        self.bind(size=self._resize)
        self._resize()

    def _fit(self, *_):
        if not self.rows:
            return
        width = max(1, self.width-dp(16))
        height = max(1, self.height-dp(16))
        count = len(self.rows)
        self.spacing = min(dp(14), height*.035)
        budget = max(1, height-self.spacing*(count-1))
        # Four hero stats use the card's height rather than fixed 16sp rows.
        font = min(sp(34 if self.hero else 23), width/(16 if self.hero else 24),
                   budget/count*.48)
        font = max(sp(12), font)
        for _ in range(12):
            icon_size = font*1.6
            heights = []
            for row, icon, label in self.rows:
                icon.size = (icon_size, icon_size)
                label.font_size = font
                label.text_size = (max(1, width-icon_size-row.spacing), None)
                label.texture_update()
                heights.append(max(icon_size, label.texture_size[1]+dp(6)))
            if sum(heights) <= budget or font <= sp(12):
                break
            font = max(sp(12), font*.9)
        extra = max(0, budget-sum(heights))/count
        for (row, _, _), height in zip(self.rows, heights):
            row.height = height+extra
