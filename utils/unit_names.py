"""Presentation only: database names remain stable identifiers."""
import re


def unit_display_name(name):
    text=str(name or '').strip()
    text=re.sub(r'^(?:Спутник|Странник|Легион):\s*','',text)
    text=re.sub(r'\s*/\s*(?:Север|Элины|Адепты|Вампиры|Эльфы|Нежить|Мятежники)(?:\s*#\d+)?\s*$','',text)
    text=re.sub(r'\s*\[(?:Герой|Чемпион|Легенда)\]\s*$','',text)
    return text.strip()
