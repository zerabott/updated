#!/usr/bin/env python3
"""
Debug script to check database structure
"""
import sqlite3

def check_database():
    try:
        conn = sqlite3.connect('bot.db')
        cursor = conn.cursor()
        
        print("🔍 Checking database structure...")
        
        # Get all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        
        print(f"\n📋 Found {len(tables)} tables:")
        for table in tables:
            table_name = table[0]
            print(f"  - {table_name}")
            
            # Get count for each table
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                count = cursor.fetchone()[0]
                print(f"    Records: {count}")
            except Exception as e:
                print(f"    Error counting records: {e}")
        
        # Check specific tables we need
        required_tables = ['reports', 'comments', 'posts', 'users']
        
        print(f"\n🔍 Checking required tables...")
        for table_name in required_tables:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
            exists = cursor.fetchone()
            
            if exists:
                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                count = cursor.fetchone()[0]
                print(f"  ✅ {table_name}: {count} records")
                
                # Show schema for reports table
                if table_name == 'reports' and count == 0:
                    print("    🔧 Creating test report...")
                    # First check if we have comments
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='comments'")
                    comments_exist = cursor.fetchone()
                    
                    if comments_exist:
                        cursor.execute("SELECT COUNT(*) FROM comments")
                        comment_count = cursor.fetchone()[0]
                        print(f"    📝 Comments available: {comment_count}")
                        
                        if comment_count > 0:
                            cursor.execute("SELECT comment_id FROM comments LIMIT 1")
                            first_comment = cursor.fetchone()
                            if first_comment:
                                cursor.execute("""
                                    INSERT INTO reports (user_id, target_type, target_id, reason)
                                    VALUES (?, ?, ?, ?)
                                """, (999999999, 'comment', first_comment[0], 'Test report for admin testing'))
                                conn.commit()
                                print(f"    ✅ Created test report for comment #{first_comment[0]}")
                    else:
                        print("    ❌ No comments table found")
            else:
                print(f"  ❌ {table_name}: NOT FOUND")
        
        # Test the get_reports function
        print(f"\n🧪 Testing get_reports function...")
        try:
            from moderation import get_reports
            reports = get_reports()
            print(f"  📋 get_reports() returned {len(reports)} reports")
            
            if reports:
                for report in reports[:3]:  # Show first 3
                    print(f"    - Report: {report}")
            else:
                print("    ⚠️ No reports returned by get_reports()")
        except Exception as e:
            print(f"    ❌ Error testing get_reports(): {e}")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Error checking database: {e}")

if __name__ == "__main__":
    check_database()
