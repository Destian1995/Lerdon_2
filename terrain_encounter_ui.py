"""Replay persisted terrain battles on the UI thread, after the marches finish."""
import json
import sqlite3
from battle_ui import BattleViewer


def show_pending(screen):
    if getattr(screen,'_terrain_battle_popup',None) is not None:return
    faction=getattr(screen,'selected_faction',None)
    if not faction:return
    try:
        row=screen.conn.execute('''SELECT id,result FROM terrain_battles WHERE seen=0
            AND (attacker=? OR defender=?) ORDER BY id LIMIT 1''',(faction,faction)).fetchone()
    except sqlite3.OperationalError:return
    if not row:return
    bid,data=row;result=json.loads(data)
    class EncounterView(BattleViewer):
        def show_frame(view,index):
            super().show_frame(index)
            view.round_label.text+=f' · {result["attacker"]}: −15% урона и защиты'
        def reveal_result(view,*args):
            super().reveal_result(*args)
            if result['winner']=='draw':view.result_label.text='БОЙ ПРЕРВАН · ОТСТУПЛЕНИЕ'
            view.result_detail.text=(f'Позднее прибытие: {result["attacker"]} · −15% урона и защиты в этом бою.')
            view.finish_button.text='Закрыть'
            view.event_label.text='Потери сохранены. Города не меняют владельца.'
    def closed():
        screen.conn.execute('UPDATE terrain_battles SET seen=1 WHERE id=?',(bid,));screen.conn.commit()
        screen._terrain_battle_popup=None
        show_pending(screen)
    def image(key):
        return next((u['unit_image'] for u in result[key] if u.get('unit_image')),None)
    popup=EncounterView(result['rounds'],result['attacker'],result['defender'],result['winner'],
                        faction,result['attacker_source'],result['place'],callback=closed,
                        attacker_image=image('army'),defender_image=image('defenders'))
    screen._terrain_battle_popup=popup
    popup.event_label.text=f'Позднее прибытие: {result["attacker"]} · штраф −15% на этот бой.'
    popup.open()
