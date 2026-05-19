# VNStock Prediction Pipeline

This project builds an end-to-end pipeline for forecasting Vietnamese stock price movements: collecting market data, generating technical features, running multi-horizon prediction models, crawling financial news, using Gemini to analyze news semantics, and rendering the combined outputs in a local web dashboard.

The main goal of the repository is to monitor roughly 100 highly liquid Vietnamese stocks and provide two parallel signal layers:

- Quantitative signals from `Random Forest`, `XGBoost`, and `LSTM` models for the `1-day`, `5-day`, and `10-day` horizons.
- Qualitative signals from `Gemini`, based on news articles crawled during the day, including sentiment, summary, bull points, bear points, and risk flags.

This repository is intended for research, experimentation with a stock analysis system, and local operation using Docker + Apache Airflow.

## Architecture Overview

The current processing flow has five main parts:

1. **Price data synchronization**
   - Historical and incremental quote data are fetched with `vnstock`.
   - The combined dataset is stored in `data/raw_data.csv`.
   - Per-ticker datasets are stored in `data/singular_stock/`.

2. **Feature engineering and prediction**
   - The system computes technical features from price data and builds the latest 20-day window for each ticker.
   - `RF`, `XGBoost`, and `LSTM` generate probabilities/predictions for the `1D`, `5D`, and `10D` horizons.
   - Outputs are saved in `data/predictions/daily/`.
   - Daily comparison against realized outcomes is saved in `data/predictions/comparison/`.

3. **Financial news crawling**
   - Airflow crawls news articles by ticker from financial news sources.
   - Articles are stored in PostgreSQL through the `stock_news` table.

4. **Gemini-based news analysis**
   - After crawling finishes, Gemini groups articles by ticker for the day.
   - Each ticker is analyzed at most once per day to reduce quota usage.
   - Results are stored in the `stock_news_daily_analysis` table and exported to `data/news_analysis/` snapshots.

5. **Local dashboard**
   - The local dashboard displays the ticker list, avatars/logos, prediction outputs, and the `Gemini News Analysis` section.
   - Clicking a ticker shows the latest 20-day feature inputs and all model outputs.

## Main Components

### 1. Price prediction models

The repository currently uses three model families:

- `Random Forest`
- `XGBoost`
- `LSTM`

These models operate independently from the news-analysis layer. In practice:

- Price forecasts still come from numeric market data and technical features.
- Gemini only acts as a news-language analyst that provides an additional reference signal.

### 2. Airflow orchestration

The repository uses Dockerized Apache Airflow to automate daily jobs. The most important DAGs are:

- `collect_vnstock_test`: verifies that the Airflow runtime can import `vnstock`.
- `vnstock_backfill_to_today`: backfills missing quote data up to the current date.
- `vnstock_weekday_quotes_18h`: synchronizes price data every weekday at `18:00` Vietnam time.
- `vnstock_daily_predictions`: runs feature engineering + inference at `18:15` Vietnam time.
- `vnstock_news_crawl`: crawls financial news at `19:00` Vietnam time.
- `vnstock_news_llm_analysis`: analyzes crawled news with Gemini at `19:30` Vietnam time.

### 3. Local dashboard

The dashboard in `web/` can be run locally to view:

- a paginated ticker list
- manual avatars/logos stored in `web/img/ava/`
- `RF/XGBoost/LSTM` prediction outputs
- the latest 20-day feature input table
- Gemini-based news analysis

## Prerequisites

Your local machine should have:

- `Git`
- `Python`
- `Docker Desktop`
- `PowerShell` on Windows

You also need to prepare the required API keys and environment variables in `.env`.

## Environment Variables

Create a `.env` file from `.env.example` and fill in the real values:

```env
VNSTOCK_API_KEY=your_vnstock_api_key_here
AIRFLOW_UID=50000
_AIRFLOW_WWW_USER_USERNAME=your_airflow_username
_AIRFLOW_WWW_USER_PASSWORD=your_airflow_password
AIRFLOW__API_AUTH__JWT_SECRET=replace_with_a_long_random_secret
NEWS_DB_CONN=postgresql://airflow:airflow@postgres:5432/stock_news
GEMINI_API_KEY=your_gemini_api_key_here
```

Quick explanation:

