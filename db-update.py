import sqlite3
import json

DB_PATH = '/data/scripts/gambler/gambler.db'
USERS_JSON_PATH = '/data/scripts/gambler/users.json'

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

with open(USERS_JSON_PATH, 'r') as f:
    users = json.load(f)

for user in users:
    discord_id = int(user['discord_id'])
    mc_name = user['minecraft_username']
    cursor.execute('''
        INSERT OR IGNORE INTO users (discord_id, minecraft_username, tokens, gains)
        VALUES (?, ?, ?, ?)
    ''', (discord_id, mc_name, 100, 0))

conn.commit()
conn.close()

