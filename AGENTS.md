# AGENTS.md

## Repo state

- M0 data work is implemented; models and real datasets are not. Real ASSISTments
  data is **not** in the repo (`data/raw/` is gitignored). See
  `docs/dataset_cards/assistments.md`.
- `README.md` is the research protocol. Its layout is partly implemented:
  `src/ktlab/data/`, `tests/`, `docs/`, and `notebooks/01_data_eda.ipynb` exist;
  model/training/evaluation paths are still planned.
- No extra instruction files (`CLAUDE.md`, `.cursor/rules/`, `opencode.json`)
  exist. If tooling appears, trust the executable config over this file.

## Commands

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -t . -v
python -m ktlab.data --input tests/fixtures/synthetic_interactions.csv --out outputs/m0_fixture
```

- Stdlib only. Do not add runtime dependencies for the pipeline. `pytest` is not
  installed; tests use `unittest` and `tests/__init__.py` puts `src/` on the path
  (hence `-t .`).
- A real run needs a canonical CSV; the synthetic fixture is only a smoke test:
  `python -m ktlab.data --input data/raw/<dataset>.csv --out outputs/<experiment_id>`.
- There is no lint/typecheck/CI yet. Do not claim one exists.

## Data pipeline

- Entrypoint: `src/ktlab/data/cli.py`; contract and split semantics:
  `docs/protocols/cs_s_splits.md`; feature rules:
  `docs/protocols/feature_permissions.md`.
- Canonical columns: `student_id`, `interaction_id`, `step`, `question_id`,
  `kc_ids` (`;`-separated), `correct` (`0`/`1`), optional `timestamp` (ISO-8601)
  and `question_text`. Reuse these names; extra source columns are ignored.
- Invalid rows are rejected, never silently fixed. Default runs abort; use
  `--allow-invalid` only to inspect and drop bad rows, and always keep the
  report. `source_row` is the CSV record number starting at 2.
- Splits are whole-student and deterministic from `seed` + fractions. ID maps
  come from **training rows only**, with `__unk__ = 0`; val/test students are
  intentionally unmapped in CS-S.
- `cs_s_examples.csv` is the only place support and query roles are defined.
  Query labels must never influence support selection or adaptation.
- Outputs go under `outputs/` (gitignored). Never commit raw data, predictions,
  checkpoints, or generated EDA tables; commit manifest hashes instead.
- EDA is descriptive. `kc_transitions.csv` counts all ordered KC pairs between
  consecutive interactions, so multi-KC rows contribute multiple transitions.

## Writing and artifact conventions

- Prose, docstrings, and commit messages: English.
- Use `$$...$$` LaTeX and `mermaid` blocks as in `README.md`.
- Keep the README prediction-export columns and figure naming
  (`RQ<n>_F<nn>_<slug>.png`) when adding evaluation code.
- Notebook narrative order: question → hypothesis + diagram → code/checks →
  figures/metrics → interpretation → next falsifiable experiment.
- Commit locally on a non-`main` branch with Conventional Commits; never push,
  open a PR, merge, or rewrite history unless explicitly asked. Stage only files
  for the current task (no `git add -A`).

## Scientific rules

- Report CS-S (new student), CS-Q (new question), and CS-K (new concept)
  separately; student-level novelty is not global cold start.
- No leakage: no target-student fitting outside the support prefix, no query
  labels in training or adaptation, and label-dependent statistics fit on
  training data only.
- Separate paper reproduction from extensions; label conclusions as *proven*,
  *empirically supported*, or *unresolved*.
- Never treat attention weights, t-SNE clusters, or hidden dimensions as
  explanations of mastery; distinguish observed data, simulator truth, and
  model-derived quantities.
- Follow the milestone order (M0 protocol/EDA → M1 BKT/IRT → M2 MAML-KT); no
  architectural novelty before baselines exist.

## Verification before saying "done"

- Run the full test suite and the fixture pipeline; paste the real pass count.
- Exercise one bad input (missing column, bad label, duplicate step) and confirm
  it fails loudly rather than dropping data silently.
- Check `git status` for `outputs/`, `data/raw/`, and `__pycache__/` leaks.