- `VNSTOCK_API_KEY`: key for the market-data layer.
- `_AIRFLOW_WWW_USER_USERNAME`, `_AIRFLOW_WWW_USER_PASSWORD`: credentials for the Airflow UI.
- `AIRFLOW__API_AUTH__JWT_SECRET`: internal secret shared between Airflow services.
- `NEWS_DB_CONN`: database connection string for storing and querying news.
- `GEMINI_API_KEY`: key for the Gemini news-analysis step.

Do not commit the real `.env` file to GitHub.

## How To Run From Scratch After Cloning

### 1. Clone the repository

```powershell
git clone https://github.com/caohoanglinh/Vietnam-Stock-Market-Prediction.git
cd Vietnam-Stock-Market-Prediction
```

If you clone the repo into another folder, adjust the paths in the later commands accordingly.

### 2. Create `.env`

```powershell
copy .env.example .env
```

Then open `.env` and fill in the API keys, username, password, and JWT secret.

### 3. Install local Python dependencies

```powershell
pip install -r requirements.txt
```

These dependencies are for notebooks, local scripts, and the dashboard builder. Airflow containers use their own dependency set from `requirements-airflow.txt` and `Dockerfile`.

### 4. Build the Airflow image

```powershell
docker compose build
```

This step installs the dependencies required by Airflow, including `vnstock` and the project's Python packages inside the container environment.

### 5. Initialize the Airflow metadata database

```powershell
docker compose up airflow-init
```

You usually only need this once during the first setup or after a full database-volume reset.

### 6. Start the main Airflow services

```powershell
docker compose up -d airflow-apiserver airflow-scheduler airflow-dag-processor airflow-triggerer
```

Open the Airflow UI at:

