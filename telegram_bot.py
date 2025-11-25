import logging
import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
import toml
import os

# Import database functions
# Note: We need to make sure we're in the right directory or path is set
from database import link_telegram_user, get_user_by_telegram_id, get_user_current_event, add_expense

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Load secrets
try:
    secrets = toml.load(".streamlit/secrets.toml")
    BOT_TOKEN = secrets["telegram"]["bot_token"]
except Exception as e:
    print("❌ Error loading secrets. Make sure .streamlit/secrets.toml exists and has [telegram] section with 'bot_token'.")
    exit(1)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/start command handler"""
    user_id = update.effective_user.id
    username = get_user_by_telegram_id(user_id)
    
    if username:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"👋 Welcome back, {username}! I'm ready to help you manage expenses."
        )
    else:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=(
                "👋 Hi! I'm the SplitSync Bot.\n\n"
                "To link your account, please send:\n"
                "`/link <your_username>`\n\n"
                "Example: `/link john_doe`"
            ),
            parse_mode='Markdown'
        )

async def link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/link command handler"""
    user_id = update.effective_user.id
    
    if not context.args:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="⚠️ Please provide your username.\nUsage: `/link <username>`", parse_mode='Markdown')
        return

    target_username = context.args[0]
    
    # In a real app, we'd use a secure code, but for this MVP we'll just use username
    # Security Note: Anyone could claim a username if they know it. 
    # Better approach: Generate a code in the web app and use that.
    
    if link_telegram_user(target_username, user_id):
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"✅ Successfully linked to **{target_username}**! You can now add expenses.",
            parse_mode='Markdown'
        )
    else:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"❌ Could not find user '{target_username}'. Please check the spelling."
        )

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/status command handler"""
    user_id = update.effective_user.id
    username = get_user_by_telegram_id(user_id)
    
    if not username:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="⚠️ You are not linked. Use `/link <username>` first.", parse_mode='Markdown')
        return
        
    event = get_user_current_event(username)
    if event:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"📊 **Current Event**: {event['name']}\nCurrency: {event.get('currency', 'USD')}",
            parse_mode='Markdown'
        )
    else:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="ℹ️ You are not part of any events yet."
        )

async def add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/add command handler - /add 50 Lunch"""
    user_id = update.effective_user.id
    username = get_user_by_telegram_id(user_id)
    
    if not username:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="⚠️ You are not linked. Use `/link <username>` first.", parse_mode='Markdown')
        return

    if len(context.args) < 2:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="⚠️ Usage: `/add <amount> <description>`\nExample: `/add 50 Lunch`", parse_mode='Markdown')
        return
        
    try:
        amount = float(context.args[0])
        description = " ".join(context.args[1:])
    except ValueError:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="❌ Invalid amount. Please use a number.")
        return
        
    event = get_user_current_event(username)
    if not event:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="❌ You need to be in an event to add expenses.")
        return
        
    # Add expense logic
    # We assume equal split among all members for simplicity in the bot
    # Or we could just add it with the payer as the only participant (which doesn't make sense)
    # Let's assume split equally among all event members for now
    
    participants = event.get('members', [])
    if not participants:
        participants = [username] # Fallback
        
    # Call database function
    # Note: add_expense in database.py might need to be adapted or we use the one we imported
    # We need to make sure add_expense is importable and works
    
    if add_expense(event['id'], username, amount, description, event.get('currency', 'USD'), participants, username):
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"✅ **Expense Added!**\n\n💸 {event.get('currency', 'USD')} {amount:.2f}\n📝 {description}\n📍 {event['name']}",
            parse_mode='Markdown'
        )
    else:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="❌ Failed to add expense. Please try again.")

if __name__ == '__main__':
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('link', link))
    application.add_handler(CommandHandler('status', status))
    application.add_handler(CommandHandler('add', add))
    
    print("🤖 Bot is running...")
    application.run_polling()
