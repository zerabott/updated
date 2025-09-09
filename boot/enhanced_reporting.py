"""
Enhanced Reporting System for Telegram Confession Bot
Features: Multiple report reasons, immediate admin notifications, admin management
"""

import sqlite3
import logging
from datetime import datetime
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from config import DB_PATH, ADMIN_IDS
from utils import escape_markdown_text, truncate_text

logger = logging.getLogger(__name__)

# Report reason categories
REPORT_REASONS = [
    ("spam", "🚫 Spam", "Unwanted repetitive content or advertisements"),
    ("harassment", "😡 Harassment", "Bullying, threats, or abusive language"),
    ("inappropriate", "🔞 Inappropriate Content", "Sexual, violent, or disturbing content"),
    ("hate_speech", "💔 Hate Speech", "Discriminatory or hateful language"),
    ("misinformation", "🚨 Misinformation", "False or misleading information"),
    ("personal_info", "🆔 Personal Information", "Sharing private information"),
    ("off_topic", "📍 Off Topic", "Content not relevant to the community"),
    ("other", "❓ Other", "Other reason not listed above")
]

def get_report_reasons_keyboard(content_type, content_id):
    """Create keyboard with report reason options"""
    keyboard = []
    
    # Create two-column layout for reasons
    for i in range(0, len(REPORT_REASONS), 2):
        row = []
        reason_id, emoji_title, description = REPORT_REASONS[i]
        row.append(InlineKeyboardButton(emoji_title, callback_data=f"report_reason_{content_type}_{content_id}_{reason_id}"))
        
        if i + 1 < len(REPORT_REASONS):
            reason_id2, emoji_title2, description2 = REPORT_REASONS[i + 1]
            row.append(InlineKeyboardButton(emoji_title2, callback_data=f"report_reason_{content_type}_{content_id}_{reason_id2}"))
        
        keyboard.append(row)
    
    # Add cancel button
    keyboard.append([InlineKeyboardButton("🚫 Cancel", callback_data="cancel_report")])
    
    return InlineKeyboardMarkup(keyboard)

def get_report_reason_info(reason_id):
    """Get report reason information by ID"""
    for r_id, emoji_title, description in REPORT_REASONS:
        if r_id == reason_id:
            return emoji_title, description
    return "❓ Other", "Other reason"

async def show_report_reasons(update, context, content_type, content_id):
    """Show report reason selection interface"""
    query = update.callback_query
    
    # Get content preview for context
    content_preview = get_content_preview(content_type, content_id)
    
    if not content_preview:
        await query.answer("❗ Content not found or no longer available!")
        return
    
    preview_text = truncate_text(content_preview, 100)
    
    report_text = f"""🚩 **Report {content_type.title()}**

**Content Preview:**
_{escape_markdown_text(preview_text)}_

**Why are you reporting this {content_type}?**
Choose the reason that best describes the issue:"""
    
    keyboard = get_report_reasons_keyboard(content_type, content_id)
    
    await query.edit_message_text(
        report_text,
        reply_markup=keyboard,
        parse_mode="MarkdownV2"
    )

def get_content_preview(content_type, content_id):
    """Get content preview for report context"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        
        if content_type == "comment":
            cursor.execute("SELECT content FROM comments WHERE comment_id = ?", (content_id,))
        elif content_type == "post":
            cursor.execute("SELECT content FROM posts WHERE post_id = ?", (content_id,))
        else:
            return None
            
        result = cursor.fetchone()
        return result[0] if result else None

def submit_report(user_id, content_type, content_id, reason_id, custom_reason=None):
    """Submit a report to the database with immediate processing"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        
        # Check if user has already reported this content
        cursor.execute(
            "SELECT COUNT(*) FROM reports WHERE user_id = ? AND target_type = ? AND target_id = ?",
            (user_id, content_type, content_id)
        )
        existing_report = cursor.fetchone()[0]
        
        if existing_report > 0:
            return False, "already_reported"
        
        # Get reason info
        reason_emoji, reason_description = get_report_reason_info(reason_id)
        final_reason = custom_reason if custom_reason else reason_description
        
        # Insert new report
        cursor.execute(
            "INSERT INTO reports (user_id, target_type, target_id, reason) VALUES (?, ?, ?, ?)",
            (user_id, content_type, content_id, f"{reason_emoji}: {final_reason}")
        )
        
        # Get total report count for this content
        cursor.execute(
            "SELECT COUNT(*) FROM reports WHERE target_type = ? AND target_id = ?",
            (content_type, content_id)
        )
        report_count = cursor.fetchone()[0]
        
        conn.commit()
        
        return True, report_count

