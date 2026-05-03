# Hackie

A Discord bot that acts as an AI project manager for hackathon teams. It tracks tasks, runs periodic check-ins, helps manage scope, and keeps your team focused on shipping.

## Features

- **Natural language interaction** — chat normally in the PM channel; the bot understands task updates, completions, blockers, and team changes without slash commands
- **Task tracking** — team members log what they're working on; the bot maintains a live project state in a markdown file
- **Periodic check-ins** — bot posts a brief status snapshot and asks the team for updates on a configurable interval
- **Rabbit hole detection** — flags anyone who has been on a task longer than a configurable threshold
- **Risk tracking** — team members report blockers; the bot assesses severity (HIGH / MED / LOW) and suggests mitigations
- **Scope guard** — when a new task is added, the bot evaluates whether it aligns with the demo goal or is scope creep
- **Multi-provider AI** — works with Anthropic (Claude) or any OpenAI-compatible API (OpenAI, Azure, Ollama, etc.)
- **Configurable** — check-in interval, rabbit hole threshold, and AI provider are all set in `config.json`; the check-in timer can also be changed via natural language at runtime

## Slash Commands

| Command                      | Description                                            |
| ---------------------------- | ------------------------------------------------------ |
| `/pm-setchannel`             | Set the current channel as the PM channel              |
| `/pm-init <goal> <deadline>` | Initialize a new project with a demo goal and deadline |
| `/pm-status`                 | Get a full project status report                       |
| `/pm-working <task>`         | Log what you're currently working on                   |
| `/pm-done <task>`            | Mark a task as completed                               |
| `/pm-add <task>`             | Add a task to the backlog                              |
| `/pm-risk <description>`     | Flag a risk or blocker                                 |
| `/pm-checkin`                | Trigger a manual check-in                              |
| `/pm-reset confirm:yes`      | Wipe the project state and start fresh                 |

## Natural Language Examples

In the PM channel, you can just talk normally:

- `"My team is Travis, Alice, and Bob"` → registers team members
- `"I'm working on the login page"` → updates your current task
- `"Bob finished the demo video"` → marks Bob's task complete
- `"We're building a music app, demo is a live Spotify integration"` → updates project info
- `"Blocked on the API rate limits"` → adds a HIGH/MED/LOW risk
- `"Change check-ins to every 30 minutes"` → updates the timer live

Tag the bot directly to ask questions: `@Hackie how much time is left?`

## Setup

### 1. Create a Discord bot

1. Go to [discord.com/developers/applications](https://discord.com/developers/applications) and create a new application
2. Navigate to **Bot** → click **Reset Token** and copy the token
3. Under **Privileged Gateway Intents**, enable **Message Content Intent**
4. Navigate to **OAuth2 → URL Generator**, select scopes: `bot`, `applications.commands`
5. Select permissions: `Send Messages`, `Read Message History`, `View Channels`, `Add Reactions`
6. Open the generated URL and add the bot to your server

### 2. Get an API key

- **Anthropic:** [console.anthropic.com](https://console.anthropic.com)
- **OpenAI:** [platform.openai.com](https://platform.openai.com)

### 3. Install and configure

```bash
git clone https://github.com/Travh98/hackie
cd hackie
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env and fill in DISCORD_TOKEN and your API key
```

### 4. Configure `config.json`

```json
{
  "provider": "anthropic",
  "model": "claude-sonnet-4-6",
  "checkin_interval_minutes": 60,
  "rabbit_hole_threshold_minutes": 90,
  "checkin_channel_id": null,
  "project_state_file": "project_state.md"
}
```

Set `provider` to `"openai"` to use OpenAI or any compatible API. Set `OPENAI_BASE_URL` in `.env` for Azure, Ollama, or other endpoints.

For faster slash command sync during development, add your server's ID to `.env`:

```
GUILD_ID=your_discord_server_id
```

### 5. Run

```bash
python bot.py
```

In Discord:

1. Run `/pm-setchannel` in the channel you want the bot to use
2. Run `/pm-init` with your demo goal and deadline
3. Tell the bot your team: `"My team is Alice, Bob, and Travis"`

## Customizing the AI behavior

The agent's instructions live in `system_prompt.md`. Edit this file to change how the bot communicates, what it tracks, or how it handles check-ins. Restart the bot after any changes.

## Deployment

The bot runs as a persistent process. For long-running deployments:

**Raspberry Pi / Linux server — systemd service:**

```ini
[Unit]
Description=Hackie Discord Bot

[Service]
WorkingDirectory=/path/to/hackie
ExecStart=/path/to/hackie/venv/bin/python bot.py
Restart=always

[Install]
WantedBy=multi-user.target
```

**Cloud:** Deploy to any platform that runs a persistent Python process (Railway, Fly.io, a VPS, etc.).

## Contributing

1. **Open an issue first** — describe the feature or bug before writing any code. We'll discuss the approach before any PR is opened.
2. Once the issue is approved, fork the repo and create a branch off `main`.
3. Make your changes and open a pull request referencing the issue.
