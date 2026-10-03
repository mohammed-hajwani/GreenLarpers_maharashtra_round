import json
import tempfile
from pathlib import Path

from relearn.app.demo import SCRIPT_PATH, load_script, run_demo
from relearn.learner.store import LearnerStore
from relearn.models.loader import get_active_model
from relearn.pipeline import Tutor


def main() -> None:
    script = load_script()
    with tempfile.TemporaryDirectory() as tmp:
        tutor = Tutor(LearnerStore(Path(tmp) / "record.db"), get_active_model().model)
        steps = run_demo(tutor, script)
        tutor.store.conn.close()
    script["recorded_steps"] = json.loads(json.dumps(steps, default=str))
    SCRIPT_PATH.write_text(json.dumps(script, indent=2), encoding="utf-8")
    for s in steps:
        print(s["title"])


if __name__ == "__main__":
    main()
