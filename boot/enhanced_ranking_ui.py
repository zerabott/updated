#!/usr/bin/env python3
"""
Enhanced Ranking UI with Better Progress Visualization and User Experience
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes
from typing import List, Dict, Optional
import math
from datetime import datetime, timedelta

from enhanced_ranking_system import EnhancedPointSystem, EnhancedAchievementSystem
from enhanced_leaderboard import EnhancedLeaderboardManager, LeaderboardType
from enhanced_ranking_system import UserRank
from ranking_integration import ranking_manager
from utils import escape_markdown_text
from logger import get_logger

logger = get_logger('enhanced_ranking_ui')

def format_number_for_markdown(value: float, decimal_places: int = 1) -> str:
    """Format a number for MarkdownV2 display, escaping decimal points"""
    if decimal_places == 0:
        formatted = f"{value:.0f}"
    else:
        formatted = f"{value:.{decimal_places}f}"
    
    # Escape decimal points for MarkdownV2
    return formatted.replace('.', '\.')  

class EnhancedRankingUI:
    """Enhanced UI components with better visualizations"""
    
    @staticmethod
    def create_advanced_progress_bar(current: int, maximum: int, length: int = 15) -> str:
        """Create an advanced progress bar with realistic loading appearance"""
        if maximum == 0:
            return "█" * length + " 100% MAXED!"
        
        # Ensure we don't have negative values
        current = max(0, current)
        progress = min(current / maximum, 1.0) if maximum > 0 else 0
        filled = int(progress * length)
        empty = length - filled
        
        # Use realistic loading bar characters
        fill_char = "█"  # Solid block
        empty_char = "░"  # Light shade
        
        bar = fill_char * filled + empty_char * empty
        percentage = f"{int(progress * 100)}%"
        
        return f"{bar} {percentage}"
    
    @staticmethod
    def create_streak_visualization(streak_days: int) -> str:
        """Create visual representation of streak"""
        if streak_days == 0:
            return "📅 No streak yet - start your journey!"
        elif streak_days < 7:
            return f"🔥 {streak_days} day streak - keep it up!"
        elif streak_days < 30:
            return f"⚡ {streak_days} day streak - you're on fire!"
        elif streak_days < 90:
            return f"🚀 {streak_days} day streak - amazing dedication!"
        elif streak_days < 365:
            return f"👑 {streak_days} day streak - you're a legend!"
        else:
            return f"🌟 {streak_days} day streak - ULTIMATE DEVOTEE!"
    
    @staticmethod
    def format_enhanced_rank_display(user_rank: UserRank, user_id: int) -> str:
        """Enhanced rank display with more visual elements"""
        # Calculate progress to next rank with debugging info
        if user_rank.points_to_next > 0:
            # Direct approach: calculate what percentage of the way we are to next rank
            # If next_rank_points = 1000 and points_to_next = 200, then we're at 800/1000 = 80%
            current_points_in_rank = user_rank.next_rank_points - user_rank.points_to_next
            progress_percentage = int((current_points_in_rank / user_rank.next_rank_points) * 100)
            
            # Ensure percentage is within valid range
            progress_percentage = max(0, min(100, progress_percentage))
            
            # Create the visual progress bar
            filled_blocks = int((progress_percentage / 100) * 12)
            empty_blocks = 12 - filled_blocks
            progress_bar = f"{'█' * filled_blocks}{'░' * empty_blocks} {progress_percentage}%"
            
            next_rank_text = f"Next: {user_rank.points_to_next:,} points to go"
            
        else:
            progress_bar = "████████████ 100% MAXED!"
            next_rank_text = "🎉 Maximum rank achieved!"
        
        # Get streak visualization
        from db_connection import get_db_connection
        db_conn = get_db_connection()
        with db_conn.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT consecutive_days FROM user_rankings WHERE user_id = %s", (user_id,))
            result = cursor.fetchone()
            streak_days = result[0] if result else 0
        
        streak_viz = EnhancedRankingUI.create_streak_visualization(streak_days)
        
        # Special rank indicator
        rank_indicator = "⭐ SPECIAL RANK" if user_rank.is_special_rank else "📊 Standard Rank"
        
        rank_text = f"""
 🏆 *YOUR RANKING STATUS*

 {escape_markdown_text(user_rank.rank_emoji)} **{escape_markdown_text(user_rank.rank_name)}** {escape_markdown_text('(' + rank_indicator + ')')}
 💎 **{user_rank.total_points:,} Total Points**

 📈 *Progress to Next Rank*
 {progress_bar}
 {escape_markdown_text(next_rank_text)}

 {escape_markdown_text(streak_viz)}

 🎯 **{user_rank.total_points:,}** total points earned
 🏅 **{ranking_manager.get_user_achievements(user_id).__len__()}** achievements unlocked
 """
        
        return rank_text
    
    # ... rest of the file unchanged ...
