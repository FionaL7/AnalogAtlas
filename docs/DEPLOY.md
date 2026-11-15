# Deploy

Both halves run in one Cloud project, `$GCP_PROJECT` (Rishabh's account), region `us-central1` ([#45](https://github.com/FionaL7/AnalogAtlas/issues/45)):

- **API**: Cloud Run, service `analogatlas-api`. URL on the Team log (#2).
- **Frontend**: Firebase Hosting at **https://analogatlas.earth** (`www` redirects there). Config: [firebase.json](../firebase.json).
- The project id is in `.env` as `GCP_PROJECT`. Don't write it into the repo (so no `.firebaserc`; pass `--project`).

## How it works

Every deploy is a Cloud Build trigger on `main` (repo connected by Fiona, #45). No keys in the repo.

| Trigger | Runs on push to `main` touching | Config | Does |
| --- | --- | --- | --- |
| `deploy-api` | `api/**`, `analogatlas/**`, `deploy/api/**` | [deploy/api/cloudbuild.yaml](../deploy/api/cloudbuild.yaml) | Build image (CLIP baked in, index + tiles from the `data` release) → Cloud Run |
| `deploy-web` | `web/**`, `analogatlas/**`, `api/indices.py`, `scripts/03_export.py`, `firebase.json`, `deploy/web/**` | [deploy/web/cloudbuild.yaml](../deploy/web/cloudbuild.yaml) | Index from the release → `03_export.py` → `npm run build` → Firebase Hosting |

- **New data:** `python scripts/data.py push index` (or `tiles`) starts the triggers itself after uploading. A release upload alone triggers nothing.
- The web build reads the API URL from Cloud Run, so it is never in the repo.
- **Scale to zero** (`--min-instances=0`): ~free while idle. The first request after ~15 min idle waits up to ~30 s (cold start). The frontend pings `/health` on page load to start it early.
- Only the 2 newest API images are kept ([cleanup-policy.json](../deploy/api/cleanup-policy.json)), so storage stays ~$0.50/month.
- Run either by hand: `gcloud builds triggers run deploy-web --branch=main --region=us-central1`.

## Who can deploy

Fiona and Rishabh both have the Editor role on the project. That is enough to run the commands below.

## API: deploy by hand

Use after `python scripts/data.py push index` (or tiles), or while the trigger isn't set up. From a clean checkout of `main`:

```bash
gcloud config set project $GCP_PROJECT
gcloud builds submit --config deploy/api/cloudbuild.yaml --region=us-central1 \
  --service-account=projects/$GCP_PROJECT/serviceAccounts/deployer@$GCP_PROJECT.iam.gserviceaccount.com .
```

Once the trigger exists, this also works: `gcloud builds triggers run deploy-api --branch=main --region=us-central1`.

Check it:

```bash
URL=$(gcloud run services describe analogatlas-api --region=us-central1 --format='value(status.url)')
curl $URL/health    # should list moon, moon_polar, earth
```

## Frontend: deploy by hand

From a clean checkout of `main`. Needs `npm i -g firebase-tools` and `gcloud auth application-default login` once (`firebase login` doesn't work in agent shells).

```bash
python scripts/data.py pull                # data/index/ from the release
python scripts/03_export.py                # -> web/public/data/
cd web && npm ci
VITE_API_BASE=<API URL> npm run build      # PowerShell: $env:VITE_API_BASE="<API URL>"; npm run build
cd .. && firebase deploy --only hosting --project $GCP_PROJECT
```

Check: open https://analogatlas.earth and run a free-text search (it calls the API).

## One-time setup

Done already (#45), kept here in case the project has to be rebuilt.

1. **Billing**: link a billing account to the project. Then Billing → Budgets & alerts → a ~$5 budget with email alerts. The budget currency must match the billing account (ours is INR: ₹450).
2. **gcloud**: install the [Google Cloud CLI](https://cloud.google.com/sdk/docs/install), then:
   ```bash
   gcloud auth login
   gcloud config set project $GCP_PROJECT
   ```
3. **APIs, image repo, cleanup**:
   ```bash
   gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com
   gcloud artifacts repositories create analogatlas --repository-format=docker --location=us-central1
   gcloud artifacts repositories set-cleanup-policies analogatlas --location=us-central1 \
     --policy=deploy/api/cleanup-policy.json --no-dry-run
   ```
4. **Deploy service account**:
   ```bash
   SA=deployer@$GCP_PROJECT.iam.gserviceaccount.com
   gcloud iam service-accounts create deployer --display-name="Cloud Build deployer"
   for r in run.admin artifactregistry.writer logging.logWriter iam.serviceAccountUser storage.objectViewer             firebasehosting.admin serviceusage.serviceUsageConsumer; do
     gcloud projects add-iam-policy-binding $GCP_PROJECT --member=serviceAccount:$SA --role=roles/$r
   done
   ```
   `storage.objectViewer` is only needed for `gcloud builds submit`: it reads the uploaded source. The last two are for the web deploy.
4b. **Verdict LLM secret** (#51, optional). The verdict prose is generated offline by `scripts/07_verdicts.py`, not by the API — this only puts the key on the service for future use; nothing in `api/` reads it today.
   ```bash
   gcloud services enable secretmanager.googleapis.com
   printf '%s' "<the API key>" | gcloud secrets create llm-api-key --replication-policy=automatic --data-file=-
   RUNTIME_SA=$(gcloud run services describe analogatlas-api --region=us-central1 --format='value(spec.template.spec.serviceAccountName)' 2>/dev/null || echo "$(gcloud projects describe $GCP_PROJECT --format='value(projectNumber)')-compute@developer.gserviceaccount.com")
   gcloud secrets add-iam-policy-binding llm-api-key --member=serviceAccount:$RUNTIME_SA --role=roles/secretmanager.secretAccessor
   gcloud secrets add-iam-policy-binding llm-api-key --member=serviceAccount:deployer@$GCP_PROJECT.iam.gserviceaccount.com --role=roles/secretmanager.secretAccessor
   ```
   Granting (`add-iam-policy-binding`) needs Owner on the project, not just Editor. `deploy/api/cloudbuild.yaml` already passes `LLM_BASE_URL`, `LLM_MODEL` and this secret as `LLM_API_KEY` to every deploy once it exists; a deploy before the secret exists fails with "Revision is not ready" until it's created.
5. **Access for the team**:
   ```bash
   gcloud projects add-iam-policy-binding $GCP_PROJECT --member=user:<google email> --role=roles/editor
   ```
6. **Trigger** (Console → Cloud Build → Triggers, region `us-central1`). Connecting the repo needs the repo owner (Fiona) to approve the Cloud Build GitHub app.
   - Connect repository → GitHub → install the Cloud Build app on `FionaL7/AnalogAtlas`.
   - Create trigger: name `deploy-api`, event *Push to a branch*, branch `^main$`.
   - Included files filter: `api/**`, `analogatlas/**`, `deploy/api/**`.
   - Configuration: Cloud Build file, location `deploy/api/cloudbuild.yaml`.
   - Service account: `deployer@<project id>.iam.gserviceaccount.com`.

7. **Firebase Hosting**: add Firebase to the project in the [Firebase console](https://console.firebase.google.com) (first time per Google account: accept the terms there, the API refuses until then). Then Hosting → Add custom domain `analogatlas.earth` and `www` (redirect to the bare domain). At Porkbun: delete the parking ALIAS/CNAME/`_acme-challenge` records, add the A, TXT and `www` CNAME records Firebase shows. HTTPS follows within ~1 h.

## Gotchas

- `$` starts a substitution in `cloudbuild.yaml`; shell variables must be `$$`.
- `_IMAGE` uses `${PROJECT_ID}`, which only works with `dynamicSubstitutions: true` under `options:`. Without it the build fails with "repository name must be lowercase".
- torch and torchvision must both come from the CPU index (see the Dockerfile).
- uvicorn needs `--proxy-headers`, or `tile_url` comes back `http://` and HTTPS pages block it.
- `moon_polar` tile images aren't on the `data` release yet, so `/tile/moon_polar/...` returns 404.
- Local test: `echo local > .build-stamp && docker build -f deploy/api/Dockerfile -t aa-api . && docker run -p 8080:8080 aa-api`.
