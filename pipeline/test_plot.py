"""Step 3 · Plot (contract v1.1 §5): per case 1–10 slots with every closed-list
value decided by code, coherent with the case."""

import datetime as dt
import random

from pipeline.cm_id import cm_id
from pipeline.contracts import PersonasIn, PlotOutline
from pipeline.plot import outline_case, plot


def _cm(config, n=10):
    rows = [{"firstName": "Ada", "lastName": "Visser", "department": "IT", "position": "IT Manager"}]
    rows += [{"firstName": f"N{i}", "lastName": "Bos", "department": "IT",
              "position": "Software Developer"} for i in range(n - 1)]
    return cm_id(PersonasIn.model_validate({"employees": rows}), config)


def test_one_valid_outline_per_case(config):
    cm = _cm(config)
    outline = plot(cm, config)
    assert isinstance(outline, PlotOutline)
    assert [o.employee_number for o in outline.outlines] == [c.case_number for c in cm.cases]
    for o in outline.outlines:
        assert [s.slot for s in o.slots] == [f"S{i:02d}" for i in range(1, len(o.slots) + 1)]


def test_appraisals_only_in_years_the_employee_was_there(config):
    cm = _cm(config)
    for case, o in zip(cm.cases, plot(cm, config).outlines):
        hire = case.employments[0].start_date
        for s in o.slots:
            if s.type == "appraisal":
                assert hire < dt.date(s.year, 6, 30) <= config.as_of_date


def test_a_promotion_follows_an_exceeds_appraisal_and_a_better_position(config):
    cm = _cm(config, 10)
    found = False
    for seed in range(20):
        for o in plot(cm, config, seed).outlines:
            kinds = [s for s in o.slots if s.type == "contract_change" and s.change == "promotion"]
            if kinds:
                found = True
                ratings = [s.rating for s in o.slots if s.type == "appraisal"]
                assert ratings[-1] == "Exceeds expectations"
                assert kinds[0].new_position == "Senior Software Developer"
    assert found, "no promotion in 20 seeds: the rule never fires"


def test_a_temporary_contract_is_made_permanent_after_a_year(config):
    cm = _cm(config)
    for case, o in zip(cm.cases, plot(cm, config).outlines):
        job = case.employments[0]
        if job.contract_type == "Temporary" and (config.as_of_date - job.start_date).days >= 366:
            assert any(s.type == "contract_change" and s.change == "made_permanent" for s in o.slots)


def test_no_training_without_a_training_provider(request_data):
    from pipeline.contracts import RunConfig
    request_data["config"]["company"].pop("trainingProvider")
    config = RunConfig.model_validate(request_data["config"])
    for o in plot(_cm(config), config).outlines:
        assert not any(s.type == "training" for s in o.slots)


def test_a_new_hire_still_gets_one_slot(config):
    case = _cm(config).cases[0].model_copy(deep=True)
    case.employments[0].start_date = config.as_of_date - dt.timedelta(days=10)
    out = outline_case(case, config, random.Random(0))
    assert 1 <= len(out["slots"]) <= 10


def test_the_same_seed_gives_the_same_plot(config):
    cm = _cm(config)
    assert plot(cm, config, 5) == plot(cm, config, 5)
