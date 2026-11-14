"""Full-access price selection. Store callbacks are supplied by the billing adapter."""
from kivy.metrics import dp,sp
from kivy.uix.label import Label
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from strategy_ui import StrategyButton,surface,GOLD,MUTED
from mirror_readable_ui import ReadableText
from premium_plans import MONTHLY,PERMANENT,BENEFITS
from window_theme import prepare_custom_popup


class FullVersionNotice(BoxLayout):
    """An inline content lock that leaves the surrounding preview visible."""
    def __init__(self,on_change=None,compact=False,**kwargs):
        super().__init__(orientation='horizontal' if compact else 'vertical',
                         size_hint_y=None,height=dp(52 if compact else 88),
                         padding=dp(6),spacing=dp(4),**kwargs)
        self._strategy_fixed_layout=True
        surface(self,(.08,.10,.13,1),GOLD)
        self.message=Label(text='Доступно в полной версии',color=GOLD,
                           font_size=sp(13 if compact else 15),halign='center',valign='middle')
        self.message.bind(size=lambda label,_:setattr(label,'text_size',label.size))
        self.add_widget(self.message)
        self.buy=StrategyButton(text='Получить полную версию',primary=True,font_size=sp(13),
                               size_hint_y=1 if compact else None,height=dp(48))
        self.buy.bind(on_release=self.open_options)
        self.add_widget(self.buy)
        self.on_change=on_change

    def open_options(self,*_):
        popup=show_full_access()
        if self.on_change:popup.bind(on_dismiss=lambda *_:self.on_change())


class LockedContentPopup(Popup):
    def __init__(self,on_change=None,**kwargs):
        self.on_change=on_change
        root=BoxLayout(orientation='vertical',padding=dp(14),spacing=dp(10))
        root._strategy_fixed_layout=True
        super().__init__(title='',content=root,size_hint=(.92,.92),
                         size_hint_max=(dp(440),dp(260)),auto_dismiss=False,**kwargs)
        prepare_custom_popup(self)
        self.message=Label(text='Доступно в полной версии',font_size=sp(20),bold=True,
                           color=GOLD,halign='center',valign='middle')
        self.message.bind(size=lambda label,_:setattr(label,'text_size',label.size))
        root.add_widget(self.message)
        self.get_full=StrategyButton(text='Получить полную версию',primary=True,
                                    size_hint_y=None,height=dp(48))
        self.close_button=StrategyButton(text='Закрыть',size_hint_y=None,height=dp(48))
        self.get_full.bind(on_release=self.purchase_options)
        self.close_button.bind(on_release=self.dismiss)
        root.add_widget(self.get_full);root.add_widget(self.close_button)

    def purchase_options(self,*_):
        self.dismiss()
        popup=show_full_access()
        if self.on_change:popup.bind(on_dismiss=lambda *_:self.on_change())


def show_locked_content(on_change=None):
    popup=LockedContentPopup(on_change=on_change)
    popup.open()
    return popup


