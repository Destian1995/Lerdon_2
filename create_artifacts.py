import os
import random

from ui_components import show_message
from utils.helpers import format_number

_CLR_BG = (0.05, 0.06, 0.10, 1)
_CLR_BG_CARD = (0.08, 0.09, 0.14, 1)
_CLR_BG_PANEL = (0.07, 0.08, 0.12, 1)
_CLR_GOLD = (0.90, 0.75, 0.25, 1)
_CLR_GOLD_DIM = (0.65, 0.55, 0.18, 1)
_CLR_PURPLE = (0.55, 0.30, 0.80, 1)
_CLR_PURPLE_LIGHT = (0.65, 0.40, 0.90, 1)
_CLR_TEXT = (0.88, 0.90, 0.95, 1)
_CLR_TEXT_DIM = (0.55, 0.58, 0.65, 1)
_CLR_GREEN = (0.30, 0.75, 0.40, 1)
_CLR_RED = (0.80, 0.25, 0.25, 1)
_CLR_BLUE = (0.30, 0.55, 0.85, 1)

_SLOT_MAP = {0: 'Оружие', 1: 'Голова', 2: 'Ноги', 3: 'Туловище', 4: 'Аксессуар'}
_SLOT_LABELS = ['Оружие', 'Голова', 'Ноги', 'Туловище', 'Аксессуар']
_SLOT_PREFIXES = {'Оружие': '0', 'Голова': '1', 'Ноги': '2', 'Туловище': '3', 'Аксессуар': '4'}


