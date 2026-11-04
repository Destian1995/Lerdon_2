"""Exact terms shared by all unsolicited AI resource exchanges."""


def full_balance_offer(conn,seller,player,resources=None):
    from decimal import Decimal
    stock=resources if resources is not None else dict(conn.execute('SELECT resource_type,amount FROM resources WHERE faction=?',(seller,)))
    balances=dict(conn.execute('SELECT resource_type,amount FROM resources WHERE faction=?',(player,)))
    preferred=('Кристаллы','Кроны') if seller in ('Элины','Адепты') else ('Кроны','Кристаллы')
    for give in preferred:
        want='Кристаллы' if give=='Кроны' else 'Кроны'
        requested=balances.get(want,0) or 0
        if requested<=0:continue
        amount=requested*5/6
        if amount<=0 or (stock.get(give,0) or 0)<amount:continue
        if float(amount).is_integer():amount=int(amount)
        if float(requested).is_integer():requested=int(requested)
        exact=lambda value:format(Decimal(str(value)),'f')
        names={'Кроны':'Крон','Кристаллы':'Кристаллов'}
        text=f'Мы отдаём {exact(amount)} {names[give]}, вы — {exact(requested)} {names[want]}.'
        return give,amount,want,requested,text
    return None


def resource_offer(give_type, amount):
    """AI gives five units for six: exact 1:1.2 in either direction."""
    if give_type not in ('Кроны', 'Кристаллы'):
        raise ValueError('Для обмена доступны только кроны и кристаллы.')
    # Integer lots preserve the ratio without fractional resources or rounding
    # the displayed terms differently from the amounts actually transferred.
    give_amount = int(amount) // 5 * 5
    if give_amount < 5:
        return None
    want_type = 'Кристаллы' if give_type == 'Кроны' else 'Кроны'
    want_amount = give_amount // 5 * 6
    names = {'Кроны': 'Крон', 'Кристаллы': 'Кристаллов'}
    text = f'Мы отдаём {give_amount} {names[give_type]}, вы — {want_amount} {names[want_type]}.'
    return give_type, give_amount, want_type, want_amount, text
