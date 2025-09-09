#!/usr/bin/env python3
"""
Complete database reset script with full schema
"""

import os
import sqlite3
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def reset_database():
    """Reset the database completely with full schema"""
    
    # Database files to remove
    db_files = [
        'confessions.db', 
        'bot.db', 
        'university_confession_bot.db'
    ]
    
    # Remove existing database files
    for db_file in db_files:
        if os.path.exists(db_file):
            os.remove(db_file)
            logger.info(f"Removed {db_file}")
    
    # Create a fresh database with complete schema
    conn = sqlite3.connect('confessions.db')
    cursor = conn.cursor()
    
    # Users table with join date tracking
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            join_date TEXT DEFAULT CURRENT_TIMESTAMP,
            questions_asked INTEGER DEFAULT 0,
            comments_posted INTEGER DEFAULT 0,
            blocked INTEGER DEFAULT 0
        )
    ''')
    
    # Posts table with full schema
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS posts (
            post_id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT,
            category TEXT NOT NULL,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
            user_id INTEGER NOT NULL,
            approved INTEGER DEFAULT NULL,
            channel_message_id INTEGER,
            flagged INTEGER DEFAULT 0,
            likes INTEGER DEFAULT 0,
            post_number INTEGER DEFAULT NULL,
            status TEXT DEFAULT 'pending',
            sentiment_score REAL DEFAULT 0.0,
            profanity_detected INTEGER DEFAULT 0,
            spam_score REAL DEFAULT 0.0,
            media_type TEXT DEFAULT NULL,
            media_file_id TEXT DEFAULT NULL,
            media_file_unique_id TEXT DEFAULT NULL,
            media_caption TEXT DEFAULT NULL,
            media_file_size INTEGER DEFAULT NULL,
            media_mime_type TEXT DEFAULT NULL,
            media_duration INTEGER DEFAULT NULL,
            media_width INTEGER DEFAULT NULL,
            media_height INTEGER DEFAULT NULL,
            media_thumbnail_file_id TEXT DEFAULT NULL,
            rejection_reason TEXT,
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        )
    ''')
    
    # Comments table with enhanced structure
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS comments (
            comment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            content TEXT NOT NULL,
            parent_comment_id INTEGER,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
            likes INTEGER DEFAULT 0,
            dislikes INTEGER DEFAULT 0,
            flagged INTEGER DEFAULT 0,
            FOREIGN KEY(post_id) REFERENCES posts(post_id),
            FOREIGN KEY(user_id) REFERENCES users(user_id),
            FOREIGN KEY(parent_comment_id) REFERENCES comments(comment_id)
        )
    ''')
    
    # Likes/Reactions table
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
        )
    ''')
    
    # Reports table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reports (
            report_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            target_type TEXT NOT NULL,
            target_id INTEGER NOT NULL,
            reason TEXT,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        )
    ''')
    
    # Admin messages table for admin-user communication
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS admin_messages (
            message_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            admin_id INTEGER,
            user_message TEXT,
            admin_reply TEXT,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
            replied INTEGER DEFAULT 0,
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        )
    ''')
    
    # Ranking system tables
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_rankings (
            user_id INTEGER PRIMARY KEY,
            total_points INTEGER DEFAULT 0,
            weekly_points INTEGER DEFAULT 0,
            monthly_points INTEGER DEFAULT 0,
            current_rank_id INTEGER DEFAULT 1,
            rank_progress REAL DEFAULT 0.0,
            total_achievements INTEGER DEFAULT 0,
            highest_rank_achieved INTEGER DEFAULT 1,
            consecutive_days INTEGER DEFAULT 0,
            last_login_date TEXT,
            last_activity TEXT DEFAULT CURRENT_TIMESTAMP,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS point_transactions (
            transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            points_change INTEGER NOT NULL,
            transaction_type TEXT NOT NULL,
            reference_id INTEGER,
            reference_type TEXT,
            description TEXT,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_achievements (
            achievement_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            achievement_type TEXT NOT NULL,
            achievement_name TEXT NOT NULL,
            achievement_description TEXT,
            points_awarded INTEGER DEFAULT 0,
            is_special INTEGER DEFAULT 0,
            metadata TEXT,
            achieved_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS rank_definitions (
            rank_id INTEGER PRIMARY KEY,
            rank_name TEXT NOT NULL,
            rank_emoji TEXT NOT NULL,
            min_points INTEGER NOT NULL,
            max_points INTEGER,
            special_perks TEXT,
            is_special INTEGER DEFAULT 0
        )
    ''')
    
    # Insert default rank definitions
    cursor.execute('''
        INSERT OR IGNORE INTO rank_definitions (rank_id, rank_name, rank_emoji, min_points, max_points, special_perks, is_special)
        VALUES 
            (1, 'Freshman', '🥉', 0, 99, '{}', 0),
            (2, 'Sophomore', '🥈', 100, 249, '{}', 0),
            (3, 'Junior', '🥇', 250, 499, '{}', 0),
            (4, 'Senior', '🏆', 500, 999, '{"daily_confessions": 8}', 0),
            (5, 'Graduate', '🎓', 1000, 1999, '{"daily_confessions": 10, "priority_review": true}', 0),
            (6, 'Master', '👑', 2000, 4999, '{"daily_confessions": 15, "priority_review": true, "comment_highlight": true}', 1),
            (7, 'Legend', '🌟', 5000, NULL, '{"all_perks": true, "unlimited_daily": true, "legend_badge": true}', 1)
    ''')
    
    # Analytics tables
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_activity_log (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            activity_type TEXT NOT NULL,
            details TEXT,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS daily_stats (
            stat_date TEXT PRIMARY KEY,
            new_users INTEGER DEFAULT 0,
            total_confessions INTEGER DEFAULT 0,
            approved_confessions INTEGER DEFAULT 0,
            rejected_confessions INTEGER DEFAULT 0,
            total_comments INTEGER DEFAULT 0,
            active_users INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Migration table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS migrations (
            version INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            checksum TEXT NOT NULL,
            applied_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Mark all migrations as completed to avoid issues
    cursor.execute('''
        INSERT INTO migrations (version, name, checksum) VALUES 
        (1, 'initial_schema', 'completed'),
        (2, 'add_user_preferences', 'completed'),
        (3, 'add_confession_drafts', 'completed'),
        (4, 'add_scheduled_confessions', 'completed'),
        (5, 'add_analytics_tables', 'completed'),
        (6, 'add_notification_system', 'completed'),
        (7, 'enhance_content_moderation', 'completed'),
        (8, 'add_performance_indexes', 'completed'),
        (9, 'add_backup_metadata', 'completed'),
        (10, 'add_user_profile_columns', 'completed'),
        (11, 'add_channel_message_id', 'completed'),
        (12, 'add_post_number_column', 'completed'),
        (13, 'ensure_rank_definitions_columns', 'completed'),
        (14, 'add_media_support_to_confessions', 'completed'),
        (15, 'fix_content_null_constraint_for_media', 'completed')
    ''')
    
    conn.commit()
    conn.close()
    
    logger.info("✅ Fresh database created successfully with complete schema!")

if __name__ == "__main__":
    reset_database()
