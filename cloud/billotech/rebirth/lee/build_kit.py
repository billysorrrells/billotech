import json, numpy as np, soundfile as sf, os
from scipy import signal
import pyloudnorm as pyln
SR=44100; os.makedirs('out/kit',exist_ok=True)
G=json.load(open('src/gt_grid.json')); K=json.load(open('src/k3_grid.json'))
gt,_=sf.read('src/gt.wav',dtype='float32'); BAR=240/G['bpm']; BL=int(round(BAR*SR)); BEAT=BL//4
def bar(b,n=1):
    a=int(round((G['t0']+b*BAR)*SR)); return gt[a:a+BL*n].copy()
def fade(x,ms=4):
    n=int(ms*SR/1000); x=x.copy(); r=np.linspace(0,1,n,dtype=np.float32)[:,None]; x[:n]*=r; x[-n:]*=r[::-1]; return x
def fit(x,n=None):
    n=n or BL; return x[:n] if len(x)>=n else np.vstack([x,np.zeros((n-len(x),2),np.float32)])
def stutter(x):  # beat1,beat1,half-beats of 1, then beats 3-4
    b1=fade(x[:BEAT]); h=fade(x[:BEAT//2]); return fit(np.vstack([b1,h,h,fade(x[2*BEAT:])]))
def chop(x,order):
    return fit(np.vstack([fade(x[i*BEAT:(i+1)*BEAT]) for i in order]))
def hp(x,fc): return signal.sosfilt(signal.butter(2,fc,'highpass',fs=SR,output='sos'),x,axis=0).astype(np.float32)
def lp(x,fc): return signal.sosfilt(signal.butter(2,fc,'lowpass',fs=SR,output='sos'),x,axis=0).astype(np.float32)
# ---- one-shots from 3 Kings breakdown (bass out) and from Get Throwed
k3,_=sf.read('src/k3.wav',dtype='float32',start=int((K['t0']+4*240/K['bpm'])*SR),frames=int(3*240/K['bpm']*SR))
def hits(x,band,n,length,gap=0.2):
    m=x.mean(1); y=signal.sosfilt(signal.butter(4,band,'bandpass' if isinstance(band,list) else 'lowpass',fs=SR,output='sos'),m)
    e=np.abs(y); e=signal.sosfilt(signal.butter(1,40,'lowpass',fs=SR,output='sos'),e); d=np.maximum(np.diff(e,prepend=0),0)
    pk,pr=signal.find_peaks(d,distance=int(gap*SR),height=d.max()*0.35); order=np.argsort(-pr['peak_heights'])[:n]; out=[]
    for i in sorted(pk[order]):
        a=max(0,i-int(0.006*SR)); s=x[a:a+int(length*SR)].copy(); s*=np.linspace(1,0,len(s),dtype=np.float32)[:,None]**1.5; out.append(s/ (np.abs(s).max()+1e-9)*0.9)
    return out
kit={}
kit['k3_kick']=hits(k3,90,3,0.28); kit['k3_snare']=[hp(s,180) for s in hits(k3,[180,4000],3,0.25)]; kit['k3_hat']=[hp(s,6000) for s in hits(k3,[7000,15000],3,0.07,0.08)]
g8=bar(6,4); kit['gt_kick']=hits(g8,90,3,0.3); kit['gt_snare']=[hp(s,160) for s in hits(g8,[200,5000],3,0.26)]; kit['gt_hat']=[hp(s,6000) for s in hits(g8,[7000,15000],3,0.07,0.08)]
for k,v in kit.items():
    for i,s in enumerate(v): sf.write(f'out/kit/{k}_{i+1}.wav',s,SR,subtype='PCM_16')
gi=bar(0,4); sf.write('out/kit/gt_guitar_intro_4bars.wav',gi,SR,subtype='PCM_16'); sf.write('out/kit/gt_groove_4bars.wav',bar(6,4),SR,subtype='PCM_16')
def layer(x,name,steps,gain=0.5,idx=0):
    v=kit.get(name) or []; 
    if not v: return x
    s=v[idx%len(v)]
    for st in steps:
        a=int(st*BEAT/4); e=min(len(x),a+len(s)); x[a:e]+=s[:e-a]*gain
    return x
# ---- arrangement
out=[]; marks=[]
def add(name,segs): marks.append((name,sum(len(o) for o in out)/SR)); out.extend(segs)
add('intro',[fade(bar(b)) for b in (0,1,2,3)])
hook=[fade(bar(b)) for b in range(6,14)]
add('hook',[layer(h.copy(),'k3_hat',[14,14.5,15,15.5],0.35) if i%2 else h for i,h in enumerate(hook)])
v1=[]
for i,b in enumerate(range(14,30)):
    x=fade(bar(b))
    if i%8==3: x=stutter(x)
    if i%8==7: x=chop(x,[0,1,0,3]); x=layer(x,'k3_snare',[12,13,14,14.5,15,15.5],0.5)
    if i==8: x=hp(x,300)*0.9
    v1.append(x)
add('verse 1',v1)
add('hook',[layer(h.copy(),'k3_snare',[4,12],0.35,1) for h in hook])
br=[]
for i,b in enumerate((0,1,2,3)):
    x=lp(fade(bar(b)),2500) if i<2 else fade(bar(b)); x=layer(x,'gt_kick',[0,6,10],0.7); x=layer(x,'k3_snare',[4,12],0.55); x=layer(x,'k3_hat',list(range(0,16,2))+([12.5,13.5,14.5,15.5] if i%2 else []),0.3); br.append(x)
add('bridge: guitar + rebuilt drums',br)
v2=[]
for i,b in enumerate(range(30,38)):
    x=fade(bar(b))
    if i%4==3: x=chop(x,[0,0,2,3]) if i==3 else stutter(x)
    v2.append(x)
add('verse 2',v2)
add('hook',[layer(h.copy(),'k3_hat',[12,12.5,13,13.5,14,14.5,15,15.5],0.3) if i%4==3 else h for i,h in enumerate(hook)])
body=np.vstack(out)
def screw(seg,r0,r1):
    rate=np.linspace(r0,r1,len(seg)); pos=np.cumsum(rate); pos=pos[pos<len(seg)-2]; i0=pos.astype(int); fr=(pos-i0)[:,None].astype(np.float32); return seg[i0]*(1-fr)+seg[i0+1]*fr
tail=screw(np.vstack(hook[:4]),0.86,0.6); tail*=np.linspace(1,0,len(tail),dtype=np.float32)[:,None]**0.7
marks.append(('screwed outro',len(body)/SR))
def master(x,target=-9.5):
    x=signal.sosfilt(signal.butter(2,28,'highpass',fs=SR,output='sos'),x,axis=0).astype(np.float32); mt=pyln.Meter(SR)
    for _ in range(3):
        l=mt.integrated_loudness(x[:SR*60].astype(np.float64)); x=x*10**((target-l)/20); x=np.tanh(x*1.1)/np.tanh(1.1)*0.89
    return x.astype(np.float32)
A=master(np.vstack([body,tail])); sf.write('out/stay_throwed_LEE_A_chop.wav',A,SR,subtype='PCM_16')
B=screw(np.vstack([body,tail]),0.88,0.88); 
# extra chops for the screwed version: repeat last half-beat before each section
B=master(B.astype(np.float32)); sf.write('out/stay_throwed_LEE_B_screwed.wav',B,SR,subtype='PCM_16')
info={'A':{'bpm':G['bpm'],'seconds':round(len(A)/SR,1),'marks':[(n,round(t,1)) for n,t in marks]},'B':{'bpm':round(G['bpm']*0.88,2),'seconds':round(len(B)/SR,1),'pitch_semitones':round(12*np.log2(0.88),2)},'kit':{k:len(v) for k,v in kit.items()}}
json.dump(info,open('out/info.json','w')); print(json.dumps(info))
