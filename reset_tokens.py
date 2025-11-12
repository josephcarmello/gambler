import sqlite3

DB_FILE = "gambler.db"  # change if your db has a different name
BASE_TOKENS = 100

def reset_tokens():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    # Set every user's tokens back to BASE_TOKENS
    c.execute("UPDATE users SET tokens = ?", (BASE_TOKENS,))

    conn.commit()
    conn.close()
    print(f"✅ All users' tokens reset to {BASE_TOKENS}")

if __name__ == "__main__":
    reset_tokens()
