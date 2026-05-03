"""
Spot-check: would hackie have caught Travis's 4-hour microphone rabbit hole?

Scenario: SoundSense hackathon, 5-person team, 2-day project.
Travis has been on "Research microphone data acquisition from scratch" for 4 hours.
The rabbit hole threshold is 80 minutes.

We inject that state and fire a check-in to see what hackie says.
"""

import asyncio
import sys
import os

sys.stdout.reconfigure(encoding="utf-8")
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv

# Allow imports from the project root
root = Path(__file__).parent.parent
sys.path.insert(0, str(root))
load_dotenv(root / ".env")

from agent import ProjectManagerAgent

STATE_FILE = Path(__file__).parent / "test_state.md"
CONFIG = {
    "provider": "openai",
    "rabbit_hole_threshold_minutes": 80,
    "project_state_file": str(STATE_FILE),
}

DEADLINE = "2026-05-04 18:00"


def build_state(hours_on_task: float = 4.0) -> str:
    now = datetime.now()
    task_started = now - timedelta(hours=hours_on_task)
    fmt = "%Y-%m-%d %H:%M"

    return f"""\
# SoundSense

**Demo Goal:** Live caption wearable for the hearing impaired — live demo + 5-min pitch
**Deadline:** {DEADLINE}
**Last Updated:** {now.strftime(fmt)}

## Team Members

| Member  | Discord ID | Current Task                                        | Task Started         |
| ------- | ---------- | --------------------------------------------------- | -------------------- |
| Travis  | 111000001  | Research microphone data acquisition from scratch   | {task_started.strftime(fmt)} |
| Jordan  | 111000002  | Build caption overlay UI                            | {(now - timedelta(hours=1, minutes=20)).strftime(fmt)} |
| Priya   | 111000003  | Integrate speech-to-text API                        | {(now - timedelta(minutes=45)).strftime(fmt)} |
| Sam     | 111000004  | 3D-print wearable enclosure                         | {(now - timedelta(hours=2)).strftime(fmt)} |
| Morgan  | 111000005  | Write pitch deck                                    | {(now - timedelta(minutes=30)).strftime(fmt)} |

## Active Tasks

- [ ] Research microphone data acquisition from scratch — _assigned: Travis_ | _started: {task_started.strftime(fmt)}_
- [ ] Build caption overlay UI — _assigned: Jordan_ | _started: {(now - timedelta(hours=1, minutes=20)).strftime(fmt)}_
- [ ] Integrate speech-to-text API — _assigned: Priya_ | _started: {(now - timedelta(minutes=45)).strftime(fmt)}_
- [ ] 3D-print wearable enclosure — _assigned: Sam_ | _started: {(now - timedelta(hours=2)).strftime(fmt)}_
- [ ] Write pitch deck — _assigned: Morgan_ | _started: {(now - timedelta(minutes=30)).strftime(fmt)}_
- [ ] Source USB microphone — _unassigned_
- [ ] End-to-end integration test — _unassigned_
- [ ] Record demo video — _unassigned_

## Completed Tasks

_(none yet)_

## Risks

- **MED** Speech-to-text API latency may be too high for real-time captions

## Notes

Hackathon Day 2 of 2. Team is spread across hardware, software, and pitch prep.
"""


async def run():
    print("=" * 60)
    print("SCENARIO: Travis — 4-hour microphone rabbit hole")
    print(f"Threshold: {CONFIG['rabbit_hole_threshold_minutes']} min")
    print("=" * 60)
    print()

    STATE_FILE.write_text(build_state(hours_on_task=4.0), encoding="utf-8")
    print(f"[setup] Injected state -> {STATE_FILE.name}")
    print(f"[setup] Travis started mic task 4 hours ago")
    print()

    agent = ProjectManagerAgent(CONFIG)

    print("[hackie] Running check-in...\n")
    response = await agent.checkin()

    print("-" * 60)
    print(response)
    print("-" * 60)


if __name__ == "__main__":
    asyncio.run(run())
