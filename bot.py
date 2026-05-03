import json
import os
import discord
from discord import app_commands
from discord.ext import commands
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv
from agent import ProjectManagerAgent

load_dotenv()

CONFIG_PATH = "config.json"


def load_config() -> dict:
    with open(CONFIG_PATH) as f:
        return json.load(f)


def save_config(config: dict) -> None:
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)


def split_message(text: str, limit: int = 2000) -> list[str]:
    if len(text) <= limit:
        return [text]
    chunks = []
    while text:
        if len(text) <= limit:
            chunks.append(text)
            break
        split_at = text.rfind("\n", 0, limit)
        if split_at == -1:
            split_at = limit
        chunks.append(text[:split_at])
        text = text[split_at:].lstrip("\n")
    return chunks


async def send_chunks(target, chunks: list[str], first_fn=None) -> None:
    """Send a list of chunks. first_fn overrides how the first chunk is sent."""
    for i, chunk in enumerate(chunks):
        if i == 0 and first_fn:
            await first_fn(chunk)
        else:
            await target.send(chunk)


config = load_config()
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)
agent = ProjectManagerAgent(config)
scheduler = AsyncIOScheduler()
_scheduler_started = False


async def do_checkin() -> None:
    channel_id = config.get("checkin_channel_id")
    if not channel_id:
        return
    channel = bot.get_channel(int(channel_id))
    if not channel:
        return
    try:
        response = await agent.checkin()
        for chunk in split_message(response):
            await channel.send(chunk)
    except Exception as e:
        print(f"[checkin error] {e}")


@bot.event
async def on_ready() -> None:
    global _scheduler_started
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")

    guild_id = os.getenv("GUILD_ID")
    try:
        if guild_id:
            guild = discord.Object(id=int(guild_id))
            bot.tree.copy_global_to(guild=guild)
            synced = await bot.tree.sync(guild=guild)
        else:
            synced = await bot.tree.sync()
        print(f"Synced {len(synced)} slash commands")
    except Exception as e:
        print(f"[sync error] {e}")

    if not _scheduler_started:
        interval = config.get("checkin_interval_minutes", 60)
        scheduler.add_job(do_checkin, "interval", minutes=interval, id="checkin")
        scheduler.start()
        _scheduler_started = True
        print(f"Check-ins scheduled every {interval} minute(s)")


@bot.event
async def on_message(message: discord.Message) -> None:
    if message.author.bot:
        return

    channel_id = config.get("checkin_channel_id")
    in_pm_channel = channel_id and str(message.channel.id) == str(channel_id)
    mentioned = bot.user in message.mentions

    if not (in_pm_channel or mentioned):
        await bot.process_commands(message)
        return

    # Strip bot mentions from content
    content = message.content
    for user in message.mentions:
        content = content.replace(f"<@{user.id}>", "").replace(f"<@!{user.id}>", "")
    content = content.strip()

    if not content:
        await bot.process_commands(message)
        return

    async with message.channel.typing():
        try:
            response = await agent.chat(
                user_name=message.author.display_name,
                user_id=str(message.author.id),
                message=content,
            )
        except Exception as e:
            response = f"❌ Agent error: {e}"

    chunks = split_message(response)
    await send_chunks(message.channel, chunks, first_fn=message.reply)
    await bot.process_commands(message)


# ── Slash commands ──────────────────────────────────────────────────────────────

@bot.tree.command(name="pm-setchannel", description="Set this channel as the PM check-in channel")
async def pm_setchannel(interaction: discord.Interaction) -> None:
    config["checkin_channel_id"] = str(interaction.channel_id)
    save_config(config)
    interval = config.get("checkin_interval_minutes", 60)
    await interaction.response.send_message(
        f"✅ PM channel set. Check-ins will post here every **{interval} min**.\n"
        f"Run `/pm-init` to configure your project goal and deadline."
    )


@bot.tree.command(name="pm-init", description="Initialize or reset the hackathon project")
@app_commands.describe(
    goal="The end demo goal (e.g. 'Live demo + 5-min pitch')",
    deadline="Deadline: YYYY-MM-DD HH:MM",
)
async def pm_init(interaction: discord.Interaction, goal: str, deadline: str) -> None:
    await interaction.response.defer()
    try:
        response = await agent.init_project(goal=goal, deadline=deadline)
    except Exception as e:
        response = f"❌ Error: {e}"
    chunks = split_message(response)
    await send_chunks(interaction.channel, chunks, first_fn=interaction.followup.send)


@bot.tree.command(name="pm-status", description="Get a project status report")
async def pm_status(interaction: discord.Interaction) -> None:
    await interaction.response.defer()
    try:
        response = await agent.get_status()
    except Exception as e:
        response = f"❌ Error: {e}"
    chunks = split_message(response)
    await send_chunks(interaction.channel, chunks, first_fn=interaction.followup.send)


@bot.tree.command(name="pm-working", description="Log what you're currently working on")
@app_commands.describe(task="What are you working on right now?")
async def pm_working(interaction: discord.Interaction, task: str) -> None:
    await interaction.response.defer()
    try:
        response = await agent.update_task(
            user_name=interaction.user.display_name,
            user_id=str(interaction.user.id),
            task=task,
        )
    except Exception as e:
        response = f"❌ Error: {e}"
    await interaction.followup.send(response[:2000])


@bot.tree.command(name="pm-done", description="Mark a task as completed")
@app_commands.describe(task="What did you just finish?")
async def pm_done(interaction: discord.Interaction, task: str) -> None:
    await interaction.response.defer()
    try:
        response = await agent.task_done(
            user_name=interaction.user.display_name,
            user_id=str(interaction.user.id),
            task=task,
        )
    except Exception as e:
        response = f"❌ Error: {e}"
    await interaction.followup.send(response[:2000])


@bot.tree.command(name="pm-add", description="Add a task to the project backlog")
@app_commands.describe(task="Task description")
async def pm_add(interaction: discord.Interaction, task: str) -> None:
    await interaction.response.defer()
    try:
        response = await agent.add_task(
            user_name=interaction.user.display_name,
            task=task,
        )
    except Exception as e:
        response = f"❌ Error: {e}"
    await interaction.followup.send(response[:2000])


@bot.tree.command(name="pm-risk", description="Flag a risk or blocker")
@app_commands.describe(risk="Describe the risk or blocker")
async def pm_risk(interaction: discord.Interaction, risk: str) -> None:
    await interaction.response.defer()
    try:
        response = await agent.add_risk(
            user_name=interaction.user.display_name,
            risk=risk,
        )
    except Exception as e:
        response = f"❌ Error: {e}"
    await interaction.followup.send(response[:2000])


@bot.tree.command(name="pm-checkin", description="Trigger a manual team check-in")
async def pm_checkin(interaction: discord.Interaction) -> None:
    await interaction.response.defer()
    try:
        response = await agent.checkin()
    except Exception as e:
        response = f"❌ Error: {e}"
    await interaction.followup.send(response[:2000])


bot.run(os.getenv("DISCORD_TOKEN"))
