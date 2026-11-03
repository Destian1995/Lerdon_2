"""AI takes reachable dead-end challenges only with a sufficient hero army."""
from monster_sites import (sites,reward,hunt_status,begin_hunt,resolve_hunt,finish_hunt,
                           progress,owned_artifacts,upgrade_artifact)


def try_hunt(conn,faction,controller=None):
    from utils.garrison_stats import garrison_totals
    choices=[]
    for site in sites(conn):
        allowed,source=hunt_status(conn,site,faction)
        if allowed and garrison_totals(conn,source)['attack']>=reward(site['tier'])['defense']:
            choices.append(site)
    if not choices:
        return False
    site=max(choices,key=lambda s:s['tier'])
    eid=begin_hunt(conn,site['id'],faction)
    from types import SimpleNamespace
    from troop_movement import _screen
    screen=_screen(SimpleNamespace(conn=conn))
    if screen:
        from monster_sites import expedition
        camp=expedition(conn,eid)['camp']
        count=conn.execute('SELECT SUM(unit_count) FROM garrisons WHERE city_name=?',(camp,)).fetchone()[0]
        if not hasattr(screen,'_ai_march_queue'):screen._ai_march_queue=[]
        if not hasattr(screen,'_ai_march_destinations'):screen._ai_march_destinations=set()
        if not hasattr(screen,'_terrain_moving_camps'):screen._terrain_moving_camps=set()
        screen._ai_march_queue.append((('@monster',site['road']),faction,count,count,'',None,None,'',False,True))
    resolve_hunt(conn,eid)
    finish_hunt(conn,eid)
    state=progress(conn,faction)
    if state['relic_earned'] and not state['relic_used']:
        items=owned_artifacts(conn,faction)
        if items:
            item=max(items,key=lambda a:max(a['attack'],a['defense']))
            stat='attack' if item['attack']>=item['defense'] else 'defense'
            upgrade_artifact(conn,faction,item['table'],item['id'],stat,item['hero'],item['slot'])
            if controller and getattr(controller,'season_manager',None):
                controller.season_manager.apply_artifact_bonuses(conn)
    if controller and hasattr(controller,'load_resources_from_db'):
        controller.load_resources_from_db()
    return True
