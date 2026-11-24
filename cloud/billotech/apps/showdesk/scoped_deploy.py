#!/usr/bin/env python3
"""Scoped deploy for billysorrells.com: publish ONLY the paths given, on top of the
CURRENT live deploy's full manifest (fetched fresh, never the stale local one).
Nothing else on the live site changes. Prints the rollback id.
usage: python3 scoped_deploy.py <site_dir> <prefix> [<prefix> ...] [--dry-run]
  e.g. python3 scoped_deploy.py ~/billotech-source/site /billotech/apps/showdesk/ /billotech/index.html
"""
import sys, os, json, time, hashlib, urllib.parse
sys.path.insert(0, os.path.expanduser('~/billotech-source'))
import deploy as D   # reuses token() and api() from the existing safe deploy script

def sha1(p):
    h = hashlib.sha1(); h.update(open(p, 'rb').read()); return h.hexdigest()

def live_manifest():
    code, site = D.api('GET', f'/sites/{D.SITE_ID}')
    dep = site['published_deploy']['id']
    files, page = {}, 1
    while True:
        code, res = D.api('GET', f'/deploys/{dep}/files?page={page}&per_page=100')
        if code >= 300: raise SystemExit(f'file list failed on page {page}: {code}')
        if not res: break
        for f in res: files[f['path']] = f['sha']
        page += 1
    return dep, files

def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    dry = '--dry-run' in sys.argv
    site_dir, prefixes = os.path.expanduser(args[0]), args[1:]
    live_id, files = live_manifest()
    print(f'live deploy {live_id}: {len(files)} files')
    if len(files) < 1400: raise SystemExit(f'SAFETY STOP: live manifest has only {len(files)} files; refusing to deploy')
    mine = {}
    for root, _, names in os.walk(site_dir):
        for n in names:
            full = os.path.join(root, n)
            rel = '/' + os.path.relpath(full, site_dir).replace(os.sep, '/')
            if any(rel == p or (p.endswith('/') and rel.startswith(p)) for p in prefixes):
                mine[rel] = (sha1(full), full)
    for rel, (s, _) in sorted(mine.items()):
        print(('  ~ ' if rel in files else '  + ') + rel, '' if files.get(rel) != s else '(same)')
    if dry: return
    for rel, (s, _) in mine.items(): files[rel] = s
    code, dep = D.api('POST', f'/sites/{D.SITE_ID}/deploys', {'files': files, 'draft': False, 'async': False})
    if code >= 300: print('CREATE FAILED', code, dep); sys.exit(1)
    by = {s: (rel, full) for rel, (s, full) in mine.items()}
    for s in dep.get('required') or []:
        rel, full = by[s]
        c, _ = D.api('PUT', f"/deploys/{dep['id']}/files{urllib.parse.quote(rel)}", raw=open(full, 'rb').read(), ctype='application/octet-stream')
        print('  upload', c, rel)
    for _ in range(90):
        c, d = D.api('GET', f"/deploys/{dep['id']}")
        if d.get('state') in ('ready', 'current', 'error'): break
        time.sleep(2)
    print('state', d.get('state'), '| deploy', dep['id'], '| rollback: python3 deploy.py --rollback', live_id)

main()
