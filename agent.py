import json
import os
import anthropic
from openai import AsyncOpenAI
from datetime import datetime
from state import StateManager

SYSTEM_PROMPT = """You are a Hackathon Project Manager AI helping a small team (1–7 people) ship on time.

## Responsibilities
- Track each team member's current task and progress
- Keep the team focused on the demo goal and deadline
- Run periodic check-ins: push a brief status snapshot, then ask what everyone is working on
- Detect rabbit holes: flag when someone has been on a task past the threshold
- Identify risks, help cut scope to meet the deadline

## Communication Style
- Discord markdown (bold, bullets, code blocks, @mentions)
- Short and direct — hackathon teams are busy, no fluff
- Encouraging but firm about the deadline

## State File Structure
You maintain a single markdown file as your memory. Always read it before acting, then write the
full updated file after any changes. The file must follow this structure exactly:

---
# [Project Name]

**Demo Goal:** [goal]
**Deadline:** [YYYY-MM-DD HH:MM]
**Last Updated:** [YYYY-MM-DD HH:MM]

## Team Members
| Member | Discord ID | Current Task | Task Started |
|--------|------------|--------------|--------------|
| Alice | 111222333 | Build login page | 2026-05-03 09:00 |

## Active Tasks
- [ ] Task name — *assigned: Alice* | *started: 2026-05-03 09:00*
- [ ] Task name — *unassigned*

## Completed Tasks
- [x] Task name — *completed by Alice at 2026-05-03 10:30*

## Risks
- **HIGH** Description of risk
- **MED** Description of risk
- **LOW** Description of risk

## Notes

---

State writing rules:
- Always update "Last Updated" to the current time when writing
- When a member starts a task: update their Team Members row AND add a started timestamp to the task entry
- When a task completes: move it to Completed Tasks with timestamp, clear their Current Task and Task Started columns
- Preserve all sections even if empty — use "*(none yet)*" as placeholder
- Never delete a team member row — just clear their task columns when they finish

## Rabbit Hole Detection
During check-ins, compare each member's Task Started time to now. If elapsed time exceeds the
configured threshold, flag them by name and suggest they timebox 15 more minutes then pivot or ask for help.

## Check-in Format
When running a check-in, output EXACTLY this structure — no more, no less:
Line 1: Status snapshot (e.g. "📊 3/8 tasks done · 5h left until deadline")
Line 2: Most critical flag OR "✅ All clear" (rabbit holes take priority, then HIGH risks, then deadline risk)
Line 3: @here quick check-in — what's everyone working on right now? Drop a reply 👇

Three lines only. Do not list individual tasks or people in the check-in message itself."""

# Tool definitions in a provider-neutral format
_TOOLS = [
    {
        "name": "read_project_state",
        "description": (
            "Read the current project state markdown file. "
            "Always call this first before making decisions or updates."
        ),
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "write_project_state",
        "description": (
            "Write the full updated project state markdown. "
            "Must include all sections. Always read first, then write."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "Complete markdown content for project_state.md",
                }
            },
            "required": ["content"],
        },
    },
    {
        "name": "get_current_time",
        "description": "Get the current date and time as YYYY-MM-DD HH:MM.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
]


def _to_anthropic_tools(tools: list) -> list:
    result = []
    for i, t in enumerate(tools):
        entry = {
            "name": t["name"],
            "description": t["description"],
            "input_schema": t["parameters"],
        }
        if i == len(tools) - 1:
            entry["cache_control"] = {"type": "ephemeral"}
        result.append(entry)
    return result


def _to_openai_tools(tools: list) -> list:
    return [
        {
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t["description"],
                "parameters": t["parameters"],
            },
        }
        for t in tools
    ]


class AnthropicBackend:
    def __init__(self, model: str):
        self.client = anthropic.AsyncAnthropic()
        self.model = model
        self.tools = _to_anthropic_tools(_TOOLS)

    async def run(self, prompt: str, process_tool_fn) -> str:
        messages = [{"role": "user", "content": prompt}]

        for _ in range(10):
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                system=[{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
                tools=self.tools,
                messages=messages,
            )

            if response.stop_reason == "end_turn":
                for block in response.content:
                    if hasattr(block, "text"):
                        return block.text
                return "Done."

            if response.stop_reason == "tool_use":
                messages.append({"role": "assistant", "content": response.content})
                tool_results = [
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": process_tool_fn(block.name, block.input),
                    }
                    for block in response.content
                    if block.type == "tool_use"
                ]
                messages.append({"role": "user", "content": tool_results})
            else:
                break

        return "Agent stopped — max iterations reached."


