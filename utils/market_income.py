"""Markets boost one income stream, chosen by the current political system."""
import sqlite3


def market_policy(conn,faction):
    try:row=conn.execute('SELECT system FROM political_systems WHERE faction=?',(faction,)).fetchone()
    except sqlite3.OperationalError:row=None
    if row and row[0]=='Борьба':
        return 'Кристаллы',{'Элины':110,'Вампиры':130,'Эльфы':130,'Адепты':80}.get(faction,65)
    return 'Кроны',15 if faction=='Север' else 10


def market_profile(conn,faction):
    resource,percent=market_policy(conn,faction)
    from utils.faction_bonuses import supplied_cities
    supplied=supplied_cities(conn,faction)
    rows=conn.execute('''SELECT DISTINCT b.city_name FROM buildings b
        JOIN cities c ON c.name=b.city_name AND c.faction=b.faction
        WHERE b.faction=? AND b.building_type='Рынок' AND b.count>0''',(faction,))
    count=sum(city in supplied for city, in rows)
    return count,percent if resource=='Кроны' else 0,percent if resource=='Кристаллы' else 0


def additional_income(base,markets,percent):
    """Linear stacking, whole resources, and no multiplier on expenses or debts."""
    return int(max(0,base)*max(0,markets)*percent/100)
