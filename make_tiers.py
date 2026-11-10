"""BilloTech tier map: every app and tool → Free / Pro / Enterprise. Run: python3 make_tiers.py → tiers.json"""
import json

RULE = {
    "free": "Runs on your own device, or costs BilloTech next to nothing to serve. Always free, full quality, no watermark, no time limit.",
    "pro": "Costs BilloTech money every time you use it: our servers, GPUs, AI models, storage, bandwidth, outgoing email or texts. $8 a month covers it.",
    "enterprise": "Built for a whole organization: seats, admin, sign-in through your school or company, data agreements, private hosting, support. Priced per organization. Donated to schools.",
}

# (id, name, group, status, free, pro, enterprise)
A = [
 # ---- Page ----
 ("draft", "Billo Draft", "Write & plan", "Live", "Full screenplay editor, FDX + Fountain in and out, PDF export, save to device or Drive", "Live co-writing with other people, version history in the cloud", "Writers' room seats, studio templates, locked drafts and watermarked PDFs for distribution"),
 ("analysis", "Script Analysis", "Write & plan", "Live", "Breakdown, cast tiers, stripboard, shoot days, coverage sheet", "AI coverage notes written by a model on our servers", "Slate-wide analytics across every script the company owns"),
 ("budget", "Billo Budget", "Write & plan", "Live", "Top sheet, fringes, every template, PDF export", "Cloud sync + shared budgets with your producer", "Union rate tables kept current, approvals, cost reports for financiers"),
 ("director", "Billo Director", "Write & plan", "Live", "Shot plan, crew list, locations, call sheets on your device", "Location photos turned into 3D on our GPUs, auto transcripts of meetings", "Production company workspace: every show, every crew, one admin"),
 ("plot", "Billo Plot", "Write & plan", "Live", "Ground plan + 3D through-the-lens view, gear library", "Shared plots your crew can open on set", "Venue and studio libraries for the whole company"),
 ("binder", "Billo Binder", "Write & plan", "Live", "Script room, coverage, stripboard, call sheets for your own projects", "Cloud binder shared with your cast and crew, payroll exports", "Billo Binder Enterprise: studios, film commissions, HBCU programs, SSO, audit trail"),
 # ---- Image ----
 ("photo", "Billo Photo", "Image", "Preview", "Layers, masks, type, real PSD open and save", "Generative fill and background removal on our GPUs", "Shared brand libraries and asset approvals"),
 ("light", "Billo Light", "Image", "Early", "Develop and library for whole shoots on your device", "Cloud catalog that syncs between laptop and phone", "Team catalogs with client proofing"),
 ("vector", "Billo Vector", "Image", "Early", "Logos, wordmarks, cut-ready outlines", "Image-to-vector on our servers", "Brand kits locked across the org"),
 ("layout", "Billo Layout", "Image", "Early", "Programs, one-sheets, sponsor kits, print PDF", "Print-ready preflight + ordering through BilloTech print partners", "Templates locked to the brand, approvals"),
 ("drawworks", "Billo DrawWorks", "Image", "Live", "Print-and-cut sticker design, die-cut tracing, RIP-ready PDF", "Hosted batch label jobs and SKU runs", "Shop floor: multiple printers, operators, job queue"),
 # ---- Video & sound ----
 ("forge", "Billo Forge", "Video & sound", "Live", "Every effect, look, recipe and beat cut. Full-resolution export. EDL. Save to device or Drive", "Long renders on our machines, Billo Swarm community render farm, cloud project sync", "Lab-wide Swarm, class templates, brand kit on every export"),
 ("cut", "Billo Cut", "Video & sound", "Preview", "Full NLE, captions, color, keyframes, social presets", "Cloud proxies, server export for long projects", "Shared projects, review links with time-coded notes, seats"),
 ("motion", "Billo Motion", "Video & sound", "Early", "Titles, lower thirds, end cards, animated flyers", "Server rendering for long motion pieces", "Brand-locked title kits for the whole team"),
 ("sound", "Billo Sound", "Video & sound", "Preview", "Dialogue cleanup, beds, podcast mixes, stems on your device", "Stem separation on our GPUs for big files", "Shared sound libraries, loudness specs per network"),
 ("direct", "Billo Direct", "Video & sound", "Live", "Type it, get the film. Kinetic type, counters, lineups. MP4 export", "AI shots generated on paid models (credits included)", "Bulk promo runs for a whole season or tour"),
 ("clip", "Billo Clip", "Video & sound", "Live", "Find the clips, score them, reframe vertical, captions, export", "Batch clipping of long sets on our servers, auto-posting", "Multi-channel clip desk for a network or label"),
 ("voice", "Billo Voice", "Video & sound", "Live", "Text to speech, transcription, dubbing, cloning on your device", "Hosted voices on our GPUs when your machine can't", "Approved voice rosters with talent consent records"),
 ("laugh", "Billo Laugh", "Video & sound", "Live", "Find real laughs, lift them under your voice, stems first", "Batch processing of whole tours", "Network delivery specs and QC reports"),
 ("nle-bridge", "NLE Bridge", "Video & sound", "Live", "Drive Resolve, Final Cut and Premiere from one clip spec", "Hosted render workers", "Post-house pipelines across many editors"),
 ("drumclone", "Billo Drum Clone", "Video & sound", "Live", "Song in, generated kit, groove and pattern out", "Stem separation on our GPUs for long songs", "Label and producer catalogs"),
 ("cadence", "Billo Cadence", "Video & sound", "Live", "Beat-locked cut lists, all recipes, EDL", "Auto-cut on our servers for many songs at once", "Season-wide promo automation"),
 # ---- Live & capture ----
 ("live", "Billo Live", "Live & capture", "Live", "Browser studio, guests, scenes, overlays, local recording, your own relay", "Hosted relay that pushes to every platform at once (bandwidth costs), cloud recordings", "Multi-room broadcast for districts and venues, operator seats"),
 ("audio-hub", "Audio Hub", "Live & capture", "Beta", "Any mic, phone or camera into one stream, live levels, card ingest", "Cloud backup of every card as it ingests", "Venue installs with many rooms"),
 ("cam", "Billo Cam Control", "Live & capture", "Live", "Drive your cameras from the browser", "Remote control from anywhere through our relay", "Multi-camera stages with operators"),
 ("rig", "Billo Rig", "Live & capture", "Live", "3D lighting previs, DMX bridge", "Shared show files with your LD", "Venue fixture libraries and touring rigs"),
 # ---- Sell & run the show ----
 ("the-door", "THE DOOR", "Sell & run the show", "Live", "Event pages, checkout, comps, promo codes, door scanner (card fees only)", "Text and email blasts to buyers, seating charts", "Venue groups: many rooms, settlements, staff roles"),
 ("tix", "Billo Tix", "Sell & run the show", "Live", "Venue-owned box office with PIN sign-in", "Hosted reminders and waitlists", "Multi-venue reporting"),
 ("desk", "Billo Desk", "Sell & run the show", "Live", "Chat widget, shared inbox, help center for one site", "Push alerts, email-in, more seats", "SSO, many brands, routing rules, SLA timers"),
 ("dispatch", "Billo Dispatch", "Sell & run the show", "Live demo", "Live map dispatch for your own crew", "Texts to crew, live tracking at scale", "City and agency deployments"),
 ("outreach", "Billo Outreach", "Sell & run the show", "Live", "Write and plan e-blasts and outreach", "Sending at volume from our servers, warm-up, tracking", "Team sequences, compliance, shared lists"),
 ("iq", "Billo IQ", "Sell & run the show", "Live", "Channel growth and intel from public data", "Daily tracking runs on our servers", "Network-wide dashboards"),
 # ---- Office & agents ----
 ("mail", "Billo Mail", "Office & agents", "Live", "Keyboard-first inbox for Gmail, Outlook or IMAP, rules, snooze", "Scheduled send and follow-ups run by our servers", "Shared mailboxes, admin, retention"),
 ("write", "Billo Write", "Office & agents", "Preview", "Contracts, riders, scripts, DOCX in and out", "Live co-editing, e-sign", "Template libraries, approvals, audit"),
 ("grid", "Billo Grid", "Office & agents", "Early", "Budgets, settlements, XLSX in and out", "Live co-editing", "Org-wide templates and permissions"),
 ("deck", "Billo Deck", "Office & agents", "Early", "Pitch and sponsor decks, PPTX in and out", "AI deck drafts on our servers", "Brand-locked deck system"),
 ("drop", "Billo Drop", "Office & agents", "Live", "Convert, edit or act on any file on your device", "Big conversions on our servers", "Managed install for every machine in the org"),
 ("pdf", "Billo PDF", "Office & agents", "Early", "Fill, sign, redact, merge, split", "Signature requests that email signers", "Audit trails and retention"),
 ("xray", "Billo X-Ray", "Office & agents", "Live", "Read-only teardown of links, files, apps you own", "Long jobs on our workers", "Private deployment for security teams"),
 ("mcp", "Agent access (MCP)", "Office & agents", "Live", "One URL any agent connects to, public tools", "Higher limits, private tools on your account", "Org-wide agent keys, scopes, audit"),
 ("os", "Billo OS", "Office & agents", "Live", "The engine under everything, your own workflows", "Hosted workflow runs and schedules", "Private Billo OS for a company, custom workflows built for you"),
 # ---- Build ----
 ("cad", "Billo CAD", "Build", "Early", "2D drafting, DXF in and out", "Cloud drawing sets", "Shop-wide drawing control"),
 ("frame", "Billo Frame", "Build", "Early", "Screens, components, prototypes", "Shared prototypes with comments", "Design systems for the org"),
 ("hardware-lab", "Hardware Lab", "Build", "Building", "Lab guides and part lists", "Remote lab sessions", "School makerspace program"),
 ("garage", "Billo Garage", "Build", "Live", "Car and house dossiers, codes, fix plans", "Live part pricing runs", "Fleet and property managers"),
 # ---- Learn (schools front) ----
 ("games", "BilloTech Games", "Learn & play", "Building", "Games that teach the tech while you make", "Saved progress across devices", "Class rosters, teacher dashboards, standards mapping"),
 ("channel", "Student channel", "Learn & play", "Building", "Watch and post student work", "Hosted video at scale", "District-run channel with moderation and approvals"),
]

