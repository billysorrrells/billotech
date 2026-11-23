"""Insert the Billo Show Desk card into the LIVE /billotech/index.html (fetched fresh),
right after the Billo Direct card. Additive only: nothing else in the page changes."""
import sys, urllib.request
out = sys.argv[1]
html = urllib.request.urlopen('https://billysorrells.com/billotech/', timeout=60).read().decode()
if '/billotech/apps/showdesk/' in html: print('card already present'); open(out,'w').write(html); sys.exit()
card = ('<a class="bt-app has-shot" href="/billotech/apps/showdesk/"><img class="bx-shot" src="/billotech/apps/showdesk/img/billo-showdesk-shot.webp" alt="" loading="lazy" width="640" height="400">'
        '<span class="g v">Sd</span><span><span class="h"><b>Billo Show Desk</b><span class="bt-pill bt-pill--live">Live</span></span>'
        '<span class="rp">Replaces Canva flyers + Claude Motion</span><p>Every show in one place: postable banners in six sizes, motion cards and captions, '
        'built on Billo Motion, our own code-built motion engine. Pulls the shows from Billo OS.</p><span class="go">Open →</span></span></a>')
anchor = 'href="/billotech/apps/direct/">'
i = html.find(anchor)
assert i > 0, 'Billo Direct card not found'
end = html.find('</a>', i) + 4
html = html[:end] + card + html[end:]
open(out, 'w').write(html); print('card inserted after Billo Direct')
