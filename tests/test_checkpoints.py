from pathlib import Path

from engine.state.checkpoints import CheckpointStore
from engine.state.db import StateDB


def test_process_resume_state_persists(tmp_path: Path):
    db_path = tmp_path / "state.db"
    store = CheckpointStore(StateDB(db_path))
    store.save("run1", "task1", "RUNNING", {"step": 3})
    restored = CheckpointStore(StateDB(db_path)).resumable()
    assert restored[0]["state"] == "RUNNING"
    assert restored[0]["payload"]["step"] == 3
