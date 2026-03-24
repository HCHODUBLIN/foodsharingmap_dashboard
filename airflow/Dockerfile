FROM apache/airflow:2.8.1-python3.11

COPY requirements.txt /requirements.txt

ARG AIRFLOW_VERSION=2.8.1

RUN pip install --no-cache-dir \
    "apache-airflow==${AIRFLOW_VERSION}" \
    -r /requirements.txt \
    --constraint "https://raw.githubusercontent.com/apache/airflow/constraints-${AIRFLOW_VERSION}/constraints-3.11.txt"