def workshop(faction, db_conn):
    from kivy.uix.popup import Popup
    from kivy.uix.boxlayout import BoxLayout
    from kivy.uix.button import Button
    from kivy.uix.label import Label
    from kivy.uix.slider import Slider
    from kivy.uix.image import Image
    from kivy.graphics import Color, RoundedRectangle
    from kivy.metrics import dp, sp
    from kivy.utils import platform as _platform

    is_android = _platform == 'android'
    font_title = sp(17) if not is_android else sp(15)
    font_normal = sp(13) if not is_android else sp(11)
    font_small = sp(11) if not is_android else sp(9)
    font_tiny = sp(9) if not is_android else sp(7)
    padding_main = dp(10) if is_android else dp(14)
    btn_height = dp(36) if is_android else dp(40)
    preview_size = dp(160) if is_android else dp(200)

    workshop_popup = Popup(
        title="", separator_height=0,
        size_hint=(0.96 if is_android else 0.80, 0.94 if is_android else 0.90),
        background_color=(0, 0, 0, 0), auto_dismiss=False
    )

    current_data = {
        'icon': None, 'name': '', 'attack': 0, 'defense': 0,
        'season': 'Нет', 'slot': 'Оружие'
    }

    artifact_images_path = r"files/pict/artifacts/custom"
    if os.path.exists(artifact_images_path):
        all_image_files = sorted([
            f for f in os.listdir(artifact_images_path)
            if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp'))
        ])
    else:
        all_image_files = []

    current_index = [0]
    current_filter = ['Оружие']

    def _get_filtered():
        pfx = _SLOT_PREFIXES.get(current_filter[0], '0')
        return [f for f in all_image_files if f.startswith(pfx)]

    def _bg(widget, color, radius=dp(10)):
        with widget.canvas.before:
            widget._bg_color = Color(*color)
            widget._bg_rect = RoundedRectangle(pos=widget.pos, size=widget.size, radius=[radius])
        widget.bind(
            pos=lambda w, v: setattr(w._bg_rect, 'pos', v),
            size=lambda w, v: setattr(w._bg_rect, 'size', v)
        )

    def _btn(text, color, font_sz=None, height=None):
        b = Button(
            text=text, size_hint_y=None, height=height or btn_height,
            background_color=(0, 0, 0, 0), background_normal='',
            font_size=font_sz or font_normal, color=(1, 1, 1, 1), bold=True
        )
        _bg(b, color, dp(10))
        return b

    def _lbl(text, font_sz=None, color=None, bold=False, halign='center', height=None, shint_y=None):
        l = Label(
            text=text, font_size=font_sz or font_normal,
            color=color or _CLR_TEXT, bold=bold, halign=halign, valign='middle',
            size_hint_y=shint_y, height=height or dp(24), markup=True
        )
        if shint_y is None:
            l.size_hint_y = None
        l.bind(size=lambda i, v: setattr(i, 'text_size', (i.width, None)))
        return l

    def _step(n):
        r = ''
        for i in range(1, 4):
            r += f'[color=e6bf3a][{i}][/color]  ' if i == n else f'[color=555555]{i}[/color]  '
        return r.strip()

    def switch_screen(fn):
        root = BoxLayout(orientation='vertical', padding=0, spacing=0)
        _bg(root, _CLR_BG, dp(12))
        fn(root)
        workshop_popup.content = root

    def gen_name(filename=None):
        pfx_map = {
            0: ["Секира", "Меч", "Клинок", "Винтовка", "Мушкет", "Арбалет", "Кинжал", "Скипетр", "Копье", "Посох", "Шпага"],
            1: ["Шлем", "Шляпа", "Корона", "Венец", "Диадема", "Каска", "Тиара", "Венок"],
            2: ["Сапоги", "Обувь", "Ботинки", "Поножи", "Сандалии", "Башмаки"],
            3: ["Броня", "Панцирь", "Кираса", "Доспех", "Мантия", "Кольчуга", "Латы", "Жилет", "Плащ"],
            4: ["Амулет", "Кольцо", "Серьга", "Браслет", "Талисман", "Медальон", "Подвеска", "Перстень"]
        }
        sfx = ["Силы", "Защиты", "Мудрости", "Света", "Тьмы", "Мощи", "Судьбы",
               "Смерти", "Дракона", "Феникса", "Бездны", "Рассвета", "Бури", "Огня",
               "Льда", "Ветра", "Теней", "Истины", "Хаоса", "Веры", "Заката"]
        at = 0
        if filename:
            try:
                cn = os.path.splitext(filename)[0].lower()
                if cn and cn[0].isdigit():
                    at = int(cn[0])
            except Exception:
                pass
        return f"{random.choice(pfx_map.get(at, pfx_map[0]))} {random.choice(sfx)}", at

    # ==================================================================
    #  ЭКРАН 1 — Выбор типа и иконки (стрелки)
    # ==================================================================
    def screen1(layout):
        # Шапка
        hdr = BoxLayout(orientation='vertical', size_hint_y=None, height=dp(50),
                        padding=[padding_main, dp(6), padding_main, 0])
        _bg(hdr, _CLR_BG_PANEL, dp(10))
        hdr.add_widget(_lbl(_step(1), font_sz=font_normal, height=dp(18)))
        hdr.add_widget(_lbl("Выберите тип и облик", font_sz=font_title, color=_CLR_GOLD, bold=True, height=dp(26)))
        layout.add_widget(hdr)

        # Фильтр по типу
        frow = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(34),
                         spacing=dp(3), padding=[dp(4), dp(2)])
        _filter_btns = []

        def _on_filter(sn, *_a):
            current_filter[0] = sn
            current_index[0] = 0
            for fb, fn in _filter_btns:
                active = fn == sn
                if hasattr(fb, '_bg_color'):
                    fb._bg_color.rgba = _CLR_GOLD_DIM if active else (0.15, 0.16, 0.22, 1)
                fb.color = (1, 1, 1, 1) if active else (0.6, 0.6, 0.65, 1)
            _update()

        for sn in _SLOT_LABELS:
            fb = Button(
                text=sn, size_hint_y=None, height=dp(30),
                background_color=(0, 0, 0, 0), background_normal='',
                font_size=font_small, bold=True,
                color=(1, 1, 1, 1) if sn == current_filter[0] else (0.6, 0.6, 0.65, 1)
            )
            _bg(fb, _CLR_GOLD_DIM if sn == current_filter[0] else (0.15, 0.16, 0.22, 1), dp(6))
            fb.bind(on_release=lambda inst, s=sn: _on_filter(s))
            frow.add_widget(fb)
            _filter_btns.append((fb, sn))
        layout.add_widget(frow)

        # Центральная панель: < [КАРТИНКА] >
        center = BoxLayout(orientation='horizontal', size_hint_y=1,
                           padding=[padding_main, dp(10)], spacing=dp(8))

        # Стрелка влево
        left_btn = _btn("<", _CLR_GOLD_DIM, font_sz=sp(24), height=dp(60))
        left_btn.size_hint = (None, None)
        left_btn.width = dp(50)
        left_btn.pos_hint = {'center_y': 0.5}

        # Стрелка вправо
        right_btn = _btn(">", _CLR_GOLD_DIM, font_sz=sp(24), height=dp(60))
        right_btn.size_hint = (None, None)
        right_btn.width = dp(50)
        right_btn.pos_hint = {'center_y': 0.5}

        # Панель с картинкой и инфо
        mid = BoxLayout(orientation='vertical', spacing=dp(6), padding=[dp(4), dp(4)])
        _bg(mid, _CLR_BG_CARD, dp(10))

        preview_img = Image(
            source="", size_hint=(1, 1),
            allow_stretch=True, keep_ratio=True
        )
        mid.add_widget(preview_img)

        name_lbl = _lbl("--", font_sz=font_title, color=_CLR_GOLD, bold=True, height=dp(26))
        mid.add_widget(name_lbl)

        info_row = BoxLayout(size_hint_y=None, height=dp(20), spacing=dp(10))
        type_lbl = _lbl("Тип: --", font_sz=font_small, color=_CLR_TEXT_DIM, halign='left', height=dp(20))
        counter_lbl = _lbl("", font_sz=font_small, color=_CLR_TEXT_DIM, halign='right', height=dp(20))
        info_row.add_widget(type_lbl)
        info_row.add_widget(counter_lbl)
        mid.add_widget(info_row)

        rename_btn = _btn("Новое имя", (0.20, 0.35, 0.55, 1), font_sz=font_small, height=dp(30))
        mid.add_widget(rename_btn)

        center.add_widget(left_btn)
        center.add_widget(mid)
        center.add_widget(right_btn)
        layout.add_widget(center)

        # Нижняя панель
        bot = BoxLayout(orientation='horizontal', size_hint_y=None,
                        height=btn_height + dp(8), spacing=dp(8),
                        padding=[padding_main, dp(4)])
        _bg(bot, _CLR_BG_PANEL, dp(10))
        close_btn = _btn("Закрыть", _CLR_RED)
        next_btn = _btn("Далее >>", (0.18, 0.52, 0.28, 1))
        bot.add_widget(close_btn)
        bot.add_widget(next_btn)
        layout.add_widget(bot)

        def _update():
            imgs = _get_filtered()
            idx = current_index[0]
            if not imgs:
                preview_img.source = ''
                name_lbl.text = '--'
                type_lbl.text = 'Тип: --'
                counter_lbl.text = '0 / 0'
                return
            if idx >= len(imgs):
                idx = 0
                current_index[0] = 0
            fn = imgs[idx]
            preview_img.source = os.path.join(artifact_images_path, fn)
            current_data['icon'] = fn
            nm, dt = gen_name(fn)
            current_data['name'] = nm
            name_lbl.text = nm
            if dt in _SLOT_MAP:
                current_data['slot'] = _SLOT_MAP[dt]
                type_lbl.text = f"Тип: {_SLOT_MAP[dt]}"
            counter_lbl.text = f"{idx + 1} / {len(imgs)}"

        def _prev(*_):
            imgs = _get_filtered()
            if imgs:
                current_index[0] = (current_index[0] - 1) % len(imgs)
                _update()

        def _next_img(*_):
            imgs = _get_filtered()
            if imgs:
                current_index[0] = (current_index[0] + 1) % len(imgs)
                _update()

        def _rename(*_):
            if current_data['icon']:
                nm, _ = gen_name(current_data['icon'])
                current_data['name'] = nm
                name_lbl.text = nm

        def _next_screen(*_):
            if not current_data['icon']:
                show_message("Ошибка", "Выберите иконку артефакта")
                return
            switch_screen(screen2)

        left_btn.bind(on_press=_prev)
        right_btn.bind(on_press=_next_img)
        rename_btn.bind(on_release=_rename)
        close_btn.bind(on_release=lambda x: workshop_popup.dismiss())
        next_btn.bind(on_release=_next_screen)

        _update()

    # ==================================================================
    #  ЭКРАН 2 — Характеристики
    # ==================================================================
    def screen2(layout):
        _fn = getattr(faction, 'faction', '')
        _MAX = 12_000_000 if _fn == 'Элины' else 9_900_000
        _max_stats = _MAX - 50_000
        _budget = min(faction.money, _max_stats)
        tokens = _budget / 3200.0

        def calc_tokens(a, d):
            return a / 1.5 + d, a / 1.5, d

        hdr = BoxLayout(orientation='vertical', size_hint_y=None, height=dp(48),
                        padding=[padding_main, dp(4), padding_main, 0])
        _bg(hdr, _CLR_BG_PANEL, dp(10))
        hdr.add_widget(_lbl(_step(2), font_sz=font_normal, height=dp(16)))
        hdr.add_widget(_lbl("Характеристики", font_sz=font_title, color=_CLR_GOLD, bold=True, height=dp(26)))
        layout.add_widget(hdr)

        # Мини-превью
        mp = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(54),
                       padding=[padding_main, dp(4)], spacing=dp(8))
        _bg(mp, _CLR_BG_CARD, dp(8))
        _ip = os.path.join(artifact_images_path, current_data['icon']) if current_data['icon'] else ''
        mp.add_widget(Image(source=_ip, size_hint=(None, None), size=(dp(44), dp(44)),
                            pos_hint={'center_y': 0.5}, allow_stretch=True, keep_ratio=True))
        mi = BoxLayout(orientation='vertical', spacing=dp(1))
        mi.add_widget(_lbl(current_data['name'], font_sz=font_normal, color=_CLR_GOLD, bold=True, halign='left', height=dp(20)))
        mi.add_widget(_lbl(f"Слот: {current_data['slot']}", font_sz=font_small, color=_CLR_TEXT_DIM, halign='left', height=dp(16)))
        mi.add_widget(_lbl(f"Бюджет: {format_number(int(_budget))}", font_sz=font_small, color=_CLR_BLUE, halign='left', height=dp(16)))
        mp.add_widget(mi)
        layout.add_widget(mp)

        # Атака
        ar = BoxLayout(orientation='vertical', spacing=dp(1), size_hint_y=None, height=dp(64),
                       padding=[padding_main, dp(3)])
        _bg(ar, _CLR_BG_CARD, dp(8))
        ah = BoxLayout(size_hint_y=None, height=dp(20))
        atk_val = _lbl("АТК: 0", font_sz=font_small, color=_CLR_RED, bold=True, halign='left', height=dp(20))
        atk_cost = _lbl("0 крон", font_sz=font_tiny, color=_CLR_TEXT_DIM, halign='right', height=dp(20))
        ah.add_widget(atk_val)
        ah.add_widget(atk_cost)
        ar.add_widget(ah)
        _ma = max(min(int(tokens * 1.5), int(_max_stats / 2400)), 100)
        atk_sl = Slider(min=0, max=_ma, value=current_data.get('attack', 0), step=1,
                        size_hint_y=None, height=dp(36),
                        cursor_size=(dp(26), dp(26)) if is_android else (dp(22), dp(22)))
        ar.add_widget(atk_sl)
        layout.add_widget(ar)

        # Защита
        dr = BoxLayout(orientation='vertical', spacing=dp(1), size_hint_y=None, height=dp(64),
                       padding=[padding_main, dp(3)])
        _bg(dr, _CLR_BG_CARD, dp(8))
        dh = BoxLayout(size_hint_y=None, height=dp(20))
        def_val = _lbl("ЗАЩ: 0", font_sz=font_small, color=_CLR_BLUE, bold=True, halign='left', height=dp(20))
        def_cost = _lbl("0 крон", font_sz=font_tiny, color=_CLR_TEXT_DIM, halign='right', height=dp(20))
        dh.add_widget(def_val)
        dh.add_widget(def_cost)
        dr.add_widget(dh)
        _md = max(int(tokens), 100)
        def_sl = Slider(min=0, max=_md, value=current_data.get('defense', 0), step=1,
                        size_hint_y=None, height=dp(36),
                        cursor_size=(dp(26), dp(26)) if is_android else (dp(22), dp(22)))
        dr.add_widget(def_sl)
        layout.add_widget(dr)

        # Сезон
        sp_row = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(34),
                           padding=[padding_main, dp(2)], spacing=dp(4))
        _bg(sp_row, _CLR_BG_CARD, dp(8))
        seasons = [
            'Нет', 'Весна', 'Лето', 'Осень', 'Зима',
            'Весна, Лето', 'Весна, Осень', 'Весна, Зима',
            'Лето, Осень', 'Лето, Зима', 'Осень, Зима',
            'Весна, Лето, Осень', 'Весна, Лето, Зима',
            'Весна, Осень, Зима', 'Лето, Осень, Зима', 'Все'
        ]
        si = [seasons.index(current_data['season']) if current_data['season'] in seasons else 0]
        stl = _lbl("Сезон:", font_sz=font_small, color=_CLR_PURPLE_LIGHT, bold=True, halign='left', height=dp(28))
        stl.size_hint_x = 0.18
        sp_row.add_widget(stl)
        pb = _btn("<", (0.25, 0.20, 0.40, 1), font_sz=font_small, height=dp(28))
        pb.size_hint_x = 0.10
        sp_row.add_widget(pb)
        sl = _lbl(current_data['season'], font_sz=font_small, color=_CLR_TEXT, height=dp(28))
        sl.size_hint_x = 0.44
        sp_row.add_widget(sl)
        nb = _btn(">", (0.25, 0.20, 0.40, 1), font_sz=font_small, height=dp(28))
        nb.size_hint_x = 0.10
        sp_row.add_widget(nb)
        disc_lbl = _lbl("", font_sz=font_tiny, color=_CLR_GREEN, bold=True, height=dp(28))
        disc_lbl.size_hint_x = 0.18
        sp_row.add_widget(disc_lbl)
        layout.add_widget(sp_row)

        def _upd_disc():
            s = seasons[si[0]]
            if s in ('Нет', 'Все'):
                disc_lbl.text = ""
            else:
                cnt = len([x.strip() for x in s.split(',')])
                d = {1: 75, 2: 50, 3: 25}.get(cnt, 0)
                disc_lbl.text = f"-{d}%" if d else ""

        pb.bind(on_release=lambda *_: (si.__setitem__(0, (si[0] - 1) % len(seasons)),
                                        setattr(sl, 'text', seasons[si[0]]), _upd_disc(), _upd_vals()))
        nb.bind(on_release=lambda *_: (si.__setitem__(0, (si[0] + 1) % len(seasons)),
                                        setattr(sl, 'text', seasons[si[0]]), _upd_disc(), _upd_vals()))

        # Стоимость
        tp = BoxLayout(orientation='vertical', size_hint_y=None, height=dp(44),
                       padding=[padding_main, dp(2)])
        _bg(tp, (0.06, 0.08, 0.14, 1), dp(8))
        total_lbl = _lbl("Стоимость: 0 крон", font_sz=font_normal, color=_CLR_TEXT, bold=True, height=dp(20))
        budget_lbl = _lbl("", font_sz=font_tiny, color=_CLR_GREEN, height=dp(18))
        tp.add_widget(total_lbl)
        tp.add_widget(budget_lbl)
        layout.add_widget(tp)

        layout.add_widget(BoxLayout(size_hint_y=1))

        bot = BoxLayout(orientation='horizontal', size_hint_y=None,
                        height=btn_height + dp(8), spacing=dp(8),
                        padding=[padding_main, dp(4)])
        _bg(bot, _CLR_BG_PANEL, dp(10))
        back_btn = _btn("<< Назад", _CLR_GOLD_DIM)
        next_btn = _btn("Далее >>", (0.18, 0.52, 0.28, 1))
        bot.add_widget(back_btn)
        bot.add_widget(next_btn)
        layout.add_widget(bot)

        def _calc_cost(av, dv, sn):
            base = abs(av) * 2400 + abs(dv) * 3200
            if sn not in ('Нет', 'Все'):
                cnt = len([x.strip() for x in sn.split(',')])
                d = {1: 0.75, 2: 0.50, 3: 0.25}.get(cnt, 0)
                base = base * (1 - d)
            return base

        def _upd_vals(*_):
            av = int(atk_sl.value)
            dv = int(def_sl.value)
            atk_val.text = f"АТК: {av}"
            def_val.text = f"ЗАЩ: {dv}"
            atk_cost.text = f"{format_number(av * 2400)} крон"
            def_cost.text = f"{format_number(dv * 3200)} крон"
            sn = seasons[si[0]]
            tc = _calc_cost(av, dv, sn)
            total_lbl.text = f"Стоимость: {format_number(int(tc))} крон"
            tu, _, _ = calc_tokens(av, dv)
            if tu > tokens:
                budget_lbl.color = _CLR_RED
                budget_lbl.text = f"ПРЕВЫШЕН БЮДЖЕТ! {tu:.0f} / {tokens:.0f}"
                next_btn.disabled = True
                if hasattr(next_btn, '_bg_color'):
                    next_btn._bg_color.rgba = (0.3, 0.3, 0.3, 1)
            else:
                budget_lbl.color = _CLR_GREEN
                budget_lbl.text = f"Жетонов: {tokens - tu:.0f} / {tokens:.0f}"
                next_btn.disabled = False
                if hasattr(next_btn, '_bg_color'):
                    next_btn._bg_color.rgba = (0.18, 0.52, 0.28, 1)
            current_data['attack'] = av
            current_data['defense'] = dv

        atk_sl.bind(value=_upd_vals)
        def_sl.bind(value=_upd_vals)
        _upd_vals()
        _upd_disc()

        back_btn.bind(on_release=lambda *_: (
            current_data.update({'attack': int(atk_sl.value), 'defense': int(def_sl.value), 'season': seasons[si[0]]}),
            switch_screen(screen1)
        ))

        def _next(*_):
            av, dv = int(atk_sl.value), int(def_sl.value)
            tu, _, _ = calc_tokens(av, dv)
            if tu > tokens:
                show_message("Бюджет", "Недостаточно жетонов!")
                return
            current_data.update({'attack': av, 'defense': dv, 'season': seasons[si[0]]})
            switch_screen(screen3)
        next_btn.bind(on_release=_next)

    # ==================================================================
    #  ЭКРАН 3 — Итог
    # ==================================================================
    def screen3(layout):
        hdr = BoxLayout(orientation='vertical', size_hint_y=None, height=dp(48),
                        padding=[padding_main, dp(4), padding_main, 0])
        _bg(hdr, _CLR_BG_PANEL, dp(10))
        hdr.add_widget(_lbl(_step(3), font_sz=font_normal, height=dp(16)))
        hdr.add_widget(_lbl("Чертёж артефакта", font_sz=font_title, color=_CLR_GOLD, bold=True, height=dp(26)))
        layout.add_widget(hdr)

        card = BoxLayout(orientation='vertical', size_hint_y=None,
                         height=preview_size + dp(100), padding=[padding_main, dp(6)], spacing=dp(4))
        _bg(card, _CLR_BG_CARD, dp(12))
        ir = BoxLayout(size_hint_y=None, height=preview_size)
        ir.add_widget(BoxLayout())
        _ip = os.path.join(artifact_images_path, current_data['icon']) if current_data['icon'] else ''
        ir.add_widget(Image(source=_ip, size_hint=(None, None),
                            size=(preview_size - dp(12), preview_size - dp(12)),
                            pos_hint={'center_y': 0.5}, allow_stretch=True, keep_ratio=True))
        ir.add_widget(BoxLayout())
        card.add_widget(ir)
        card.add_widget(_lbl(current_data['name'], font_sz=font_title, color=_CLR_GOLD, bold=True, height=dp(24)))

        av, dv = current_data['attack'], current_data['defense']
        card.add_widget(_lbl(f"АТК: [b]{av}[/b]     ЗАЩ: [b]{dv}[/b]", font_sz=font_normal, color=_CLR_TEXT, height=dp(20)))

        sn = current_data['season']
        sc = _CLR_PURPLE_LIGHT if sn != 'Нет' else _CLR_TEXT_DIM
        card.add_widget(_lbl(f"Сезон: {sn}    Слот: {current_data['slot']}", font_sz=font_small, color=sc, height=dp(18)))

        # Стоимость
        attack_bonus, defense_bonus = av, dv
        base = abs(av) * 2400 + abs(dv) * 3200
        if sn == 'Нет':
            seasons_bonus = []
        elif sn == 'Все':
            seasons_bonus = ['Весна', 'Лето', 'Осень', 'Зима']
        else:
            seasons_bonus = [s.strip() for s in sn.split(',')]
            cnt = len(seasons_bonus)
            d = {1: 0.75, 2: 0.50, 3: 0.25}.get(cnt, 0)
            base = base * (1 - d)

        total_cost = max(20000, base)
        _fn3 = getattr(faction, 'faction', '')
        total_cost = min(total_cost, 11_950_000 if _fn3 == 'Элины' else 9_850_000)

        disc_text = ""
        if seasons_bonus and sn not in ('Нет', 'Все'):
            dp_ = {1: 75, 2: 50, 3: 25}.get(len(seasons_bonus), 0)
            if dp_:
                disc_text = f"  [color=55cc66](скидка {dp_}%)[/color]"

        card.add_widget(_lbl(
            f"Стоимость: [b]{format_number(int(total_cost))}[/b] + 50K{disc_text}",
            font_sz=font_small, color=_CLR_TEXT, height=dp(20)
        ))
        layout.add_widget(card)
        layout.add_widget(BoxLayout(size_hint_y=1))

        create_btn = _btn("Создать чертёж", _CLR_PURPLE, font_sz=font_title, height=dp(42))
        layout.add_widget(create_btn)

        bot = BoxLayout(orientation='horizontal', size_hint_y=None,
                        height=btn_height + dp(8), spacing=dp(8),
                        padding=[padding_main, dp(4)])
        _bg(bot, _CLR_BG_PANEL, dp(10))
        back_btn = _btn("<< Назад", _CLR_GOLD_DIM)
        close_btn = _btn("Закрыть", _CLR_RED)
        bot.add_widget(back_btn)
        bot.add_widget(close_btn)
        layout.add_widget(bot)

        back_btn.bind(on_release=lambda *_: switch_screen(screen2))
        close_btn.bind(on_release=lambda x: workshop_popup.dismiss())

        def _create(*_):
            if av == 0 and dv == 0:
                show_message("Ошибка", "Установите АТК или ЗАЩ больше 0.")
                return
            _fn = getattr(faction, 'faction', '')
            _mc = 12_000_000 if _fn == 'Элины' else 9_900_000
            if total_cost + 50_000 > _mc:
                show_message("Ошибка", f"Стоимость превышает лимит {format_number(_mc)}")
                return
            if faction.money < 50000:
                show_message("Ошибка", "Недостаточно средств (50 000 крон)")
                return
            faction.money -= 50000
            aname = current_data['name'] or gen_name()[0]
            apath = os.path.join(artifact_images_path, current_data['icon'])
            tmap = {'Оружие': 0, 'Голова': 1, 'Ноги': 2, 'Туловище': 3, 'Аксессуар': 4}
            try:
                cur = db_conn.cursor()
                cur.execute("SELECT MAX(id) FROM artifacts")
                nid = (cur.fetchone()[0] or 0) + 1
                cur.execute('''INSERT INTO artifacts (id, attack, defense, season_name, image_url, name, cost, artifact_type, is_created)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    (nid, attack_bonus, defense_bonus, ', '.join(seasons_bonus),
                     apath, aname, int(total_cost), tmap[current_data['slot']], 1))
                db_conn.commit()
                show_message("Успех", f'Артефакт "{aname}" создан!')
                workshop_popup.dismiss()
            except Exception as e:
                show_message("Ошибка", f"Не удалось создать: {e}")
        create_btn.bind(on_release=_create)

    switch_screen(screen1)
    workshop_popup.open()
