"""Text fallbacks for symbols absent from the game's bundled font."""
import re

_PICTOGRAMS = re.compile('[\u2600-\u27bf\U0001f000-\U0001faff\u2139\u25b2\u25bc\ufe0e\ufe0f\u200d]')
_ARROWS = str.maketrans({'→':'->', '←':'<-', '⇒':'=>', '⇐':'<='})
_OTHER_ARROWS = re.compile('[\u2190-\u21ff]')


def plain_ui_text(text):
    if text.strip() in ('✕','✖','✗'):
        return '×'
    return _PICTOGRAMS.sub('',_OTHER_ARROWS.sub('',text.translate(_ARROWS)))


def bind_plain_text(widget, property_name='text'):
    """Clean initial and later text, preserving markup, line breaks and values."""
    marker='_plain_ui_'+property_name
    if getattr(widget,marker,False):
        return
    def clean(instance,value):
        result=plain_ui_text(value)
        if result != value:
            setattr(instance,property_name,result)
    setattr(widget,marker,True)
    widget.bind(**{property_name:clean})
    clean(widget,getattr(widget,property_name))
