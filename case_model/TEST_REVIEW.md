# Test review — case model (AX-018a)

A critical pass over every test of the case model, added after the review
feedback of 15 October. For each test it answers two questions: what does it
prove, and does the right test go red when the code is broken on purpose?

Method: the mutation mindset. A test is only worth its green if a matching
break turns it red. Where a test could pass over a broken implementation, it is
noted and fixed.

## What was fixed

1. **Over-broad refusal guards.** Seven refusal tests caught `Exception`, which
   also passes on the wrong kind of failure (a `TypeError` from a bug would look
   like a correct refusal). They now catch `ValueError`, the module's documented
   refusal type — pydantic's `ValidationError` is a `ValueError`, so the ISO-date,
   `Money` and missing-field cases still match. Files: `test_case_model.py`
   (non-ISO date, missing employment field, dossier without a number),
   `test_format_rules.py` (formatted amount, thousands separator, two currency
   cases).
2. **Refusal tests that did not check nothing was stored.** The module rule is
   "a refusal test also asserts that nothing was stored."
   `test_unknown_organisation_is_refused` and
   `test_document_with_unknown_event_is_refused` now assert `case.personas == {}`
   and `case.documents == {}` after the refusal.

No production code changed; the schema is frozen at v1.

## What each test proves

### `test_case_model.py`
| Test | What it proves |
|---|---|
| test_ids_are_assigned_by_code | IDs are handed out by code, counting up (P001, P002) |
| test_event_references_persona_by_id | an event stores participant IDs, never names |
| test_unknown_persona_is_refused | an event with an unknown participant is refused and no event is stored |
| test_caller_supplied_id_is_refused | a caller-supplied `id=` is refused and no persona is stored |
| test_non_iso_date_is_refused | a non-ISO date is refused and no event is stored |
| test_persona_points_at_a_known_organisation | a professional persona may point at a known organisation (ORG-01) |
| test_unknown_organisation_is_refused | a persona pointing at an unknown organisation is refused and nothing is stored |
| test_employment_links_persona_and_organisation | employment links a persona and an organisation by ID |
| test_employment_missing_field_fails | employment with a missing required field is refused |
| test_document_with_unknown_event_is_refused | a document tied to an unknown event is refused and nothing is stored |
| test_dossier_needs_an_employee_number | a dossier without an employee number is refused |
| test_employee_number_must_be_six_digits | an employee number that is not six digits is refused |
| test_full_case_validates_in_one_call | a complete, consistent Case validates in one call |
| test_case_refuses_document_pointing_at_missing_event | a Case built with a document pointing at a missing event is refused |
| test_build_without_dossier_fails | `build()` without dossier facts is refused |

### `test_format_rules.py`
| Test | What it proves |
|---|---|
| test_the_five_types_have_a_pattern | the ID patterns cover exactly the five entity types |
| test_well_formed_id_is_accepted (5 cases) | each type's canonical ID shape is accepted |
| test_wrong_pattern_is_refused (12 cases) | wrong digit counts, wrong case and missing separators are refused |
| test_a_non_string_is_not_an_id | a non-string is never a valid ID |
| test_unknown_type_is_refused | an unknown entity type is refused |
| test_example_id_is_the_first_of_the_type | `example_id` returns the first ID of a type |
| test_next_id_counts_up_per_type | `next_id` counts up from the IDs already in use, per type |
| test_employee_number_is_six_digits | only a six-digit string is a valid employee number |
| test_reject_caller_id_passes_clean_input | input without an `id` is accepted |
| test_reject_caller_id_refuses_an_id | input that already carries an `id` is refused |
| test_money_takes_a_number_and_a_currency | `Money` holds a number plus a currency |
| test_money_accepts_a_plain_numeric_string | a plain numeric string is parsed to a number |
| test_formatted_amount_text_is_refused | a currency-formatted string is refused |
| test_thousands_separator_is_refused | a thousands separator is refused |
| test_currency_must_be_an_iso_code | a non-ISO currency code is refused |

### `test_reference_dossier.py`
| Test | What it proves |
|---|---|
| test_reference_dossier_loads_without_error | the reference dossier 100101 validates in one call |
| test_every_event_participant_exists | every event participant is a persona the case holds |
| test_five_documents_each_with_event_and_a_participant | five documents, each with its event and a participant |
| test_metadata_has_the_five_fields | document metadata carries AMEXIO's five fields |
| test_reference_dossier_matches_golden | the dossier's full export matches the frozen snapshot (AX-019) |

### `test_storage.py`
| Test | What it proves |
|---|---|
| test_round_trip_is_equal | save then load returns an equal Case |
| test_the_four_files_are_written | exactly the four documented files are written |
| test_files_are_valid_json_and_split_as_documented | the files are valid JSON split as documented |
| test_saving_is_stable | the same case saved twice gives identical bytes |

### `test_uniqueness.py`
| Test | What it proves |
|---|---|
| test_no_duplicate_ids_over_100_dossiers | over 100 dossiers, case numbers are unique and no `(case number, id)` pair repeats |

## Deliberate breaks checked

| Break in the code | Test that goes red |
|---|---|
| `next_id` always returns the first ID | test_ids_are_assigned_by_code, test_next_id_counts_up_per_type |
| drop the six-digit employee-number check | test_employee_number_must_be_six_digits |
| change a fact in the reference dossier | test_reference_dossier_matches_golden |
| accept a caller-supplied `id` | test_caller_supplied_id_is_refused |
| skip the save/load round trip's sorting | test_saving_is_stable |

## Known limits (kept on purpose)

- **Uniqueness is per dossier, not global.** IDs restart at P001 in every
  dossier, so uniqueness is checked for the `(case number, id)` pair, which is
  the team's design. A side effect: because each entity is stored in a dict
  keyed by its ID, a "constant ID" bug collapses entries instead of creating a
  duplicate, so `test_uniqueness` alone does not catch it — the counting tests
  (`test_ids_are_assigned_by_code`, `test_next_id_counts_up_per_type`) are the
  guard for that, as the mutation above confirms.
- **Behaviour, not wording.** Refusal tests check that the right type of error
  is raised, not the exact message text.

## Conclusion

For each of the 55 tests I can say in one sentence what it proves, and a
deliberate break makes the right test go red. AX-018a is closed.
