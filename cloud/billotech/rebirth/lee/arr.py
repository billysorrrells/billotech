import json, glob, numpy as np, soundfile as sf
from scipy import signal
SR=44100; G=json.load(open('src/gt_grid.json')); BAR=240/G['bpm']; BL=int(round(BAR*SR)); BEAT=BL//4
src=sf.SoundFile('src/gt.wav')
def bar(b):
    src.seek(int(round((G['t0']+b*BAR)*SR))); x=src.read(BL,dtype='float32'); 
    return x if len(x)==BL else np.vstack([x,np.zeros((BL-len(x),2),np.float32)])
def fade(x,ms=4):
    n=int(ms*SR/1000); r=np.linspace(0,1,n,dtype=np.float32)[:,None]; x[:n]*=r; x[-n:]*=r[::-1]; return x
def fit(x): return x[:BL] if len(x)>=BL else np.vstack([x,np.zeros((BL-len(x),2),np.float32)])
def stutter(x): b1=fade(x[:BEAT].copy()); h=fade(x[:BEAT//2].copy()); return fit(np.vstack([b1,h,h,fade(x[2*BEAT:].copy())]))
def chop(x,order): return fit(np.vstack([fade(x[i*BEAT:(i+1)*BEAT].copy()) for i in order]))
def filt(x,fc,kind): return signal.sosfilt(signal.butter(2,fc,kind,fs=SR,output='sos'),x,axis=0).astype(np.float32)
kit={}
for p in sorted(glob.glob('out/kit/*_[123].wav')):
    k=p.split('/')[-1].rsplit('_',1)[0]; s,_=sf.read(p,dtype='float32',always_2d=True); kit.setdefault(k,[]).append(s if s.shape[1]==2 else np.repeat(s,2,1))
def layer(x,name,steps,gain=0.5,idx=0):
    s=kit[name][idx%len(kit[name])]
    for st in steps:
        a=int(st*BEAT/4); e=min(len(x),a+len(s)); x[a:e]+=s[:e-a]*gain
    return x
out=sf.SoundFile('out/A.wav','w',SR,2,'PCM_16'); marks=[]; pos=0
def put(x):
    global pos; out.write(np.tanh(x*1.05)*0.92); pos+=len(x)
def mark(n): marks.append((n,round(pos/SR,1)))
H=list(range(6,14))
def hook(var):
    for i,b in enumerate(H):
        x=fade(bar(b))
        if var==0 and i%2: layer(x,'k3_hat',[14,14.5,15,15.5],0.35)
        if var==1: layer(x,'k3_snare',[4,12],0.35,1)
        if var==2 and i%4==3: layer(x,'k3_hat',[12,12.5,13,13.5,14,14.5,15,15.5],0.3)
        put(x)
mark('intro: your guitar'); [put(fade(bar(b))) for b in (0,1,2,3)]
mark('hook'); hook(0)
mark('verse 1')
for i,b in enumerate(range(14,30)):
    x=fade(bar(b))
    if i%8==3: x=stutter(x)
    if i%8==7: x=layer(chop(x,[0,1,0,3]),'k3_snare',[12,13,14,14.5,15,15.5],0.5)
    if i==8: x=filt(x,300,'highpass')*0.9
    put(x)
mark('hook'); hook(1)
mark('bridge: your guitar + your drum hits re-played')
for i,b in enumerate((0,1,2,3)):
    x=fade(bar(b)); x=filt(x,2500,'lowpass') if i<2 else x
    layer(x,'gt_kick',[0,6,10],0.7); layer(x,'k3_snare',[4,12],0.55); layer(x,'k3_hat',list(range(0,16,2))+([12.5,13.5,14.5,15.5] if i%2 else []),0.3); put(x)
mark('verse 2')
for i,b in enumerate(range(30,38)):
    x=fade(bar(b)); x=chop(x,[0,0,2,3]) if i==3 else (stutter(x) if i==7 else x); put(x)
mark('hook'); hook(2)
mark('screwed outro')
seg=np.vstack([bar(b) for b in H[:4]]); rate=np.linspace(0.86,0.6,len(seg)); p=np.cumsum(rate); p=p[p<len(seg)-2]; i0=p.astype(int); fr=(p-i0)[:,None].astype(np.float32)
t=seg[i0]*(1-fr)+seg[i0+1]*fr; t*=np.linspace(1,0,len(t),dtype=np.float32)[:,None]**0.7; put(t); out.close()
json.dump({'bpm':G['bpm'],'seconds':round(pos/SR,1),'marks':marks},open('out/info.json','w')); print(marks,round(pos/SR,1))
