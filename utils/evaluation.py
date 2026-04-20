

import glob
import os
from datetime import datetime, timedelta

import numpy as np
import pandas as pd


# Daily Comparison: Yesterday's 1D Prediction vs Today's Actual

def compare_yesterday(project_root, today_str=None):
    """
    Compare yesterday's 1D predictions against actual price movement.

    Logic:
        1. Find the most recent prediction file before today
        2. Load actual close prices for pred_date and eval_date
        3. actual_1d = 1 if close_today > close_pred_date else 0
        4. Compare pred_1d vs actual_1d

    Args:
        project_root: Path to project root directory.
        today_str: Today's date as "YYYY-MM-DD". If None, auto-detect.

    Returns:
        dict with keys: eval_date, daily_accuracy, n_correct, n_total, df_comparison
        Returns None if no prediction file found.
    """
    pred_dir = os.path.join(project_root, "data", "predictions", "daily")
    comp_dir = os.path.join(project_root, "data", "predictions", "comparison")
    raw_path = os.path.join(project_root, "data", "raw_data.csv")

    os.makedirs(comp_dir, exist_ok=True)

    # ── Determine today's date ───────────────────────────────────────────────
    if today_str is None:
        today_str = datetime.now().strftime("%Y-%m-%d")
    today = pd.Timestamp(today_str)

    # ── Find most recent prediction file (before today) ──────────────────────
    pred_files = sorted(glob.glob(os.path.join(pred_dir, "*.csv")))
    prev_pred_file = None
    prev_pred_date = None

    for f in reversed(pred_files):
        fname = os.path.basename(f).replace(".csv", "")
        try:
            fdate = pd.Timestamp(fname)
            if fdate < today:
                prev_pred_file = f
                prev_pred_date = fname
                break
        except ValueError:
            continue

    if prev_pred_file is None:
        print("  [WARN] No previous prediction file found. Skipping comparison.")
        return None

    print(f"  Comparing predictions from {prev_pred_date} vs actual on {today_str}")

    # ── Load prediction ──────────────────────────────────────────────────────
    pred_df = pd.read_csv(prev_pred_file)

    # ── Load actual prices ───────────────────────────────────────────────────
    raw = pd.read_csv(raw_path, parse_dates=["date"])
    raw = raw.sort_values(["ticker", "date"]).reset_index(drop=True)

    # Get close prices for prediction date and today
    close_pred = raw[raw["date"] == prev_pred_date][["ticker", "close"]].rename(
        columns={"close": "close_pred"}
    )
    close_today = raw[raw["date"] == today_str][["ticker", "close"]].rename(
        columns={"close": "close_today"}
    )

    if close_today.empty:
        print(f"  [WARN] No trading data for {today_str}. Skipping comparison.")
        return None

    # ── Merge and compare ────────────────────────────────────────────────────
    comparison = pred_df[["ticker", "pred_1d", "ensemble_1d"]].copy()
    comparison["pred_date"] = prev_pred_date
    comparison["eval_date"] = today_str

    comparison = comparison.merge(close_pred, on="ticker", how="left")
    comparison = comparison.merge(close_today, on="ticker", how="left")

    # Drop tickers without both prices
    comparison = comparison.dropna(subset=["close_pred", "close_today"])

    comparison["actual_1d"] = (comparison["close_today"] > comparison["close_pred"]).astype(int)
    comparison["correct"] = (comparison["pred_1d"] == comparison["actual_1d"]).astype(int)

    # ── Accuracy ─────────────────────────────────────────────────────────────
    n_total   = len(comparison)
    n_correct = int(comparison["correct"].sum())
    accuracy  = n_correct / n_total if n_total > 0 else 0.0

    print(f"  Daily Accuracy: {accuracy:.2%} ({n_correct}/{n_total})")

    # ── Save comparison file ─────────────────────────────────────────────────
    output_cols = [
        "ticker", "pred_date", "eval_date",
        "pred_1d", "actual_1d", "correct", "ensemble_1d",
    ]
    comp_out = comparison[output_cols]
    comp_path = os.path.join(comp_dir, f"{today_str}.csv")
    comp_out.to_csv(comp_path, index=False)
    print(f"  Saved: {comp_path}")

    return {
        "eval_date": today_str,
        "daily_accuracy": accuracy,
        "n_correct": n_correct,
        "n_total": n_total,
        "df_comparison": comp_out,
    }


