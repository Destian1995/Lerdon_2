"""A compact equipment view: slots flank the hero, stats stay above the portrait."""
from kivy.metrics import dp, sp


def layout_equipment(panel, portrait, stats, slots, labels):
    inset = dp(10)
    width, height = panel.size
    if height < dp(240) and width >= dp(270):
        # Very short Android viewports cannot fit three rows beside a portrait.
        # Use one visible equipment belt, with portrait and stats together above.
        cell = (width - inset * 2) / 5
        slot_size = min(dp(64), cell - dp(6))
        belt = slot_size + dp(24)
        stats.size = (width * .40, max(dp(60), height - belt - inset * 3))
        stats.pos = (panel.right - inset - stats.width, panel.y + inset * 2 + belt)
        stats.font_size = sp(14)
        stats.halign, stats.valign = 'center', 'middle'
        if portrait:
            portrait.pos_hint = {}
            portrait.size = (width * .52, stats.height)
            portrait.pos = (panel.x + inset, stats.y)
            portrait.fit_mode = 'contain'
        for index, key in enumerate(('0', '1', '2', '3', '4')):
            slot, label = slots.get(key), labels.get(key)
            x = panel.x + inset + index * cell
            if slot:
                slot.size = (slot_size, slot_size)
                slot.pos = (x + (cell - slot_size) / 2, panel.y + inset + dp(22))
            if label:
                if label.parent is None:
                    panel.add_widget(label)
                label.size = (cell, dp(22))
                label.pos = (x, panel.y + inset)
                label.font_size = sp(11)
                label.text_size = label.size
                label.shorten, label.max_lines = True, 1
        return
    side = min(dp(100), width * .24)
    middle = max(dp(40), width - side * 2 - inset * 2)
    stats.size = (middle, dp(72))
    stats.pos = (panel.x + (width - middle) / 2, panel.top - inset - stats.height)
    stats.font_size = sp(14 if width < dp(420) else 18)
    stats.halign, stats.valign = 'center', 'middle'
    if portrait:
        portrait.pos_hint = {}
        portrait.size = (middle, max(dp(40), height - stats.height - inset * 3))
        portrait.pos = (stats.x, panel.y + inset)
        portrait.fit_mode = 'contain'
    row_height = max(dp(70), (height - inset * 2) / 3)
    slot_size = max(dp(48), min(dp(80), side - dp(12), row_height - dp(24)))
    for index, key in enumerate(('0', '1', '2', '3', '4')):
        column, row = (0, index) if index < 3 else (1, index - 3)
        x = panel.x + inset if column == 0 else panel.right - inset - side
        top = panel.top - inset - row * row_height
        slot, label = slots.get(key), labels.get(key)
        if slot:
            slot.size = (slot_size, slot_size)
            slot.pos = (x + (side - slot_size) / 2, top - slot_size)
        if label:
            if label.parent is None:
                panel.add_widget(label)
            label.size = (side, dp(22))
            label.pos = (x, top - slot_size - dp(22))
            label.font_size = sp(12 if width < dp(420) else 14)
            label.text_size = label.size
            label.shorten, label.max_lines = True, 1


def configure_artifact_shop(root, inventory, hero_panel):
    root._responsive_keep_geometry = True
    def fit(*args):
        portrait = root.width < dp(600) and root.height > root.width
        mode = 'vertical' if portrait else 'horizontal'
        if root.orientation != mode:
            root.orientation = mode
            root.clear_widgets()
            for panel in ((hero_panel, inventory) if portrait else (inventory, hero_panel)):
                root.add_widget(panel)
        inventory.size_hint = (1, .48) if portrait else (.46, 1)
        hero_panel.size_hint = (1, .52) if portrait else (.54, 1)
    root.bind(size=fit)
    fit()
