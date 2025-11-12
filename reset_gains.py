import sqlite3

DB_FILE = "gambler.db"  # change this if your DB has a different name

def reset_gains():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    # Reset all users' gains to 0
    c.execute("UPDATE users SET gains = 0")

    conn.commit()
    conn.close()
    print("✅ All users' realized gains have been reset to 0")

if __name__ == "__main__":
    reset_gains()
