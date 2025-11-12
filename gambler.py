import discord
from discord.ext import commands
from discord import app_commands
import sqlite3
import json
import logging
import os
import random
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
try:
    MINECRAFT_CHANNEL_ID = int(os.getenv("MINECRAFT_CHANNEL_ID"))
    HUMBLER_WEBHOOK_ID = int(os.getenv("HUMBLER_WEBHOOK_ID"))
except (ValueError, TypeError):
    print("ERROR: One of your IDs in the .env file is missing or not a number.")
    exit()

DB_PATH = os.getenv("GAMBLER_DB_PATH", "gambler.db")
USERS_JSON_PATH = os.getenv("USERS_JSON_PATH", "users.json")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def initialize_database():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            discord_id INTEGER PRIMARY KEY,
            minecraft_username TEXT NOT NULL,
            tokens INTEGER NOT NULL,
            gains INTEGER DEFAULT 0
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bets (
            user_id INTEGER PRIMARY KEY,
            voted_for TEXT NOT NULL,
            voted_for_display TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS state (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    ''')

    cursor.execute("PRAGMA table_info(bets)")
    columns = [col[1] for col in cursor.fetchall()]
    if "voted_for_display" not in columns:
        cursor.execute("ALTER TABLE bets ADD COLUMN voted_for_display TEXT")
        cursor.execute("UPDATE bets SET voted_for_display = voted_for WHERE voted_for_display IS NULL")

    conn.commit()
    conn.close()

def load_minecraft_users_for_choices():
    try:
        with open(USERS_JSON_PATH, 'r') as f:
            users = json.load(f)
            return [
                app_commands.Choice(name=user['minecraft_username'], value=user['minecraft_username'])
                for user in users
            ]
    except FileNotFoundError:
        logging.error(f"CRITICAL: users.json not found at path: {USERS_JSON_PATH}")
        return []

def load_current_minecraft_usernames():
    try:
        with open(USERS_JSON_PATH, 'r') as f:
            users = json.load(f)
            return [user['minecraft_username'].lower() for user in users]
    except FileNotFoundError:
        logging.error(f"CRITICAL: users.json not found at path: {USERS_JSON_PATH}")
        return []

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.webhooks = True

bot = commands.Bot(command_prefix="!!!!!!!!", intents=intents)
tree = bot.tree

gambler = app_commands.Group(name="gambler", description="Commands for the gambler bot")

@bot.event
async def on_ready():
    logging.info(f'{bot.user} has connected to Discord!')
    initialize_database()
    try:
        synced = await bot.tree.sync()
        logging.info(f"Synced {len(synced)} command(s)")
    except Exception as e:
        logging.error(f"Failed to sync commands: {e}")

async def player_autocomplete(interaction: discord.Interaction, current: str):
    try:
        with open(USERS_JSON_PATH, 'r') as f:
            users = json.load(f)
            choices = [
                app_commands.Choice(name=user['minecraft_username'], value=user['minecraft_username'])
                for user in users if current.lower() in user['minecraft_username'].lower()
            ]
            return choices[:25]  # Discord limits to max 25
    except FileNotFoundError:
        return []


@gambler.command(name="vote", description="Vote for who you think will die next.")
@app_commands.describe(player="The Minecraft username of the player you want to vote for.")
@app_commands.autocomplete(player=player_autocomplete)
async def vote(interaction: discord.Interaction, player: str):
    discord_id = interaction.user.id
    guess = player.strip().lower()

    current_players = load_current_minecraft_usernames()

    if guess not in current_players:
        await interaction.response.send_message("That player isn't currently listed in users.json.", ephemeral=True)
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT minecraft_username FROM users WHERE discord_id = ?", (discord_id,))
    row = cursor.fetchone()

    if not row or not row[0]:
        await interaction.response.send_message("You haven't registered your Minecraft username.", ephemeral=True)
        conn.close()
        return

    mc_username = row[0].lower()
    if guess == mc_username:
        await interaction.response.send_message("You cannot vote for yourself!", ephemeral=True)
        conn.close()
        return

    # Check if user already voted this round
    cursor.execute("SELECT voted_for_display FROM bets WHERE user_id = ?", (discord_id,))
    existing_vote = cursor.fetchone()
    if existing_vote:
        await interaction.response.send_message(f"You have already voted for **{existing_vote[0]}** this round!", ephemeral=True)
        conn.close()
        return

    # Debit 10 tokens and register the vote
    cursor.execute("SELECT tokens FROM users WHERE discord_id = ?", (discord_id,))
    tokens_row = cursor.fetchone()
    if not tokens_row or tokens_row[0] < 10:
        await interaction.response.send_message("You don't have enough tokens (10 required) to vote.", ephemeral=True)
        conn.close()
        return

    cursor.execute("UPDATE users SET tokens = tokens - 10 WHERE discord_id = ?", (discord_id,))
    cursor.execute("REPLACE INTO bets (user_id, voted_for, voted_for_display) VALUES (?, ?, ?)", (discord_id, guess, player.strip()))
    conn.commit()
    conn.close()

    await interaction.response.send_message(f"You voted for **{player.strip()}** to die next. 10 tokens have been deducted from your wallet.", ephemeral=True)


@gambler.command(name="wallet", description="View your current token balance.")
async def wallet(interaction: discord.Interaction):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT tokens, gains FROM users WHERE discord_id = ?", (interaction.user.id,))
    user_data = cursor.fetchone()
    conn.close()

    if not user_data:
        await interaction.response.send_message("You are not registered yet. Place a vote first!", ephemeral=True)
        return

    tokens, gains = user_data
    await interaction.response.send_message(
        f"You currently have **{tokens}** tokens.\nYour total realized gains: **{gains}** tokens.",
        ephemeral=True
    )


@gambler.command(name="scoreboard", description="See everyone's wallet balances.")
async def scoreboard(interaction: discord.Interaction):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT minecraft_username, tokens FROM users ORDER BY tokens DESC")
    all_users = cursor.fetchall()
    conn.close()

    scoreboard = "\n".join([f"**{name}** : {tokens} tokens" for name, tokens in all_users])
    await interaction.response.send_message(f"🏆 **Scoreboard** 🏆\n{scoreboard}", ephemeral=False)


bot.tree.add_command(gambler)

@bot.event
async def on_message(message):
    if message.channel.id == MINECRAFT_CHANNEL_ID and message.webhook_id == HUMBLER_WEBHOOK_ID:
        if message.embeds:
            embed = message.embeds[0]
            if embed.description:
                deceased_player = embed.description.split()[0]
                await process_death(message.channel, deceased_player)
    await bot.process_commands(message)


async def process_death(channel, deceased_player):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("INSERT OR REPLACE INTO state (key, value) VALUES (?, ?)", ("last_death", deceased_player))

    cursor.execute("SELECT user_id FROM bets WHERE voted_for = ?", (deceased_player.lower(),))
    winners = cursor.fetchall()
    cursor.execute("SELECT * FROM bets")
    all_bets = cursor.fetchall()

    if not all_bets:
        await channel.send(f"**{deceased_player}** has died, but no bets were placed for this round.")
        conn.close()
        return

    pot_size = len(all_bets) * 10 + 10 + random.randint(5, 10)
    if winners:
        winnings_per_winner = pot_size // len(winners)
        winner_mentions = []
        for (winner_id,) in winners:
            cursor.execute("UPDATE users SET tokens = tokens + ?, gains = gains + ? WHERE discord_id = ?",
                           (winnings_per_winner, winnings_per_winner, winner_id))
            user = await bot.fetch_user(winner_id)
            winner_mentions.append(user.mention)
        await channel.send(f"**{deceased_player}** has tragically died! The following players have won {winnings_per_winner} tokens each: {', '.join(winner_mentions)}")
    else:
        await channel.send(f"**{deceased_player}** has died! No one correctly predicted this outcome. **{pot_size}** tokens have been lost to the void.")

    cursor.execute("DELETE FROM bets")
    conn.commit()
    conn.close()


if BOT_TOKEN:
    bot.run(BOT_TOKEN)
else:
    print("ERROR: BOT_TOKEN not found in .env file. Bot cannot start.")
