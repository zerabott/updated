import sqlite3
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from config import DB_PATH, COMMENTS_PER_PAGE, CHANNEL_ID, BOT_USERNAME
from utils import escape_markdown_text
from db import get_comment_count
from submission import is_media_post, get_media_info


def save_comment(post_id, content, user_id, parent_comment_id=None):
    """Save a comment to the database"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO comments (post_id, content, user_id, parent_comment_id) VALUES (?, ?, ?, ?)",
                (post_id, content, user_id, parent_comment_id)
            )
            comment_id = cursor.lastrowid

            # Update user stats
            cursor.execute(
                "UPDATE users SET comments_posted = comments_posted + 1 WHERE user_id = ?",
                (user_id,)
            )
            conn.commit()
            return comment_id, None
    except Exception as e:
        return None, f"Database error: {str(e)}"


def get_post_with_channel_info(post_id):
    """Get post information including channel message ID"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT post_id, content, category, channel_message_id, approved FROM posts WHERE post_id = ?",
            (post_id,)
        )
        return cursor.fetchone()


def get_comments_paginated(post_id, page=1):
    """Get comments for a post in flat structure like Telegram native replies"""
    offset = (page - 1) * COMMENTS_PER_PAGE

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()

        # Get total count of ALL comments for this post (flat structure)
        cursor.execute(
            "SELECT COUNT(*) FROM comments WHERE post_id = ?",
            (post_id,)
        )
        total_comments = cursor.fetchone()[0]

        # Get paginated comments in chronological order (flat structure)
        cursor.execute('''
            SELECT comment_id, content, timestamp, likes, dislikes, flagged, parent_comment_id,
                   ROW_NUMBER() OVER (ORDER BY timestamp ASC) as comment_number
            FROM comments 
            WHERE post_id = ?
            ORDER BY timestamp ASC
            LIMIT ? OFFSET ?
        ''', (post_id, COMMENTS_PER_PAGE, offset))
        comments = cursor.fetchall()

        # Transform into simplified flat structure
        comments_flat = []
        for comment in comments:
            comment_id = comment[0]
            content = comment[1]
            timestamp = comment[2]
            likes = comment[3]
            dislikes = comment[4]
            flagged = comment[5]
            parent_comment_id = comment[6]
            comment_number = comment[7]
            
            comment_data = {
                'comment_id': comment_id,
                'content': content,
                'timestamp': timestamp,
                'likes': likes,
                'dislikes': dislikes,
                'flagged': flagged,
                'parent_comment_id': parent_comment_id,
                'comment_number': comment_number,
                'is_reply': parent_comment_id is not None
            }
            
            # If this is a reply, get the original comment info for quoting
            if parent_comment_id:
                cursor.execute('''
                    SELECT comment_id, content, timestamp 
                    FROM comments 
                    WHERE comment_id = ?
                ''', (parent_comment_id,))
                original = cursor.fetchone()
                if original:
                    comment_data['original_comment'] = {
                        'comment_id': original[0],
                        'content': original[1],
                        'timestamp': original[2]
                    }
            
            comments_flat.append(comment_data)

        total_pages = (total_comments + COMMENTS_PER_PAGE - 1) // COMMENTS_PER_PAGE

        return comments_flat, page, total_pages, total_comments


