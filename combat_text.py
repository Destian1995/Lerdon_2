"""Consistent red critical-hit information, with safe Kivy text markup."""
import re
from kivy.utils import escape_markup

CRITICAL_COLOR=(1,81/255,72/255,1)
CRITICAL_HEX='ff5148'
_CRITICAL=re.compile(r'критические удары ×\d+|критов:\s*\d+|крит:\s*[\d.,]+%|\bКРИТ\b',re.IGNORECASE)


def critical_markup(text):
    return _CRITICAL.sub(lambda m:'[color='+CRITICAL_HEX+']'+m[0]+'[/color]',escape_markup(text))
