#!/usr/bin/env python3
import sqlite3
from datetime import datetime

def create_test_reports():
    conn = sqlite3.connect('confessions.db')
    cursor = conn.cursor()
    
    # Get some comment IDs to create reports for
    cursor.execute("SELECT comment_id FROM comments LIMIT 3")
    comment_ids = [row[0] for row in cursor.fetchall()]
    
    if not comment_ids:
        print("No comments found to create reports for!")
        return
    
    # Create test reports
    test_user_id = 123456  # Fake user ID for testing
    
    for comment_id in comment_ids:
        # Create multiple reports for the same comment to simulate reported content
        for i in range(3):
            cursor.execute("""
                INSERT INTO reports (user_id, target_type, target_id, reason, timestamp)
                VALUES (?, 'comment', ?, 'Test report - inappropriate content', ?)
            """, (test_user_id + i, comment_id, datetime.now().isoformat()))
    
    conn.commit()
    
    # Verify reports were created
    cursor.execute("SELECT COUNT(*) FROM reports")
    total_reports = cursor.fetchone()[0]
    
    print(f"Created test reports. Total reports in database: {total_reports}")
    
    # Show sample reports
    cursor.execute("""
        SELECT r.report_id, r.user_id, r.target_type, r.target_id, r.reason, r.timestamp,
               c.content
        FROM reports r
        LEFT JOIN comments c ON r.target_id = c.comment_id AND r.target_type = 'comment'
        ORDER BY r.report_id DESC
        LIMIT 5
    """)
    
    reports = cursor.fetchall()
    print("\nSample reports created:")
    for report in reports:
        content_preview = report[6][:50] + "..." if report[6] and len(report[6]) > 50 else (report[6] or "N/A")
        print(f"  - Report ID {report[0]}: User {report[1]} reported {report[2]} ID {report[3]}")
        print(f"    Reason: {report[4]}")
        print(f"    Content: {content_preview}")
        print()
    
    conn.close()

if __name__ == "__main__":
    create_test_reports()
