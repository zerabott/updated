"""
Admin User Activity Management Module
This module provides functions for displaying user posts and comments in the admin dashboard.
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from utils import escape_markdown_text, truncate_text, format_time_ago
from db import get_db
from config import CHANNEL_ID

logger = logging.getLogger(__name__)

async def admin_user_posts_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show detailed list of posts by a specific user"""
    query = update.callback_query
    await query.answer()
    
    # Extract user ID from callback data
    try:
        # Debug log
        logger.info(f"Processing admin_user_posts_ callback with data: {query.data} (type: {type(query.data)})")
        # Ensure query.data is a string
        callback_data = str(query.data) if query.data is not None else ""
        logger.info(f"Converted callback_data to string: '{callback_data}'")
        user_id = int(callback_data.replace("admin_user_posts_", ""))
        logger.info(f"Extracted user_id: {user_id}")
    except (ValueError, AttributeError) as e:
        logger.error(f"Invalid callback data for admin_user_posts_: {query.data}, error: {e}")
        await query.edit_message_text(
            "❌ *Invalid Request*\n\nThere was an error processing your request.",
            parse_mode="MarkdownV2",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Back to User Search", callback_data="admin_search_user")
            ]])
        )
        return
    
    # Get posts by this user from the database
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            
            # Get user info first
            cursor.execute(
                "SELECT username, first_name, last_name FROM users WHERE user_id = ?",
                (user_id,)
            )
            user_data = cursor.fetchone()
            
            if not user_data:
                await query.edit_message_text(
                    "❌ *User Not Found*\n\nUnable to find user data.",
                    parse_mode="MarkdownV2",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Back to User Search", callback_data="admin_search_user")
                    ]])
                )
                return
            
            username, first_name, last_name = user_data
            display_name = f"{first_name or ''} {last_name or ''}".strip() or username or "Anonymous"
            
            # Get all posts by this user, including both approved and pending
            cursor.execute("""
                SELECT 
                    post_id, content, category, timestamp, approved, 
                    (SELECT COUNT(*) FROM comments WHERE post_id = p.post_id) as comment_count,
                    media_type, channel_message_id, flagged
                FROM posts p
                WHERE user_id = ?
                ORDER BY timestamp DESC
                LIMIT 20
            """, (user_id,))
            
            posts = cursor.fetchall()
        
        if not posts:
            # No posts found
            await query.edit_message_text(
                f"📝 *User Posts*\n\n"
                f"User: {escape_markdown_text(display_name)} \\(ID: `{user_id}`\\)\n\n"
                f"⚠️ This user has not submitted any posts yet.",
                parse_mode="MarkdownV2",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("👤 User Info", callback_data=f"admin_user_info_{user_id}"),
                    InlineKeyboardButton("💬 View Comments", callback_data=f"admin_user_comments_{user_id}")
                ], [
                    InlineKeyboardButton("🔙 Back to User Search", callback_data="admin_search_user")
                ]])
            )
            return
        
        # Build and show posts list
        # First, delete the current message to start fresh with multiple messages
        await query.delete_message()
        
        # Send header message
        header_text = (
            f"📝 *User Posts*\n\n"
            f"User: {escape_markdown_text(display_name)} \\(ID: `{user_id}`\\)\n"
            f"Total Posts: {len(posts)}\n\n"
            f"Showing most recent submissions:"
        )
        
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=header_text,
            parse_mode="MarkdownV2"
        )
        
        # Send each post as a separate message
        import asyncio
        from datetime import datetime
        
        logger.info(f"Processing {len(posts)} posts for user {user_id}")
        for i, post in enumerate(posts):
            logger.info(f"Processing post {i+1}/{len(posts)}: {post}")
            post_id, content, category, timestamp, approved, comment_count, media_type, channel_message_id, flagged = post
            
            # Format the status
            status = "✅ Approved" if approved == 1 else "❌ Rejected" if approved == 0 else "⏳ Pending"
            
            # Add flags if any
            if flagged == 1:
                status += " 🚩"
            
            # Format timestamp
            try:
                # Ensure timestamp is a string
                timestamp_str = str(timestamp) if timestamp is not None else ""
                dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                time_ago = format_time_ago(dt)
                escaped_time = escape_markdown_text(time_ago)
            except:
                escaped_time = escape_markdown_text("unknown time")
            
            # Format post content (shortened preview)
            content_preview = truncate_text(content or "[Media content]", 150)
            
            # Create post message
            post_text = (
                f"*Post \\#{post_id}*\n"
                f"*Category:* {escape_markdown_text(category)}\n"
                f"*Status:* {status}\n"
                f"*Time:* {escaped_time}\n"
                f"*Comments:* {comment_count}\n"
                f"*Media:* {escape_markdown_text(media_type) if media_type else 'None'}\n\n"
                f"*Content:*\n{escape_markdown_text(content_preview)}"
            )
            
            # Create action buttons based on post status
            keyboard = []
            
            # View button is always available
            view_button = InlineKeyboardButton("👀 View Full Post", callback_data=f"view_post_{post_id}")
            
            # Delete button is available for all posts
            delete_button = InlineKeyboardButton("🗑️ Delete Post", callback_data=f"admin_delete_post_{post_id}")
            
            # For approved posts with channel messages, add view in channel button
            if approved == 1 and channel_message_id:
                # Ensure CHANNEL_ID is a string for replace operation
                channel_id_str = str(CHANNEL_ID).replace('-100', '')
                keyboard.append([view_button, InlineKeyboardButton("📢 View in Channel", url=f"https://t.me/c/{channel_id_str}/{channel_message_id}")])
            else:
                keyboard.append([view_button])
            
            # Add comment/moderation buttons
            if approved == 1:  # Approved posts
                keyboard.append([
                    InlineKeyboardButton(f"💬 Comments ({comment_count})", callback_data=f"see_comments_{post_id}_1"),
                    delete_button
                ])
            elif approved is None:  # Pending posts
                keyboard.append([
                    InlineKeyboardButton("✅ Approve", callback_data=f"approve_{post_id}"),
                    InlineKeyboardButton("❌ Reject", callback_data=f"reject_{post_id}")
                ])
                keyboard.append([delete_button])
            else:  # Rejected posts
                keyboard.append([delete_button])
            
            # Send the post
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=post_text,
                parse_mode="MarkdownV2",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
            # Small delay between posts
            await asyncio.sleep(0.3)
        
        # Send navigation buttons at the end
        nav_keyboard = [
            [
                InlineKeyboardButton("👤 User Info", callback_data=f"admin_user_info_{user_id}"),
                InlineKeyboardButton("💬 View Comments", callback_data=f"admin_user_comments_{user_id}")
            ],
            [
                InlineKeyboardButton("🔙 Back to User Search", callback_data="admin_search_user"),
                InlineKeyboardButton("🔧 Admin Dashboard", callback_data="admin_dashboard")
            ]
        ]
        
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="📋 *Navigation*",
            parse_mode="MarkdownV2",
            reply_markup=InlineKeyboardMarkup(nav_keyboard)
        )
    
    except Exception as e:
        logger.error(f"Error in admin_user_posts_callback: {e}")
        # If an error occurred and we deleted the original message, send a new error message
        try:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"❌ *Error*\n\nFailed to retrieve user posts: {escape_markdown_text(str(e))}",
                parse_mode="MarkdownV2",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Back to User Search", callback_data="admin_search_user")
                ]])
            )
        except:
            # If we can't send a new message, try to edit the original
            try:
                await query.edit_message_text(
                    f"❌ *Error*\n\nFailed to retrieve user posts: {escape_markdown_text(str(e))}",
                    parse_mode="MarkdownV2",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Back to User Search", callback_data="admin_search_user")
                    ]])
                )
            except:
                logger.error("Failed to send error message in admin_user_posts_callback")

