# H3 · Plot recheck against pipeline contract v1.1 §5 (20 Nov 2026)

Method: break one rule at a time in `pipeline/contracts.py` (C, the
`PlotOutline` contract) or `pipeline/plot.py` (P, the coherence of the plot),
run `pytest pipeline`, restore. Script: `docs/evidence/h3_break_each_rule.py`
(run from the repository root: `python3 docs/evidence/h3_break_each_rule.py .`).

Before H3, 3 contract rules (C12, C15, C17) and 7 plot rules (P2, P3, P5, P8,
P9, P10, P13) broke without any test failing, and 7 contract rules (C2, C3, C6,
C7, C9, C10, C14, C19) were caught only by the schema snapshot, which fails on
any change to the model, not for the rule. After H3 every break fails a test
named after its rule. `schema-snapshot` = `test_committed_schema_matches_the_model`.

```
C1 max 10 slots: CAUGHT by schema-snapshot, test_plot_outline_refuses_more_than_ten_slots
C2 at least 1 slot: CAUGHT by schema-snapshot, test_plot_outline_refuses_an_outline_without_slots
C3 slot key format S01: CAUGHT by schema-snapshot, schema-snapshot, test_plot_outline_refuses_a_slot_key_not_made_by_code
C4 slot keys unique: CAUGHT by test_plot_outline_refuses_two_slots_with_the_same_key
C5 no date on a slot: CAUGHT by schema-snapshot, test_plot_outline_refuses_a_date
C6 no participant on a slot: CAUGHT by schema-snapshot, test_plot_outline_refuses_a_participant
C7 no ID on a slot: CAUGHT by schema-snapshot, test_plot_outline_refuses_an_id_under_another_name
C8 rating closed list: CAUGHT by schema-snapshot, test_plot_outline_refuses_a_rating_outside_the_list
C9 termination reason closed list: CAUGHT by schema-snapshot, test_plot_outline_refuses_a_termination_reason_outside_the_list
C10 change kind closed list: CAUGHT by schema-snapshot, test_plot_outline_refuses_a_contract_change_kind_outside_the_list
C11 promotion needs newPosition: CAUGHT by test_plot_outline_refuses_a_promotion_without_new_position
C12 newPosition only on promotion: CAUGHT by test_plot_outline_refuses_a_new_position_without_a_promotion
C13 durationDays <= 5: CAUGHT by schema-snapshot, test_plot_outline_refuses_a_training_longer_than_five_days
C14 durationDays >= 1: CAUGHT by schema-snapshot, test_plot_outline_refuses_a_training_of_zero_days
C15 one termination: CAUGHT by test_plot_outline_refuses_two_terminations
C16 nothing after termination: CAUGHT by test_plot_outline_refuses_an_event_after_the_termination
C17 one outline per employee: CAUGHT by test_plot_outline_refuses_two_outlines_for_one_employee
C18 hire is not a slot: CAUGHT by schema-snapshot, test_plot_outline_refuses_hire_as_a_slot
C19 at least one outline: CAUGHT by schema-snapshot, test_plot_outline_refuses_an_empty_run
P1 appraisal only while employed: CAUGHT by test_a_fake_run_gives_valid_cases_that_load, test_the_trace_has_a_line_per_code_step_and_per_llm_call, test_the_reference_seed_keeps_its_facts, test_appraisals_only_in_years_the_employee_was_there
P2 at most 4 appraisals: CAUGHT by test_at_most_the_last_four_appraisals
P3 permanent only after a year: CAUGHT by test_a_temporary_contract_under_a_year_stays_temporary
P4 promotion only after Exceeds: CAUGHT by test_a_promotion_follows_an_exceeds_appraisal_and_a_better_position
P5 promotion to non-manager: CAUGHT by test_no_promotion_to_a_manager_position
P6 promotion to better-paid: CAUGHT by test_a_promotion_follows_an_exceeds_appraisal_and_a_better_position, test_no_promotion_to_a_manager_position
P7 training only with provider: CAUGHT by test_no_training_without_a_training_provider
P8 medical check after 2 years: CAUGHT by test_no_medical_check_before_two_years
P9 new hire gets one slot: CAUGHT by test_every_new_hire_gets_a_slot_whatever_the_seed
P10 drop oldest appraisal first: CAUGHT by test_over_ten_slots_the_oldest_appraisal_goes_first
P11 same seed same plot: CAUGHT by test_the_same_seed_gives_the_same_plot
P12 duration 1-5 picked: CAUGHT by test_a_fake_run_gives_valid_cases_that_load, test_the_trace_has_a_line_per_code_step_and_per_llm_call, test_the_reference_seed_keeps_its_facts, test_a_run_of_seeds_only_makes_no_personas_call, test_event_content_answers_every_slot_in_batches_of_5, test_a_missing_slot_gets_the_retry_then_fails, test_one_valid_outline_per_case, test_appraisals_only_in_years_the_employee_was_there, test_a_promotion_follows_an_exceeds_appraisal_and_a_better_position, test_a_temporary_contract_is_made_permanent_after_a_year, test_the_same_seed_gives_the_same_plot
P13 salary review after a year: CAUGHT by test_no_salary_review_in_the_first_year
```
