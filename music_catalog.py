"""Faction soundtrack selection; runtime needs no synthesis libraries."""
from pathlib import Path

ROOT=Path(__file__).resolve().parent/'files/music'
FACTIONS={'Север':'north','Элины':'elines','Эльфы':'elves','Адепты':'adepts',
          'Вампиры':'vampires','Нежить':'undead','Мятежники':'rebels'}


def track_for(faction='Север',scene='background'):
    if scene=='menu':return ROOT/'menu.wav'
    key=FACTIONS.get(faction,'north')
    scene='battle' if scene=='battle' else 'background'
    return ROOT/(key+'_'+scene+'.wav')
