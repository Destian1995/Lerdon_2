"""Resource aid requests quote a real player balance and can be accepted only once."""
import re
from utils.resource_payments import ensure_resource_schema


def request_amount(conn,player,own_resources):
    available={kind:amount for kind,amount in conn.execute('''SELECT resource_type,amount FROM resources
        WHERE faction=? AND resource_type IN ('Кроны','Кристаллы') AND amount>0''',(player,))}
    if not available:return None
    kind=min(available,key=lambda k:own_resources.get(k,0))
    amount=available[kind]
    number=str(int(amount)) if float(amount).is_integer() else str(amount)
    return kind,amount,f'Просим передать {number} '+('крон.' if kind=='Кроны' else 'кристаллов.')


def accept_request(conn,player,receiver,message):
    match=re.search(r'Просим передать (\d+(?:[.,]\d+)?) (крон|кристаллов)',message)
    if not match:return False,'В просьбе не указана точная сумма ресурсов.'
    amount=float(match[1].replace(',','.'));kind='Кроны' if match[2]=='крон' else 'Кристаллы'
    if amount<=0:return False,'Сумма запроса некорректна.'
    ensure_resource_schema(conn)
    conn.execute('CREATE TABLE IF NOT EXISTS resource_aid_payments(message_id INTEGER PRIMARY KEY)')
    row=conn.execute('''SELECT id FROM negotiation_history WHERE faction1=? AND faction2=? AND message=?
        AND is_player=0 ORDER BY id DESC LIMIT 1''',(receiver,player,message)).fetchone()
    if not row:return False,'Запрос больше недоступен.'
    conn.execute('SAVEPOINT resource_aid')
    try:
        inserted=conn.execute('INSERT OR IGNORE INTO resource_aid_payments VALUES(?)',row)
        if not inserted.rowcount:
            conn.execute('RELEASE resource_aid');return False,'Эта просьба уже выполнена.'
        paid=conn.execute('''UPDATE resources SET amount=amount-? WHERE faction=? AND resource_type=? AND amount>=?''',
                          (amount,player,kind,amount))
        if paid.rowcount!=1:
            conn.execute('ROLLBACK TO resource_aid');conn.execute('RELEASE resource_aid')
            return False,'Ресурсов уже недостаточно для указанной в письме суммы.'
        conn.execute('''INSERT INTO resources(faction,resource_type,amount) VALUES(?,?,?)
            ON CONFLICT(faction,resource_type) DO UPDATE SET amount=amount+excluded.amount''',(receiver,kind,amount))
        conn.execute('RELEASE resource_aid')
    except Exception:
        conn.execute('ROLLBACK TO resource_aid');conn.execute('RELEASE resource_aid');raise
    return True,f'Передано {match[1]} '+('крон.' if kind=='Кроны' else 'кристаллов.')
