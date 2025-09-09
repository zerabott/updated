import sqlite3
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from config import ADMIN_IDS, CHANNEL_ID, BOT_USERNAME, DB_PATH
from db import get_comment_count
from submission import get_post_with_media, is_media_post, get_media_info, get_media_type_emoji

# Import ranking system integration
from ranking_integration import award_points_for_confession_approval, RankingIntegration

def approve_post(post_id, message_id, post_number):
    """Approve a post and save channel message ID with sequential post number"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE posts SET approved=1, channel_message_id=?, post_number=? WHERE post_id=?",
            (message_id, post_number, post_id)
        )
        conn.commit()

def reject_post(post_id, rejection_reason=None):
    """Reject a post with optional rejection reason"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE posts SET approved=0, rejection_reason=? WHERE post_id=?", (rejection_reason, post_id))
        conn.commit()

def get_next_post_number():
    """Get the next sequential post number for approved posts"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT MAX(post_number) FROM posts WHERE post_number IS NOT NULL")
        result = cursor.fetchone()
        return (result[0] + 1) if result[0] is not None else 1

def flag_post(post_id):
    """Flag a post for review"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE posts SET flagged=1 WHERE post_id=?", (post_id,))
        conn.commit()

def block_user(user_id):
    """Block a user"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET blocked=1 WHERE user_id=?", (user_id,))
        conn.commit()

def unblock_user(user_id):
    """Unblock a user"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET blocked=0 WHERE user_id=?", (user_id,))
        conn.commit()

def get_post_by_id(post_id):
    """Get a specific post by ID"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM posts WHERE post_id=?", (post_id,))
        return cursor.fetchone()

def is_blocked_user(user_id):
    """Check if user is blocked"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT blocked FROM users WHERE user_id=?", (user_id,))
        result = cursor.fetchone()
        return result and result[0] == 1

