"""Willie Sims announcement -> two ~28s vertical promos (real footage, captions, end card)."""
import json, subprocess, os
U='/mnt/user-data/uploads/'
SRC=U+'IMG_4336.mov'
W=json.load(open('transcript.json'))
words=[(w[0],w[1],w[2].strip()) for s in W for w in s['w']]
FIX={'Show':"Show's",'us':None}
def ass_time(t):
    h=int(t//3600);m=int(t%3600//60);s=t%60
    return f"{h}:{m:02d}:{s:05.2f}"
WK1=U+'quick_edit_dsf_week_1_shot_by__gladihadmycamera.mov'
PROMOS={
 'A_jive_turkeys_5pm':dict(segs=[(0.55,21.75),(24.35,27.15)],card='/home/claude/motion/out/jive-turkeys-21/jive-turkeys-21_story_motion_1080x1920.mp4',
     tag='SPECIAL ANNOUNCEMENT',
     cut=[('img','/home/claude/motion/assets/rt-band.jpg',4.4,8.75,'Bad Turkeys render: the band'),
          ('vid',WK1,10.25,12.45,'DSF wk1 crowd @11.0s',11.0)]),
 'B_beast_after_the_feast':dict(segs=[(27.2,41.85),(43.3,52.85)],card='/home/claude/motion/out/beast-after-the-feast-2026/beast-after-the-feast-2026_story_motion_1080x1920.mp4',
     tag='THURSDAY NIGHT',
     cut=[('img',U+'16dd6523-image.jpg',4.9,8.0,'DSF trio photo'),
          ('img',U+'f1e049d3-image.jpg',8.0,12.7,'DSF cast photo'),
          ('img','/home/claude/refs/mocity/MOCITY_exterior_sign_night.jpg',14.75,17.45,'Mo City sign, night'),
          ('vid',WK1,20.8,22.55,'DSF wk1 stage @19.0s',19.0)]),
}
CARD_IN,CARD_LEN=3.5,4.0
def build(name,p):
    # map words into the cut timeline
    out_t=0;chunks=[];cur=[]
    for a,b in p['segs']:
        for (ws,we,txt) in words:
            if ws>=a-0.05 and we<=b+0.05:
                if txt=='us' and cur and cur[-1][2]=='Show': cur[-1]=(cur[-1][0],we-a+out_t,"Show's"); continue
                if txt.lower().strip(',.') in ('uh',): continue
                if txt.startswith("'") and cur: cur[-1]=(cur[-1][0],we-a+out_t,cur[-1][2]+txt); continue
                if txt in ('.m.','.M.') and cur: cur[-1]=(cur[-1][0],we-a+out_t,cur[-1][2]+'M'); continue
                if txt=='o' : txt="O"
                cur.append((ws-a+out_t,we-a+out_t,txt))
                if len(cur)>=4 or (txt[-1] in '.?!' and len(cur)>=2) or (txt[-1]==',' and len(cur)>=3):
                    chunks.append(cur);cur=[]
        if cur: chunks.append(cur);cur=[]
        out_t+=b-a
    body=out_t
    ev=[]
    for i,c in enumerate(chunks):
        s=c[0][0]; e=max(c[-1][1]+0.6, s+0.8)
        if i+1<len(chunks): e=min(e,chunks[i+1][0][0])
        e=min(e,body)
        t=' '.join(x[2] for x in c).upper().replace("5 O 'CLOCK","5 O'CLOCK").replace("5 O'CLOCK","5 O'CLOCK").replace(" -","-").replace("P.M","P.M.")
        ev.append(f"Dialogue: 0,{ass_time(s)},{ass_time(e)},Cap,,0,0,0,,{t}")
    ass=f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,Anton,108,&H00F4F2EC,&H000000FF,&H000A0A0B,&H96000000,0,0,0,0,100,100,1,0,1,6,3,2,80,80,560,1
Style: Tag,Anton,54,&H0037AFD4,&H000000FF,&H000A0A0B,&H00000000,0,0,0,0,100,100,6,0,1,3,0,8,60,60,120,1
Style: Name,Anton,96,&H00F4F2EC,&H000000FF,&H000A0A0B,&H00000000,0,0,0,0,100,100,4,0,1,4,2,8,60,60,185,1
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 1,{ass_time(0)},{ass_time(min(5,body))},Tag,,0,0,0,,{{\\fad(250,300)}}{p['tag']}
Dialogue: 1,{ass_time(0)},{ass_time(min(5,body))},Name,,0,0,0,,{{\\fad(250,300)}}WILLIE SIMS
""" + '\n'.join(ev)+'\n'
    open(f'promos/{name}.ass','w').write(ass)
    # filtergraph: trim segments + concat body, burn captions, append card
    fc=[];n=len(p['segs'])
    for i,(a,b) in enumerate(p['segs']):
        d=b-a
        fc.append(f"[0:v]trim={a}:{b},setpts=PTS-STARTPTS,scale=1080:1920,fps=30,format=yuv420p[v{i}]")
        fc.append(f"[0:a:0]atrim={a}:{b},asetpts=PTS-STARTPTS,afade=t=in:d=0.04,afade=t=out:st={d-0.06:.3f}:d=0.06[a{i}]")
    fc.append(''.join(f"[v{i}][a{i}]" for i in range(n))+f"concat=n={n}:v=1:a=1[bv][ba]")
    fc.append(f"[bv]ass=promos/{name}.ass,fade=t=out:st={body-0.3:.2f}:d=0.3[bvc]")
    fc.append(f"[1:v]trim={CARD_IN}:{CARD_IN+CARD_LEN},setpts=PTS-STARTPTS,scale=1080:1920,fps=30,format=yuv420p,fade=t=in:d=0.3[cv]")
    fc.append(f"anullsrc=r=48000:cl=stereo,atrim=0:{CARD_LEN}[ca]")
    fc.append("[ba]aformat=sample_rates=48000:channel_layouts=stereo,afade=t=out:st=%.2f:d=0.35[bao]"%(body-0.35))
    fc.append("[bvc][bao][cv][ca]concat=n=2:v=1:a=1[v][a0]")
    fc.append("[a0]loudnorm=I=-14:TP=-1.5:LRA=11[a]")
    tmp=f'promos/.{name}.tmp.mp4'
    extra=[];k0=2
    for j,cw in enumerate(p.get('cut',[])):
        kind,src,a,b=cw[0],cw[1],cw[2],cw[3];d=b-a;n_=k0+j
        if kind=='img': extra+=['-loop','1','-t',f'{d:.2f}','-i',src]
        else: extra+=['-ss',f'{cw[5]:.2f}','-t',f'{d:.2f}','-i',src]
        z=f"scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=30:3,eq=brightness=-0.12[bg{j}];[ct{j}]scale=1080:-2,zoompan=z='min(1+0.0009*on,1.12)':d=1:s=1080x{{H}}:fps=30[fg{j}];[bg{j}][fg{j}]overlay=(W-w)/2:(H-h)/2-120"
        # pre-size fg height from the source aspect
        import subprocess as sp
        wh=sp.run(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=width,height','-of','csv=p=0',src],capture_output=True,text=True).stdout.split(',')
        H=int(round(1080*int(wh[1])/int(wh[0])/2)*2)
        fc.append(f"[{n_}:v]fps=30,format=yuv420p,split[cb{j}][ct{j}];[cb{j}]"+z.replace('{H}',str(H))+f",format=yuv420p,setpts=PTS-STARTPTS+{a}/TB,fade=t=in:st={a}:d=0.12:alpha=0[cv{j}]")
    cur='bv'
    for j,cw in enumerate(p.get('cut',[])):
        fc.append(f"[{cur}][cv{j}]overlay=0:0:eof_action=pass:enable='between(t,{cw[2]},{cw[3]})'[ov{j}]");cur=f'ov{j}'
    fc[[i for i,x in enumerate(fc) if x.startswith('[bv]ass=')][0]]=fc[[i for i,x in enumerate(fc) if x.startswith('[bv]ass=')][0]].replace('[bv]ass=',f'[{cur}]ass=',1)
    cmd=['ffmpeg','-v','error','-y','-i',SRC,'-i',p['card'],*extra,'-filter_complex',';'.join(fc),'-map','[v]','-map','[a]',
         '-c:v','libx264','-preset','veryfast','-crf','18','-pix_fmt','yuv420p','-c:a','aac','-b:a','192k','-ar','48000','-movflags','+faststart',tmp]
    subprocess.run(cmd,check=True); os.rename(tmp,f'promos/WILLIE_SIMS_{name}.mp4')
    print(name, round(body+CARD_LEN,2),'s')
for k,v in PROMOS.items(): build(k,v)
