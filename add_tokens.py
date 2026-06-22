#!/usr/bin/env python3
import argparse
import os
import sqlite3
import sys

DB_PATH = os.getenv("GAMBLER_DB_PATH", "gambler.db")


def add_tokens(amount: int, *, discord_id: int | None = None, minecraft_username: str | None = None, all_users: bool = False):
    if amount <= 0:
        raise ValueError("amount must be a positive integer")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    if all_users:
        cursor.execute("UPDATE users SET tokens = tokens + ?", (amount,))
        updated = cursor.rowcount
        conn.commit()
        conn.close()
        print(f"Added {amount} tokens to {updated} user(s)")
        return

    if discord_id is not None:
        cursor.execute("SELECT minecraft_username, tokens FROM users WHERE discord_id = ?", (discord_id,))
    else:
        cursor.execute(
            "SELECT discord_id, tokens FROM users WHERE LOWER(minecraft_username) = LOWER(?)",
            (minecraft_username,),
        )

    row = cursor.fetchone()
    if not row:
        conn.close()
        identifier = discord_id if discord_id is not None else minecraft_username
        raise LookupError(f"No user found matching {identifier!r}")

    if discord_id is not None:
        mc_name, old_tokens = row
        cursor.execute("UPDATE users SET tokens = tokens + ? WHERE discord_id = ?", (amount, discord_id))
        print(f"Added {amount} tokens to {mc_name} ({discord_id}): {old_tokens} -> {old_tokens + amount}")
    else:
        user_discord_id, old_tokens = row
        cursor.execute("UPDATE users SET tokens = tokens + ? WHERE discord_id = ?", (amount, user_discord_id))
        print(f"Added {amount} tokens to {minecraft_username} ({user_discord_id}): {old_tokens} -> {old_tokens + amount}")

    conn.commit()
    conn.close()


def parse_args():
    parser = argparse.ArgumentParser(description="Add tokens to gambler bot user(s).")
    parser.add_argument(
        "-a", "--amount",
        type=int,
        required=True,
        help="Number of tokens to add (must be positive)",
    )
    parser.add_argument(
        "-d", "--discord-id",
        type=int,
        help="Discord user ID",
    )
    parser.add_argument(
        "-u", "--username",
        help="Minecraft username",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Add tokens to every registered user",
    )
    parser.add_argument(
        "--db",
        default=DB_PATH,
        help=f"Path to gambler SQLite database (default: {DB_PATH})",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    global DB_PATH
    DB_PATH = args.db

    targets = sum([
        args.discord_id is not None,
        args.username is not None,
        args.all,
    ])
    if targets != 1:
        print("Specify exactly one target: --discord-id, --username, or --all", file=sys.stderr)
        sys.exit(1)

    try:
        add_tokens(
            args.amount,
            discord_id=args.discord_id,
            minecraft_username=args.username,
            all_users=args.all,
        )
    except (ValueError, LookupError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