async def handle_final_rejection(update: Update, context: ContextTypes.DEFAULT_TYPE, post_id: int, rejection_reason: str):
    """Handle the final rejection process with reason"""
    try:
        # Get post details
        post = get_post_by_id(post_id)
        if not post:
            if update.callback_query:
                await update.callback_query.edit_message_text("❗ Post not found.")
            else:
                await update.message.reply_text("❗ Post not found.")
            return
        
        # Get submitter info
        submitter_id = post[4]  # user_id is at index 4
        category = post[2]  # category is at index 2
        
        # Reject the post with reason
        reject_post(post_id, rejection_reason)
        
        # Clear admin state
        context.user_data.pop('admin_rejecting_post_id', None)
        context.user_data.pop('admin_rejecting_submitter_id', None)
        context.user_data.pop('admin_rejecting_category', None)
        context.user_data.pop('state', None)
        
        # Update admin interface
        if update.callback_query:
            await update.callback_query.edit_message_text(
                f"❌ *Submission rejected\\.*\n\n"
                f"**Reason:** {rejection_reason}\n\n"
                f"The user has been notified with the rejection reason\\.",
                parse_mode="MarkdownV2"
            )
        else:
            await update.message.reply_text(
                f"❌ *Submission rejected\\.*\n\n"
                f"**Reason:** {rejection_reason}\n\n"
                f"The user has been notified with the rejection reason\\.",
                parse_mode="MarkdownV2"
            )
        
        # Get admin info for logging
        admin_id = None
        if update and update.effective_user:
            admin_id = update.effective_user.id
        
        # Deduct points for rejected confession
        if admin_id is not None:
            await RankingIntegration.handle_confession_rejected(submitter_id, post_id, admin_id)
        
        # Notify the submitter with rejection reason
        if submitter_id:
            try:
                # Import escape function for proper markdown formatting
                from utils import escape_markdown_text
                
                # Determine if this is a media post
                confession_type = "confession"
                media_info = get_media_info(post_id)
                if media_info:
                    media_type_name = media_info['type'].title()
                    emoji = get_media_type_emoji(media_info['type'])
                    confession_type = f"{emoji} {media_type_name} confession"
                
                # Build notification message with reason
                message_text = f"""
❌ *{confession_type.title()} Rejected*

Your {escape_markdown_text(confession_type)} in category `{escape_markdown_text(category)}` was not approved for the following reason:

💬 *Admin feedback:*
_{escape_markdown_text(rejection_reason)}_

📝 *What's next?*
You can review the feedback and submit a new confession that addresses the concerns mentioned above\\.

🌟 *Thank you for your understanding\\!*
"""
                
                # Create keyboard with helpful buttons
                keyboard = [
                    [InlineKeyboardButton("🆕 Submit New Confession", callback_data="start_confession")],
                    [InlineKeyboardButton("📞 Contact Admin", callback_data="contact_admin")],
                    [InlineKeyboardButton("🏠 Main Menu", callback_data="menu")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                # Send notification
                await context.bot.send_message(
                    chat_id=submitter_id,
                    text=message_text,
                    parse_mode="MarkdownV2",
                    reply_markup=reply_markup
                )
            except Exception as e:
                logging.warning(f"Could not notify user {submitter_id} about rejection: {e}")
                
    except Exception as e:
        logging.error(f"Error in handle_final_rejection: {e}")
        try:
            if update.callback_query:
                await update.callback_query.edit_message_text(
                    f"❗ Error processing rejection: {e}"
                )
            else:
                await update.message.reply_text(
                    f"❗ Error processing rejection: {e}"
                )
        except:
            pass

async def handle_admin_rejection_reason_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle admin's custom rejection reason text input"""
    if not update.message or not update.message.text:
        return
    
    # Check if admin is in rejection reason input state
    if context.user_data.get('state') != 'admin_writing_rejection_reason':
        return
    
    post_id = context.user_data.get('admin_rejecting_post_id')
    if not post_id:
        await update.message.reply_text("❗ Error: Post ID not found. Please try again.")
        return
    
    rejection_reason = update.message.text.strip()
    
    # Validate rejection reason
    if len(rejection_reason) < 10:
        await update.message.reply_text(
            "⚠️ Please provide a more detailed rejection reason (at least 10 characters). "
            "This helps users understand how to improve their submissions."
        )
        return
    
    if len(rejection_reason) > 500:
        await update.message.reply_text(
            "⚠️ Rejection reason is too long. Please keep it under 500 characters."
        )
        return
    
    # Process the rejection with custom reason
    await handle_final_rejection(update, context, post_id, rejection_reason)
    
    # Send confirmation to admin
    await update.message.reply_text(
        f"✅ Rejection processed with custom reason.\n\n"
        f"**Reason:** {rejection_reason}"
    )

async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle admin approval/rejection callbacks"""
    if not update or not update.callback_query:
        return
    
    query = update.callback_query
    await query.answer()
    
    if not query or not query.data:
        return
    
    data = query.data
    admin_id = None
    if update and update.effective_user:
        admin_id = update.effective_user.id
    
    if admin_id not in ADMIN_IDS:
        try:
            await query.edit_message_text("❗ You are not authorized to moderate.")
        except:
            pass
        return

    if data.startswith("approve_"):
        post_id = int(data.split("_")[1])
        post = get_post_by_id(post_id)
        if not post:
            try:
                await query.edit_message_text("❗ Post not found.")
            except:
                pass
            return
        
        # Check if post is already approved (prevent duplicate approvals)
        # Use safe indexing to avoid index out of range errors
        if len(post) > 5 and post[5] == 1:  # approved field is at index 5
            try:
                await query.edit_message_text(
                    "✅ Approved by another admin\\!\n\n"
                    "This post was already approved by a different admin\\. "
                    "You can still view it in the channel\\.",
                    parse_mode="MarkdownV2"
                )
            except:
                pass
            return
        
        # Check if post is already rejected
        if len(post) > 5 and post[5] == 0:  # approved field is at index 5
            try:
                await query.edit_message_text(
                    "❌ Already rejected\\!\n\n"
                    "This post was already rejected by a different admin\\. "
                    "No further action is needed\\.",
                    parse_mode="MarkdownV2"
                )
            except:
                pass
            return
        
        # Get submitter info
        submitter_id = post[4]  # user_id is at index 4
        category = post[2]  # category is at index 2
        
        # Initialize post_number to None
        post_number = None
        
        try:
            # Get the next sequential post number
            post_number = get_next_post_number()
            
            # Get current comment count
            comment_count = get_comment_count(post_id)
            
            # Create inline buttons for the channel post
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
            
            # Test channel access first
            try:
                # Try to get channel info to verify access
                await context.bot.get_chat(CHANNEL_ID)
                channel_accessible = True
            except Exception as e:
                logging.warning(f"Channel {CHANNEL_ID} not accessible: {e}")
                channel_accessible = False
            
            # Convert categories into hashtags
            categories = post[2]  # category is at index 2
            # Create the category hashtags
            categories_text = " ".join(
                [f"#{cat.strip().replace(' ', '')}" for cat in categories.split(",")]
            )
            
            # Check if this is a media post
            is_media = False
            media_info = None
            
            # Get media information
            media_info = get_media_info(post_id)
            if media_info:
                is_media = True
            
            # Award points for approved confession
            submitter_id = post[4]  # user_id is at index 4
            
            # Try to post to the channel only if accessible
            # Initialize variables
            content = post[1]  # content is at index 1
            msg = None
            channel_post_successful = False
            
            if channel_accessible:
                # Check if this is a media post
                if is_media and media_info:
                    # Prepare caption with post number, text content, and hashtags
                    caption_text = f"<b>Confess # {post_number}</b>\n\n"
                    
                    # Add text content if available
                    if content and content.strip():
                        caption_text += f"{content}\n\n"
                    
                    # Add media caption if available and different from main content
                    if media_info.get('caption') and media_info['caption'] != content:
                        caption_text += f"{media_info['caption']}\n\n"
                    
                    # Add hashtags
                    caption_text += categories_text
                    
                    # Send media message based on type
                    if media_info['type'] == 'photo':
                        msg = await context.bot.send_photo(
                            chat_id=CHANNEL_ID,
                            photo=media_info['file_id'],
                            caption=caption_text,
                            parse_mode="HTML",
                            reply_markup=reply_markup
                        )
                    elif media_info['type'] == 'video':
                        msg = await context.bot.send_video(
                            chat_id=CHANNEL_ID,
                            video=media_info['file_id'],
                            caption=caption_text,
                            parse_mode="HTML",
                            reply_markup=reply_markup
                        )
                    elif media_info['type'] == 'animation':
                        msg = await context.bot.send_animation(
                            chat_id=CHANNEL_ID,
                            animation=media_info['file_id'],
                            caption=caption_text,
                            parse_mode="HTML",
                            reply_markup=reply_markup
                        )
                    else:
                        # Fallback to text message if media type is not supported
                        msg = await context.bot.send_message(
                            chat_id=CHANNEL_ID,
                            text=f"<b>Confess # {post_number}</b>\n\n"
                                f"<i>[Media type '{media_info['type']}' not supported]</i>\n\n"
                                f"{content}\n\n"
                                f"{categories_text}",
                            parse_mode="HTML",
                            reply_markup=reply_markup
                        )
                else:
                    # Text-only post
                    msg = await context.bot.send_message(
                        chat_id=CHANNEL_ID,
                        text=f"<b>Confess # {post_number}</b>\n\n"
                            f"{content}\n\n"
                            f"{categories_text}",
                        parse_mode="HTML",
                        reply_markup=reply_markup
                    )
                    
                if msg:
                    channel_post_successful = True
                    
            # Handle case where channel is not accessible
            if not channel_accessible:
                logging.warning(f"Channel not accessible, approving post {post_id} without posting to channel")
                # Still approve the post in database without channel message ID
                approve_post(post_id, None, post_number)
            
            # Update the post with the channel message ID and post number
            if msg:
                approve_post(post_id, msg.message_id, post_number)
                
            try:
                if channel_accessible and msg:
                    await query.edit_message_text(f"✅ Approved and posted to channel as Post #{post_number}.")
                elif channel_accessible and not msg:
                    await query.edit_message_text(f"✅ Approved as Post #{post_number}, but failed to post to channel.")
                else:
                    await query.edit_message_text(f"✅ Approved as Post #{post_number}. (Channel not accessible - post saved locally)")
            except:
                pass
            
            # Award points for approved confession
            if admin_id is not None:
                await award_points_for_confession_approval(submitter_id, post_id, admin_id, context)
            
            # Notify the submitter with media support
            if submitter_id:
                try:
                    # Import escape function for proper markdown formatting
                    from utils import escape_markdown_text
                    
                    # Determine confession type for notification
                    confession_type = "confession"
                    if is_media and media_info:
                        media_type_name = media_info['type'].title()
                        emoji = get_media_type_emoji(media_info['type'])
                        confession_type = f"{emoji} {media_type_name} confession"
                    
                    # Generate proper channel link if possible
                    channel_link_text = "Check the channel"  # Default fallback
                    if msg:
                        try:
                            if CHANNEL_ID < 0:
                                # Private channel - use c/ format
                                # Remove the -100 prefix that Telegram adds to supergroups
                                channel_link_id = str(CHANNEL_ID)[4:] if str(CHANNEL_ID).startswith('-100') else str(abs(CHANNEL_ID))
                                channel_link_text = f"[View in Channel](https://t.me/c/{channel_link_id}/{msg.message_id})"
                            else:
                                # Public channel - try to get username
                                try:
                                    chat = await context.bot.get_chat(CHANNEL_ID)
                                    if hasattr(chat, 'username') and chat.username:
                                        channel_link_text = f"[View in Channel](https://t.me/{chat.username}/{msg.message_id})"
                                    else:
                                        # Public channel but no username available
                                        channel_link_text = f"[View in Channel](https://t.me/c/{CHANNEL_ID}/{msg.message_id})"
                                except Exception as e:
                                    logging.warning(f"Could not get channel info for link: {e}")
                                    channel_link_text = f"[View in Channel](https://t.me/c/{CHANNEL_ID}/{msg.message_id})"
                        except Exception as e:
                            logging.warning(f"Error generating channel link: {e}")
                            channel_link_text = "Check the channel"
                    
                    # Build the notification message with proper escaping
                    message_text = f"""
✅ *{confession_type.title()} Approved\\!*

Your {escape_markdown_text(confession_type)} in category `{escape_markdown_text(category)}` has been approved and posted to the channel\\!

🔢 *Post Number:* \\#{post_number}

💡 {channel_link_text}

🌟 *Thank you for sharing with us\\!*
"""
                    
                    # Create keyboard with helpful buttons
                    keyboard = [
                        [InlineKeyboardButton("🆕 Submit New Confession", callback_data="start_confession")],
                        [InlineKeyboardButton("📋 View My Stats", callback_data="my_stats")],
                        [InlineKeyboardButton("🏠 Main Menu", callback_data="menu")]
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    
                    # Send notification with proper formatting
                    await context.bot.send_message(
                        chat_id=submitter_id,
                        text=message_text,
                        parse_mode="MarkdownV2",
                        reply_markup=reply_markup,
                        disable_web_page_preview=False
                    )
                except Exception as e:
                    logging.warning(f"Could not notify user {submitter_id}: {e}")
                    
        except Exception as e:
            logging.error(f"Failed to post to channel: {e}")
            try:
                await query.edit_message_text(f"❗ Failed to post to channel: {e}")
            except:
                pass

    elif data.startswith("reject_"):
        # Get post details
        post_id = int(data.split("_")[1])
        post = get_post_by_id(post_id)
        if not post:
            try:
                await query.edit_message_text("❗ Post not found.")
            except:
                pass
            return
        
        # Check if post is already rejected (prevent duplicate rejections)
        # Use safe indexing to avoid index out of range errors
        if len(post) > 5 and post[5] == 0:  # approved field is at index 5
            try:
                # Get post number if it exists
                post_number = None
                try:
                    post_number = get_next_post_number()
                except:
                    pass
                
                await query.edit_message_text(
                    f"❌ This post has already been rejected by another admin\\. \nYou can still view it in the channel as post #{post_number if post_number is not None else 'unknown'}\\.",
                    parse_mode="MarkdownV2"
                )
            except:
                pass
            return

        # Check if post is already approved
        if len(post) > 5 and post[5] == 1:  # approved field is at index 5
            try:
                # Get post number if it exists
                post_number = None
                try:
                    post_number = get_next_post_number()
                except:
                    pass
                
                await query.edit_message_text(
                    f"✅ Already approved by another admin\\!\n\nThis post was already approved and posted to the channel as post #{post_number if post_number is not None else 'unknown'}\\.",
                    parse_mode="MarkdownV2"
                )
            except:
                pass
            return
        
        # Get submitter info
        submitter_id = post[4]  # user_id is at index 4
        category = post[2]  # category is at index 2
        
        # Start rejection reason flow - ask admin for reason
        context.user_data['admin_rejecting_post_id'] = post_id
        context.user_data['admin_rejecting_submitter_id'] = submitter_id
        context.user_data['admin_rejecting_category'] = category
        context.user_data['state'] = 'admin_providing_rejection_reason'
        
        # Create keyboard with quick reason options and custom option
        # Use short callback data to avoid Telegram's 64-byte limit
        quick_reasons = [
            [InlineKeyboardButton("❌ Inappropriate Content", callback_data=f"qreject_{post_id}_1")],
            [InlineKeyboardButton("📝 Incomplete/Unclear", callback_data=f"qreject_{post_id}_2")],
            [InlineKeyboardButton("🔁 Duplicate Content", callback_data=f"qreject_{post_id}_3")],
            [InlineKeyboardButton("⚠️ Spam/Low Quality", callback_data=f"qreject_{post_id}_4")],
            [InlineKeyboardButton("✏️ Write Custom Reason", callback_data=f"custom_reject_{post_id}")],
            [InlineKeyboardButton("🚫 Cancel Rejection", callback_data=f"cancel_reject_{post_id}")]
        ]
        reply_markup = InlineKeyboardMarkup(quick_reasons)
        
        try:
            await query.edit_message_text(
                "📝 *Please provide a reason for rejection:*\n\n"
                "Choose a quick reason below or select 'Write Custom Reason' to provide your own specific feedback\\.",
                reply_markup=reply_markup,
                parse_mode="MarkdownV2"
            )
        except Exception as e:
            logging.error(f"Error showing rejection reason options: {e}")
            # Fallback to direct rejection if UI fails
            reject_post(post_id, "Rejected by admin")
            try:
                await query.edit_message_text("❌ Submission rejected.")
            except:
                pass
    
    elif data.startswith("qreject_"):
        # Handle quick rejection with predefined reason using short callback data
        parts = data.split("_")  # qreject_postid_reasoncode
        if len(parts) < 3:
            return
        
        post_id = int(parts[1])  # Extract post_id
        reason_code = parts[2]   # Extract reason code
        
        # Map reason codes to full rejection messages
        reason_map = {
            "1": "Inappropriate content - violates community guidelines",
            "2": "Incomplete or unclear submission", 
            "3": "Duplicate or repetitive content",
            "4": "Spam or low quality content"
        }
        
        rejection_reason = reason_map.get(reason_code, "Rejected by admin")
        
        await handle_final_rejection(update, context, post_id, rejection_reason)
    
    elif data.startswith("custom_reject_"):
        # Handle custom rejection reason request
        post_id = int(data.split("_")[2])
        context.user_data['admin_rejecting_post_id'] = post_id
        context.user_data['state'] = 'admin_writing_rejection_reason'
        
        # Create cancel button
        cancel_keyboard = [[InlineKeyboardButton("🚫 Cancel", callback_data=f"cancel_reject_{post_id}")]]
        cancel_reply_markup = InlineKeyboardMarkup(cancel_keyboard)
        
        try:
            await query.edit_message_text(
                "✏️ *Please type your custom rejection reason:*\n\n"
                "Provide specific feedback to help the user understand why their submission was rejected\\. "
                "Be constructive and helpful in your explanation\\.",
                reply_markup=cancel_reply_markup,
                parse_mode="MarkdownV2"
            )
        except Exception as e:
            logging.error(f"Error requesting custom rejection reason: {e}")
    
    elif data.startswith("cancel_reject_"):
        # Handle cancellation of rejection
        post_id = int(data.split("_")[2])
        
        # Get post details to access user_id
        post = get_post_by_id(post_id)
        if not post:
            try:
                await query.edit_message_text("❗ Post not found.")
            except:
                pass
            return
        
        # Clear rejection state
        context.user_data.pop('admin_rejecting_post_id', None)
        context.user_data.pop('admin_rejecting_submitter_id', None)
        context.user_data.pop('admin_rejecting_category', None)
        context.user_data.pop('state', None)
        
        # Restore original admin panel for this post
        keyboard = [
            [
                InlineKeyboardButton("✅ Approve", callback_data=f"approve_{post_id}"),
                InlineKeyboardButton("❌ Reject", callback_data=f"reject_{post_id}")
            ],
            [
                InlineKeyboardButton("🚩 Flag", callback_data=f"flag_{post_id}"),
                InlineKeyboardButton("⛔ Block User", callback_data=f"block_{post[4]}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        try:
            await query.edit_message_text(
                "🔄 *Rejection cancelled\\.*\n\n"
                "Please choose an action for this submission\\:",
                reply_markup=reply_markup,
                parse_mode="MarkdownV2"
            )
        except Exception as e:
            logging.error(f"Error cancelling rejection: {e}")

    elif data.startswith("flag_"):
        # Handle flagging
        post_id = int(data.split("_")[1])
        flag_post(post_id)
        
        try:
            await query.edit_message_text("🚩 Submission flagged for review.")
        except:
            pass

    elif data.startswith("block_"):
        # Handle blocking
        block_uid = int(data.split("_")[1])
        block_user(block_uid)
        
        try:
            await query.edit_message_text(f"⛔ User {block_uid} blocked.")
        except:
            pass

    elif data.startswith("unblock_"):
        # Handle unblocking
        block_uid = int(data.split("_")[1])
        unblock_user(block_uid)
        
        try:
            await query.edit_message_text(f"✅ User {block_uid} unblocked.")
        except:
            pass

    # Handle other cases
