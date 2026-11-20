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


# H3: the coherence rules of the plot, each with a test that fails for it.

class _Extreme:
    """A loaded die: always the most of everything. Every training, every
    "Exceeds expectations", every absence, so each rule surely fires."""

    def randint(self, a, b):
        return b

    def choices(self, population, weights, k):
        return [population[-1]] * k

    def random(self):
        return 0.0


def _case(config, years, contract="Permanent", position="Software Developer"):
    case = _cm(config).cases[1].model_copy(deep=True)
    job = case.employments[0]
    job.start_date = config.as_of_date - dt.timedelta(days=round(years * 365.25))
    job.contract_type = contract
    job.position = position
    return case


def _types(out):
    return [s["type"] for s in out["slots"]]


class _Calm(_Extreme):
    """The opposite die: no training, "Meets expectations", no absence, so
    the slots are few and the cut at ten slots cannot hide a rule."""

    def randint(self, a, b):
        return a

    def choices(self, population, weights, k):
        return [population[1]] * k

    def random(self):
        return 0.99


def test_at_most_the_last_four_appraisals(config):
    out = outline_case(_case(config, 10), config, _Calm())
    years = [s["year"] for s in out["slots"] if s["type"] == "appraisal"]
    assert years == [2023, 2024, 2025, 2026]


def test_over_ten_slots_the_oldest_appraisal_goes_first(config):
    out = outline_case(_case(config, 10, contract="Temporary"), config, _Extreme())
    assert len(out["slots"]) == 10
    assert [s["year"] for s in out["slots"] if s["type"] == "appraisal"] == [2024, 2025, 2026]
    assert "absence" in _types(out)


def test_a_temporary_contract_under_a_year_stays_temporary(config):
    out = outline_case(_case(config, 0.5, contract="Temporary"), config, _Extreme())
    assert not any(s.get("change") == "made_permanent" for s in out["slots"])


def test_no_salary_review_in_the_first_year(config):
    out = outline_case(_case(config, 0.5), config, _Extreme())
    assert not any(s.get("change") == "salary_review" for s in out["slots"])


def test_no_medical_check_before_two_years(config):
    out = outline_case(_case(config, 1.5), config, _Extreme())
    assert "medical_check" not in _types(out)


def test_no_promotion_to_a_manager_position(config):
    out = outline_case(_case(config, 5, position="Senior Software Developer"), config, _Extreme())
    assert not any(s.get("change") == "promotion" for s in out["slots"])


def test_every_new_hire_gets_a_slot_whatever_the_seed(config):
    case = _case(config, 10 / 365.25)
    for seed in range(20):
        assert outline_case(case, config, random.Random(seed))["slots"], f"seed {seed}"