PLATFORM = [
 ("Account", "Free account, API key, save small project files (1,000 projects)", "Bigger cloud storage for media, version history", "Single sign-on (Google Workspace, Microsoft), roster sync"),
 ("Saving", "Save to your device or snap to your own Google Drive, always", "Auto-backup to Drive on every save, sync between devices", "Saves to the organization's Drive or storage, retention rules"),
 ("Export quality", "Full resolution, no watermark, no forced end card", "Server renders for long or heavy jobs", "Brand kit on every export"),
 ("Commercial use", "See the license question below", "Covered", "Covered for every seat"),
 ("Billo Swarm", "Split a render across your own devices", "Community render farm: other members' idle machines", "Whole-lab and district render pools"),
 ("AI", "Every AI that runs on your device (Whisper captions, local voices)", "AI on our GPUs and paid models, credits included each month", "Pooled AI credits, model choices, data stays in the org"),
 ("Support", "Help center, build requests board", "Priority build requests on Billy's desk", "Named contact, onboarding, training, uptime promise"),
 ("Data & legal", "No ads. Your footage never leaves your machine", "Same", "Data privacy agreements (FERPA, COPPA, Texas TX-NDPA), audit logs, private hosting"),
 ("Billing", "Free", "$8 a month on Square, cancel any time", "Invoice, purchase order or ACH. Donated to schools"),
]

out = {"rule": RULE, "apps": [dict(zip(["id", "name", "group", "status", "free", "pro", "enterprise"], a)) for a in A],
       "platform": [dict(zip(["area", "free", "pro", "enterprise"], p)) for p in PLATFORM],
       "prices": {"free": "$0", "pro": "$8 / month", "enterprise": "Per organization · donated to schools"}}
json.dump(out, open("/home/claude/tiermap/tiers.json", "w"), indent=1)
print(len(A), "apps,", len(PLATFORM), "platform rows")
