"""Weapon presentation is separate from faction matchup types and saved stats."""
import re

DEFENSIVE_HERO_IMAGES={
    'people/olga.jpg':'mage','adepts/sestra.jpg':'mage','poly/clare.jpg':'mage',
    'vampires/anabel.jpg':'mage','vampires/isabel.jpg':'mage',
    'vampires/frost.jpg':'infantry',
}
DEFENSIVE_HERO_NAMES={
    'ольга':'mage','сестра милосердия':'mage','сестра':'mage','кристол':'mage',
    'анабэль':'mage','анабель':'mage','изабэлл':'mage','изабелл':'mage','дитрих фрост':'infantry',
    'люци':'mage','моргана':'mage',
}
MIRROR_ROLES={'sentinel':'infantry','archer':'archer','rider':'cavalry',
              'weaver':'mage','golem':'infantry','boss':'mage'}


def image_reference(unit):
    return str(unit.get('unit_image') or unit.get('image_path') or '').replace('\\','/').lower()


def mirror_profile(unit):
    image=image_reference(unit)
    match=re.search(r'files/otherworld/themes/(north|elves|vampires|adepts|elines)/(?:units|women)/([^/]+)$',image)
    if match and match[2] in MIRROR_ROLES:return match[1],match[2]
    match=re.search(r'files/otherworld/units/([^/]+)\.png$',image)
    if match and match[1] in MIRROR_ROLES:return 'common',match[1]
    return None


def presentation_role(unit):
    image=image_reference(unit)
    for ending,role in DEFENSIVE_HERO_IMAGES.items():
        if image.endswith(ending):return role
    name=str(unit.get('unit_name') or '').strip().casefold()
    if name in DEFENSIVE_HERO_NAMES:return DEFENSIVE_HERO_NAMES[name]
    profile=mirror_profile(unit)
    if profile:return MIRROR_ROLES[profile[1]]
    return None


def mirror_attack_sound(unit,ranged):
    profile=mirror_profile(unit)
    if not profile:return None
    faction,kind=profile
    if ranged:
        if kind=='archer':return 'bow'
        return 'frost' if faction=='north' else 'magic'
    if kind=='golem':return 'monster' if faction=='vampires' else 'hit'
    if kind in ('weaver','boss') or faction=='elves' and kind=='sentinel':return 'hit'
    return 'sword'


def movement_sound(unit):
    profile=mirror_profile(unit)
    if profile and profile[1]=='rider':return 'hooves'
    if profile and profile[1]=='golem':return 'stone_step'
    return 'step'
