import os
import re
import asyncio
import time
import random
import string
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, filters,
    ContextTypes, CallbackQueryHandler, ConversationHandler
)

ADMIN_ID = 5795065284
RATE_FILE = "rate.txt"
SELL_AMOUNT, SELL_NAME, SELL_PHONE, SELL_PAN, SELL_PI_TXN, SELL_UPI, NEW_RATE = range(7)
pending_transactions = {}

def get_sell_rate():
    if os.path.exists(RATE_FILE):
        with open(RATE_FILE, "r") as f:
            return float(f.read().strip())
    return None

def generate_txn_id(user_id=None):
    ts = time.strftime("%Y%m%d%H%M%S", time.gmtime())
    rand = ''.join(random.choices(string.ascii_uppercase + string.digits, k=3))
    uid = str(user_id)[-4:] if user_id else ''
    return f"TXN{ts}{uid}{rand}"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id == ADMIN_ID:
        keyboard = [[InlineKeyboardButton("✏️ Set Sell Rate", callback_data="set_rate")]]
        await update.message.reply_text("🛠 Admin Panel", reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        sell_rate = get_sell_rate()
        keyboard = [[InlineKeyboardButton("Sell Pi", callback_data="sell_pi")]]
        await update.message.reply_text(
            f"👋 Welcome!\n💸 Sell Pi Rate: ₹{sell_rate if sell_rate else '--'}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

async def set_rate_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text("✏️ Please send the new sell rate (numbers only):")
    return NEW_RATE

async def save_new_rate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        new_rate = float(update.message.text.strip())
        with open(RATE_FILE, "w") as f:
            f.write(str(new_rate))
        await update.message.reply_text(f"✅ Sell rate updated to ₹{new_rate}")
    except:
        await update.message.reply_text("⚠️ Invalid number. Please try again.")
    return ConversationHandler.END

async def option_choice_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "sell_pi":
        sell_rate = get_sell_rate()
        if sell_rate is None:
            await query.message.reply_text("❌ Sell rate not set. Please try again later.")
            return ConversationHandler.END
        await query.message.reply_text(f"💸 Current Sell Rate: ₹{sell_rate}\nHow many Pi do you want to sell?")
        return SELL_AMOUNT

async def sell_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        pi = float(update.message.text.strip())
        if pi <= 0:
            raise ValueError
        context.user_data['sell_pi'] = pi
        await update.message.reply_text("🪪 Please enter your full name:")
        return SELL_NAME
    except:
        await update.message.reply_text("⚠️ Invalid amount. Please enter again:")
        return SELL_AMOUNT

async def sell_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['sell_name'] = update.message.text.strip()
    await update.message.reply_text("📱 Enter your 10-digit mobile number:")
    return SELL_PHONE

async def sell_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phone = update.message.text.strip()
    if not phone.isdigit() or len(phone) != 10:
        await update.message.reply_text("⚠️ Invalid number. Try again:")
        return SELL_PHONE
    context.user_data['sell_phone'] = phone
    await update.message.reply_text("🤖 Enter your PAN number:")
    return SELL_PAN

async def sell_pan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pan = update.message.text.strip().upper()
    if not re.fullmatch(r"[A-Z]{5}[0-9]{4}[A-Z]", pan):
        await update.message.reply_text("⚠️ Invalid PAN format. Try again:")
        return SELL_PAN
    context.user_data['sell_pan'] = pan

    wallet_address = "GAP6UFB27DCORJA7LTGCCVVM2CD5VJJIHDRS34PIYUZNN663IDAEGNPL"
    await update.message.reply_text(
        f"✅ Send your Pi now to this wallet:\n`{wallet_address}`",
        parse_mode="Markdown"
    )
    await update.message.reply_text("🔗 After sending, paste your Pi transaction link:")
    return SELL_PI_TXN

async def sell_pi_txn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    link = update.message.text.strip()
    if not link.startswith("https://"):
        await update.message.reply_text("⚠️ Invalid link. Try again:")
        return SELL_PI_TXN
    context.user_data['sell_pi_txn'] = link
    await update.message.reply_text("💳 Enter your UPI ID or Paytm number:")
    return SELL_UPI

async def sell_upi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['sell_upi'] = update.message.text.strip()
    txn_id = generate_txn_id(update.effective_user.id)
    sell_rate = get_sell_rate()
    pi = context.user_data['sell_pi']
    gross = pi * sell_rate
    net = gross * 0.68
    pending_transactions[txn_id] = context.user_data

    # Notify user
    await update.message.reply_text(
        f"✅ Request submitted! Transaction ID: `{txn_id}`\nGross: ₹{gross:.2f}, Net: ₹{net:.2f}",
        parse_mode="Markdown"
    )

    # Notify admin
    msg = (
        f"📥 *New Sell Request*\n"
        f"👤 Name: {context.user_data['sell_name']}\n"
        f"📱 Phone: {context.user_data['sell_phone']}\n"
        f"🪪 PAN: {context.user_data['sell_pan']}\n"
        f"🔗 Txn Link: {context.user_data['sell_pi_txn']}\n"
        f"💳 UPI/Paytm: {context.user_data['sell_upi']}\n"
        f"💰 Amount: {pi} Pi\n"
        f"💸 Gross: ₹{gross:.2f}\n"
        f"✅ Net: ₹{net:.2f}\n"
        f"🆔 Transaction ID: `{txn_id}`"
    )
    await context.bot.send_message(chat_id=ADMIN_ID, text=msg, parse_mode="Markdown")
    return ConversationHandler.END

def main():
    TOKEN = os.getenv("BOT_TOKEN")
    app = ApplicationBuilder().token(TOKEN).build()

    conv = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CallbackQueryHandler(option_choice_handler, pattern="^sell_pi$"),
            CallbackQueryHandler(set_rate_callback, pattern="^set_rate$")
        ],
        states={
            SELL_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, sell_amount)],
            SELL_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, sell_name)],
            SELL_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, sell_phone)],
            SELL_PAN: [MessageHandler(filters.TEXT & ~filters.COMMAND, sell_pan)],
            SELL_PI_TXN: [MessageHandler(filters.TEXT & ~filters.COMMAND, sell_pi_txn)],
            SELL_UPI: [MessageHandler(filters.TEXT & ~filters.COMMAND, sell_upi)],
            NEW_RATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_new_rate)],
        },
        fallbacks=[]
    )

    app.add_handler(conv)
    print("🤖 Bot starting...")
    asyncio.run(app.run_polling())

if __name__ == "__main__":
    main()