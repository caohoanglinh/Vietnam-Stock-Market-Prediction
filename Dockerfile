FROM apache/airflow:3.2.0

COPY requirements-airflow.txt /requirements-airflow.txt
RUN pip install --no-cache-dir "apache-airflow==3.2.0" -r /requirements-airflow.txt
