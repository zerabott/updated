import datetime
from config import DB_PATH
from db_connection import get_db_connection, execute_query, adapt_query
import logging

logger = logging.getLogger(__name__)

# Keep backward compatibility
def get_db():
    """Get database connection (backward compatibility)"""
    db_conn = get_db_connection()
    return db_conn.get_connection()

def init_db():
    """Initialize database with enhanced schema"""
    db_conn = get_db_connection()
    with db_conn.get_connection() as conn:
        cursor = conn.cursor()
        
        # Users table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            questions_asked INTEGER DEFAULT 0,
            comments_posted INTEGER DEFAULT 0,
            blocked INTEGER DEFAULT 0
        )''')
        
        # Posts table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS posts (
            post_id SERIAL PRIMARY KEY,
            content TEXT NOT NULL,
            category TEXT NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            user_id BIGINT NOT NULL,
            approved INTEGER DEFAULT NULL,
            channel_message_id BIGINT,
            flagged INTEGER DEFAULT 0,
            likes INTEGER DEFAULT 0,
            post_number INTEGER DEFAULT NULL,
            status TEXT DEFAULT 'pending',
            sentiment_score REAL DEFAULT 0.0,
            profanity_detected INTEGER DEFAULT 0,
            spam_score REAL DEFAULT 0.0,
            media_type TEXT,
            media_file_id TEXT,
            media_file_unique_id TEXT,
            media_caption TEXT,
            media_file_size BIGINT,
            media_mime_type TEXT,
            media_duration INTEGER,
            media_width INTEGER,
            media_height INTEGER,
            media_thumbnail_file_id TEXT,
            rejection_reason TEXT,
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        )''')
        
        # Comments
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS comments (
            comment_id SERIAL PRIMARY KEY,
            post_id INTEGER NOT NULL,
            user_id BIGINT NOT NULL,
            content TEXT NOT NULL,
            parent_comment_id INTEGER,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            likes INTEGER DEFAULT 0,
            dislikes INTEGER DEFAULT 0,
            flagged INTEGER DEFAULT 0,
            FOREIGN KEY(post_id) REFERENCES posts(post_id),
            FOREIGN KEY(user_id) REFERENCES users(user_id),
            FOREIGN KEY(parent_comment_id) REFERENCES comments(comment_id)
        )''')
        
        # Reactions
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS reactions (
            reaction_id SERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            target_type TEXT NOT NULL,
            target_id INTEGER NOT NULL,
            reaction_type TEXT NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, target_type, target_id),
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        )''')
        
        # Reports
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS reports (
            report_id SERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            target_type TEXT NOT NULL,
            target_id INTEGER NOT NULL,
            reason TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        )''')
        
        # Admin messages
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS admin_messages (
            message_id SERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            admin_id BIGINT,
            user_message TEXT,
            admin_reply TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            replied INTEGER DEFAULT 0,
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        )''')
        
        # Rankings
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_rankings (
            user_id BIGINT PRIMARY KEY,
            total_points INTEGER DEFAULT 0,
            weekly_points INTEGER DEFAULT 0,
            monthly_points INTEGER DEFAULT 0,
            current_rank_id INTEGER DEFAULT 1,
            rank_progress REAL DEFAULT 0.0,
            total_achievements INTEGER DEFAULT 0,
            highest_rank_achieved INTEGER DEFAULT 1,
            consecutive_days INTEGER DEFAULT 0,
            last_login_date TIMESTAMP,
            last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        )''')
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS point_transactions (
            transaction_id SERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            points_change INTEGER NOT NULL,
            transaction_type TEXT NOT NULL,
            reference_id INTEGER,
            reference_type TEXT,
            description TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        )''')
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_achievements (
            achievement_id SERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            achievement_type TEXT NOT NULL,
            achievement_name TEXT NOT NULL,
            achievement_description TEXT,
            points_awarded INTEGER DEFAULT 0,
            is_special INTEGER DEFAULT 0,
            metadata TEXT,
            achieved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        )''')
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS rank_definitions (
            rank_id INTEGER PRIMARY KEY,
            rank_name TEXT NOT NULL,
            rank_emoji TEXT NOT NULL,
            min_points INTEGER NOT NULL,
            max_points INTEGER,
            special_perks TEXT,
            is_special INTEGER DEFAULT 0
        )''')
        
        # Insert default ranks (ON CONFLICT DO NOTHING for Postgres)
        cursor.execute('''
        INSERT INTO rank_definitions (rank_id, rank_name, rank_emoji, min_points, max_points, special_perks, is_special)
        VALUES 
            (1, 'Freshman', '🥉', 0, 99, '{}', 0),
            (2, 'Sophomore', '🥈', 100, 249, '{}', 0),
            (3, 'Junior', '🥇', 250, 499, '{}', 0),
            (4, 'Senior', '🏆', 500, 999, '{"daily_confessions": 8}', 0),
            (5, 'Graduate', '🎓', 1000, 1999, '{"daily_confessions": 10, "priority_review": true}', 0),
            (6, 'Master', '👑', 2000, 4999, '{"daily_confessions": 15, "priority_review": true, "comment_highlight": true}', 1),
            (7, 'Legend', '🌟', 5000, NULL, '{"all_perks": true, "unlimited_daily": true, "legend_badge": true}', 1)
        ON CONFLICT (rank_id) DO NOTHING
        ''')
        
        # Analytics
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_activity_log (
            log_id SERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            activity_type TEXT NOT NULL,
            details TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        )''')
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS daily_stats (
            stat_date DATE PRIMARY KEY,
            new_users INTEGER DEFAULT 0,
            total_confessions INTEGER DEFAULT 0,
            approved_confessions INTEGER DEFAULT 0,
            rejected_confessions INTEGER DEFAULT 0,
            total_comments INTEGER DEFAULT 0,
            active_users INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        
        conn.commit()

def add_user(user_id, username=None, first_name=None, last_name=None):
    """Add or update user information"""
    db_conn = get_db_connection()
    with db_conn.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO users (user_id, username, first_name, last_name, join_date, questions_asked, comments_posted, blocked)
            VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP, 0, 0, 0)
            ON CONFLICT (user_id) DO UPDATE
            SET username = EXCLUDED.username,
                first_name = EXCLUDED.first_name,
                last_name = EXCLUDED.last_name
        ''', (user_id, username, first_name, last_name))
        conn.commit()