async def notify_admins_immediate(context, content_type, content_id, reason_id, user_id, report_count):
    """Send immediate notification to admins about the report"""
    # Get content details
    content_info = get_content_details(content_type, content_id)
    if not content_info:
        return False
    
    reason_emoji, reason_description = get_report_reason_info(reason_id)
    
    if content_type == "comment":
        comment_id, post_id, content, timestamp = content_info
        preview = truncate_text(content, 150)
        admin_text = f"""🚨 **New Comment Report**

**Reported Content:** Comment \\#{comment_id} \\(Post \\#{post_id}\\)
**Reason:** {reason_emoji} {reason_description}
**Reporter:** User {user_id}
**Total Reports:** {report_count}
**Time:** {escape_markdown_text(timestamp[:16])}

**Content:**
{escape_markdown_text(preview)}

Please review and take appropriate action\\."""

        # Create action buttons for admins
        keyboard = [
            [
                InlineKeyboardButton("🔄 Replace Comment", callback_data=f"admin_delete_comment_{comment_id}"),
                InlineKeyboardButton("📖 View Full Post", callback_data=f"view_post_{post_id}")
            ],
            [
                InlineKeyboardButton("✅ Dismiss Report", callback_data=f"admin_dismiss_report_comment_{comment_id}"),
                InlineKeyboardButton("⛔ Block Reporter", callback_data=f"block_{user_id}")
            ]
        ]
        
    elif content_type == "post":
        post_id, content, category, timestamp = content_info
        preview = truncate_text(content, 150)
        admin_text = f"""🚨 **New Post Report**

**Reported Content:** Post \\#{post_id}
**Category:** {escape_markdown_text(category)}
**Reason:** {reason_emoji} {reason_description}
**Reporter:** User {user_id}
**Total Reports:** {report_count}
**Time:** {escape_markdown_text(timestamp[:16])}

**Content:**
{escape_markdown_text(preview)}

Please review and take appropriate action\\."""

        # Create action buttons for admins
        keyboard = [
            [
                InlineKeyboardButton("🗑️ Delete Post", callback_data=f"admin_delete_post_{post_id}"),
                InlineKeyboardButton("📖 View Full Post", callback_data=f"view_post_{post_id}")
            ],
            [
                InlineKeyboardButton("✅ Dismiss Report", callback_data=f"admin_dismiss_report_post_{post_id}"),
                InlineKeyboardButton("⛔ Block Reporter", callback_data=f"block_{user_id}")
            ]
        ]
    else:
        return False
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Send to all admins
    success_count = 0
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=admin_text,
                reply_markup=reply_markup,
                parse_mode="MarkdownV2"
            )
            success_count += 1
        except Exception as e:
            logger.error(f"Failed to send report notification to admin {admin_id}: {e}")
    
    return success_count > 0

def get_content_details(content_type, content_id):
    """Get details about reported content"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        
        if content_type == 'comment':
            cursor.execute(
                "SELECT comment_id, post_id, content, timestamp FROM comments WHERE comment_id = ?",
                (content_id,)
            )
        elif content_type == 'post':
            cursor.execute(
                "SELECT post_id, content, category, timestamp FROM posts WHERE post_id = ?",
                (content_id,)
            )
        else:
            return None
            
        return cursor.fetchone()

async def handle_report_reason_callback(update, context):
    """Handle report reason selection - now shows confirmation step"""
    query = update.callback_query
    await query.answer()
    
    # Parse callback data: report_reason_{content_type}_{content_id}_{reason_id}
    parts = query.data.split('_')
    if len(parts) < 5:
        await query.answer("❗ Invalid report data!")
        return
    
    content_type = parts[2]  # comment or post
    content_id = int(parts[3])
    reason_id = parts[4]
    
    user_id = update.effective_user.id
    
    # Get reason info for display
    reason_emoji, reason_description = get_report_reason_info(reason_id)
    
    # Get content preview for context
    content_preview = get_content_preview(content_type, content_id)
    if not content_preview:
        await query.answer("❗ Content not found or no longer available!")
        return
    
    preview_text = truncate_text(content_preview, 100)
    
    # Show confirmation screen
    confirmation_text = f"""🚩 **Report Confirmation**

