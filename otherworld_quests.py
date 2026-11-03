"""Persistent detective case, fairy allegiance and repeatable campaign rewards."""
import random
import json
import sqlite3
from city_war import current_turn

SUSPECTS=('Ирель','Валтор','Серена')
TOKENS=('серебряный браслет','янтарный перстень','алый плащ')
SIDES=('Лунный двор','Стеклянный престол')


def ensure_schema(conn):
    conn.execute('''CREATE TABLE IF NOT EXISTS portal_quest_runs(
        faction TEXT PRIMARY KEY,cycle INTEGER NOT NULL,culprit INTEGER NOT NULL,
        detective INTEGER NOT NULL DEFAULT 0,war INTEGER NOT NULL DEFAULT 0,side TEXT,
        finished_turn INTEGER,repeat_turn INTEGER NOT NULL DEFAULT 0)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS portal_quest_rewards(
        faction TEXT NOT NULL,cycle INTEGER NOT NULL,reward INTEGER NOT NULL,artifact_id INTEGER,
        PRIMARY KEY(faction,cycle,reward))''')
    conn.execute('''CREATE TABLE IF NOT EXISTS portal_quest_buffs(
        faction TEXT PRIMARY KEY,until_turn INTEGER NOT NULL)''')
    if 'scenario' not in {r[1] for r in conn.execute('PRAGMA table_info(portal_quest_runs)')}:
        conn.execute('ALTER TABLE portal_quest_runs ADD COLUMN scenario TEXT')
    conn.execute('''CREATE TABLE IF NOT EXISTS portal_quest_history(
        faction TEXT NOT NULL,kind TEXT NOT NULL,template TEXT NOT NULL,cycle INTEGER NOT NULL,
        PRIMARY KEY(faction,kind,template))''')


def state(conn,faction):
    ensure_schema(conn)
    row=conn.execute('SELECT cycle,culprit,detective,war,side,finished_turn,repeat_turn,scenario FROM portal_quest_runs WHERE faction=?',(faction,)).fetchone()
    return dict(zip(('cycle','culprit','detective','war','side','finished_turn','repeat_turn','scenario'),row)) if row else None


def details(run):
    from otherworld_quest_pool import legacy
    return json.loads(run['scenario']) if run and run.get('scenario') else legacy()


def local_detective_clue(run,city_id):
    """Each clue stays at its source; the accusation never displays evidence."""
    if not run or not 1<=run['detective']<3:return ''
    d=details(run)['detective']
    if city_id==d['cities'][0]:
        return 'Улика свидетеля: '+d['tokens'][run['culprit']]+'.'
    if run['detective']>=2 and city_id==d['cities'][1]:
        return 'Записи: '+'; '.join(n+' — '+t for n,t in zip(d['suspects'],d['tokens']))+'.'
    return ''


def pending(conn,faction):
    ensure_schema(conn)
    return [r[0] for r in conn.execute('SELECT reward FROM portal_quest_rewards WHERE faction=? AND artifact_id IS NULL ORDER BY cycle,reward',(faction,))]


def cap_multiplier(conn,faction):
    try:
        row=conn.execute('SELECT until_turn FROM portal_quest_buffs WHERE faction=?',(faction,)).fetchone()
        return 1.35 if row and row[0]>current_turn(conn) else 1.0
    except sqlite3.OperationalError:return 1.0


def cap_turns(conn,faction):
    try:
        row=conn.execute('SELECT until_turn FROM portal_quest_buffs WHERE faction=?',(faction,)).fetchone()
        return max(0,row[0]-current_turn(conn)) if row else 0
    except sqlite3.OperationalError:return 0


def _queue(conn,faction,key):
    run=state(conn,faction)
    conn.execute('INSERT OR IGNORE INTO portal_quest_rewards VALUES(?,?,?,NULL)',(faction,run['cycle'],key))


def _finish(conn,faction):
    run=state(conn,faction)
    if run['detective']==3 and run['war']==3 and run['finished_turn'] is None:
        turn=current_turn(conn)
        conn.execute('UPDATE portal_quest_runs SET finished_turn=?,repeat_turn=? WHERE faction=?',(turn,turn+15,faction))
        _queue(conn,faction,103)


def begin(conn,faction,rng=None):
    from otherworlds import atomic,_party_city
    ensure_schema(conn)
    with atomic(conn):
        _,city=_party_city(conn,faction)
        if city['id']!=1:raise ValueError('Примите задания у Врат странников.')
        old=state(conn,faction)
        if old and (old['finished_turn'] is None or old['repeat_turn']>current_turn(conn)):
            raise ValueError('Цепочка уже идёт или ещё не восстановилась.')
        if pending(conn,faction):raise ValueError('Сначала заберите все награды предыдущей цепочки.')
        cycle=(old['cycle']+1) if old else 1
        if old and not old['scenario']:
            # Record legacy stories when replacing them, without writes on reads.
            for kind,key in (('detective','key'),('war','moon')):
                conn.execute('INSERT OR IGNORE INTO portal_quest_history VALUES(?,?,?,?)',
                             (faction,kind,key,old['cycle']))
        from otherworld_quest_pool import generate
        generator=rng or random
        scenario=generate(conn,faction,cycle,generator)
        culprit=generator.randrange(3)
        conn.execute('''INSERT INTO portal_quest_runs(faction,cycle,culprit,detective,war,side,finished_turn,repeat_turn,scenario)
            VALUES(?,?,?,0,0,NULL,NULL,0,?)
            ON CONFLICT(faction) DO UPDATE SET cycle=excluded.cycle,culprit=excluded.culprit,
            detective=0,war=0,side=NULL,finished_turn=NULL,repeat_turn=0,scenario=excluded.scenario''',
            (faction,cycle,culprit,json.dumps(scenario,ensure_ascii=False)))
    return 'Новые задания: «'+scenario['detective']['title']+'» и «'+scenario['war']['title']+'». Маршруты указаны в журнале.'


