"""Exact terms shared by all unsolicited AI resource exchanges."""


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
