#!/usr/bin/env python3
import sqlite3

def check_tables():
    conn = sqlite3.connect('bot.db')
    cursor = conn.cursor()
    
    # List all tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    print("All tables in database:")
    for table in tables:
        print(f"- {table[0]}")
    
    print("\n" + "="*50 + "\n")
    
    # Check reactions table
    cursor.execute('SELECT sql FROM sqlite_master WHERE name="reactions"')
    result = cursor.fetchone()
    if result:
        print("Reactions table schema:")
        print(result[0])
    else:
        print("Reactions table not found")
    
    print("\n" + "="*50 + "\n")
    
    # Check if there's a comment_reactions table instead
    cursor.execute('SELECT sql FROM sqlite_master WHERE name="comment_reactions"')
    result = cursor.fetchone()
    if result:
        print("Comment_reactions table schema:")
        print(result[0])
    else:
        print("Comment_reactions table not found")
    
    print("\n" + "="*50 + "\n")
    
    # Check reports table
    cursor.execute('SELECT sql FROM sqlite_master WHERE name="reports"')
    result = cursor.fetchone()
    if result:
        print("Reports table schema:")
        print(result[0])
    else:
        print("Reports table not found")
    
    conn.close()

if __name__ == "__main__":
    check_tables()
