"""One reusable alpha-contour shader for the currently acting tactical unit."""
from kivy.graphics import Color, Rectangle, RenderContext
from kivy.metrics import dp

FRAGMENT='''$HEADER$
uniform vec2 outline_step;
uniform vec4 uv_bounds;
uniform vec4 outline_color;
float a(vec2 point) {
    return texture2D(texture0, clamp(point, uv_bounds.xy, uv_bounds.zw)).a;
}
void main(void) {
    vec2 p=tex_coord0;
    vec2 d=outline_step;
    float edge=max(max(a(p+vec2(d.x,0.0)),a(p-vec2(d.x,0.0))),
                   max(a(p+vec2(0.0,d.y)),a(p-vec2(0.0,d.y))));
    edge=max(edge,max(max(a(p+d),a(p-d)),
                      max(a(p+vec2(d.x,-d.y)),a(p+vec2(-d.x,d.y)))));
    float contour=smoothstep(0.18,0.72,edge)*(1.0-smoothstep(0.12,0.70,a(p)));
    gl_FragColor=vec4(outline_color.rgb,outline_color.a*contour)*frag_color;
}
'''


class UnitOutline:
    def __init__(self):
        self.context=RenderContext(use_parent_projection=True,use_parent_modelview=True)
        self.context.shader.fs=FRAGMENT
        with self.context:
            Color(1,1,1,1)
            self.rectangle=Rectangle()
        self.context['outline_color']=(1.,.84,.24,.98)

    def draw(self,canvas,texture,coords,pos,size):
        us=coords[::2];vs=coords[1::2]
        self.context['uv_bounds']=(min(us),min(vs),max(us),max(vs))
        self.context['outline_step']=(abs(max(us)-min(us))*dp(1.7)/max(1,size[0]),
                                      abs(max(vs)-min(vs))*dp(1.7)/max(1,size[1]))
        self.rectangle.texture=texture
        self.rectangle.tex_coords=coords
        self.rectangle.pos=pos;self.rectangle.size=size
        canvas.add(self.context)
