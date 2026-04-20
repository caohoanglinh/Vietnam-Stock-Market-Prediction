import os
import time
import subprocess
import sys

# Configure paths
PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))
FLAG_FILE = os.path.join(PROJECT_ROOT, "data", "predictions", ".trigger_retrain")
CHECK_INTERVAL_SECONDS = 60  # Check every 60 seconds

def main():
    print("=" * 60)
    print(" VNSTOCK RETRAIN WATCHER (HOST/GPU MODE)")
    print("=" * 60)
    print(f"Monitoring  : {FLAG_FILE}")
    print(f"Interval    : {CHECK_INTERVAL_SECONDS} seconds")
    print(f"Environment : {sys.executable}")
    print("Press Ctrl+C to exit.")
    print("\nWaiting for retrain signal from Airflow...")

    try:
        while True:
            if os.path.exists(FLAG_FILE):
                print(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] FLAG DETECTED!")
                
                try:
                    with open(FLAG_FILE, "r") as f:
                        pred_date = f.read().strip()
                    print(f"[*] Trigger Date : {pred_date}")
                except Exception:
                    pass
                
                print("[*] Starting GPU retraining job...")
                print("-" * 60)
                
                # Execute retrain module
                try:
                    subprocess.run(
                        [sys.executable, "-m", "utils.retrain"], 
                        cwd=PROJECT_ROOT, 
                        check=True
                    )
                    print("-" * 60)
                    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [OK] Retraining finished successfully.")
                except subprocess.CalledProcessError as e:
                    print("-" * 60)
                    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [ERROR] Retraining failed (exit code {e.returncode}).")
                except Exception as e:
                    print("-" * 60)
                    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [ERROR] Could not start retrain script: {e}")
                
                # Clean up flag file
                print("[*] Removing flag file...")
                try:
                    os.remove(FLAG_FILE)
                except Exception as e:
                    print(f"[ERROR] Failed to remove flag file: {e}")

                print("\nWaiting for next signal...")

            time.sleep(CHECK_INTERVAL_SECONDS)

    except KeyboardInterrupt:
        print("\nWatcher stopped by user.")

if __name__ == "__main__":
    main()
