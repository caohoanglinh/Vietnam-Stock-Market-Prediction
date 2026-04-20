"""Integration test for the full prediction pipeline."""
import os
import pandas as pd

# Ensure we can import from project root
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.feature_engineering import prepare_featured_data, extract_inference_windows
from utils.inference import load_all_models, load_auc_weights, run_ensemble_predictions

print("=== INTEGRATION TEST ===")

print("1. Loading raw data...")
raw = pd.read_csv("data/raw_data.csv", parse_dates=["date"])
print(f"   {len(raw):,} rows, {raw['ticker'].nunique()} tickers")

print("2. Computing features...")
featured = prepare_featured_data(raw)
print(f"   Featured: {len(featured):,} rows")

print("3. Extracting windows...")
windows, pred_date, skipped = extract_inference_windows(featured)
print(f"   Windows: {len(windows)} tickers, date: {pred_date}")
if skipped:
    print(f"   Skipped: {skipped}")

print("4. Loading models...")
models = load_all_models("models")

print("5. Loading weights...")
weights = load_auc_weights("config/model_weights.json")

print("6. Running predictions...")
df = run_ensemble_predictions(windows, models, weights)
df["date"] = str(pred_date)

print(f"\n   Total predictions: {len(df)}")

# Save test output
os.makedirs("data/predictions/daily", exist_ok=True)
df.to_csv("data/predictions/daily/test_run.csv", index=False)
print("   Saved to data/predictions/daily/test_run.csv")

print("\n=== TOP 10 by consensus ===")
top = df.sort_values("consensus_votes", ascending=False).head(10)
for _, r in top.iterrows():
    print(f"   {r['ticker']:5s} | votes={r['consensus_votes']} | "
          f"{r['consensus_decision']:10s} | "
          f"1D={r['ensemble_1d']:.3f} 5D={r['ensemble_5d']:.3f} 10D={r['ensemble_10d']:.3f}")

print("\nDONE")
