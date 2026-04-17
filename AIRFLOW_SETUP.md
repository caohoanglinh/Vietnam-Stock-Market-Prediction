# Airflow Local Setup Notes

## Current Setup Goals

The goals of this setup are:

- Run Apache Airflow locally using Docker on a Windows machine.
- Create a test DAG to confirm that Airflow can execute Python tasks.
- Install `vnstock` into the Airflow runtime environment.
- Prepare for the next step: writing a DAG to collect data using `vnstock`.

## Added Files and Directories

- `dags/`: contains DAG files.
- `logs/`: Airflow local logs.
- `plugins/`: empty for now, used later for custom plugins/operators if needed.
- `config/`: contains generated or custom Airflow configurations.
- `docker-compose.yaml`: declares Airflow and Postgres services.
- `Dockerfile`: builds a custom Airflow image with additional packages installed.
- `requirements-airflow.txt`: specific dependencies for the Airflow image.
- `dags/collect_vnstock_test.py`: test DAG to import `vnstock`.
- `dags/vnstock_daily_sync.py`: production DAGs for backfill and weekday quote sync.

## What Has Been Setup

### 1. Running Airflow with Docker Compose

Airflow is currently running with the following services:

- `postgres`: metadata database for Airflow.
- `airflow-apiserver`: Web UI + API server.
- `airflow-scheduler`: scheduler, task queue, running LocalExecutor.
- `airflow-dag-processor`: parses DAG files in `dags/`.
- `airflow-triggerer`: process for deferred/trigger-based workloads.
- `airflow-init`: initialization service for the database during first-time setup.

### 2. Local Auth for UI

Currently using Airflow 3.x's `Simple auth manager` with:

- `AIRFLOW__CORE__SIMPLE_AUTH_MANAGER_ALL_ADMINS=True`

Meaning:

- All local access to the UI is treated as admin.
- Suitable for local development.
- Not considered a production setup.

### 3. Execution API for Scheduler

The scheduler is configured with:

- `AIRFLOW__CORE__EXECUTION_API_SERVER_URL=http://airflow-apiserver:8080/execution/`

Reason:

- Inside a container, `localhost:8080` is not the API server.
- The scheduler must call the correct Docker service name: `airflow-apiserver`.

### 4. Shared JWT Secret Across Services

Airflow 3.x uses JWT for some internal communication. All Airflow services need to use the same secret:

- `AIRFLOW__API_AUTH__JWT_SECRET`

This secret is currently read from `.env`, no longer hardcoded in the repo.

### 5. Installing `vnstock` into the Airflow Image

Instead of temporary installations inside containers:

- `requirements-airflow.txt` contains `vnstock`.
- `Dockerfile` builds the image from `apache/airflow:3.2.0`.
- This custom image is used by all Airflow services.

Reason:

- Packages remain stable after recreating containers.
- The Airflow task runtime will be able to import `vnstock`.

## Current Test DAG

File:

- [collect_vnstock_test.py](C:/Work/vnstock/dags/collect_vnstock_test.py)

Purpose:

- Only tests `import vnstock`.
- No actual data collection yet.

If this DAG is a `Success`, it means:

- Airflow parsed the DAG.
- The scheduler can run the task.
- The runtime environment has `vnstock`.

## Current Production Quote DAGs

File:

- [vnstock_daily_sync.py](C:/Work/vnstock/dags/vnstock_daily_sync.py)

This file currently contains 2 DAGs:

- `vnstock_backfill_to_today`
- `vnstock_weekday_quotes_18h`

### `vnstock_backfill_to_today`

Use this one first.

Behavior:

- No schedule, manual trigger only.
- Reads local quote files already present in `data/raw_data.csv` and `data/singular_stock/`.
- For each configured ticker, only fetches the missing dates up to today.
- Rebuilds `data/raw_data.csv` from the per-ticker files after the sync completes.

### `vnstock_weekday_quotes_18h`

Use this one for ongoing automation.

Behavior:

- Runs at `18:00` Asia/Ho_Chi_Minh.
- Runs only on weekdays, Monday to Friday.
- Skips Saturday and Sunday.
- On each run, fetches only the missing quote rows since the latest local date.

