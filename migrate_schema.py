import sqlite3
import os

def migrate():
    db_path = os.path.join('data', 'behave_sec.db')
    if not os.path.isfile(db_path):
        print(f"ERROR: Database not found at {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Define columns to add
    columns_to_add = [
        ("ip_address", "VARCHAR(45)"),
        ("risk_score", "FLOAT"),
        ("hijack_suspected", "BOOLEAN DEFAULT False")
    ]

    # Get current columns
    cursor.execute('PRAGMA table_info(sessions)')
    existing_columns = [row[1] for row in cursor.fetchall()]

    for col_name, col_type in columns_to_add:
        if col_name not in existing_columns:
            try:
                print(f"Adding column '{col_name}' to 'sessions' table...")
                cursor.execute(f"ALTER TABLE sessions ADD COLUMN {col_name} {col_type}")
                print(f"SUCCESS: Column '{col_name}' added.")
            except Exception as e:
                print(f"ERROR adding '{col_name}': {e}")
        else:
            print(f"INFO: Column '{col_name}' already exists.")

    conn.commit()
    conn.close()
    print("\nMigration complete.")

if __name__ == "__main__":
    migrate()
