import os
import logging
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Updater,
    CommandHandler,
    MessageHandler,
    Filters,
    CallbackContext,
)
from pymongo import MongoClient
from dotenv import load_dotenv
from PIL import Image
import google.generativeai as gemini

# Load environment variables
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Configure logging
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

# MongoDB setup
client = MongoClient(MONGO_URI)
db = client.telegram_bot

# Gemini API setup
gemini.configure(api_key=GEMINI_API_KEY)

# Start command: Registers user
def start(update: Update, context: CallbackContext):
    user = update.effective_user
    chat_id = user.id

    # Save user to MongoDB if not already registered
    if not db.users.find_one({"chat_id": chat_id}):
        db.users.insert_one(
            {"first_name": user.first_name, "username": user.username, "chat_id": chat_id}
        )
        logging.info(f"New user registered: {user.username}")

    # Request phone number
    contact_button = ReplyKeyboardMarkup(
        [[KeyboardButton("Share Phone Number", request_contact=True)]], resize_keyboard=True
    )
    update.message.reply_text("Welcome! Please share your phone number to complete registration.", reply_markup=contact_button)

# Handles contact sharing
def contact_handler(update: Update, context: CallbackContext):
    contact = update.message.contact
    db.users.update_one(
        {"chat_id": contact.user_id}, {"$set": {"phone_number": contact.phone_number}}
    )
    update.message.reply_text("Thank you! Your phone number has been saved.")

# Gemini-powered chat
def chat_handler(update: Update, context: CallbackContext):
    user_message = update.message.text
    try:
        gemini_response = gemini.chat(messages=[{"text": user_message}])["text"]

        # Store chat history in MongoDB
        db.chat_history.insert_one(
            {
                "chat_id": update.effective_chat.id,
                "user_input": user_message,
                "bot_response": gemini_response,
                "timestamp": datetime.utcnow(),
            }
        )
        update.message.reply_text(gemini_response)

    except Exception as e:
        logging.error(f"Gemini API error: {e}")
        update.message.reply_text("Sorry, I couldn't process that right now.")

# Handles image/file analysis
def file_handler(update: Update, context: CallbackContext):
    file = update.message.document or update.message.photo[-1]
    file_name = file.file_name if hasattr(file, 'file_name') else "photo.jpg"
    file_path = file.get_file().download()

    try:
        # Example Gemini analysis (placeholder; actual API may differ)
        gemini_analysis = f"Analysis of {file_name} completed by Gemini AI."

        # Save metadata to MongoDB
        db.files.insert_one(
            {
                "file_name": file_name,
                "chat_id": update.effective_chat.id,
                "description": gemini_analysis,
                "timestamp": datetime.utcnow(),
            }
        )
        update.message.reply_text(f"File analyzed: {gemini_analysis}")

    except Exception as e:
        logging.error(f"File analysis error: {e}")
        update.message.reply_text("Sorry, I couldn't analyze the file.")

# Web search functionality
def web_search(update: Update, context: CallbackContext):
    query = " ".join(context.args)
    if not query:
        update.message.reply_text("Please provide a query after /websearch.")
        return

    try:
        # Perform web search (replace with actual API call or scraping logic)
        search_results = f"Results for '{query}' retrieved by AI."
        
        # Save to MongoDB
        db.web_search.insert_one(
            {"chat_id": update.effective_chat.id, "query": query, "results": search_results, "timestamp": datetime.utcnow()}
        )
        update.message.reply_text(search_results)

    except Exception as e:
        logging.error(f"Web search error: {e}")
        update.message.reply_text("Sorry, I couldn't perform the web search.")

# Main function to start the bot
def main():
    updater = Updater(TELEGRAM_TOKEN)
    dispatcher = updater.dispatcher

    # Command handlers
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("websearch", web_search))

    # Message handlers
    dispatcher.add_handler(MessageHandler(Filters.contact, contact_handler))
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, chat_handler))
    dispatcher.add_handler(MessageHandler(Filters.document | Filters.photo, file_handler))

    # Start the bot
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
