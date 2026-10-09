# Cloud Run deployment

This packages the existing synchronous HTTP endpoint. It does not add an Apps
Script button or asynchronous execution. Commands below create billable resources;
review them and configure a billing budget before running them.

## Local container test

```bash
docker build -t yahoo-roster-scraper:cloud-run .
export SCRAPER_API_SECRET="$(openssl rand -hex 32)"
docker run --rm -p 8080:8080 -e SCRAPER_API_SECRET yahoo-roster-scraper:cloud-run
```

From another terminal, `curl http://localhost:8080/health` should return
`{"status":"ok"}`. Starting without `SCRAPER_API_SECRET` must fail. To test a
non-default port, pass `-e PORT=9090 -p 9090:9090` instead.

The image installs locked production dependencies only, runs as a non-root user,
and binds `0.0.0.0:$PORT` (default 8080) with one Uvicorn worker. It uses `exec` so
Cloud Run termination signals reach Uvicorn. Docker's HEALTHCHECK and Cloud Run's
HTTP probes use `/health`; neither checks Google credentials or triggers scraping.

The final image contains the installed application, not your source working tree.
The Docker/Cloud Build contexts exclude local credentials, tokens, `.env`, `.venv`,
reports, Git history, and tests. Never copy service-account JSON keys into it.
A health-only test needs no Google access. Do not send a successful `/scrape`
request unless you intend to update a real spreadsheet.

## Google Cloud setup (first deployment)

Choose a project and region and authenticate with `gcloud`. Billing must be enabled.
The deploying user needs permission to build/push images, manage Cloud Run,
configure Secret Manager, and attach the runtime service account.

```bash
export PROJECT_ID="your-project-id"
export REGION="europe-west1"
export IMAGE_TAG="$(git rev-parse --short HEAD)"
export IMAGE="$REGION-docker.pkg.dev/$PROJECT_ID/roster-scraper/service:$IMAGE_TAG"
gcloud config set project "$PROJECT_ID"

gcloud services enable run.googleapis.com cloudbuild.googleapis.com \
  artifactregistry.googleapis.com secretmanager.googleapis.com sheets.googleapis.com

gcloud artifacts repositories create roster-scraper \
  --repository-format=docker --location="$REGION"
gcloud iam service-accounts create roster-scraper \
  --display-name="Roster scraper runtime"

openssl rand -hex 32 | tr -d '\n' | \
  gcloud secrets create roster-scraper-api-secret --replication-policy=automatic --data-file=-

gcloud secrets add-iam-policy-binding roster-scraper-api-secret \
  --member="serviceAccount:roster-scraper@$PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

Share each target spreadsheet with
`roster-scraper@PROJECT_ID.iam.gserviceaccount.com` as **Editor**. This file-sharing
permission is separate from Cloud IAM. The runtime needs no Drive role because it
receives an existing spreadsheet ID and updates it using the Sheets API and ADC.
Cloud Run supplies ADC through its attached identity; no OAuth browser or token
pickle is used.

Depending on the project's Cloud Build configuration, its build identity may need
Artifact Registry Writer access to the repository. Grant build permissions to the
build identity, not to the scraper runtime account.

## Build and deploy

```bash
gcloud builds submit --tag "$IMAGE" .

# Render the checked-in template without overwriting it.
sed -e "s/PROJECT_ID/$PROJECT_ID/g" \
    -e "s/REGION/$REGION/g" \
    -e "s/IMAGE_TAG/$IMAGE_TAG/g" \
    deployment/cloud-run.yaml > /tmp/roster-cloud-run.yaml

gcloud run services replace /tmp/roster-cloud-run.yaml --region="$REGION"
```

The template sets:

- minimum instances 0; maximum instances 1 (per revision)
- concurrency 1 and one process worker
- request-based CPU billing, 1 vCPU and 512 MiB RAM
- 300-second request timeout
- Secret Manager version `1` exposed as `SCRAPER_API_SECRET`
- explicit startup/liveness probes and service-account identity

The template does **not** grant public invocation by itself. The planned Apps
Script integration uses the application's bearer secret rather than Cloud Run IAM
ID tokens. To use that model, explicitly allow network invocation:

```bash
gcloud run services add-iam-policy-binding yahoo-roster-scraper \
  --region="$REGION" --member="allUsers" --role="roles/run.invoker"
```

This makes `/health` publicly reachable; `/scrape` remains protected by the
application's constant-time secret check. Keep the secret private, use HTTPS, and
do not disable the application check. If organization policy prohibits public
invocation, keep IAM protection and implement an ID-token-capable caller instead.

## Verify and monitor

```bash
export SERVICE_URL="$(gcloud run services describe yahoo-roster-scraper \
  --region="$REGION" --format='value(status.url)')"
curl "$SERVICE_URL/health"
# Should return 401 without starting a scrape (once public invocation is enabled).
curl -X POST "$SERVICE_URL/scrape" -H 'Content-Type: application/json' \
  -d '{"spreadsheet_id":"YOUR_SPREADSHEET_ID"}'
```

Retrieve the secret only on a trusted machine when configuring the caller:
`gcloud secrets versions access 1 --secret=roster-scraper-api-secret`. Store it in
Apps Script's Script Properties later, never in `_config` or source control.
A real run requires that value in `Authorization: Bearer <secret>`.

Check Cloud Run logs/metrics and Billing budgets. Scale limits and budgets are not
hard spending caps. Keep traffic on one revision: splitting traffic across
revisions can create more than one active worker. Concurrency 1 also does not
provide distributed locking or prevent a timed-out run from overlapping a retry.

Cloud Run may return 504 after the request timeout without stopping Python's
in-progress scrape. Do not immediately retry; inspect `_config.run_status` and
logs first. If runs approach five minutes, use the planned asynchronous worker
rather than simply increasing timeouts. Yahoo may block Google-hosted egress even
when scraping succeeds locally; test that separately after deployment.

When rotating the secret, add a new version and update the template's version
number and the caller together. Deleting the service stops further invocations,
but images/logs/other project resources may still incur charges.
