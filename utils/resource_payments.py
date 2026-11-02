"""Persistent, atomic payments shared by paid player actions."""
import math
import sys


def sync_resources(conn, faction, model=None):
    balances = dict(conn.execute('SELECT resource_type,amount FROM resources WHERE faction=?', (faction,)))
    screen = getattr(sys.modules.get('game_process'), '_active_game_screen', None)
    if model is None and screen and getattr(screen, 'selected_faction', None) == faction:
        model = screen.faction
    if model is not None:
        model.resources.update(balances)
        for resource, field in {'Кроны': 'money', 'Рабочие': 'free_peoples',
                                'Кристаллы': 'raw_material', 'Население': 'population'}.items():
            if resource in balances:
                setattr(model, field, balances[resource])
    if screen and getattr(screen, 'faction', None) is model and getattr(screen, 'resource_box', None):
        screen.resource_box.update_resources()
    return balances


def spend_resources(conn, faction, costs):
    """Charge all requested resources or none, checking the live database balance."""
    if any(not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0
           for value in costs.values()):
        return False
    conn.execute('SAVEPOINT paid_action')
    try:
        for resource, amount in costs.items():
            if amount == 0:
                continue
            result = conn.execute('''UPDATE resources SET amount=amount-?
                WHERE faction=? AND resource_type=? AND amount>=?''', (amount, faction, resource, amount))
            if result.rowcount != 1:
                conn.execute('ROLLBACK TO paid_action')
                conn.execute('RELEASE paid_action')
                return False
        conn.execute('RELEASE paid_action')
        conn.commit()
    except Exception:
        conn.execute('ROLLBACK TO paid_action')
        conn.execute('RELEASE paid_action')
        raise
    sync_resources(conn, faction)
    return True


def exchange_resources(conn, first, second, give_type, give_amount, receive_type, receive_amount):
    """Perform both sides of an exchange together; never invent the missing balance."""
    if first == second or any(not isinstance(v, (int, float)) or not math.isfinite(v) or v <= 0
                              for v in (give_amount, receive_amount)):
        return False
    conn.execute('SAVEPOINT resource_exchange')
    try:
        for owner, resource, amount in ((first, give_type, give_amount), (second, receive_type, receive_amount)):
            result = conn.execute('UPDATE resources SET amount=amount-? WHERE faction=? AND resource_type=? AND amount>=?',
                                  (amount, owner, resource, amount))
            if result.rowcount != 1:
                conn.execute('ROLLBACK TO resource_exchange')
                conn.execute('RELEASE resource_exchange')
                return False
        for owner, resource, amount in ((second, give_type, give_amount), (first, receive_type, receive_amount)):
            result = conn.execute('UPDATE resources SET amount=amount+? WHERE faction=? AND resource_type=?',
                                  (amount, owner, resource))
            if result.rowcount != 1:
                raise ValueError('Recipient resource row is missing')
        conn.execute('RELEASE resource_exchange')
        conn.commit()
    except Exception:
        conn.execute('ROLLBACK TO resource_exchange')
        conn.execute('RELEASE resource_exchange')
        raise
    sync_resources(conn, first)
    sync_resources(conn, second)
    return True
