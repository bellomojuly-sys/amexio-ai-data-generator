"""Shared test data for the pipeline: the run request of contract v1.1 §3 (HR,
fictional company) and AMEXIO's example employees as seeds."""

import copy
import json
from pathlib import Path

import pytest

from pipeline.contracts import RunConfig, RunRequest

HERE = Path(__file__).resolve().parent
REQUEST = json.loads((HERE / "fixtures" / "run_request.json").read_text(encoding="utf-8"))
AMEXIO = json.loads((HERE.parent / "case_model" / "fixtures" / "generator" / "amexio_example"
                     / "employees.json").read_text(encoding="utf-8"))


@pytest.fixture
def request_data():
    """A fresh copy of the run request JSON, safe to break in a test."""
    return copy.deepcopy(REQUEST)


@pytest.fixture
def config(request_data):
    return RunConfig.model_validate(request_data["config"])


@pytest.fixture
def run_request(request_data):
    return RunRequest.model_validate(request_data)


@pytest.fixture
def amexio_employees():
    return copy.deepcopy(AMEXIO)
