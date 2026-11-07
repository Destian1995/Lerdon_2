"""Resource storage ceilings, including the temporary Mirror Realm reward."""
def caps(conn,faction):
    from otherworld_quests import cap_multiplier
    mult=cap_multiplier(conn,faction)
    from morgana_covenant import multiplier
    mult*=multiplier(conn,faction)
    base=12_000_000 if faction=='Элины' else 10_000_000
    return {'Кроны':round(base*mult),'Кристаллы':round(base*mult),
            'Рабочие':round(500_000*mult),'Население':round(100_000_000*mult)}
