# Dataset card: ASSISTments

**Status: not acquired.** No ASSISTments rows are committed to this repository.

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
| `student_id` | | pseudonymous ID |
| `interaction_id` | | must be unique per row |
| `step` | | chronological within student, starting at 1 |
| `question_id` | | |
| `kc_ids` | | `;`-separated if multi-KC |
| `correct` | | 0/1 only |
| `timestamp` | | ISO-8601 if available |
| `question_text` | | optional; check licensing |

## Known limitations to verify before use

- Null or duplicated IDs, and repeated attempts on the same question.
- Multi-skill items and whether the mapping is one-to-many.
- Whether `correct` means first attempt only.
- Timestamp coverage and granularity; check monotonicity per student.
- Students with very short histories; report support-size coverage.
- Any question text or KC metadata that is missing or license-restricted.
