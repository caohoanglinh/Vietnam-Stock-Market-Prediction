# VN Stock Market Prediction

A complete, end-to-step machine learning pipeline designed to predict price movements in the Vietnamese stock market (HOSE/HNX). This project covers the entire ecosystem: from automated data collection and professional-grade feature engineering to multi-model training and workflow orchestration using Apache Airflow.

## 🚀 Project Overview

The core objective is to predict directional price movements (Up/Down) for approximately 100 high-liquidity Vietnamese stocks across three distinct horizons: **1-Day, 5-Day, and 10-Day**. By combining classical technical analysis with modern machine learning, we aim to build a system that identifies stable trading signals.

## 🛠️ Key Components

### 1. Data Pipeline (`collect_data.ipynb`)
- **Acquisition**: Seamless extraction of historical OHLCV data using the `vnstock` library.
- **Feature Engineering**: Computation of 13 technical indicators (RSI, ATR, OBV, MACD, Bollinger Bands, EMA Ratios, etc.).
- **Data Quality**: Professional cleaning including 1st-99th percentile outlier clipping (Winsorization) and sliding window preparation.
- **Global Scale**: Processes 100 tickers simultaneously, generating both a unified `total_stocks.csv` and individual ticker files.

### 2. Model Zoo
We implement and benchmark three major architectures to find the best fit for financial time-series:
- **Random Forest (`train_RF_2.ipynb`)**: Utilizes a 20-day flattened sliding window (320 features) and dynamic class weighting to address market imbalances.
- **XGBoost (`train_XGBoost.ipynb`)**: A robust tree ensemble optimized with walk-forward validation to simulate real-world trading performance.
- **LSTM (`train_LSTM.ipynb`)**: A Deep Learning approach using PyTorch, specifically designed to capture non-linear temporal dependencies across sequences.

### 3. Analysis & Explainability
- **Feature Matrices**: High-resolution heatmaps that visualize "importance over time," showing which indicators the models prioritize most.
- **Distribution Analysis**: Automated monitoring of Buy/Sell ratios across horizons to ensure the model isn't "afraid" to predict buys.

### 4. Automation & MLOps
- **Airflow Orchestration**: Full environment setup using Dockerized Apache Airflow 3.x to automate the daily collection and retraining cycle.
- **Secure Configuration**: Credential management using `.env` files and custom Docker images with specific library dependencies.

## 📦 Getting Started

### Setup
1. **Clone the repo** to your local machine.
2. **Environment**: Create a `.env` file (see `.env.example`) and add your `VNSTOCK_API_KEY`.
3. **Libraries**:
   ```bash
   pip install -r requirements.txt
   ```

### Execution
- **Run the pipeline**: Open `collect_data.ipynb` and run all cells to build your dataset.
- **Train Models**: Execute any of the `train_*.ipynb` notebooks to generate models in the `models/` directory.
- **Automate**: Run `docker compose build` to build image.
- **Init database**: Run `docker compose up airflow-init` to init database.
- **Run Airflow**: Run `docker compose up -d airflow-apiserver airflow-scheduler airflow-dag-processor airflow-triggerer` to start the Airflow automation suite.
- **Open UI**: http://localhost:8080 and login


## 📁 Repository Structure
- `data/`: Contains raw data and processed feature sets.
- `models/`: Serialized model weights (`.pkl`, `.pt`) and feature configurations.
- `img/`: Distribution plots and feature importance matrices.
- `dags/`: Airflow task definitions for automated workflows.
- `AIRFLOW_SETUP.md`: Detailed documentation for the Dockerized Airflow environment.

---
**Disclaimer**: *This project is for research and educational purposes. Trading in the stock market involves high risk. Past performance does not guarantee future results.*
