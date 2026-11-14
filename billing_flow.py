"""Main-thread purchase orchestration with resumable, idempotent server work."""
import json
import traceback
from pathlib import Path
from weakref import WeakSet

from billing_client import BillingClient,BillingError


class BillingController:
    def __init__(self,client,native=None,schedule=None,run=None):
        self.client=client;self.native=native;self.views=WeakSet();self.busy=False
        self.message='';self.poll_count=0
        if schedule is None:
            from kivy.clock import Clock
            schedule=lambda callback,delay=0:Clock.schedule_once(lambda dt:callback(),delay)
        self.schedule=schedule
        if run is None:
            from background_tasks import tasks
            run=lambda target:tasks.start(target,'billing-request')
        self.run=run

    def notify(self,message=None):
        if message is not None:self.message=message
        for view in tuple(self.views):view.sync_billing(self)

    def job(self,operation,complete):
        if self.busy:return
        self.busy=True;self.notify()
        def worker():
            try:result=operation();error=None
            except BillingError as exc:result=None;error=str(exc)
            except Exception as exc:
                result=None
                # Record only exception class and code locations. Exception text,
                # request bodies and locals may contain payment/recovery tokens.
                frames=traceback.extract_tb(exc.__traceback__)
                location=frames[-1] if frames else None
                code=type(exc).__name__+('@'+Path(location.filename).name+':'+str(location.lineno) if location else '')
                self.last_error_code=code
                try:
                    path=self.client.path.with_name('diagnostic.json')
                    path.write_text(json.dumps({'error':type(exc).__name__,
                        'frames':[{'file':Path(f.filename).name,'line':f.lineno,'function':f.name} for f in frames]}),encoding='utf-8')
                except Exception:pass
                error='Не удалось проверить оплату. Код: '+code+'. Повторно оплачивать не нужно.'
            def finish():
                from background_tasks import tasks
                if tasks.stopping.is_set():return
                self.busy=False
                if error:self.notify(error)
                else:
                    try:complete(result)
                    except BillingError as exc:self.notify(str(exc))
                    self.notify()
            self.schedule(finish)
        try:self.run(worker)
        except Exception:
            self.busy=False;self.notify('Платёжный запрос не запущен.')

    def open(self,view):
        self.views.add(view);self.notify()
        def load():
            catalog=self.client.load_catalog()
            if self.client.code:self.client.refresh_access()
            return catalog
        def loaded(_):
            if self.client.pending and self.client.pending['stage']!='tokenizing':self.check()
            else:self.notify(self.access_caption())
        self.job(load,loaded)

    def access_caption(self):
        access=self.client.access()
        prefix='ТЕСТОВЫЙ МАГАЗИН. ' if self.client.config['test_mode'] else ''
        if access:return prefix+('Покупка навсегда подтверждена.' if access['permanent'] else 'Подписка подтверждена.')
        if self.native is None:return prefix+'Оплата доступна в Android-приложении.'
        if not self.client.config.get('sdk_key'):return prefix+'Ключ мобильного SDK ещё не настроен.'
        if not self.client.config.get('public_key'):return prefix+'Магазин ещё настраивается: не указан ключ проверки покупок.'
        if self.client.pending:
            if self.client.pending['stage']=='tokenizing':
                return prefix+'Оплата подготовлена. Если форма ЮKassa закрыта, нажмите «Отменить подготовку оплаты» и повторите покупку.'
            return prefix+'Есть незавершённая оплата. Нажмите «Проверить покупку».'
        return prefix+'Деньги в тестовом магазине не списываются.' if prefix else 'Выберите способ покупки.'

    def purchase(self,plan,email='',consent=False):
        if self.busy:return
        if self.native is None:self.notify('Оплата доступна в Android-приложении.');return
        self.notify('Подготовка оплаты…')
        def launch(request):
            try:self.native.tokenize(request,self.client.config)
            except Exception:
                self.client.token_canceled(request['request_id'])
                raise BillingError('Не удалось открыть форму ЮKassa. Проверьте Android-сборку.') from None
            self.notify('Заполните форму ЮKassa. Доступ откроется после проверки сервером.')
        self.job(lambda:self.client.prepare(plan,email,consent),launch)

    def check(self,allow_confirmation=True):
        if self.busy:return
        pending=self.client.pending
        if not pending:
            self.job(self.client.refresh_access,lambda _:self.notify(self.access_caption()));return
        if pending['stage']=='tokenizing':
            self.notify('Форма оплаты ещё не завершена. Можно отменить подготовку и открыть её заново.');return
        self.notify('Проверка оплаты…')
        def checked(result):
            if not result:return
            status=result['status']
            if status=='succeeded':
                self.notify(self.access_caption() if not result.get('refunded') else 'Платёж возвращён. Доступ обновлён.')
            elif status=='canceled':self.notify('Платёж отменён. Списания не подтверждены.')
            elif status=='review':self.notify('Платёж требует проверки поддержкой. Не создавайте повторную оплату.')
            elif result.get('confirmation_url') and allow_confirmation and self.native:
                try:self.native.confirm(self.client.pending,result['confirmation_url'],self.client.config)
                except Exception:raise BillingError('Не удалось открыть подтверждение. Проверьте покупку повторно.') from None
                self.notify('Подтвердите платёж в форме ЮKassa.')
            elif self.poll_count<12:
                self.poll_count+=1;self.schedule(lambda:self.check(False),2)
            else:self.notify('Оплата ещё обрабатывается. Нажмите «Проверить покупку» позже.')
        self.job(self.client.check_order,checked)

    def native_event(self,event):
        pending=self.client.pending
        if not pending or event.get('session')!=pending['request_id']:return
        kind=event.get('type')
        if kind=='token':
            try:
                if self.client.token_received(event['session'],event.get('payment_token'),event.get('method')):
                    self.poll_count=0;self.check()
            except BillingError as exc:self.notify(str(exc))
        elif kind=='confirmation':self.poll_count=0;self.check(False)
        elif kind in ('canceled','error'):
            self.client.token_canceled(event['session'])
            self.notify('Оплата отменена.' if kind=='canceled' else 'Форма ЮKassa не открылась. Повторите позже.')

    def cancel_preparation(self):
        if self.busy:return
        if self.client.pending:self.client.token_canceled(self.client.pending['request_id'])
        self.notify('Подготовка отменена. Проверенные сервером платежи не изменены.')

    def restore(self,code):
        self.job(lambda:self.client.restore(code),lambda _:self.notify(self.access_caption()))

    def redeem_gift(self,key,email=''):
        if self.busy:return
        self.notify('Проверка подарочного ключа…')
        def activated(_):
            prefix='ТЕСТОВЫЙ МАГАЗИН. ' if self.client.config['test_mode'] else ''
            self.notify(prefix+'Ключ принят. Полная версия открыта навсегда. Сохраните личный код восстановления.')
        self.job(lambda:self.client.redeem_gift(key,email),activated)

    def cancel_subscription(self):
        self.job(self.client.cancel_subscription,lambda _:self.notify('Автопродление отключено. Оплаченный доступ сохранён.'))


def get_billing_controller():
    from kivy.app import App
    from kivy.utils import platform
    from kivy.clock import Clock
    app=App.get_running_app()
    if app is None:raise BillingError('Приложение ещё не запущено.')
    if getattr(app,'_billing_controller',None):return app._billing_controller
    config=json.loads(Path(__file__).with_name('billing_config.json').read_text(encoding='utf-8'))
    mode='test' if config['test_mode'] else 'live'
    client=BillingClient(Path(app.user_data_dir)/'billing'/(mode+'-'+config['shop_id'])/'access.json',config)
    native=None
    if platform=='android':
        try:
            from billing_android import AndroidPayments
            native=AndroidPayments()
            client.verify=native.verify_license
        except Exception:pass
    controller=BillingController(client,native)
    app._billing_controller=controller
    if native:
        def poll(_dt):
            for event in native.poll():controller.native_event(event)
        controller._native_poll=Clock.schedule_interval(poll,.25)
    return controller
