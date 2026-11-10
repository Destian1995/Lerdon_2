"""Crystal quotes per 100-unit lot; trading skill narrows a positive spread."""
from decimal import Decimal,ROUND_CEILING,ROUND_FLOOR,InvalidOperation
import sqlite3

LOT_SIZE=100


def trade_efficiency(faction,markets=0,season=-1,council=0):
    value=1+max(0,markets)*.10+max(0,council)/100
    if faction=='Элины':value+=(.25*2.75 if season==2 else .25)+.20
    return value


def crystal_quotes(price,efficiency=1):
    price=Decimal(str(price));efficiency=Decimal(str(efficiency))
    if not price.is_finite() or price<=0 or not efficiency.is_finite():
        raise ValueError('Некорректная котировка кристаллов.')
    spread=Decimal('.05')/max(Decimal(1),efficiency)
    buy=(price*(1+spread)).quantize(Decimal('.01'),rounding=ROUND_CEILING)
    sell=(price*(1-spread)).quantize(Decimal('.01'),rounding=ROUND_FLOOR)
    return float(buy),float(sell)


def total_price(lot_price,lots):
    try:quantity=Decimal(str(lots))
    except InvalidOperation:raise ValueError('Некорректное количество лотов.') from None
    if not quantity.is_finite() or quantity<=0 or quantity!=quantity.to_integral_value():
        raise ValueError('Количество лотов должно быть положительным целым числом.')
    return float(Decimal(str(lot_price))*quantity)


def affordable_lots(crowns,lot_price):
    return max(0,int(Decimal(str(crowns))//Decimal(str(lot_price))))


def ai_sell_price(ai):
    """AI stores a quote per lot too; return crowns for one crystal."""
    conn=getattr(ai,'db_connection',None) or getattr(ai,'conn',None)
    markets=getattr(ai,'markets',0);season=-1
    if conn is not None:
        from utils.market_income import market_profile
        try:markets=market_profile(conn,ai.faction)[0]
        except sqlite3.OperationalError:pass
        try:
            row=conn.execute('SELECT season_index FROM season LIMIT 1').fetchone()
            if row:season=row[0]
        except sqlite3.OperationalError:pass
    _,sell=crystal_quotes(ai.raw_material_price,trade_efficiency(ai.faction,markets,season))
    return sell/LOT_SIZE
