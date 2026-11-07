# Dataset card: ASSISTments

**Status: raw file present locally; provenance and terms are unverified.** No
ASSISTments rows are committed to this repository.

## Why this family

ASSISTments 2009-2010 (skill builder), 2015, and 2017 are the candidate datasets
for the initial MAML-KT reproduction and the shared CS-S benchmark. Pick **one**
version at the first integration meeting and record the decision here.

## Source and terms

- Official portal: <https://sites.google.com/site/assistmentsdata/>
- Secondary index (verify every claim against the official files):
  <https://pykt-toolkit.readthedocs.io/en/latest/datasets.html>
- The 2009-2010 skill-builder page states the data are free to use; papers must
  link to the data page. Record the exact terms and citation after acquisition.
- Do not acquire restricted data or any identifiable student records without
  permission. Report suspected PII instead of using it.

## Acquisition checklist

Fill this in when a file is obtained; leave unknown fields blank rather than
guessing.

| Field | Value |
| --- | --- |
| Version / school year | |
| Official URL | |
| Access date | |
| License / terms snapshot | |
| Required citation | |
| Raw file name(s) | |
| SHA-256 of each raw file | |
| Rows / students / questions / KCs | |
| Data dictionary source | |

## Canonical mapping

Map the official columns to the canonical contract only after reading the data
dictionary. Do not infer a mapping from column names alone.

| Canonical column | Source column | Notes |
| --- | --- | --- |
| `student_id` | `user_id` | Remapped to contiguous pseudonymous integers; source IDs are not output. |
| `interaction_id` | `order_id` | Preserved as a string; verified unique in the local raw file. |
| `step` | source row order | Counted per student in file order; source has no timestamp column. |
| `question_id` | `problem_id` | Remapped to contiguous integers. |
| `kc_ids` | `skill_id` | Remapped to integer strings; `NA` rows are excluded and counted. |
| `correct` | `correct` | Only exact `0` and `1` values are retained. |
| `timestamp` | — | Not present in the local raw file. |
| `question_text` | — | Not included in the adapter output. |

Run the adapter from the repository root (requires the project dependencies):

```bash
python3 scripts/adapt_assistments_2009.py
```

By default, it reads `data/raw/assistments_2009.csv` without modifying it and
writes `outputs/assistments_2009/canonical.csv`. It prints aggregate input,
output, and exclusion counts without printing source identifiers. Sequential
IDs are pseudonyms, not anonymization; keep the derived student-level file out
of Git as well.

## Known limitations to verify before use

- Null or duplicated IDs, and repeated attempts on the same question.
- Multi-skill items and whether the mapping is one-to-many.
- Whether `correct` means first attempt only.
- Timestamp coverage and granularity; check monotonicity per student.
- Students with very short histories; report support-size coverage.
- Any question text or KC metadata that is missing or license-restricted.
