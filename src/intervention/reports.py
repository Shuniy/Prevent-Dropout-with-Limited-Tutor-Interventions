"""Save JSON results after complete serialization."""

import json
from pathlib import Path


def write_report(path: Path, report: dict) -> None:
    contents = json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(contents, encoding="utf-8")
    temporary.replace(path)
