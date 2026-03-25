"""DAG validation tests — ensure DAGs load without errors."""

import logging
import os
from contextlib import contextmanager

import pytest
from airflow.models import DagBag


@contextmanager
def suppress_logging(namespace):
    logger = logging.getLogger(namespace)
    old_value = logger.disabled
    logger.disabled = True
    try:
        yield
    finally:
        logger.disabled = old_value


def get_import_errors():
    with suppress_logging("airflow"):
        dag_bag = DagBag(include_examples=False)
    return [(None, None)] + [
        (os.path.relpath(k, os.environ.get("AIRFLOW_HOME", ".")), v.strip())
        for k, v in dag_bag.import_errors.items()
    ]


def get_dags():
    with suppress_logging("airflow"):
        dag_bag = DagBag(include_examples=False)
    return [
        (k, v, os.path.relpath(v.fileloc, os.environ.get("AIRFLOW_HOME", ".")))
        for k, v in dag_bag.dags.items()
    ]


@pytest.mark.parametrize(
    "rel_path,rv",
    get_import_errors(),
    ids=[x[0] for x in get_import_errors()],
)
def test_file_imports(rel_path, rv):
    """Every DAG file should import without errors."""
    if rel_path and rv:
        raise Exception(f"{rel_path} failed to import with message \n {rv}")


@pytest.mark.parametrize(
    "dag_id, dag, fileloc",
    get_dags(),
    ids=[x[0] for x in get_dags()],
)
def test_dag_has_tags(dag_id, dag, fileloc):
    """Every DAG should have at least one tag."""
    assert dag.tags, f"Dag {dag_id} ({fileloc}) has no tags."


@pytest.mark.parametrize(
    "dag_id, dag, fileloc",
    get_dags(),
    ids=[x[0] for x in get_dags()],
)
def test_dag_has_description(dag_id, dag, fileloc):
    """Every DAG should have a description."""
    assert dag.description, f"Dag {dag_id} ({fileloc}) has no description."


@pytest.mark.parametrize(
    "dag_id, dag, fileloc",
    get_dags(),
    ids=[x[0] for x in get_dags()],
)
def test_dag_has_retries(dag_id, dag, fileloc):
    """Every DAG should have retries configured."""
    for task in dag.tasks:
        assert task.retries > 0, (
            f"Task {task.task_id} in {dag_id} has no retries."
        )
