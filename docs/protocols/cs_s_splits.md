# CS-S split contract (M0)

This is the shared data contract for Workstream 1. All models must consume the
same manifest; do not regenerate splits privately.

## Input contract

Canonical CSV, UTF-8 (BOM accepted), one row per interaction:

| Column | Required | Rule |
| --- | --- | --- |
| `student_id` | yes | non-empty pseudonymous ID |
| `interaction_id` | yes | non-empty, unique per student |
| `step` | yes | integer >= 1, unique per student; defines chronological order |
| `question_id` | yes | non-empty |
| `kc_ids` | yes | one or more IDs, `;`-separated |
| `correct` | yes | exactly `0` or `1` |
| `timestamp` | no | ISO-8601; if present, non-decreasing when sorted by `step` |
| `question_text` | no | optional; check licensing |

Extra source-specific columns are allowed and ignored by the pipeline.

Invalid rows are **rejected, never silently fixed**. The default run validates the
whole file, reports all errors, and aborts. `--allow-invalid` drops bad rows and
records them in `data_quality.json`, but the run still fails if fewer than 3 valid
students remain.

Rejected cases include blank required fields, a non-integer `step`, `correct`
outside `{0,1}`, duplicate `(student_id, interaction_id)`, duplicate
`(student_id, step)`, unparseable timestamps, and timestamps that go backwards
within a student when ordered by `step`. Rows may appear out of order in the
file; `step` is the ordering key. `source_row` in error reports is the CSV record
number starting at 2.

## Student-disjoint split

- One student's full history goes to exactly one of `train`, `val`, or `test`.
- Students are sorted, shuffled with `random.Random(seed)`, then allocated as
  test, val, train. At least one student per split is required; the minimum
  viable dataset is 3 students.
- Fractions default to 0.1 / 0.1. Counts are rounded and bounded so train never
  becomes empty.
- The assignment depends only on the student list, seed, and fractions. It does
  not look at labels, question IDs, or KCs.
- `manifest.json` records the config, input SHA-256, per-file SHA-256, counts,
  unmapped-ID counts, and ID-map hash. JSON keys are sorted and no wall-clock
  time is written, so identical input + config produces identical manifest bytes.

## CS-S support/query examples

For every **val and test** student, and every requested support size `K`:

- support = first `K` interactions by `step`;
- query = all remaining interactions;
- `K = 0` means every interaction is a query;
- if `K >= history length`, that student/K pair emits no rows.

`cs_s_examples.csv` contains both roles, so support labels are available for
adaptation and query labels for evaluation. The same interaction appears once per
`K`. Never use query labels to choose a support prefix or adapt a model.

## ID maps

`id_maps.json` is built from **training rows only**:

```json
{"student": {"__unk__": 0, "...": 1}, "question": {...}, "kc": {...}}
```

Indices are 1-based after `__unk__ = 0`, assigned in sorted ID order. Validation
and test students are unmapped by design in CS-S; their counts appear under
`unmapped_ids`. Models that use ID embeddings must route unseen IDs to 0.

## Outputs

```text
outputs/<experiment_id>/
  data_quality.json
  splits/
    train.csv
    val.csv
    test.csv
    cs_s_examples.csv
    id_maps.json
    manifest.json
  eda/
    eda_summary.json
    sequence_lengths.csv
    correct_by_position.csv
    question_frequency.csv
    kc_frequency.csv
    kc_transitions.csv
```

`outputs/` is gitignored. Track the manifest and selected lightweight figures
instead of raw predictions or checkpoints.

## Commands

```powershell
$env:PYTHONPATH = "src"
python -m ktlab.data --input data/raw/assistments_2009.csv --out outputs/m0_assistments_2009
python -m unittest discover -s tests -t . -v
```

Smoke-test the pipeline without real data:

```powershell
python -m ktlab.data --input tests/fixtures/synthetic_interactions.csv --out outputs/m0_fixture
```

## Current limitations

- Only CS-S is implemented. Global CS-Q/CS-K holdouts wait for verified question
  and KC metadata.
- `question_text` is passed through but never used.
- EDA is descriptive; it is not evidence of mastery or causality.
- `kc_transitions.csv` counts every ordered KC pair between consecutive
  interactions, so multi-KC rows contribute multiple transitions.
- Random student assignment is not stratified by cohort or history length.
- The committed fixture is synthetic and must not be cited as empirical data.
