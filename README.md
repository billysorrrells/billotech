# BilloTech

Browser tools for video, color and beat editing, by Billy Sorrells Entertainment. Source-available under the **BilloTech Source License 1.1** (`LICENSE.md`): read it, use every tool free at full quality; Pro ($8 a month) covers what costs money to run plus paid client work. Everything you make is yours.

- **Billo Forge** (`cloud/billotech/cloud/`): drop a clip, pick a recipe, export. 11 effects and 7 color looks in one WebGL pass, beat-cut editing (Billo Cadence), export in the browser, save to your device or your Google Drive. Live: https://billotech-cloud.netlify.app/billotech/cloud/
- **Plans** (`cloud/billotech/pro/`), **Schools** (`cloud/billotech/schools/`), **License** (`cloud/billotech/license/`).
- **Backend** (`cloud/supabase/`): `billotech-api` (accounts, plans, project sync, usage) and `billotech-billing` (Square subscriptions → plans).
- **Command line** (`forge/billo_fx.py`): the same effects, looks and cut recipes for ffmpeg pipelines.

Your footage never leaves your machine. BilloTech stores accounts, plans and small project files only.