class FullAccessPopup(Popup):
    def __init__(self,on_purchase=None,on_restore=None,**kwargs):
        self.purchase_callback=on_purchase;self.restore_callback=on_restore
        root=BoxLayout(orientation='vertical',padding=dp(10),spacing=dp(8))
        root._strategy_fixed_layout=True
        super().__init__(title='Полная версия',content=root,size_hint=(.94,.94),auto_dismiss=False,**kwargs)
        self.status=ReadableText('Покупки пока недоступны.' if on_purchase is None else '',size=14,color=GOLD)
        root.add_widget(self.status)
        scroll=ScrollView(do_scroll_x=False,bar_width=dp(4))
        body=BoxLayout(orientation='vertical',size_hint_y=None,spacing=dp(8))
        body.bind(minimum_height=body.setter('height'));scroll.add_widget(body);root.add_widget(scroll)
        body.add_widget(ReadableText('Одинаковый полный доступ. Выберите удобный срок.',size=17,bold=True,color=GOLD))
        body.add_widget(ReadableText('Почта для чека и связи по покупке',size=13,color=MUTED))
        self.email=TextInput(multiline=False,size_hint_y=None,height=dp(46),hint_text='name@example.ru',
            background_color=(.08,.10,.15,1),foreground_color=(.94,.94,.94,1),
            disabled_foreground_color=(.82,.85,.90,1),padding=(dp(10),dp(10)))
        body.add_widget(self.email)
        self.cards=GridLayout(cols=1,size_hint_y=None,spacing=dp(8))
        self.cards.bind(minimum_height=self.cards.setter('height'),width=self.fit_cards)
        self.buy_buttons={}
        for plan in (MONTHLY,PERMANENT):
            card=surface(BoxLayout(orientation='vertical',padding=dp(10),spacing=dp(8),
                size_hint_y=None),(.075,.095,.12,1),GOLD)
            card.bind(minimum_height=card.setter('height'))
            card.add_widget(ReadableText(plan.title,size=18,bold=True,color=GOLD))
            card.add_widget(ReadableText(plan.price_text,size=25,bold=True))
            terms=('Доступ на оплаченный месяц. Условия продления и отмены будут показаны перед оплатой.'
                   if plan is MONTHLY else 'Один платёж. Бессрочный доступ ко всему перечисленному контенту.')
            card.add_widget(ReadableText(terms,size=13,color=MUTED))
            button=StrategyButton(text='Подключить подписку' if plan is MONTHLY else 'Купить навсегда',
                                  size_hint_y=None,height=dp(48),primary=plan is PERMANENT)
            button.disabled=on_purchase is None
            button.bind(on_release=lambda *_,key=plan.key:self.purchase(key))
            card.add_widget(button);self.cards.add_widget(card);self.buy_buttons[plan.key]=button
        body.add_widget(self.cards)
        self.gift_button=StrategyButton(text='Активировать подарочный ключ',size_hint_y=None,height=dp(48),disabled=True)
        self.gift_button.bind(on_release=self.open_gift)
        body.add_widget(self.gift_button)
        body.add_widget(ReadableText('Полный доступ включает:',size=16,bold=True,color=GOLD))
        for text in BENEFITS:body.add_widget(ReadableText('• '+text,size=14))
        months=PERMANENT.price_kopecks//MONTHLY.price_kopecks+1
        body.add_widget(ReadableText(f'{months} месяцев подписки — {months*MONTHLY.price_kopecks//100} ₽. Покупка навсегда — {PERMANENT.price_kopecks//100} ₽. Подписка не является рассрочкой покупки.',size=13,color=MUTED))
        self.code_label=ReadableText('',size=13,color=MUTED);body.add_widget(self.code_label)
        self.copy_code=StrategyButton(text='Скопировать личный код',size_hint_y=None,height=dp(46),disabled=True)
        self.copy_code.bind(on_release=self.copy_recovery);body.add_widget(self.copy_code)
        self.check_button=StrategyButton(text='Проверить покупку',size_hint_y=None,height=dp(46),disabled=True)
        self.check_button.bind(on_release=self.check_purchase)
        # Recovery from an unfinished SDK form must remain visible on phones.
        root.add_widget(self.check_button)
        self.cancel_renewal=StrategyButton(text='Отключить автопродление',size_hint_y=None,height=dp(46),disabled=True)
        self.cancel_renewal.bind(on_release=lambda *_:self.controller.cancel_subscription() if getattr(self,'controller',None) else None)
        body.add_widget(self.cancel_renewal)
        footer=BoxLayout(size_hint_y=None,height=dp(48),spacing=dp(8))
        self.restore_button=StrategyButton(text='Восстановить покупку',disabled=on_restore is None)
        self.restore_button.bind(on_release=self.restore)
        close=StrategyButton(text='Закрыть');close.bind(on_release=self.dismiss)
        footer.add_widget(self.restore_button);footer.add_widget(close);root.add_widget(footer)
        self.scroll=scroll;self.footer=footer
        prepare_custom_popup(self)

    def fit_cards(self,*_):self.cards.cols=2 if self.cards.width>=dp(560) else 1

    def purchase(self,key):
        if self.purchase_callback is not None:self.purchase_callback(key)

    def attach_billing(self,controller):
        self.controller=controller
        self.purchase_callback=self.start_purchase
        self.restore_callback=self.open_restore
        self.email.text=controller.client.state.get('email','')
        self.bind(on_dismiss=lambda *_:controller.views.discard(self))
        controller.open(self)

    def sync_billing(self,controller):
        client=controller.client;busy=controller.busy
        catalog=client.catalog or {}
        ready=bool(catalog and controller.native and client.config.get('sdk_key') and client.config.get('public_key'))
        access=client.access()
        for key,button in self.buy_buttons.items():
            button.disabled=bool(busy or not ready or client.pending or (access and access['permanent']) or
                (key==MONTHLY.key and (not catalog.get('subscriptions_available') or access)))
        self.restore_button.disabled=busy
        self.gift_button.disabled=bool(busy or client.pending or (access and access['permanent']))
        self.email.disabled=busy or bool(client.code)
        self.status.text=controller.message or ('Подключение к магазину…' if busy else controller.access_caption())
        self.status.color=(.43,.88,.60,1) if access else GOLD
        self.buy_buttons[PERMANENT.key].text=('Полная версия открыта' if access and access['permanent'] else 'Купить навсегда')
        if catalog and not catalog.get('subscriptions_available'):
            self.buy_buttons[MONTHLY.key].text='Подписка пока недоступна'
        self.copy_code.disabled=not bool(client.code)
        self.code_label.text='Сохраните личный код: он нужен для восстановления покупки после переустановки или на другом устройстве.' if client.code else ''
        preparing=bool(client.pending and client.pending['stage']=='tokenizing')
        self.check_button.text='Отменить подготовку оплаты' if preparing else 'Проверить покупку'
        self.check_button.disabled=busy or not bool(client.code)
        self.check_button.height=dp(46) if client.code else 0
        self.check_button.opacity=1 if client.code else 0
        self.cancel_renewal.disabled=busy or not bool(client.code)

    def start_purchase(self,key):
        if key!=MONTHLY.key:return self.controller.purchase(key,self.email.text)
        box=BoxLayout(orientation='vertical',padding=dp(12),spacing=dp(10))
        box.add_widget(ReadableText(f'{MONTHLY.price_kopecks//100} ₽ каждый месяц с автоматическим продлением. Продление можно отключить в этом окне или на странице управления подпиской. Оплаченный срок сохраняется. Покупка навсегда за {PERMANENT.price_kopecks//100} ₽ оформляется отдельно.',size=16))
        accept=StrategyButton(text=f'Согласен · {MONTHLY.price_kopecks//100} ₽ в месяц',size_hint_y=None,height=dp(48))
        cancel=StrategyButton(text='Отмена',size_hint_y=None,height=dp(48))
        box.add_widget(accept);box.add_widget(cancel)
        popup=Popup(title='Условия подписки',content=box,size_hint=(.94,.85),auto_dismiss=False)
        cancel.bind(on_release=popup.dismiss)
        accept.bind(on_release=lambda *_:(popup.dismiss(),self.controller.purchase(key,self.email.text,True)))
        popup.open()

    def check_purchase(self,*_):
        if not getattr(self,'controller',None):return
        pending=self.controller.client.pending
        if pending and pending['stage']=='tokenizing':self.controller.cancel_preparation()
        else:self.controller.poll_count=0;self.controller.check()

    def copy_recovery(self,*_):
        if not getattr(self,'controller',None):return
        from kivy.core.clipboard import Clipboard
        Clipboard.copy(self.controller.client.code)
        self.controller.notify('Личный код скопирован. Сохраните его в безопасном месте.')

    def open_restore(self):
        box=BoxLayout(orientation='vertical',padding=dp(10),spacing=dp(10))
        box.add_widget(ReadableText('Вставьте сохранённый личный код из 64 символов. Для восстановления нужен интернет.',size=15))
        code=TextInput(multiline=False,password=True,size_hint_y=None,height=dp(48))
        box.add_widget(code)
        restore=StrategyButton(text='Восстановить доступ',size_hint_y=None,height=dp(48))
        close=StrategyButton(text='Отмена',size_hint_y=None,height=dp(48))
        box.add_widget(restore);box.add_widget(close)
        popup=Popup(title='Восстановление покупки',content=box,size_hint=(.94,.8),auto_dismiss=False)
        restore.bind(on_release=lambda *_:(popup.dismiss(),self.controller.restore(code.text)))
        close.bind(on_release=popup.dismiss);popup.open()

    def restore(self,*_):
        if self.restore_callback is not None:self.restore_callback()

    def open_gift(self,*_):
        if self.gift_button.disabled or not getattr(self,'controller',None):return
        box=BoxLayout(orientation='vertical',padding=dp(12),spacing=dp(8))
        box._strategy_fixed_layout=True
        box.add_widget(ReadableText('Подарочный ключ',size=19,bold=True,color=GOLD))
        box.add_widget(ReadableText('Одноразовый ключ откроет полную версию навсегда. Нужен интернет. Для восстановления сохраните личный код.',size=14))
        email=TextInput(text=self.email.text,hint_text='Почта для связи',multiline=False,size_hint_y=None,height=dp(46),disabled=bool(self.controller.client.code))
        code=TextInput(hint_text='LERDON-XXXXXXXX-…',multiline=False,size_hint_y=None,height=dp(46),font_size=sp(16))
        box.add_widget(email);box.add_widget(code)
        submit=StrategyButton(text='Активировать',size_hint_y=None,height=dp(48),primary=True)
        close=StrategyButton(text='Отмена',size_hint_y=None,height=dp(44))
        box.add_widget(submit);box.add_widget(close)
        popup=Popup(title='Подарочный ключ',content=box,size_hint=(.94,.94),size_hint_max=(dp(560),dp(360)),auto_dismiss=False)
        prepare_custom_popup(popup)
        from window_theme import theme_tree
        theme_tree(box)
        popup.code_input=code;popup.email_input=email;popup.submit_button=submit
        def activate(*_):
            self.email.text=email.text
            popup.dismiss();self.controller.redeem_gift(code.text,email.text)
        submit.bind(on_release=activate);close.bind(on_release=popup.dismiss)
        self.gift_popup=popup;popup.open();return popup


def show_full_access(*_,on_purchase=None,on_restore=None):
    popup=FullAccessPopup(on_purchase=on_purchase,on_restore=on_restore)
    popup.open()
    if on_purchase is None and on_restore is None:
        from developer_access import enabled
        if enabled():
            popup.status.text='РЕЖИМ РАЗРАБОТЧИКА · Весь контент открыт локально. Покупка не оформлена.'
            return popup
        try:
            from billing_flow import get_billing_controller
            popup.attach_billing(get_billing_controller())
        except Exception:popup.status.text='Не удалось подключить сервис покупок. Попробуйте позже.'
    return popup
