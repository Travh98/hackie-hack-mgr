from datetime import datetime
from pathlib import Path

DEFAULT_STATE = """\
# Hackathon Project

> **No project initialized.** Run `/pm-init` to set up your project.

## Team Members
| Member | Discord ID | Current Task | Task Started |
|--------|------------|--------------|--------------|

## Active Tasks
*(none yet)*

## Completed Tasks
*(none yet)*

## Risks
*(none yet)*

## Notes
*(none yet)*
"""


class StateManager:
    def __init__(self, file_path: str = "project_state.md"):
        self.file_path = Path(file_path)
        if not self.file_path.exists():
            self.file_path.write_text(DEFAULT_STATE, encoding="utf-8")

    def read(self) -> str:
        return self.file_path.read_text(encoding="utf-8")

    def write(self, content: str) -> None:
        self.file_path.write_text(content, encoding="utf-8")

    def get_deadline(self) -> datetime | None:
        for line in self.read().splitlines():
            if line.startswith("**Deadline:**"):
                raw = line.replace("**Deadline:**", "").strip()
                try:
                    return datetime.strptime(raw, "%Y-%m-%d %H:%M")
                except ValueError:
                    return None
        return None