# Weekly Summary: Aggregate 5 Days of Comparisons

def weekly_summary(project_root, today_str=None):
    """
    Aggregate comparison files from the current week (Mon-Fri).
    Compute average accuracy for the week.

    Args:
        project_root: Path to project root.
        today_str: Today's date as "YYYY-MM-DD". If None, use datetime.now().

    Returns:
        dict with keys: week_label, avg_accuracy, daily_accuracies, n_days,
                        needs_retrain (True if avg < 50%)
        Returns None if insufficient data.
    """
    comp_dir = os.path.join(project_root, "data", "predictions", "comparison")
    week_dir = os.path.join(project_root, "data", "predictions", "weekly")
    os.makedirs(week_dir, exist_ok=True)

    if today_str is None:
        today_str = datetime.now().strftime("%Y-%m-%d")
    today = pd.Timestamp(today_str)

    # ── Find Monday of this week ─────────────────────────────────────────────
    monday = today - timedelta(days=today.weekday())

    # ── Collect comparison files from Mon to Fri ─────────────────────────────
    daily_accuracies = []
    all_comparisons = []

    for i in range(5):  # Mon=0 to Fri=4
        day = monday + timedelta(days=i)
        day_str = day.strftime("%Y-%m-%d")
        comp_file = os.path.join(comp_dir, f"{day_str}.csv")

        if os.path.exists(comp_file):
            df = pd.read_csv(comp_file)
            n_correct = int(df["correct"].sum())
            n_total   = len(df)
            acc = n_correct / n_total if n_total > 0 else 0.0

            daily_accuracies.append({
                "date": day_str,
                "accuracy": acc,
                "n_correct": n_correct,
                "n_total": n_total,
            })
            all_comparisons.append(df)

    if len(daily_accuracies) == 0:
        print("  [WARN] No comparison files found for this week.")
        return None

    # ── Compute average ──────────────────────────────────────────────────────
    avg_accuracy = np.mean([d["accuracy"] for d in daily_accuracies])
    week_label = f"{today.isocalendar()[0]}-W{today.isocalendar()[1]:02d}"
    needs_retrain = avg_accuracy < 0.50

    print(f"\n  ══════════════════════════════════════════")
    print(f"  Weekly Summary: {week_label}")
    print(f"  ══════════════════════════════════════════")
    for d in daily_accuracies:
        print(f"    {d['date']}: {d['accuracy']:.2%} ({d['n_correct']}/{d['n_total']})")
    print(f"  ──────────────────────────────────────────")
    print(f"  Average Accuracy : {avg_accuracy:.2%}")
    print(f"  Days with data   : {len(daily_accuracies)}/5")
    print(f"  Retrain needed   : {'YES' if needs_retrain else 'NO'}")

    # ── Save weekly summary ──────────────────────────────────────────────────
    summary_df = pd.DataFrame(daily_accuracies)
    summary_df.loc[len(summary_df)] = {
        "date": "AVERAGE",
        "accuracy": avg_accuracy,
        "n_correct": sum(d["n_correct"] for d in daily_accuracies),
        "n_total": sum(d["n_total"] for d in daily_accuracies),
    }
    summary_path = os.path.join(week_dir, f"{week_label}.csv")
    summary_df.to_csv(summary_path, index=False)
    print(f"  Saved: {summary_path}")

    return {
        "week_label": week_label,
        "avg_accuracy": avg_accuracy,
        "daily_accuracies": daily_accuracies,
        "n_days": len(daily_accuracies),
        "needs_retrain": needs_retrain,
    }
