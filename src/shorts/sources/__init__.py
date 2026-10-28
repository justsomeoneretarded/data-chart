"""Try real sources in a sensible order. If none works, fail honestly — never invent data."""
from __future__ import annotations

import json
import logging
from pathlib import Path

from ..brief import Intent
from ..dataset import Dataset, DataError
from ..llm import LLMError
from . import owid, wikipedia

log = logging.getLogger(__name__)


def resolve(intent: Intent, brief: str, out: Path) -> Dataset:
    if intent.subject_type == "countries":
        order = [("Our World in Data", lambda: owid.retrieve(intent, out)),
                 ("Wikipedia", lambda: wikipedia.retrieve(intent, out, brief))]
    else:
        order = [("Wikipedia", lambda: wikipedia.retrieve(intent, out, brief))]
    attempts = []
    for name, attempt in order:
        log.info("Trying %s", name)
        try:
            dataset = attempt()
            attempts.append({"source": name, "status": "used"})
            (out / "source_attempts.json").write_text(json.dumps(attempts, indent=2))
            return dataset
        except (DataError, LLMError, KeyError, ValueError) as exc:
            log.warning("%s failed: %s", name, exc)
            attempts.append({"source": name, "status": "failed", "reason": str(exc)})
        except Exception as exc:  # network etc.
            log.exception("%s crashed", name)
            attempts.append({"source": name, "status": "error", "reason": f"{type(exc).__name__}: {exc}"})
    (out / "source_attempts.json").write_text(json.dumps(attempts, indent=2))
    reasons = "; ".join(f"{a['source']}: {a.get('reason')}" for a in attempts)
    raise DataError(f"No real data found for this brief ({reasons}). Try rephrasing the metric more plainly.")
