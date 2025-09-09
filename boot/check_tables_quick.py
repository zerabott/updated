import sqlite3

conn = sqlite3.connect('confessions.db')
c = conn.cursor()
c.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [table[0] for table in c.fetchall()]
print("Available tables:")
for table in tables:
    print(f"  - {table}")

# Check if comment_reactions table exists
if 'comment_reactions' in tables:
    print("\ncomment_reactions table exists")
else:
    print("\ncomment_reactions table does NOT exist")
    
# Check reactions table structure
if 'reactions' in tables:
    print("\nreactions table schema:")
    c.execute("PRAGMA table_info(reactions)")
    for column in c.fetchall():
        print(f"  - {column}")

conn.close()