def get_comment_by_id(comment_id):
    """Get a specific comment by ID"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM comments WHERE comment_id = ?",
            (comment_id,)
        )
        return cursor.fetchone()


def react_to_comment(user_id, comment_id, reaction_type):
    """Add or update reaction to a comment"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()

            # Check existing reaction
            cursor.execute(
                "SELECT reaction_type FROM reactions WHERE user_id = ? AND target_type = 'comment' AND target_id = ?",
                (user_id, comment_id)
            )
            existing = cursor.fetchone()

            if existing:
                if existing[0] == reaction_type:
                    # Remove reaction if same type
                    cursor.execute(
                        "DELETE FROM reactions WHERE user_id = ? AND target_type = 'comment' AND target_id = ?",
                        (user_id, comment_id)
                    )
                    # Update comment counts
                    if reaction_type == 'like':
                        cursor.execute(
                            "UPDATE comments SET likes = likes - 1 WHERE comment_id = ?",
                            (comment_id,)
                        )
                    else:
                        cursor.execute(
                            "UPDATE comments SET dislikes = dislikes - 1 WHERE comment_id = ?",
                            (comment_id,)
                        )
                    action = "removed"
                else:
                    # Update reaction type
                    cursor.execute(
                        "UPDATE reactions SET reaction_type = ? WHERE user_id = ? AND target_type = 'comment' AND target_id = ?",
                        (reaction_type, user_id, comment_id)
                    )
                    # Update comment counts
                    if existing[0] == 'like':
                        cursor.execute(
                            "UPDATE comments SET likes = likes - 1, dislikes = dislikes + 1 WHERE comment_id = ?",
                            (comment_id,)
                        )
                    else:
                        cursor.execute(
                            "UPDATE comments SET likes = likes + 1, dislikes = dislikes - 1 WHERE comment_id = ?",
                            (comment_id,)
                        )
                    action = "changed"
            else:
                # Add new reaction
                cursor.execute(
                    "INSERT INTO reactions (user_id, target_type, target_id, reaction_type) VALUES (?, 'comment', ?, ?)",
                    (user_id, comment_id, reaction_type)
                )
                # Update comment counts
                if reaction_type == 'like':
                    cursor.execute(
                        "UPDATE comments SET likes = likes + 1 WHERE comment_id = ?",
                        (comment_id,)
                    )
                else:
                    cursor.execute(
                        "UPDATE comments SET dislikes = dislikes + 1 WHERE comment_id = ?",
                        (comment_id,)
                    )
                action = "added"

            conn.commit()

            # Return current counts along with action
            cursor.execute(
                "SELECT likes, dislikes FROM comments WHERE comment_id = ?",
                (comment_id,)
            )
            counts = cursor.fetchone()
            current_likes = counts[0] if counts else 0
            current_dislikes = counts[1] if counts else 0

            return True, action, current_likes, current_dislikes
    except Exception as e:
        return False, str(e), 0, 0


def flag_comment(comment_id):
    """Flag a comment for review"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE comments SET flagged = 1 WHERE comment_id = ?", (comment_id,))
        conn.commit()


def get_user_reaction(user_id, comment_id):
    """Get user's reaction to a specific comment"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT reaction_type FROM reactions WHERE user_id = ? AND target_type = 'comment' AND target_id = ?",
            (user_id, comment_id)
        )
        result = cursor.fetchone()
        return result[0] if result else None


def get_comment_sequential_number(comment_id):
    """Get the sequential number of a comment within its post (flat structure)"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()

        # Get the comment's post_id and timestamp
        cursor.execute(
            "SELECT post_id, timestamp FROM comments WHERE comment_id = ?",
            (comment_id,)
        )
        comment_info = cursor.fetchone()

        if not comment_info:
            return None

        post_id, timestamp = comment_info

        # Count all comments in this post that were posted before or at the same time
        cursor.execute("""
            SELECT COUNT(*) FROM comments 
            WHERE post_id = ? AND timestamp <= ?
            ORDER BY timestamp ASC
        """, (post_id, timestamp))
        result = cursor.fetchone()
        return result[0] if result else 1


def get_parent_comment_for_reply(comment_id):
    """Get the original comment details for a reply (flat structure)"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()

        cursor.execute(
            "SELECT parent_comment_id FROM comments WHERE comment_id = ?",
            (comment_id,)
        )
        result = cursor.fetchone()

        if not result or not result[0]:
            return None

        parent_comment_id = result[0]

        cursor.execute(
            "SELECT comment_id, post_id, content, timestamp FROM comments WHERE comment_id = ?",
            (parent_comment_id,)
        )
        parent_comment = cursor.fetchone()

        if parent_comment:
            parent_sequential_number = get_comment_sequential_number(parent_comment_id)
            return {
                'comment_id': parent_comment[0],
                'post_id': parent_comment[1],
                'content': parent_comment[2],
                'timestamp': parent_comment[3],
                'sequential_number': parent_sequential_number
            }

        return None


