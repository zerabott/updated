#!/usr/bin/env python3
"""
Debug script to check reports in the database
"""
import sqlite3
from datetime import datetime

def check_reports():
    try:
        conn = sqlite3.connect('bot.db')
        cursor = conn.cursor()
        
        print("🔍 Checking reports table...")
        
        # Check if reports table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='reports'")
        table_exists = cursor.fetchone()
        
        if not table_exists:
            print("❌ Reports table doesn't exist!")
            # Create reports table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS reports (
                    report_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    target_type TEXT NOT NULL,
                    target_id INTEGER NOT NULL,
                    reason TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
            print("✅ Created reports table")
        else:
            print("✅ Reports table exists")
        
        # Get table schema
        cursor.execute("PRAGMA table_info(reports)")
        schema = cursor.fetchall()
        print("\n📋 Reports table schema:")
        for col in schema:
            print(f"  - {col[1]} ({col[2]})")
        
        # Count total reports
        cursor.execute("SELECT COUNT(*) FROM reports")
        total_reports = cursor.fetchone()[0]
        print(f"\n📊 Total reports: {total_reports}")
        
        if total_reports > 0:
            # Show recent reports
            cursor.execute("""
                SELECT report_id, user_id, target_type, target_id, reason, timestamp 
                FROM reports 
                ORDER BY timestamp DESC 
                LIMIT 10
            """)
            reports = cursor.fetchall()
            
            print("\n📋 Recent reports:")
            for report in reports:
                report_id, user_id, target_type, target_id, reason, timestamp = report
                print(f"  #{report_id}: {target_type}_{target_id} by user {user_id} - '{reason}' at {timestamp}")
            
            # Group by target
            cursor.execute("""
                SELECT target_type, target_id, COUNT(*) as count
                FROM reports 
                GROUP BY target_type, target_id 
                ORDER BY count DESC
            """)
            grouped = cursor.fetchall()
            
            print("\n📈 Reports by target:")
            for target_type, target_id, count in grouped:
                print(f"  {target_type} #{target_id}: {count} reports")
        else:
            print("\n⚠️ No reports found in database")
            
            # Let's check if we have comments to potentially report
            cursor.execute("SELECT COUNT(*) FROM comments")
            comment_count = cursor.fetchone()[0]
            print(f"📝 Total comments in database: {comment_count}")
            
            if comment_count > 0:
                print("\n💡 Creating a test report...")
                # Create a test report for the first comment
                cursor.execute("SELECT comment_id FROM comments LIMIT 1")
                first_comment = cursor.fetchone()
                if first_comment:
                    cursor.execute("""
                        INSERT INTO reports (user_id, target_type, target_id, reason)
                        VALUES (?, ?, ?, ?)
                    """, (999999999, 'comment', first_comment[0], 'Test report for debugging'))
                    conn.commit()
                    print(f"✅ Created test report for comment #{first_comment[0]}")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Error checking reports: {e}")

if __name__ == "__main__":
    check_reports()
