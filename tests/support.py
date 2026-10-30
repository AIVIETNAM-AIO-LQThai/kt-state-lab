from pathlib import Path

FIXTURE = Path(__file__).parent / "fixtures" / "synthetic_interactions.csv"
HEADER = "student_id,interaction_id,step,question_id,kc_ids,correct,timestamp,question_text"


def row(
    student: str = "s1",
    interaction: str = "i1",
    step: int = 1,
    question: str = "q1",
    kcs: str = "kc1",
    correct: int = 1,
    timestamp: str = "2024-01-01T09:00:00Z",
    text: str = "",
) -> str:
    return f"{student},{interaction},{step},{question},{kcs},{correct},{timestamp},{text}"


def write_csv(text: str) -> Path:
    import tempfile

    handle = tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8", newline="")
    handle.write(text)
    handle.close()
    return Path(handle.name)
