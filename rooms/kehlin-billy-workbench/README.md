# Kehlin × Billy room (kehlin-billy-workbench.netlify.app) · 19 Nov 2026 update

- **Mix Session (Sipping):** every stem has fader, pan, M/S and switches for low cut, EQ, compressor, de-ess, plate and delay; bus glue + limiter.
  Every move is a saved step: Undo / Redo (⌘Z / ⇧⌘Z), jump to any step from the history list, Reset adds a step (nothing lost), Bounce WAV renders the mix in the browser.
- **3D Shot Board:** Whip Ep 101 is the full scene now (16 shots, 84 s, every line of Kehlin's script). Shots are editable (length, lens, dialogue, sound, make; move, duplicate, add, delete) with the same saved undo history. Project chips: Whip, Black Friday, Armageddon, One Night At… (no pass yet → blocked one shot per beat from the script room).
- **Workflow strip** on every project in the room: Script → Mix → 3D → Site → Wall.
- **Saving:** `room-work.js` → RPCs `room_work_open/commit/move` (sql/2026-11-19_room_work_sessions.sql). Until that migration is applied, steps are kept on the device and pushed to the binder on the next signed-in open.
- Audio (`mix/`, `mix/stems/`) is NOT in this public repo; it is on the live site and in Billy's Dropbox.
