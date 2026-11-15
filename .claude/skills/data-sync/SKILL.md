---
name: data-sync
description: Download or upload the shared data/ files (index, raw rasters, tiles) via the GitHub Release `data`. Use on a new device, before running the API or app, or after a pipeline step writes new files to data/.
---

# Data sync (GitHub Release `data`)

`data/` isn't in git. The shared copy lives as files on the release `data`: https://github.com/FionaL7/AnalogAtlas/releases/tag/data

- Each entry in `data/<folder>/` is one release file: a file is `index__moon_meta.parquet`, a folder is `tiles__moon.tar`.
- Push replaces files of the same name, so **the last push of an entry wins**.
- Needs a logged-in `gh`. No other tools; works on Windows.

## Download
```
python scripts/data.py pull              # data/index/: all the API needs (~40 MB)
python scripts/data.py pull raw tiles    # rasters (~200 MB) and tiles (~860 MB)
python scripts/data.py pull all
```

## Upload (after a pipeline step changes data/)
Push only what you rebuilt:
```
python scripts/data.py push index                     # all of data/index/
python scripts/data.py push index/earth_meta.parquet  # one file
python scripts/data.py push raw/minirf                # one folder, as a .tar
```
- Pushing `index/` or `tiles/` also redeploys the live site: it starts the Cloud Build triggers (`index`: API + web, `tiles`: API). Needs `gcloud` logged in and `GCP_PROJECT` in `.env`; otherwise it prints the command to run. `--no-deploy` skips it.
- Then post on the Team log what you pushed and which commit built it.

## Check it worked
- `python scripts/data.py list` shows each file's size and upload time.
- After a pull, the API starts and a search returns results.
- After a push: `gcloud builds list --region=us-central1 --limit=2` shows the deploys; each takes ~5–10 min.
