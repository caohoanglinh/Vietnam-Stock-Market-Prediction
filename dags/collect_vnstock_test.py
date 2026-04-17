from datetime import datetime

from airflow.sdk import DAG, task


with DAG(
    dag_id="collect_vnstock_test",
    start_date=datetime(2026, 4, 1),
    schedule=None,
    catchup=False,
    tags=["vnstock", "test"],
):
    @task
    def test_vnstock_import():
        import vnstock

        print("vnstock import ok")
        print(vnstock.__file__)

    test_vnstock_import()
