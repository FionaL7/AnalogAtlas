# Deploy

The API runs on **Cloud Run** in project `analogatlas-ee`, region `us-central1` ([#21](https://github.com/FionaL7/AnalogAtlas/issues/21)). The frontend host is still to do.

## How it works

- Push to `main` touching `api/`, `analogatlas/` or `deploy/api/` → Cloud Build trigger `deploy-api` runs [deploy/api/cloudbuild.yaml](../deploy/api/cloudbuild.yaml): build image → push → deploy.
- The image bakes in CLIP and pulls the index and tiles from the GitHub Release `data` at build time. No keys in the repo.
- **Scale to zero** (`--min-instances=0`): ~free while idle. The first request after ~15 min idle waits 10–30 s (cold start). The frontend pings `/health` on page load to start it early.
- Only the 2 newest images are kept ([cleanup-policy.json](../deploy/api/cleanup-policy.json)), so storage stays ~$0.50/month.

## Redeploy after new data

After `python scripts/data.py push index` (or tiles), rebuild so the image picks it up:

```bash
gcloud builds triggers run deploy-api --branch=main --region=us-central1
```
Or: Console → Cloud Build → Triggers → `deploy-api` → Run.

## One-time setup (Fiona)

1. **Billing**: link a billing account to `analogatlas-ee`. Then Billing → Budgets & alerts → budget of $5 with email alerts.
2. **gcloud**:
   ```bash
   brew install --cask google-cloud-sdk
   gcloud auth login
   gcloud config set project analogatlas-ee
   ```
3. **APIs, image repo, cleanup**:
   ```bash
   gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com
   gcloud artifacts repositories create analogatlas --repository-format=docker --location=us-central1
   gcloud artifacts repositories set-cleanup-policies analogatlas --location=us-central1 \
     --policy=deploy/api/cleanup-policy.json
   ```
4. **Deploy service account**:
   ```bash
   SA=deployer@analogatlas-ee.iam.gserviceaccount.com
   gcloud iam service-accounts create deployer --display-name="Cloud Build deployer"
   for r in run.admin artifactregistry.writer logging.logWriter iam.serviceAccountUser; do
     gcloud projects add-iam-policy-binding analogatlas-ee --member=serviceAccount:$SA --role=roles/$r
   done
   ```
5. **Trigger** (Console → Cloud Build → Triggers, region `us-central1`):
   - Connect repository → GitHub → install the Cloud Build app on `FionaL7/AnalogAtlas`.
   - Create trigger: name `deploy-api`, event *Push to a branch*, branch `^main$`.
   - Included files filter: `api/**`, `analogatlas/**`, `deploy/api/**`.
   - Configuration: Cloud Build file, location `deploy/api/cloudbuild.yaml`.
   - Service account: `deployer@analogatlas-ee.iam.gserviceaccount.com`.
6. **First deploy**: click Run on the trigger. ~10–15 min. Then:
   ```bash
   URL=$(gcloud run services describe analogatlas-api --region=us-central1 --format='value(status.url)')
   curl $URL/health    # should list moon, moon_polar, earth
   ```
   Post `$URL` on the Team log: the frontend build needs it as `VITE_API_BASE`.
7. **Give Rishabh access** so deploys don't wait on one person:
   ```bash
   gcloud projects add-iam-policy-binding analogatlas-ee \
     --member=user:<rishabh's google email> --role=roles/run.developer
   gcloud projects add-iam-policy-binding analogatlas-ee \
     --member=user:<rishabh's google email> --role=roles/cloudbuild.builds.editor
   ```

## Gotchas

- `$` starts a substitution in `cloudbuild.yaml`; shell variables must be `$$`.
- torch and torchvision must both come from the CPU index (see the Dockerfile).
- uvicorn needs `--proxy-headers`, or `tile_url` comes back `http://` and HTTPS pages block it.
- `moon_polar` tile images aren't on the `data` release yet, so `/tile/moon_polar/...` returns 404.
- Local test: `echo local > .build-stamp && docker build -f deploy/api/Dockerfile -t aa-api . && docker run -p 8080:8080 aa-api`.