def find_comment_page(comment_id):
    """Find which page a comment is on for navigation"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        
        # First get the comment's post_id and check if it's a parent comment
        cursor.execute(
            "SELECT post_id, parent_comment_id FROM comments WHERE comment_id = ?",
            (comment_id,)
        )
        comment_info = cursor.fetchone()
        
        if not comment_info:
            return None
            
        post_id, parent_comment_id = comment_info
        
        # If it's a reply, we need to find the parent comment's page
        target_comment_id = parent_comment_id if parent_comment_id else comment_id
        
        # Count parent comments before this one
        cursor.execute("""
            SELECT COUNT(*) FROM comments 
            WHERE post_id = ? AND parent_comment_id IS NULL AND comment_id < ?
            ORDER BY timestamp ASC
        """, (post_id, target_comment_id))
        
        comments_before = cursor.fetchone()[0]
        page = (comments_before // COMMENTS_PER_PAGE) + 1
        
        return {
            'page': page,
            'post_id': post_id,
            'comment_id': target_comment_id
        }


# Format replies to look like Telegram's native reply feature
def format_reply(parent_text, child_text, parent_author="Anonymous"):
    """Format reply messages to look like Telegram's native reply feature with blockquote"""
    # Truncate parent text if too long for better display
    if len(parent_text) > 150:
        parent_text = parent_text[:150] + "..."
    
    # Use Telegram's native blockquote styling
    return f"<blockquote expandable>{parent_text}</blockquote>\n\n{child_text}"


async def update_channel_message_comment_count(context, post_id):
    """Update the comment count on the channel message"""
    import logging
    logger = logging.getLogger(__name__)

    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT post_id, content, category, channel_message_id, approved, post_number FROM posts WHERE post_id = ?",
                (post_id,)
            )
            post_info = cursor.fetchone()

        if not post_info or not post_info[3]:
            return False, "No channel message found"

        post_id, content, category, channel_message_id, approved, post_number = post_info

        if approved != 1:
            return False, "Post not approved"

        comment_count = get_comment_count(post_id)

        bot_username_clean = BOT_USERNAME.lstrip('@')
        keyboard = [
            [
                InlineKeyboardButton(
                    "💬 Add Comment",
                    url=f"https://t.me/{bot_username_clean}?start=comment_{post_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    f"👀 See Comments ({comment_count})",
                    url=f"https://t.me/{bot_username_clean}?start=view_{post_id}"
                )
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        categories_text = " ".join(
            [f"#{cat.strip().replace(' ', '')}" for cat in category.split(",")]
        )

        if is_media_post(post_id):
            media_info = get_media_info(post_id)
            if media_info:
                caption_text = f"<b>Confess # {post_number}</b>"

                if content and content.strip():
                    caption_text += f"\n\n{content}"

                if media_info.get('caption') and media_info['caption'] != content:
                    caption_text += f"\n\n{media_info['caption']}"

                caption_text += f"\n\n{categories_text}"

                await context.bot.edit_message_caption(
                    chat_id=CHANNEL_ID,
                    message_id=channel_message_id,
                    caption=caption_text,
                    parse_mode="HTML",
                    reply_markup=reply_markup
                )
            else:
                await context.bot.edit_message_text(
                    chat_id=CHANNEL_ID,
                    message_id=channel_message_id,
                    text=f"<b>Confess # {post_number}</b>\n\n{content}\n\n{categories_text}",
                    parse_mode="HTML",
                    reply_markup=reply_markup
                )
        else:
            await context.bot.edit_message_text(
                chat_id=CHANNEL_ID,
                message_id=channel_message_id,
                text=f"<b>Confess # {post_number}</b>\n\n{content}\n\n{categories_text}",
                parse_mode="HTML",
                reply_markup=reply_markup
            )

        return True, f"Updated comment count to {comment_count}"

    except Exception as e:
        return False, f"Failed to update channel message: {str(e)}"
