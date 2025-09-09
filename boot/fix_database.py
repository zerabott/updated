#!/usr/bin/env python3
import sqlite3

def fix_database():
    conn = sqlite3.connect('confessions.db')
    cursor = conn.cursor()
    
    # Create reactions table
    print("Creating reactions table...")
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS reactions (
        reaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        target_type TEXT NOT NULL, -- "post" or "comment"
        target_id INTEGER NOT NULL,
        reaction_type TEXT NOT NULL, -- "like" or "dislike"
        timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, target_type, target_id),
        FOREIGN KEY(user_id) REFERENCES users(user_id)
    )''')
    
    # Create reports table
    print("Creating reports table...")
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS reports (
        report_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        target_type TEXT NOT NULL,
        target_id INTEGER NOT NULL,
        reason TEXT,
        timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(user_id)
    )''')
    
    conn.commit()
    
    # Verify tables were created
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name IN ('reactions', 'reports')")
    tables = cursor.fetchall()
    
    print(f"\nCreated tables: {[table[0] for table in tables]}")
    
    # Show schema of created tables
    for table_name in ['reactions', 'reports']:
        cursor.execute(f'SELECT sql FROM sqlite_master WHERE name="{table_name}"')
        result = cursor.fetchone()
        if result:
            print(f"\n{table_name.upper()} table schema:")
            print(result[0])
    
    conn.close()
    print("\nDatabase fix complete!")

if __name__ == "__main__":
    fix_database()