- [http://localhost:8080](http://localhost:8080)

### 7. Verify that Airflow is healthy

```powershell
docker compose ps
docker compose logs airflow-scheduler --tail 100
```

### 8. Run the initial quote backfill

After opening the Airflow UI, trigger the `vnstock_backfill_to_today` DAG once to update the local quote dataset through the current date.

Then leave `vnstock_weekday_quotes_18h` enabled for ongoing weekday synchronization.

### 9. Run the local dashboard

```powershell
powershell -ExecutionPolicy Bypass -File .\web\run_dashboard.ps1
```

Open the dashboard at:

- [http://127.0.0.1:8000/static/](http://127.0.0.1:8000/static/)

Or use the convenience launcher in the repo root:

```powershell
.\start_dashboard.bat
```

That `.bat` file checks the local server and opens the browser for you.

## Daily Operating Flow

Once the system has been set up and Airflow is running, the daily flow is:

1. `18:00` VN time: synchronize quote data through `vnstock_weekday_quotes_18h`
2. `18:15` VN time: run `vnstock_daily_predictions`
3. `19:00` VN time: crawl financial news through `vnstock_news_crawl`
4. `19:30` VN time: analyze news with `vnstock_news_llm_analysis`

Fresh outputs will appear in:

- `data/predictions/daily/`
- `data/predictions/comparison/`
- `data/news_analysis/`

To refresh the local dashboard with the latest outputs, run:

```powershell
powershell -ExecutionPolicy Bypass -File .\web\run_dashboard.ps1
```

## Common Commands

### Restart Airflow after rebooting the machine

```powershell
docker compose up -d airflow-apiserver airflow-scheduler airflow-dag-processor airflow-triggerer
```

### Stop local Airflow and Postgres

```powershell
docker compose stop airflow-apiserver airflow-scheduler airflow-dag-processor airflow-triggerer postgres
```

### Rebuild the image after changing Airflow dependencies

```powershell
docker compose build
docker compose up -d airflow-apiserver airflow-scheduler airflow-dag-processor airflow-triggerer
```

### Reset the full local Docker environment

```powershell
docker compose down --volumes --remove-orphans
```

This command also removes the local database volume, so use it only when you really want a full reset.

## Repository Structure

Below are the important folders and files to help a new reader understand the repository quickly.

### Root folders

- `config/`: supporting configuration, currently including `model_weights.json` for the ensemble.
- `dags/`: all Airflow DAGs for data synchronization, prediction, news crawling, and Gemini analysis.
- `data/`: input datasets, per-ticker quote data, prediction outputs, and exported news-analysis snapshots.
- `feature_weight_distribution/`: scripts for plotting feature-weight matrices and related distributions.
- `img/`: images, label distributions, and feature-importance visualizations.
- `logs/`: local Airflow logs.
- `models/`: model artifacts such as `.pkl`, `.pt`, scalers, and feature-column definitions.
- `plugins/`: Airflow plugin directory, currently empty or reserved for future use.
- `train_models/`: notebooks for training `RF`, `XGBoost`, and `LSTM` models.
- `utils/`: shared Python modules for feature engineering, inference, evaluation, news crawling, DB access, and Gemini integration.
- `web/`: local dashboard code and built static data.

### Important root files

- `README.md`: the main project documentation.
- `.env.example`: environment-variable template.
- `docker-compose.yaml`: Airflow + Postgres service definition.
- `Dockerfile`: custom Airflow image definition.
- `requirements.txt`: local Python dependencies.
- `requirements-airflow.txt`: Python dependencies used inside the Airflow image.
- `collect_data.ipynb`: notebook for initial data processing and exploration.
- `start_dashboard.bat`: quick Windows launcher for the local dashboard.
- `test_pipeline.py`: local pipeline test/check file.

### `dags/`

- `collect_vnstock_test.py`: test DAG for importing `vnstock`.
- `vnstock_daily_sync.py`: contains the quote backfill DAG and the weekday quote-sync DAG.
- `vnstock_daily_predictions.py`: computes features, runs inference, saves predictions, and compares against realized outcomes.
- `vnstock_news_crawl.py`: crawls financial news by ticker.
- `vnstock_news_llm_analysis.py`: analyzes news with Gemini, stores the results, and exports dashboard snapshots.

### `data/`

- `raw_data.csv`: combined quote dataset for the tracked universe in the format used by the pipeline.
- `total_stocks.csv`: aggregate dataset used in the broader historical workflow.
- `singular_stock/`: one CSV file per ticker.
- `predictions/daily/`: daily prediction outputs.
- `predictions/comparison/`: historical prediction-versus-outcome comparisons.
- `news_analysis/latest.json`: latest news-analysis snapshot used by the dashboard.
- `news_analysis/daily/`: per-day news-analysis snapshots.

### `models/`

- `rf_model_*.pkl`: Random Forest models for each horizon.
- `xgb_model_*.pkl`: XGBoost models for each horizon.
- `lstm_model_*.pt`, `lstm_best*.pt`: LSTM model weights.
- `feature_cols_*.pkl`: feature-column definitions associated with each model family.
- `scaler_*.pkl`: scalers used for standardized inputs, especially around the LSTM path.

### `utils/`

- `feature_engineering.py`: technical-feature generation and inference-window construction.
- `inference.py`: model loading and ensemble prediction logic.
- `evaluation.py`: prediction-versus-realized-outcome comparison logic.
- `news_crawler.py`: article crawling logic.
- `news_db.py`: storage and retrieval for raw news in PostgreSQL.
- `news_analysis_db.py`: daily news-analysis storage and snapshot export.
- `gemini_news_analysis.py`: Gemini API integration and structured-output parsing.

### `web/`

- `build_dashboard_data.py`: builds frontend JSON from predictions + news analysis.
- `run_dashboard.ps1`: rebuilds JSON and starts the local server.
- `server.py`: simple local web server.
- `img/ava/`: manually stored avatars/logos for each ticker.
- `static/index.html`, `static/app.js`, `static/styles.css`: dashboard frontend files.
- `static/data/`: built JSON used by the frontend.

## Suggested Reading Order

If you just cloned the repo and want to understand the workflow quickly, read the code in this order:

1. `README.md`
2. `docker-compose.yaml`
3. `dags/vnstock_daily_sync.py`
4. `dags/vnstock_daily_predictions.py`
5. `dags/vnstock_news_crawl.py`
6. `dags/vnstock_news_llm_analysis.py`
7. `utils/feature_engineering.py`
8. `utils/inference.py`
9. `web/build_dashboard_data.py`

This sequence takes you from orchestration, to forecasting logic, to the final presentation layer.

## Notes For Sharing The Repository

Do not commit or publish:

- `.env`
- real API keys
- real Airflow passwords
- the real JWT secret
- local logs in `logs/`

Safe to commit:

- `.env.example`
- `Dockerfile`
- `docker-compose.yaml`
- `requirements*.txt`
- DAG code
- notebooks, utils, and web code

## Disclaimer

This project is intended for research, learning, and system-building purposes. Prediction outputs and news analysis are not investment advice. Stock trading always involves risk.