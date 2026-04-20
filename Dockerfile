FROM apache/airflow:3.2.0

COPY requirements-airflow.txt /requirements-airflow.txt
RUN pip install --no-cache-dir "apache-airflow==3.2.0" -r /requirements-airflow.txt

# PyTorch CPU-only for LSTM inference (keeps image ~200MB smaller than full CUDA)
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu
