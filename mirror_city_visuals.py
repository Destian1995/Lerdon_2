"""Presentation-only depth and silhouettes; city IDs and travel stay unchanged."""
ROLES=('gateway','harbor','sanctuary','citadel','market','observatory','crossroads')
ROLE_SCALE=(1.02,1.12,.96,1.05,1.10,.98,1.06)


def city_scale(city_id,y):
    # Distant terraces read smaller; foreground towns stand out from the map.
    perspective=1.12-min(800,max(0,y))/800*.26
    return ROLE_SCALE[(int(city_id)-1)%7]*perspective


def depth_order(nodes):
    return sorted(nodes,key=lambda city:(-city['y'],city['id']))


def soft_shadow_texture():
    from kivy.graphics.texture import Texture
    texture=Texture.create(size=(64,64),colorfmt='rgba')
    pixels=bytearray()
    for y in range(64):
        for x in range(64):
            radius=((x-31.5)/31.5)**2+((y-31.5)/31.5)**2
            pixels.extend((255,255,255,round(255*max(0,1-radius)**2)))
    texture.blit_buffer(bytes(pixels),colorfmt='rgba',bufferfmt='ubyte')
    return texture


def aerial_texture():
    """Very light distance haze, transparent over the foreground."""
    from kivy.graphics.texture import Texture
    texture=Texture.create(size=(2,64),colorfmt='rgba')
    pixels=bytearray()
    for y in range(64):
        opacity=round(255*.11*(y/63)**2)
        pixels.extend((255,255,255,opacity)*2)
    texture.blit_buffer(bytes(pixels),colorfmt='rgba',bufferfmt='ubyte')
    return texture
