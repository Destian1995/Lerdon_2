"""Readable Russian resource quantities; formatting never changes a payment."""
import math
from utils.helpers import format_number,plural

FORMS={
    'Кроны':('крона','кроны','крон'),
    'Кристаллы':('кристалл','кристалла','кристаллов'),
    'Рабочие':('рабочий','рабочих','рабочих'),
}
PREPOSITIONAL={'Кроны':'кронах','Кристаллы':'кристаллах','Рабочие':'рабочих'}


def resource_amount(amount,resource,compact=True):
    amount=math.floor(amount)
    forms=FORMS[resource]
    if compact and abs(amount)>=1000:
        number,_,scale=format_number(amount).partition(' ')
        return number.removesuffix('.0').replace('.',',')+' '+scale+' '+forms[2]
    return f'{amount:,}'.replace(',',' ')+' '+plural(amount,*forms)
