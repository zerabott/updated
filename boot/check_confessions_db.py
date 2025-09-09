#!/usr/bin/env python3
import sqlite3

def check_confessions_db():
    conn = sqlite3.connect('confessions.db')
    cursor = conn.cursor()
    
    # List all tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    print("All tables in confessions.db:")
    for table in tables:
        print(f"- {table[0]}")
    
    print("\n" + "="*50 + "\n")
    
    # Check if reports and reactions tables exist now
    if ('reports',) in tables:
        print("Reports table exists!")
        # Check if there are any reports
        cursor.execute("SELECT COUNT(*) FROM reports")
        count = cursor.fetchone()[0]
        print(f"Number of reports: {count}")
        
        if count > 0:
            cursor.execute("SELECT * FROM reports LIMIT 3")
            reports = cursor.fetchall()
            print("Sample reports:")
            for report in reports:
                print(f"  - Report ID {report[0]}: User {report[1]} reported {report[2]} ID {report[3]}")
    
    print("\n" + "="*50 + "\n")
    
    if ('reactions',) in tables:
        print("Reactions table exists!")
        # Check if there are any reactions
        cursor.execute("SELECT COUNT(*) FROM reactions")
        count = cursor.fetchone()[0]
        print(f"Number of reactions: {count}")
    
    print("\n" + "="*50 + "\n")
    
    # Check comments table
    if ('comments',) in tables:
        print("Comments table exists!")
        cursor.execute("SELECT COUNT(*) FROM comments")
        count = cursor.fetchone()[0]
        print(f"Number of comments: {count}")
        
        if count > 0:
            cursor.execute("SELECT comment_id, post_id, content FROM comments LIMIT 3")
            comments = cursor.fetchall()
            print("Sample comments:")
            for comment in comments:
                preview = comment[2][:50] + "..." if len(comment[2]) > 50 else comment[2]
                print(f"  - Comment ID {comment[0]} on Post {comment[1]}: {preview}")
    
    conn.close()

if __name__ == "__main__":
    check_confessions_db()