**Content Preview:**
_{escape_markdown_text(preview_text)}_

**Your Report Reason:**
{reason_emoji} **{reason_description}**

**Are you sure you want to report this {content_type}?**

This action will notify administrators immediately for review\\."""
    
    # Create confirmation buttons
    keyboard = [
        [
            InlineKeyboardButton("✅ Submit Report", callback_data=f"submit_report_{content_type}_{content_id}_{reason_id}"),
            InlineKeyboardButton("🔙 Back", callback_data=f"report_{content_type}_{content_id}")
        ],
        [
            InlineKeyboardButton("🚫 Cancel", callback_data="cancel_report")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        confirmation_text,
        reply_markup=reply_markup,
        parse_mode="MarkdownV2"
    )

async def handle_submit_report(update, context):
    """Handle the actual report submission after confirmation"""
    query = update.callback_query
    await query.answer()
    
    # Parse callback data: submit_report_{content_type}_{content_id}_{reason_id}
    parts = query.data.split('_')
    if len(parts) < 5:
        await query.answer("❗ Invalid report data!")
        return
    
    content_type = parts[2]  # comment or post
    content_id = int(parts[3])
    reason_id = parts[4]
    
    user_id = update.effective_user.id
    
    # Submit the report
    success, result = submit_report(user_id, content_type, content_id, reason_id)
    
    if not success:
        if result == "already_reported":
            await query.edit_message_text(
                "⚠️ **Already Reported**\n\nYou have already reported this content\\. "
                "Our team will review it soon\\.",
                parse_mode="MarkdownV2"
            )
        else:
            await query.edit_message_text(
                "❗ **Error**\n\nThere was an error submitting your report\\. "
                "Please try again later\\.",
                parse_mode="MarkdownV2"
            )
        return
    
    report_count = result
    reason_emoji, reason_description = get_report_reason_info(reason_id)
    
    # Show confirmation to user
    await query.edit_message_text(
        f"✅ **Report Submitted Successfully**\n\n"
        f"**Reason:** {reason_emoji} {reason_description}\n\n"
        f"Thank you for helping keep our community safe\\. "
        f"Administrators have been notified and will review this content immediately\\.",
        parse_mode="MarkdownV2"
    )
    
    # Send immediate notification to admins
    try:
        notification_sent = await notify_admins_immediate(context, content_type, content_id, reason_id, user_id, report_count)
        if not notification_sent:
            logger.error(f"Failed to send admin notifications for report: {content_type}_{content_id}")
    except Exception as e:
        logger.error(f"Failed to notify admins about report: {e}")

async def handle_cancel_report(update, context):
    """Handle report cancellation"""
    query = update.callback_query
    await query.answer("Report cancelled")
    
    await query.edit_message_text(
        "🚫 **Report Cancelled**\n\n"
        "No report was submitted\\.",
        parse_mode="MarkdownV2"
    )

def dismiss_reports_for_content(content_type, content_id):
    """Dismiss all reports for specific content"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM reports WHERE target_type = ? AND target_id = ?",
            (content_type, content_id)
        )
        dismissed_count = cursor.rowcount
        conn.commit()
        return dismissed_count

async def handle_admin_dismiss_report(update, context):
    """Handle admin dismissing a report"""
    query = update.callback_query
    await query.answer()
    
    # Parse callback data
    data = query.data
    if "dismiss_report_comment_" in data:
        content_type = "comment"
        content_id = int(data.replace("admin_dismiss_report_comment_", ""))
    elif "dismiss_report_post_" in data:
        content_type = "post"
        content_id = int(data.replace("admin_dismiss_report_post_", ""))
    else:
        await query.answer("❗ Invalid dismiss data!")
        return
    
    # Dismiss all reports for this content
    dismissed_count = dismiss_reports_for_content(content_type, content_id)
    
    await query.edit_message_text(
        f"✅ **Reports Dismissed**\n\n"
        f"All reports for this {content_type} have been dismissed\\.\n"
        f"**Reports cleared:** {dismissed_count}",
        parse_mode="MarkdownV2"
    )
