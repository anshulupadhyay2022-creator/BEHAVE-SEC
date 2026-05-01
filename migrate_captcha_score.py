"""
migrate_captcha_score.py
Adds `last_captcha_score` and `captcha_score_history` columns to the
`users` table in the existing SQLite database without deleting any data.

Run once:  python migrate_captcha_score.py
"""

import sqlite3
from pathlib import Path

DB_PATH = Path("data/behave_sec.db")

if not DB_PATH.exists():
    print(f"[SKIP] Database not found at {DB_PATH}. Run the backend first to create it.")
else:
    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()

    # Check existing columns
    cur.execute("PRAGMA table_info(users)")
    existing_cols = {row[1] for row in cur.fetchall()}
    print(f"[INFO] Existing columns: {existing_cols}")

    added = []
    if "last_captcha_score" not in existing_cols:
        cur.execute("ALTER TABLE users ADD COLUMN last_captcha_score REAL")
        added.append("last_captcha_score")
    if "captcha_score_history" not in existing_cols:
        cur.execute("ALTER TABLE users ADD COLUMN captcha_score_history TEXT")
        added.append("captcha_score_history")

    conn.commit()
    conn.close()

    if added:
        print(f"[OK] Added columns: {added}")
    else:
        print("[OK] All columns already exist — no changes needed.")