class OpenAIBackend:
    def __init__(self, model: str, base_url: str | None = None):
        self.client = AsyncOpenAI(base_url=base_url) if base_url else AsyncOpenAI()
        self.model = model
        self.tools = _to_openai_tools(_TOOLS)

    async def run(self, prompt: str, process_tool_fn) -> str:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]

        for _ in range(10):
            response = await self.client.chat.completions.create(
                model=self.model,
                tools=self.tools,
                messages=messages,
            )

            choice = response.choices[0]

            if choice.finish_reason == "stop":
                return choice.message.content or "Done."

            if choice.finish_reason == "tool_calls":
                messages.append(choice.message)
                for tc in choice.message.tool_calls:
                    result = process_tool_fn(tc.function.name, json.loads(tc.function.arguments))
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": result,
                    })
            else:
                break

        return "Agent stopped — max iterations reached."


class ProjectManagerAgent:
    def __init__(self, config: dict):
        self.config = config
        self.state = StateManager(config.get("project_state_file", "project_state.md"))
        self.rabbit_hole_threshold = config.get("rabbit_hole_threshold_minutes", 90)

        provider = config.get("provider", "anthropic").lower()
        model = config.get("model")

        if provider == "anthropic":
            self.backend = AnthropicBackend(model or "claude-sonnet-4-6")
        elif provider == "openai":
            base_url = os.getenv("OPENAI_BASE_URL")
            self.backend = OpenAIBackend(model or "gpt-4o", base_url)
        else:
            raise ValueError(f"Unknown provider '{provider}'. Use 'anthropic' or 'openai'.")

    def _process_tool(self, name: str, inputs: dict) -> str:
        if name == "read_project_state":
            print("[tool] read_project_state")
            return self.state.read()
        if name == "write_project_state":
            print("[tool] write_project_state")
            self.state.write(inputs["content"])
            return "State updated."
        if name == "get_current_time":
            print("[tool] get_current_time")
            return datetime.now().strftime("%Y-%m-%d %H:%M")
        print(f"[tool] unknown: {name}")
        return f"Unknown tool: {name}"

    async def _run(self, prompt: str) -> str:
        return await self.backend.run(prompt, self._process_tool)

    async def chat(self, user_name: str, user_id: str, message: str) -> str:
        return await self._run(
            f"**{user_name}** (Discord ID: {user_id}) says: {message}"
        )

    async def get_status(self) -> str:
        return await self._run(
            "Generate a project status report. Include: demo goal, deadline + time remaining, "
            "each team member's current task, tasks done vs total, active risks, top 3 next priorities. "
            "Discord markdown. Scannable, no walls of text."
        )

    async def task_done(self, user_name: str, user_id: str, task: str) -> str:
        return await self._run(
            f"**{user_name}** (ID: {user_id}) completed: \"{task}\". "
            "Update state: move to Completed Tasks with timestamp, clear their Team Members row. "
            "Reply with a brief acknowledgment and suggest their next priority from the backlog."
        )

    async def update_task(self, user_name: str, user_id: str, task: str) -> str:
        return await self._run(
            f"**{user_name}** (ID: {user_id}) is now working on: \"{task}\". "
            f"Rabbit hole threshold: {self.rabbit_hole_threshold} minutes. "
            "Update their Team Members row with the current timestamp. "
            "If the task seems like scope creep relative to the demo goal, flag it clearly. "
            "Reply with a brief acknowledgment."
        )

    async def add_task(self, user_name: str, task: str) -> str:
        return await self._run(
            f"**{user_name}** wants to add a task: \"{task}\". "
            "Evaluate whether it aligns with the demo goal or is scope creep. "
            "Add it to Active Tasks as unassigned. Reply with your evaluation."
        )

    async def add_risk(self, user_name: str, risk: str) -> str:
        return await self._run(
            f"**{user_name}** flagged a risk/blocker: \"{risk}\". "
            "Assess severity (HIGH/MED/LOW), add to Risks section, suggest a mitigation."
        )

    async def checkin(self) -> str:
        return await self._run(
            f"Periodic check-in triggered at {datetime.now().strftime('%H:%M')}. "
            f"Rabbit hole threshold: {self.rabbit_hole_threshold} minutes. "
            "Read the state. Compute elapsed time for each member's current task. "
            "Output the 3-line check-in message exactly as specified in your instructions."
        )

    async def init_project(self, goal: str, deadline: str) -> str:
        return await self._run(
            f"Initialize a new hackathon project:\n"
            f"- Demo Goal: {goal}\n"
            f"- Deadline: {deadline}\n"
            "Write a fresh project_state.md following the exact template. "
            "All sections present, all empty with placeholders. "
            "Reply with a welcome message: state the goal + deadline, "
            "tell the team to use `/pm-working <task>` to log what they start, "
            "`/pm-done <task>` when they finish, and just chat here for anything else."
        )
