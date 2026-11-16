import sys, json, numpy as np, soundfile as sf
from scipy import signal, ndimage
p=sys.argv[1]; info=sf.info(p); sr=info.samplerate
x,_=sf.read(p,dtype='float32',frames=int(110*sr)); m=x.mean(1); del x
y=signal.resample_poly(m,1,4).astype(np.float32); fs=sr/4; hop=32; N=512   # fps ~344
win=np.hanning(N).astype(np.float32); nfr=(len(y)-N)//hop; full=np.zeros(nfr,np.float32); prev=None
for a in range(0,nfr,4000):
    b=min(nfr,a+4000); idx=(np.arange(a,b)*hop)[:,None]+np.arange(N)[None,:]
    M=np.log1p(30*np.abs(np.fft.rfft(y[idx]*win,axis=1))).astype(np.float32)
    d=np.diff(np.vstack([prev,M]) if prev is not None else np.vstack([M[:1],M]),axis=0); full[a:b]=np.maximum(d,0).sum(1); prev=M[-1:]; del M,idx,d
fps=fs/hop
sos=signal.butter(4,110,'lowpass',fs=fs,output='sos'); le=np.abs(signal.sosfilt(sos,y)); le=le[:nfr*hop].reshape(nfr,hop).mean(1); lo=np.maximum(np.diff(le,prepend=le[0]),0)
full=np.maximum(full-ndimage.uniform_filter1d(full,int(fps)),0)
best=(0,0,0)
for bpm in np.arange(74,96,0.04):
    per=60*fps/bpm
    for ph in np.linspace(0,per,32,endpoint=False):
        i1=np.round(np.arange(ph,nfr-1,per)).astype(int); i2=np.round(np.arange(ph+per/2,nfr-1,per)).astype(int); i4=np.round(np.arange(ph+per/4,nfr-1,per/2)).astype(int)
        s=full[i1].mean()+0.6*full[i2].mean()+0.3*full[i4].mean()
        if s>best[0]: best=(s,bpm,ph)
_,bpm,ph=best; per=60*fps/bpm
ph=max(np.linspace(ph-per/32,ph+per/32,65),key=lambda q: full[np.clip(np.round(np.arange(q%per,nfr-1,per)).astype(int),0,nfr-1)].mean())%per
beats=np.arange(ph,nfr-1,per); sc=[float(lo[np.round(beats[k::4]).astype(int)].mean()) for k in range(4)]; k=int(np.argmax(sc)); t0=float(beats[k]/fps); bar=240/bpm
dur=info.frames/sr; n=int((dur-t0)/bar); rms=[];low=[]
with sf.SoundFile(p) as f:
    for b in range(n):
        f.seek(int((t0+b*bar)*sr)); s=f.read(int(bar*sr),dtype='float32').mean(1); rms.append(float(np.sqrt((s**2).mean()))); l=signal.sosfilt(signal.butter(4,110,'lowpass',fs=sr,output='sos'),s); low.append(float(np.sqrt((l**2).mean())))
out={'bpm':round(float(bpm),2),'t0':round(t0,4),'bars':n,'down':[round(s/max(sc),2) for s in sc],'rms':[round(r/max(rms),2) for r in rms],'low':[round(l/max(low),2) for l in low]}
json.dump(out,open(p.replace('.wav','_grid.json'),'w')); print(json.dumps(out))