def action(conn,faction,kind,choice=None):
    from otherworlds import atomic,_party_city,_pay
    from utils.resource_payments import ensure_resource_schema
    ensure_resource_schema(conn)
    run=state(conn,faction)
    if not run or run['finished_turn'] is not None:raise ValueError('Сначала примите новую цепочку заданий.')
    scenario=details(run);detective=scenario['detective'];war=scenario['war']
    suspects,tokens=detective['suspects'],detective['tokens']
    with atomic(conn):
        _,city=_party_city(conn,faction)
        if kind=='witness' and run['detective']==0 and city['id']==detective['cities'][0]:
            conn.execute('UPDATE portal_quest_runs SET detective=1 WHERE faction=?',(faction,))
            return detective['witness']+': '+tokens[run['culprit']]+'. Следующий шаг указан в журнале.'
        if kind=='ledger' and run['detective']==1 and city['id']==detective['cities'][1]:
            conn.execute('UPDATE portal_quest_runs SET detective=2 WHERE faction=?',(faction,))
            return detective['ledger']+': '+ '; '.join(n+' — '+t for n,t in zip(suspects,tokens))+'. Место предъявления обвинения указано в журнале.'
        if kind=='accuse' and run['detective']==2 and city['id']==detective['cities'][2]:
            if choice not in suspects:raise ValueError('Выберите подозреваемого.')
            if choice!=suspects[run['culprit']]:
                conn.execute('UPDATE portal_quest_runs SET detective=0 WHERE faction=?',(faction,))
                return 'Обвинение не подтвердилось. Награды нет: снова опросите свидетеля и проверьте книгу.'
            conn.execute('UPDATE portal_quest_runs SET detective=3 WHERE faction=?',(faction,))
            _queue(conn,faction,101);_finish(conn,faction)
            return detective['solved']+' «Венец истины» доступен герою 3 класса на 25 ходов.'
        if kind=='side' and run['war']==0 and city['id']==war['embassy']:
            if choice not in war['sides']:raise ValueError('Выберите одну из двух сторон конфликта.')
            conn.execute('UPDATE portal_quest_runs SET war=1,side=? WHERE faction=?',(choice,faction))
            return 'Вы поддержали '+choice+'. Припасы: '+str(war['amount'])+' · '+war['resource']+'.'
        supply_city=war['supplies'][0 if run['side']==war['sides'][0] else 1]
        if kind=='supply' and run['war']==1 and city['id']==supply_city:
            _pay(conn,faction,war['resource'],war['amount'])
            conn.execute('UPDATE portal_quest_runs SET war=2 WHERE faction=?',(faction,))
            return 'Союзники получили припасы. Победите противостоящий двор в городе, указанном в журнале.'
        raise ValueError('Это действие доступно на другом этапе или в другом городе.')


def war_target(conn,faction,city_id):
    run=state(conn,faction)
    war=details(run)['war']
    if run and run['war']==2 and city_id==war['target']:
        return war['sides'][1] if run['side']==war['sides'][0] else war['sides'][0]
    return None


def battle_won(conn,faction,city_id):
    if war_target(conn,faction,city_id):
        conn.execute('UPDATE portal_quest_runs SET war=3 WHERE faction=?',(faction,))
        _queue(conn,faction,102);_finish(conn,faction)
        return True
    return False


def claim(conn,faction,hero=None):
    from otherworlds import atomic,_party_city
    from portal_items import issue,reward
    ensure_schema(conn)
    issued=[]
    with atomic(conn):
        p,_=_party_city(conn,faction)
        rows=conn.execute('SELECT cycle,reward FROM portal_quest_rewards WHERE faction=? AND artifact_id IS NULL ORDER BY cycle,reward',(faction,)).fetchall()
        if not rows:raise ValueError('Нет неполученных наград.')
        for cycle,key in rows:
            aid=issue(conn,faction,p['camp'],reward(conn,faction,key),hero)
            conn.execute('UPDATE portal_quest_rewards SET artifact_id=? WHERE faction=? AND cycle=? AND reward=?',(aid,faction,cycle,key))
            issued.append(aid)
            if key==103:
                conn.execute('''INSERT INTO portal_quest_buffs VALUES(?,?) ON CONFLICT(faction)
                    DO UPDATE SET until_turn=MAX(until_turn,excluded.until_turn)''',(faction,current_turn(conn)+25))
    return issued


def objectives(conn,faction):
    run=state(conn,faction)
    if not run or run['finished_turn'] is not None:return {1}
    scenario=details(run);d=scenario['detective'];w=scenario['war']
    result=set()
    if run['detective']<3:result.add(d['cities'][run['detective']])
    if run['war']<3:result.add((w['embassy'],w['supplies'][0 if run['side']==w['sides'][0] else 1],w['target'])[run['war']])
    return result