### Correct Run Order

1. Trigger `vnstock_backfill_to_today` once to catch up the local dataset to the current date.
2. Leave `vnstock_weekday_quotes_18h` enabled so Airflow keeps the quote dataset current every weekday evening.

### Important Note About the 100-Ticker Universe

The new DAG follows the current intended 100-ticker universe from `collect_data.ipynb`.

That means:

- The sync is now aligned to the current code-defined 100-stock list.
- The old local raw dataset in the repo had a small ticker mismatch versus this list.
- The rebuilt aggregate `data/raw_data.csv` will gradually align to the new DAG universe as the sync runs.

## What Happens After Turning Off or Restarting the Computer?

### Will Docker restart automatically?

Depends on two things:

1. Whether Docker Desktop starts automatically with Windows.
2. Whether the containers have `restart: always`.

In the current setup:

- `postgres`, `airflow-apiserver`, `airflow-scheduler`, `airflow-dag-processor`, and `airflow-triggerer` all have `restart: always`.

If Docker Desktop starts automatically with the machine, these containers will usually restart themselves.

`airflow-init` does not need to restart automatically. It is only used to initialize the DB during the first setup.

### Safe Way to Restart Manually After Reboot

Inside the repo:

```powershell
cd C:\Work\vnstock
docker compose up -d airflow-apiserver airflow-scheduler airflow-dag-processor airflow-triggerer
```

Verification:

```powershell
docker compose ps
```

Open UI:

- [http://localhost:8080](http://localhost:8080)

### When Do You Need to `docker compose build` Again?

Only rebuild when:

- Modifying `Dockerfile`.
- Modifying `requirements-airflow.txt`.
- Adding new packages to the Airflow image.

Then:

```powershell
docker compose build
docker compose up -d airflow-apiserver airflow-scheduler airflow-dag-processor airflow-triggerer
```

## When to Run `airflow-init` Again

Usually not necessary.

Only run it again when:

- Deleting the Postgres volume.
- Resetting the entire Airflow metadata DB.
- Setting up from scratch again.

Command:

```powershell
docker compose up airflow-init
```

## What to Hide if Pushing the Repo to GitHub

### Do Not Commit:

- `.env`
- Real API keys.
- Real passwords.
- Real JWT secret.
- Generated logs in `logs/`.
- Sensitive generated configs, if any.

### Can Commit:

- `docker-compose.yaml`
- `Dockerfile`
- `requirements-airflow.txt`
- `dags/*.py`
- `.env.example`
- This markdown documentation.

### Special Note for the Current Repo:

With this repo, the following should not appear in a public repo:

- Real `VNSTOCK_API_KEY`.
- Real `_AIRFLOW_WWW_USER_PASSWORD`.
- Real `AIRFLOW__API_AUTH__JWT_SECRET`.

If you need to share the repo:

1. Keep `.env` locally.
2. Commit `.env.example` with placeholder values.
3. Do not paste secrets into notebooks, Python files, or `docker-compose.yaml`.

## Quick Check of Current Setup

### UI

- [http://localhost:8080](http://localhost:8080)

### Container Status

```powershell
docker compose ps
```

### Scheduler Logs

```powershell
docker compose logs airflow-scheduler --tail 100
```

### Triggering Test DAG

Go to the UI and trigger the `collect_vnstock_test` DAG.

## Frequently Used Commands

### Start Services

```powershell
docker compose up -d airflow-apiserver airflow-scheduler airflow-dag-processor airflow-triggerer
```

### Stop Services

```powershell
docker compose stop airflow-apiserver airflow-scheduler airflow-dag-processor airflow-triggerer postgres
```

### Rebuild Image

```powershell
docker compose build
```

### Wipe Out Local Environment

Be careful, this command also deletes local database volumes:

```powershell
docker compose down --volumes --remove-orphans
```

## Logical Next Steps

The next step is:

1. Trigger `vnstock_backfill_to_today`.
2. Verify `data/raw_data.csv` and several files inside `data/singular_stock/` were updated through today.
3. Leave `vnstock_weekday_quotes_18h` active for daily weekday refreshes.
