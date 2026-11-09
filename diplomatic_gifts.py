"""Read-only gift quotes based on the recipient's towns and army standing."""
from dataclasses import dataclass
import math

CITY_LEVEL_PRICE=5000
ARMY_SURCHARGES={1:25,2:15}
NON_COMBAT_FACTIONS={'Нейтрал','Нейтральные',''}


def city_quality(coefficient):
    """Match the three ranges assigned by generate_map, including older saves."""
    try:value=float(coefficient or 0)
    except (TypeError,ValueError):value=0
    return 3 if value>=5.3 else 2 if value>=1.8 else 1


@dataclass(frozen=True)
class GiftQuote:
    base:int
    tiers:tuple
    city_bonus:int
    army_rank:object
    army_percent:int
    army_bonus:int

    @property
    def total(self):return self.base+self.city_bonus+self.army_bonus

    @property
    def cities(self):return sum(self.tiers)

    @property
    def quality(self):return sum(level*count for level,count in enumerate(self.tiers,1))


def quote_gift(conn,recipient,old_cost,strength_for):
    columns={r[1] for r in conn.execute('PRAGMA table_info(cities)')}
    if columns:
        coefficient='kf_crystal' if 'kf_crystal' in columns else '1'
        levels=[city_quality(row[0]) for row in conn.execute('SELECT '+coefficient+' FROM cities WHERE faction=?',(recipient,))]
        factions={r[0] for r in conn.execute('SELECT DISTINCT faction FROM cities') if r[0] is not None}
    else:levels=[];factions=set()
    tiers=tuple(levels.count(i) for i in (1,2,3))
    cities=CITY_LEVEL_PRICE*sum(levels)
    base=max(0,int(old_cost)//4)
    strengths={}
    for faction in sorted(factions-NON_COMBAT_FACTIONS):
        strength=float(strength_for(faction) or 0)
        strengths[faction]=strength if math.isfinite(strength) and strength>0 else 0
    target=strengths.get(recipient,0)
    # Equal positive strength shares a place; an empty army earns no surcharge.
    rank=1+sum(value>target for value in strengths.values()) if target>0 else None
    percent=ARMY_SURCHARGES.get(rank,0)
    return GiftQuote(base,tiers,cities,rank,percent,(base+cities)*percent//100)
