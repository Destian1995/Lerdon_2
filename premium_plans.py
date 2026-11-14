"""Store-independent full-access offers; prices in integer kopecks."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Plan:
    key:str
    title:str
    price_kopecks:int
    period:str|None

    @property
    def price_text(self):
        return str(self.price_kopecks//100)+' ₽'+(' / месяц' if self.period else ' навсегда')


MONTHLY=Plan('full_monthly','Подписка',5500,'P1M')
PERMANENT=Plan('full_permanent','Покупка навсегда',25000,None)
PLANS={plan.key:plan for plan in (MONTHLY,PERMANENT)}
BENEFITS=('Все игровые фракции и Зазеркалье',
          'Тактические бои',
          'Сюжетные задания таверны и диверсии',
          'Полное отключение рекламы')
