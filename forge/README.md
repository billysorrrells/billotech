# Billo FX Forge

Procedural effects, grades and cut rhythm for Billo OS. Built 9 Nov 2026 by mining the effects wall (`bay.fx_asset`, 1,466 assets) and the reference wall (`public.agent_video_wall`, 31 reels) for **technique only**, then rebuilding each technique from scratch in numpy + ffmpeg.

Nothing from a pack, preset, crack share or creator reel is copied or bundled, so everything the Forge renders belongs to Billy and can ship.

## One file, six commands

```bash
python3 -I billo_fx.py gen leak -o leak.mp4 --dur 3 --palette amber      # standalone overlay (add --alpha for ProRes 4444)
python3 -I billo_fx.py fx glitch -i in.mp4 -o out.mp4 --at 1.2,3.4      # effect on footage at hit times
python3 -I billo_fx.py fx flash -i in.mp4 -o out.mp4 --hits promo_sfx.cues.json   # same frames as Billo Sound FX
python3 -I billo_fx.py lut --look teal-warm -o teal.cube                 # named look
python3 -I billo_fx.py lut --ref still.jpg --src frame.jpg -o match.cube # match a reference still
python3 -I billo_fx.py grade -i in.mp4 --cube teal.cube -o graded.mp4
python3 -I billo_fx.py cadence --audio song.wav --clips a.mp4 b.mp4 --recipe burst_hold -o cut/promo --preview
python3 -I billo_fx.py sheet -i out.mp4 -o out.png                        # contact sheet for the Render Wall
```

Needs Python 3, numpy, Pillow, ffmpeg.

## Effects (what they were mined from)

| Effect | Rebuilt from | How it works |
|---|---|---|
| `glitch` | Glitch_Maps, Glitch, Glitches folders (493) | RGB split, displaced bands, crushed colour block, scanlines; window envelope across each hit |
| `vhs` | VHS / CRT overlays | chroma bleed, line wobble, rolling tracking band, head-switch noise |
| `leak` | light-leak folders (217) | moving soft colour blobs, screen blend, flicker; palettes amber / magenta / teal |
| `burn` | Film Burn folder | animated fractal noise, burning front with orange edge and white-hot core |
| `grain` | Grain, scratches, Media, lens_dirt | luminance-weighted grain, dust specks, persistent scratches, gate weave, vignette flicker |
| `flash` / `strobe` | 11.Flash FX, stingers | white flash with decay; alternating strobe |
| `shake` / `punch` | impact packs; reference wall "1.3x punch-in on the next kick" | crop-zoom with decay, random offset for shake |
| `gradient` | 07.Gradients (23); reference wall LED-wall loops | seamless looping gradient field |
| `bwsnap` | reference wall "B&W for the past, colour snaps back" | B&W until the first hit, colour in 2 frames |

## Looks (`lut --look`)

`teal-warm` · `golden-amber` · `low-sat-bright` · `warm-red` · `neutral-teal-accent` · `bw-contrast` · `practical-warm`. Each is written as maths into a 33-point `.cube` that loads in Resolve, Premiere, Billo Cut, OBS and ffmpeg (`lut3d`).

## Cadence recipes

| Recipe | Rule (from the reference wall) |
|---|---|
| `burst_hold` | runs of 3-frame shots (12-15) on the drop, then a 130-frame hold; the next burst lands on a beat |
| `pattern3` | the same 3-cut figure every bar; the third shot holds to the bar line |
| `kick_cut` | cut on the kick / sub-hit (20-150 Hz onsets), never shorter than 6 frames |
| `slow_locked` | one cut per bar, closing on a 207-frame hero hold |

Tempo and kicks are detected from the song itself. Output: `.json` plan, CMX3600 `.edl` for any NLE, optional 540x960 preview with the song.

## House rules in the code

- Previews render at 540x960. Anything 1080 or larger refuses unless you pass `--final` (lock references first).
- Same `--seed` gives the same pixels, so every Render Wall post can be re-made exactly.
- The source file is never overwritten; audio is carried through.

## Tested 9 Nov 2026

All 11 effects, 7 looks plus the match LUT, `grade`, all 4 cadence recipes (tempo read as 120.04 on a 120 BPM test track) and `sheet` ran clean on synthetic test media. The 1080 guard refused as designed.

Map of every product this opens: `../billotech-map/billotech_map.json`.
