"""Resume an existing expedition from a compact, responsive main-map control."""
import sqlite3
from kivy.clock import Clock
from kivy.core.text import Label as CoreLabel
from kivy.metrics import dp,sp
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.image import Image
from kivy.uix.label import Label
from otherworld_themes import theme
from strategy_ui import surface,INK,TEXT


class PortalShortcutButton(ButtonBehavior,BoxLayout):
    def __init__(self,faction,**kwargs):
        super().__init__(spacing=dp(4),padding=dp(4),**kwargs)
        self._strategy_fixed_layout=True
        surface(self,INK,theme(faction)['accent'])
        self.icon=Image(source='files/portals/portal_'+theme(faction)['key']+'.png',mipmap=True,fit_mode='contain')
        self.caption=Label(text='Зазеркалье',font_size=sp(13),bold=True,color=TEXT,halign='center',valign='middle')
        self.caption.bind(size=lambda label,_:setattr(label,'text_size',label.size))
        self.add_widget(self.icon);self.add_widget(self.caption)

    def inline(self,compact):
        self.caption.size_hint_x=None if compact else 1
        self.caption.width=0 if compact else self.caption.width
        self.caption.opacity=0 if compact else 1
        self.icon.size_hint_x=1 if compact else .45


class PortalShortcut:
    def __init__(self,screen):
        self.screen=screen
        self.button=PortalShortcutButton(screen.selected_faction,size_hint=(None,None))
        self.button.bind(on_release=self.open)
        self.visible=False;self.popup=None;self._poll=None;self._closed=False
        self._layout=Clock.create_trigger(self.fit,-1)
        screen.root_overlay.bind(size=self._layout,pos=self._layout)
        for name in ('resources','end_turn'):
            screen._hud_panels[name].bind(size=self._layout,pos=self._layout)
        screen.bind(parent=self._parent_changed)
        self._parent_changed()

    def _parent_changed(self,*_):
        if self._closed:return
        if self.screen.parent is None:
            if self._poll:self._poll.cancel();self._poll=None
            if self.popup:self.popup.dismiss()
        elif self._poll is None:
            self.refresh()
            self._poll=Clock.schedule_interval(self.refresh,.5)

    def refresh(self,*_):
        conn=getattr(self.screen,'conn',None)
        try:
            present=bool(conn and conn.execute('SELECT 1 FROM portal_parties WHERE faction=?',
                                              (self.screen.selected_faction,)).fetchone())
        except sqlite3.Error:present=False
        from morgana_covenant import state
        row=state(conn,self.screen.selected_faction) if conn else None
        self._morgana_only=not present and bool(row and row['status'] in ('offered','deferred'))
        present=present or self._morgana_only
        self.button.caption.text='Моргана' if self._morgana_only else 'Зазеркалье'
        self.button.icon.source='files/army/death/morgana.png' if self._morgana_only else 'files/portals/portal_'+theme(self.screen.selected_faction)['key']+'.png'
        self.visible=present
        if present:
            from otherworld_ui import _busy
            self.button.disabled=_busy(conn)
            self.button.opacity=.55 if self.button.disabled else 1
        self._layout()

    def fit(self,*_):
        if self._closed:return
        host=self.screen.root_overlay
        end=self.screen._hud_panels['end_turn']
        end_button=self.screen.end_turn_button
        if not self.visible:
            if self.button.parent:self.button.parent.remove_widget(self.button)
            end.orientation='vertical'
            end_button.text='Завершить ход'
            end_button.text_size=(None,None)
            end_button.font_size=sp(15 if host.width<dp(800) else 17)
            return
        side=dp(48)
        below=end.y-dp(6)-side
        inline=below<host.y+dp(64)
        destination=end if inline else host
        if self.button.parent is not destination:
            if self.button.parent:self.button.parent.remove_widget(self.button)
            destination.add_widget(self.button)
        end.orientation='horizontal' if inline else 'vertical'
        self.button.inline(inline)
        if inline:
            self.button.size_hint=(None,1)
            self.button.width=side
            end.spacing=dp(4)
            available=max(1,end.width-end.padding[0]-end.padding[2]-end.spacing-side-dp(8))
            measure=CoreLabel(text='Завершить',font_name=end_button.font_name,font_size=sp(14),bold=True)
            measure.refresh()
            end_button.text='Завершить\nход'
            end_button.font_size=sp(14)*min(1,available/max(1,measure.texture.width))
            end_button.text_size=(available,max(1,end.height-end.padding[1]-end.padding[3]-dp(8)))
            end_button.halign=end_button.valign='center'
        else:
            self.button.size_hint=(None,None)
            self.button.size=(end.width,side)
            self.button.pos=(end.x,below)
            end_button.text='Завершить ход'
            end_button.text_size=(None,None)
            end_button.font_size=sp(15 if host.width<dp(800) else 17)

    def open(self,*_):
        self.refresh()
        if not self.visible or self.button.disabled:return
        if self.popup and self.popup.parent:return
        if getattr(self,'_morgana_only',False):
            from morgana_covenant_ui import show_offer
            self.popup=show_offer(self.screen.conn,self.screen.selected_faction,force=True)
            if self.popup:self.popup.bind(on_dismiss=self._dismissed)
            return
        from otherworld_ui import OtherworldMap
        self.popup=OtherworldMap(self.screen.conn,self.screen.selected_faction)
        self.popup.bind(on_dismiss=self._dismissed)
        self.popup.open()

    def _dismissed(self,*_):
        self.popup=None
        if not self._closed:self.refresh()

    def close(self):
        self._closed=True
        if self._poll:self._poll.cancel();self._poll=None
        self._layout.cancel()
        self.screen.unbind(parent=self._parent_changed)
        self.screen.root_overlay.unbind(size=self._layout,pos=self._layout)
        for name in ('resources','end_turn'):
            self.screen._hud_panels[name].unbind(size=self._layout,pos=self._layout)
        if self.popup:self.popup.dismiss()
        if self.button.parent:self.button.parent.remove_widget(self.button)
