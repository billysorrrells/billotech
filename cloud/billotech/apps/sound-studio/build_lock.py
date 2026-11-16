"""Billo Sound Studio · version lock. Writes VERSION.lock.json (SHA-256 of every shipped file)
and refuses to run if a locked file changed under the same version (bump VERSION in index.html first)."""
import hashlib, json, os, re, sys
root=os.path.dirname(os.path.abspath(__file__)); os.chdir(root)
ver=re.search(r'const VERSION="([^"]+)"',open('index.html').read()).group(1)
files=['index.html','demo.json']+sorted('audio/'+f for f in os.listdir('audio'))
lock={'product':'Billo Sound Studio','version':ver,'path':'/billotech/apps/sound-studio/','files':{f:{'sha256':hashlib.sha256(open(f,'rb').read()).hexdigest(),'bytes':os.path.getsize(f)} for f in files}}
if os.path.exists('VERSION.lock.json'):
    old=json.load(open('VERSION.lock.json'))
    if old['version']==ver and old['files']!=lock['files']:
        sys.exit(f"Refused: files changed but version is still {ver}. Bump VERSION in index.html and add a CHANGES entry.")
json.dump(lock,open('VERSION.lock.json','w'),indent=1); print('locked',ver,len(files),'files')