async def admin_user_comments_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show detailed list of comments by a specific user"""
    query = update.callback_query
    await query.answer()
    
    # Extract user ID from callback data
    try:
        # Ensure query.data is a string
        callback_data = str(query.data) if query.data is not None else ""
        user_id = int(callback_data.replace("admin_user_comments_", ""))
    except (ValueError, AttributeError) as e:
        logger.error(f"Invalid callback data for admin_user_comments_: {query.data}, error: {e}")
        await query.edit_message_text(
            "❌ *Invalid Request*\n\nThere was an error processing your request.",
            parse_mode="MarkdownV2",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Back to User Search", callback_data="admin_search_user")
            ]])
        )
        return
    
    # Get comments by this user from the database
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            
            # Get user info first
            cursor.execute(
                "SELECT username, first_name, last_name FROM users WHERE user_id = ?",
                (user_id,)
            )
            user_data = cursor.fetchone()
            
            if not user_data:
                await query.edit_message_text(
                    "❌ *User Not Found*\n\nUnable to find user data.",
                    parse_mode="MarkdownV2",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Back to User Search", callback_data="admin_search_user")
                    ]])
                )
                return
            
            username, first_name, last_name = user_data
            display_name = f"{first_name or ''} {last_name or ''}".strip() or username or "Anonymous"
            
            # Get all comments by this user
            cursor.execute("""
                SELECT 
                    c.comment_id, c.post_id, c.content, c.timestamp, c.parent_comment_id, c.flagged,
                    (SELECT COUNT(*) FROM reactions WHERE target_type = 'comment' AND target_id = c.comment_id AND reaction_type = 'like') as likes,
                    (SELECT COUNT(*) FROM reactions WHERE target_type = 'comment' AND target_id = c.comment_id AND reaction_type = 'dislike') as dislikes,
                    (SELECT COUNT(*) FROM comments WHERE parent_comment_id = c.comment_id) as reply_count,
                    p.category as post_category
                FROM comments c
                LEFT JOIN posts p ON c.post_id = p.post_id
                WHERE c.user_id = ?
                ORDER BY c.timestamp DESC
                LIMIT 25
            """, (user_id,))
            
            comments = cursor.fetchall()
        
        if not comments:
            # No comments found
            await query.edit_message_text(
                f"💬 *User Comments*\n\n"
                f"User: {escape_markdown_text(display_name)} \\(ID: `{user_id}`\\)\n\n"
                f"⚠️ This user has not posted any comments yet.",
                parse_mode="MarkdownV2",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("👤 User Info", callback_data=f"admin_user_info_{user_id}"),
                    InlineKeyboardButton("📝 View Posts", callback_data=f"admin_user_posts_{user_id}")
                ], [
                    InlineKeyboardButton("🔙 Back to User Search", callback_data="admin_search_user")
                ]])
            )
            return
        
        # Build and show comments list
        # First, delete the current message to start fresh with multiple messages
        await query.delete_message()
        
        # Send header message
        header_text = (
            f"💬 *User Comments*\n\n"
            f"User: {escape_markdown_text(display_name)} \\(ID: `{user_id}`\\)\n"
            f"Total Comments: {len(comments)}\n\n"
            f"Showing most recent comments:"
        )
        
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=header_text,
            parse_mode="MarkdownV2"
        )
        
        # Send each comment as a separate message
        import asyncio
        from datetime import datetime
        
        for comment in comments:
            comment_id, post_id, content, timestamp, parent_id, flagged, likes, dislikes, reply_count, post_category = comment
            
            # Add flags if any
            status = "🚩 Flagged" if flagged == 1 else "✅ Normal"
            
            # Is this a reply?
            is_reply = "✓" if parent_id else "✗"
            
            # Format timestamp
            try:
                # Ensure timestamp is a string
                timestamp_str = str(timestamp) if timestamp is not None else ""
                dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                time_ago = format_time_ago(dt)
                escaped_time = escape_markdown_text(time_ago)
            except:
                escaped_time = escape_markdown_text("unknown time")
            
            # Format comment content (shortened preview)
            content_preview = truncate_text(content, 200)
            
            # Create comment message
            comment_text = (
                f"*Comment \\#{comment_id}*\n"
                f"*Post:* \\#{post_id} ({escape_markdown_text(post_category or 'Unknown')})\n"
                f"*Status:* {status}\n"
                f"*Time:* {escaped_time}\n"
                f"*Reactions:* 👍 {likes} | 👎 {dislikes}\n"
                f"*Is Reply:* {is_reply} | *Replies:* {reply_count}\n\n"
                f"*Content:*\n{escape_markdown_text(content_preview)}"
            )
            
            # Create action buttons
            keyboard = [
                [
                    InlineKeyboardButton("👀 View Post", callback_data=f"view_post_{post_id}"),
                    InlineKeyboardButton("💬 See Thread", callback_data=f"see_comments_{post_id}_1")
                ],
                [
                    InlineKeyboardButton("🗑️ Delete Comment", callback_data=f"admin_delete_comment_{comment_id}")
                ]
            ]
            
            # Send the comment
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=comment_text,
                parse_mode="MarkdownV2",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
            # Small delay between comments
            await asyncio.sleep(0.3)
        
        # Send navigation buttons at the end
        nav_keyboard = [
            [
                InlineKeyboardButton("👤 User Info", callback_data=f"admin_user_info_{user_id}"),
                InlineKeyboardButton("📝 View Posts", callback_data=f"admin_user_posts_{user_id}")
            ],
            [
                InlineKeyboardButton("🔙 Back to User Search", callback_data="admin_search_user"),
                InlineKeyboardButton("🔧 Admin Dashboard", callback_data="admin_dashboard")
            ]
        ]
        
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="📋 *Navigation*",
            parse_mode="MarkdownV2",
            reply_markup=InlineKeyboardMarkup(nav_keyboard)
        )
    
    except Exception as e:
        logger.error(f"Error in admin_user_comments_callback: {e}")
        # If an error occurred and we deleted the original message, send a new error message
        try:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"❌ *Error*\n\nFailed to retrieve user comments: {escape_markdown_text(str(e))}",
                parse_mode="MarkdownV2",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Back to User Search", callback_data="admin_search_user")
                ]])
            )
        except:
            # If we can't send a new message, try to edit the original
            try:
                await query.edit_message_text(
                    f"❌ *Error*\n\nFailed to retrieve user comments: {escape_markdown_text(str(e))}",
                    parse_mode="MarkdownV2",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Back to User Search", callback_data="admin_search_user")
                    ]])
                )
            except:
                logger.error("Failed to send error message in admin_user_comments_callback")
