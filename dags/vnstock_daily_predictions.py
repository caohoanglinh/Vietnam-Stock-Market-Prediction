"""
DAG: vnstock_daily_predictions
==============================
Runs daily at 18:15 (after data collection DAG at 18:00).
Pipeline: Feature Engineering → Inference → Save → Compare → Weekly + Retrain.

All tasks run strictly sequential — no parallelism.
"""

import os
import sys
from datetime import datetime, timedelta
from airflow.utils.state import DagRunState

import pendulum
from airflow.sdk import DAG, task

# ── Project setup ────────────────────────────────────────────────────────────
PROJECT_ROOT = "/opt/airflow/project"
sys.path.insert(0, PROJECT_ROOT)

LOCAL_TZ = pendulum.timezone("Asia/Ho_Chi_Minh")



with DAG(
    dag_id="vnstock_daily_predictions",
    description="Ensemble prediction (RF+XGB+LSTM) with daily eval and weekly retrain",
    schedule="15 18 * * 1-5",       # 18:15 Mon-Fri (after data DAG at 18:00)
    start_date=datetime(2026, 4, 21, tzinfo=LOCAL_TZ),
    catchup=False,
    tags=["vnstock", "prediction", "ensemble"],
    default_args={
        "owner": "vnstock",
        "retries": 2,
        "retry_delay": timedelta(minutes=5),
    },
) as dag:


    from airflow.sensors.external_task import ExternalTaskSensor

    wait_for_sync = ExternalTaskSensor(
        task_id="wait_for_daily_sync",
        external_dag_id="vnstock_weekday_quotes_18h",
        external_task_id=None, 
        execution_delta=timedelta(minutes=15),  
        timeout=3600,
        allowed_states=[DagRunState.SUCCESS],
        failed_states=[DagRunState.FAILED],
        mode="reschedule",
    )


    @task
    def compute_features():
        """Compute 16 features and extract 20-day inference windows."""
        import pandas as pd
        import joblib
        from utils.feature_engineering import prepare_featured_data, extract_inference_windows

        raw_path = os.path.join(PROJECT_ROOT, "data", "raw_data.csv")
        cache_path = os.path.join(PROJECT_ROOT, "data", "predictions", "_features_cache.pkl")

        os.makedirs(os.path.dirname(cache_path), exist_ok=True)

        print("  Loading raw data...")
        raw = pd.read_csv(raw_path, parse_dates=["date"])
        print(f"  Raw: {len(raw):,} rows, {raw['ticker'].nunique()} tickers")

        print("  Computing 16 features...")
        featured = prepare_featured_data(raw)

        print("  Extracting 20-day inference windows...")
        windows, pred_date, skipped = extract_inference_windows(featured)

        print(f"  Windows ready: {len(windows)} tickers (skipped: {len(skipped)})")
        print(f"  Prediction date: {pred_date}")

        # Save to cache file for next task
        joblib.dump({
            "windows": windows,
            "prediction_date": str(pred_date),
            "skipped": skipped,
        }, cache_path)

        return str(pred_date)

 
    @task
    def run_predictions(prediction_date: str):
        """Load 9 models, run inference, apply Multi-Horizon Consensus."""
        import joblib
        from utils.inference import load_all_models, load_auc_weights, run_ensemble_predictions

        models_dir  = os.path.join(PROJECT_ROOT, "models")
        config_path = os.path.join(PROJECT_ROOT, "config", "model_weights.json")
        cache_path  = os.path.join(PROJECT_ROOT, "data", "predictions", "_features_cache.pkl")
        pred_cache  = os.path.join(PROJECT_ROOT, "data", "predictions", "_predictions_cache.pkl")

        # Load cached windows
        cache = joblib.load(cache_path)
        windows = cache["windows"]

        print(f"  Loading 9 models...")
        models = load_all_models(models_dir)

        print(f"  Loading AUC weights...")
        auc_weights = load_auc_weights(config_path)

        print(f"  Running ensemble predictions for {len(windows)} tickers...")
        predictions_df = run_ensemble_predictions(windows, models, auc_weights)
        predictions_df["date"] = prediction_date

        # Cache predictions for save task
        joblib.dump(predictions_df, pred_cache)

        return prediction_date


    @task
    def save_predictions(prediction_date: str):
        """Save predictions to data/predictions/daily/{date}.csv."""
        import joblib

        pred_cache = os.path.join(PROJECT_ROOT, "data", "predictions", "_predictions_cache.pkl")
        daily_dir  = os.path.join(PROJECT_ROOT, "data", "predictions", "daily")

        os.makedirs(daily_dir, exist_ok=True)

        predictions_df = joblib.load(pred_cache)
        output_path = os.path.join(daily_dir, f"{prediction_date}.csv")
        predictions_df.to_csv(output_path, index=False)

        print(f"  ✅ Saved {len(predictions_df)} predictions to {output_path}")

        # Print top signals
        strong = predictions_df[predictions_df["consensus_decision"] == "STRONG_BUY"]
        buy    = predictions_df[predictions_df["consensus_decision"] == "BUY"]

        if len(strong) > 0:
            print(f"\n  ⭐ STRONG BUY ({len(strong)}):")
            for _, r in strong.iterrows():
                print(f"    {r['ticker']:5s} | 1D={r['ensemble_1d']:.3f} | "
                      f"5D={r['ensemble_5d']:.3f} | 10D={r['ensemble_10d']:.3f}")

        if len(buy) > 0:
            print(f"\n  📈 BUY ({len(buy)}):")
            for _, r in buy.iterrows():
                print(f"    {r['ticker']:5s} | 1D={r['ensemble_1d']:.3f} | "
                      f"5D={r['ensemble_5d']:.3f} | 10D={r['ensemble_10d']:.3f}")

        return prediction_date


    @task
    def compare_yesterday_task(prediction_date: str):
        """Evaluate accuracy of yesterday's 1D predictions."""
        from utils.evaluation import compare_yesterday

        result = compare_yesterday(PROJECT_ROOT, today_str=prediction_date)

        if result is None:
            print("  ⚠ Comparison skipped (no previous prediction or no trading data).")
            return "skipped"

        print(f"  ✅ Daily accuracy: {result['daily_accuracy']:.2%}")
        return prediction_date


    @task
    def weekly_and_retrain(prediction_date: str):
        """
        On Friday: compute weekly accuracy summary.
        If avg accuracy < 50%: retrain the three 1D models.
        On other days: skip.
        """
        import pandas as pd
        from datetime import datetime

        today = pd.Timestamp(prediction_date)
        weekday = today.weekday()  # 0=Mon ... 4=Fri

        if weekday != 4:
            print(f"  Not Friday (weekday={weekday}). Skipping weekly summary.")
            return

        print("  📅 Friday — Computing weekly summary...")
        from utils.evaluation import weekly_summary

        result = weekly_summary(PROJECT_ROOT, today_str=prediction_date)

        if result is None:
            print("  ⚠ Insufficient data for weekly summary.")
            return

        if result["needs_retrain"]:
            print(f"\n  [WARN] Average accuracy {result['avg_accuracy']:.2%} < 50%")
            print("  [ACTION] Creating retrain flag file for host machine...")

            flag_path = os.path.join(PROJECT_ROOT, "data", "predictions", ".trigger_retrain")
            with open(flag_path, "w") as f:
                f.write(prediction_date)

            print(f"  [OK] Flag file created at: {flag_path}")
            print("  Host machine should monitor this file and run GPU retrain.")
        else:
            print(f"\n  [OK] Average accuracy {result['avg_accuracy']:.2%} >= 50%. No retrain needed.")


    t1 = wait_for_sync
    t2 = compute_features()
    t3 = run_predictions(t2)
    t4 = save_predictions(t3)
    t5 = compare_yesterday_task(t4)
    t6 = weekly_and_retrain(t5)

    t1 >> t2  