def get_user_info(user_id):
    """Get complete user information"""
    db_conn = get_db_connection()
    with db_conn.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT user_id, username, first_name, last_name, join_date, 
                   questions_asked, comments_posted, blocked
            FROM users WHERE user_id = %s
        ''', (user_id,))
        return cursor.fetchone()

def get_comment_count(post_id):
    """Get total comment count for a post"""
    db_conn = get_db_connection()
    with db_conn.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM comments WHERE post_id = %s', (post_id,))
        result = cursor.fetchone()
        return result[0] if result else 0

def is_blocked_user(user_id):
    """Check if user is blocked"""
    db_conn = get_db_connection()
    with db_conn.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT blocked FROM users WHERE user_id = %s', (user_id,))
        result = cursor.fetchone()
        return result and result[0] == 1

def get_user_posts(user_id, limit=10):
    """Get user's posts with details"""
    db_conn = get_db_connection()
    with db_conn.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT p.post_id, p.content, p.category, p.timestamp, p.approved,
                   COUNT(c.comment_id) as comment_count, p.post_number,
                   p.media_type, p.media_file_id, p.media_file_unique_id, p.media_caption,
                   p.media_file_size, p.media_mime_type, p.media_duration, 
                   p.media_width, p.media_height, p.media_thumbnail_file_id
            FROM posts p
            LEFT JOIN comments c ON p.post_id = c.post_id
            WHERE p.user_id = %s
            GROUP BY p.post_id, p.content, p.category, p.timestamp, p.approved, p.post_number,
                     p.media_type, p.media_file_id, p.media_file_unique_id, p.media_caption,
                     p.media_file_size, p.media_mime_type, p.media_duration, 
                     p.media_width, p.media_height, p.media_thumbnail_file_id
            ORDER BY p.timestamp DESC
            LIMIT %s
        ''', (user_id, limit))
        return cursor.fetchall()
        
def get_post_author_id(post_id):
    """Get the user_id of the post author"""
    db_conn = get_db_connection()
    with db_conn.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT user_id FROM posts WHERE post_id = %s', (post_id,))
        result = cursor.fetchone()
        return result[0] if result else None
