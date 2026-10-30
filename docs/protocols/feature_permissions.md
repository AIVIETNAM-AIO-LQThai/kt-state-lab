# Feature permission table

Every experiment must state which columns it uses. "Train-only" means fitted
without validation/test labels.

| Feature | CS-S (new student) | CS-Q (new question) | CS-K (new concept) | Notes |
| --- | --- | --- | --- | --- |
| `student_id` | no ID embedding for held-out students | train IDs only; unknown -> `__unk__` | train IDs only | CS-S holds out student identity |
| Past responses (before `t`) | support prefix for new students; otherwise full past | allowed | allowed | never include the current label |
| Current `question_id` | allowed if seen in train | no | allowed if seen | CS-Q holds out global question IDs |
| `kc_ids` | allowed if seen in train | allowed if seen | no | CS-K holds out global KCs |
| `question_text` | not used in M0 | only if protocol allows text | only if protocol allows text | check licensing |
| `timestamp` | optional | optional | optional | required to be monotonic per student |
| Item difficulty / frequency | fit on train only | train only; new items need a fallback | train only | never fit on query labels |
| Student ability / history stats | support prefix only for new students | train + support only | train + support only | no target-student test labels |
| `interaction_id` | never a model input | never | never | bookkeeping/provenance only |
| Teacher / school / class IDs | no | no | no | privacy and shortcut risk |

## Enforcement

The data pipeline rejects malformed rows and records unmapped IDs in the split
manifest. It does **not** enforce every model's feature budget; each experiment
must document its own allowed-input set and keep evaluation targets fixed.
