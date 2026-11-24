import json, re
from PIL import Image, ImageDraw, ImageFont
exec(open('build_promos.py').read().split('def build')[0])  # PROMOS, words
F='/usr/share/fonts/truetype/google-fonts/ofl/anton/Anton-Regular.ttf'
import glob
mono=(glob.glob('/home/claude/motion/fontsource-jetbrains-mono/**/*.ttf',recursive=True)+glob.glob('/usr/share/fonts/**/DejaVuSansMono.ttf',recursive=True))[0]
def f(sz,m=False): return ImageFont.truetype(mono if m else F,sz)
INK=(10,10,11);BONE=(244,242,236);GOLD=(212,175,55);TEAL=(45,214,174);DIM=(140,140,145);RED=(200,70,60)
W,H=1800,1060
im=Image.new('RGB',(W,H),INK);d=ImageDraw.Draw(im)
d.text((50,30),"WILLIE SIMS ANNOUNCEMENT · EDIT MAP",font=f(46),fill=BONE)
d.text((50,92),"Source: IMG_4336.mov (55.8 s, 1080x1920) → two vertical promos · captions burned · end card from Billo Motion · loudness -14 LUFS",font=f(18,True),fill=DIM)
X0,X1=230,1740; sc=(X1-X0)/30.0
def tx(t): return X0+t*sc
y=150
for name,p in PROMOS.items():
    body=sum(b-a for a,b in p['segs']); total=body+4.0
    d.text((50,y),('A · JIVE TURKEYS 5 PM' if name.startswith('A') else 'B · BEAST AFTER THE FEAST'),font=f(30),fill=GOLD)
    d.text((50,y+40),f"{total:.1f} s total",font=f(16,True),fill=DIM)
    for s in range(0,31,2):
        d.line([(tx(s),y+70),(tx(s),y+76)],fill=DIM);d.text((tx(s)-6,y+78),str(s),font=f(13,True),fill=DIM)
    rows=[('V2 CUTAWAY',y+110),('V1 TAPE',y+170),('CAPTIONS',y+230),('A1 VOICE',y+275)]
    for lab,yy in rows: d.text((50,yy+8),lab,font=f(15,True),fill=DIM)
    # V1 segments
    o=0
    for a,b in p['segs']:
        d.rectangle([tx(o),y+170,tx(o+b-a)-2,y+215],fill=(60,60,70),outline=BONE)
        d.text((tx(o)+6,y+176),f"src {a:.2f}–{b:.2f}",font=f(14,True),fill=BONE)
        d.text((tx(o)+6,y+195),"cut" if o>0 else "in",font=f(12,True),fill=TEAL)
        d.rectangle([tx(o),y+275,tx(o+b-a)-2,y+305],fill=(30,70,60)); o+=b-a
        if o<body: d.line([(tx(o),y+105),(tx(o),y+310)],fill=RED,width=3)
    d.rectangle([tx(body),y+170,tx(total),y+215],fill=GOLD);d.text((tx(body)+6,y+182),"END CARD",font=f(16),fill=INK)
    for c in p.get('cut',[]):
        d.rectangle([tx(c[2]),y+110,tx(c[3])-2,y+155],fill=(110,40,40),outline=GOLD)
        d.text((tx(c[2])+5,y+116),c[4][:22],font=f(12,True),fill=BONE)
    ass=open(f'promos/{name}.ass').read()
    for m in re.finditer(r"Dialogue: 0,0:00:(\d+\.\d+),0:00:(\d+\.\d+),Cap",ass):
        a,b=float(m[1]),float(m[2]); d.rectangle([tx(a),y+232,tx(b)-1,y+258],fill=(80,80,40))
    y+=440
d.text((50,H-60),"Red line = jump cut (dead air removed) · gold = Billo Motion end card · captions: Anton, 3–4 words per beat · DSF/Mo City cutaways over the voice",font=f(16,True),fill=DIM)
im.save('promos/WILLIE_SIMS_EDIT_MAP.png');print('ok')
