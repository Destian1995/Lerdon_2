"""Audio controls shared by the main menu and tactical battle."""
def show_audio_settings(*args, manager=None, on_close=None):
    from kivy.metrics import dp
    from kivy.uix.boxlayout import BoxLayout
    from kivy.uix.popup import Popup
    from kivy.uix.scrollview import ScrollView
    from kivy.uix.slider import Slider
    from game_audio import get_audio
    from strategy_ui import StrategyButton, text_label, GOLD
    from window_theme import prepare_custom_popup
    audio = manager or get_audio()
    root = BoxLayout(orientation='vertical', padding=dp(8), spacing=dp(6))
    root._strategy_fixed_layout = True
    scroll = ScrollView(do_scroll_x=False)
    rows = BoxLayout(orientation='vertical', size_hint_y=None, spacing=dp(8))
    rows.bind(minimum_height=rows.setter('height'))
    scroll.add_widget(rows)
    root.add_widget(scroll)
    toggle = StrategyButton(size_hint_y=None, height=dp(48))
    def caption():
        toggle.text = 'Звук: включён' if audio.settings['enabled'] else 'Звук: выключен'
    def switch(*_):
        audio.set('enabled', not audio.settings['enabled']); caption()
    caption(); toggle.bind(on_release=switch); rows.add_widget(toggle)
    for key, title in (('effects', 'Эффекты'), ('music', 'Музыка боя')):
        label = text_label('', 14, GOLD, size_hint_y=None, height=dp(28))
        slider = Slider(min=0, max=100, value=audio.settings[key]*100, step=1,
                        size_hint_y=None, height=dp(48))
        def change(widget, value, key=key, label=label, title=title):
            label.text = f'{title}: {value:.0f}%'
            audio.set(key, value/100)
        change(slider, slider.value)
        slider.bind(value=change)
        rows.add_widget(label); rows.add_widget(slider)
    preview = StrategyButton(text='Проверить звук · выстрел', size_hint_y=None, height=dp(48))
    preview.bind(on_release=lambda *_: audio.play('rifle', owner=preview))
    rows.add_widget(preview)
    close = StrategyButton(text='Готово', size_hint_y=None, height=dp(48))
    root.add_widget(close)
    popup = Popup(title='Звук', content=root, size_hint=(.92,.92))
    prepare_custom_popup(popup)
    def finish(*_):
        audio.stop_owner(preview)
        if not audio.save():
            # Changes still apply for this session; no gameplay failure.
            from kivy.logger import Logger
            Logger.warning('Audio: settings remain active for this session only')
        if on_close: on_close()
    popup.bind(on_dismiss=finish)
    close.bind(on_release=popup.dismiss)
    popup.open()
    return popup
