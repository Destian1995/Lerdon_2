"""Faction soundtrack selection; runtime needs no synthesis libraries."""
from pathlib import Path

ROOT=Path(__file__).resolve().parent/'files/music'
BATTLE_THEME=ROOT/'battle_mirror_overture.wav'
BATTLE_MIX=BATTLE_THEME  # Compatibility for existing callers of the old constant.
FACTIONS={'Север':'north','Элины':'elines','Эльфы':'elves','Адепты':'adepts',
          'Вампиры':'vampires','Нежить':'undead','Мятежники':'rebels'}


def track_for(faction='Север',scene='background'):
    if scene=='menu':return ROOT/'menu.wav'
    if scene=='battle':return BATTLE_THEME
    key=FACTIONS.get(faction,'north')
    scene='battle' if scene=='battle' else 'background'
    return ROOT/(key+'_'+scene+'.wav')
