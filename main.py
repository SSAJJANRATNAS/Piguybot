import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    filters, ContextTypes, ConversationHandler, CallbackQueryHandler
)
import asyncio
import re
import requests

PI_AMOUNT, FULL_NAME, PHONE, PAN, WALLET, TXN_LINK, UPI = range(7)
ADMIN_ID = 5795065284

def get_rate():
    try:
        url = "https://api.coingecko.com/api/v3/simple/price?ids=pi-network&vs_currencies=inr"
        response = requests.get(url, timeout=10)
        data = response.json()
        return data["pi-network"]["inr"]
    except Exception:
        return 100

# Helper to send timer update
async def send_timer_update(context: ContextTypes.DEFAULT_TYPE, chat_id, remaining):
    mins, secs = divmod(remaining, 60)
    time_str = f"{mins}:{secs:02d} minutes left to complete the process."
    await context.bot.send_message(chat_id=chat_id, text=f"⏳ {time_str}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    if update.effective_user.id == ADMIN_ID:
        keyboard = [
            [
                InlineKeyboardButton("💰 Show Rate", callback_data="rate_show"),
                InlineKeyboardButton("✏️ Set Rate", callback_data="rate_set")
            ]
        ]
        await update.message.reply_text(
            "🛠 Admin Panel",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return ConversationHandler.END

    rate = get_rate()
    await update.message.reply_text(
        f"👋 Welcome to Pi-Guy Bot!\nCurrent rate: ₹{rate}/PI\n\nHow many PI would you like to sell?\n\n⏳ You have 5 minutes to complete this process."
    )

    # Start a countdown timer task
    chat_id = update.effective_chat.id
    context.user_data['timer_task'] = asyncio.create_task(timer_reminder(context, chat_id))

    return PI_AMOUNT

async def timer_reminder(context: ContextTypes.DEFAULT_TYPE, chat_id):
    # Sends timer reminders at 4, 3, 2, 1 min left
    intervals = [240, 180, 120, 60]  # seconds remaining
    start_time = asyncio.get_event_loop().time()
    for sec in intervals:
        now = asyncio.get_event_loop().time()
        await asyncio.sleep(sec - (now - start_time))
        await send_timer_update(context, chat_id, sec)
    # No need to send 0:00 left (timeout handler will do final message)

def cancel_timer_task(context: ContextTypes.DEFAULT_TYPE):
    task = context.user_data.get('timer_task')
    if task and not task.done():
        task.cancel()

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "rate_show":
        await query.edit_message_text(f"💰 Current Pi Rate: ₹{get_rate()}/PI")
    elif query.data == "rate_set":
        await query.edit_message_text("✏️ Please send the new rate:")
        context.user_data["awaiting_rate"] = True

async def catch_new_rate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("awaiting_rate") and update.effective_user.id == ADMIN_ID:
        try:
            new_rate = int(update.message.text.strip())
            with open("rate.txt", "w") as f:
                f.write(str(new_rate))
            await update.message.reply_text(f"✅ Rate updated to ₹{new_rate}/PI (Note: Now bot fetches live rate from CoinGecko!)")
        except Exception:
            await update.message.reply_text("⚠️ Please send a valid number.")
        context.user_data["awaiting_rate"] = False
        return ConversationHandler.END
    return ConversationHandler.END

async def pi_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cancel_timer_task(context)
    await update.message.reply_text("🪪 Enter full name (as per govt. ID):")
    # Restart timer for this step
    chat_id = update.effective_chat.id
    context.user_data['timer_task'] = asyncio.create_task(timer_reminder(context, chat_id))
    try:
        pi = float(update.message.text.strip())
        rate = get_rate()
        context.user_data['pi'] = pi
        context.user_data['gross'] = pi * rate
        return FULL_NAME
    except Exception:
        await update.message.reply_text("⚠️ Invalid PI amount.")
        return PI_AMOUNT

async def get_full_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cancel_timer_task(context)
    await update.message.reply_text("📱 Enter your 10-digit mobile number:")
    chat_id = update.effective_chat.id
    context.user_data['timer_task'] = asyncio.create_task(timer_reminder(context, chat_id))
    context.user_data['full_name'] = update.message.text.strip()
    return PHONE

async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cancel_timer_task(context)
    await update.message.reply_text("🤖 Enter your PAN number (e.g., ABCDE1234F):")
    chat_id = update.effective_chat.id
    context.user_data['timer_task'] = asyncio.create_task(timer_reminder(context, chat_id))
    phone = update.message.text.strip()
    if not phone.isdigit() or len(phone) != 10:
        await update.message.reply_text("⚠️ Invalid phone number.")
        return PHONE
    context.user_data['phone'] = phone
    return PAN

async def get_pan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cancel_timer_task(context)
    await update.message.reply_text("🔗 Enter your Pi wallet username (e.g., @piuser):")
    chat_id = update.effective_chat.id
    context.user_data['timer_task'] = asyncio.create_task(timer_reminder(context, chat_id))
    pan = update.message.text.strip().upper()
    if not re.fullmatch(r"[A-Z]{5}[0-9]{4}[A-Z]", pan):
        await update.message.reply_text("⚠️ Invalid PAN format.")
        return PAN
    context.user_data['pan'] = pan
    return WALLET

async def get_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cancel_timer_task(context)
    chat_id = update.effective_chat.id
    context.user_data['timer_task'] = asyncio.create_task(timer_reminder(context, chat_id))
    context.user_data['wallet'] = update.message.text.strip()
    await update.message.reply_text("Send Pi token to this address")
    with open("wallet_qr.png", "rb") as qr:
        await context.bot.send_photo(chat_id=update.effective_chat.id, photo=qr)
    await update.message.reply_text(
        "✂️ Touch and copy this address:\n"
        "`MD5HGPHVL73EBDUD2Z4K2VDRLUBC4FFN7GOBLKPK6OPPXH6TED4TQAAAAGKTDJBVUS32G`",
        parse_mode="Markdown"
    )
    await update.message.reply_text("📤 Paste the Pi transaction link:")
    return TXN_LINK

async def get_txn_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cancel_timer_task(context)
    chat_id = update.effective_chat.id
    context.user_data['timer_task'] = asyncio.create_task(timer_reminder(context, chat_id))
    link = update.message.text.strip()
    valid = any(
        link.startswith(p) and re.fullmatch(r"[a-fA-F0-9]{64}", link[len(p):])
        for p in [
            "https://blockexplorer.minepi.com/mainnet/tx/",
            "https://blockexplorer.minepi.com/mainnet/transactions/"
        ]
    )
    if not valid:
        await update.message.reply_text("⚠️ Invalid transaction link.")
        return TXN_LINK
    context.user_data['txn_link'] = link
    await update.message.reply_text("💳 Enter your UPI ID or Paytm number:")
    return UPI

async def get_upi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cancel_timer_task(context)
    context.user_data['upi'] = update.message.text.strip()
    user = update.effective_user

    pi = context.user_data['pi']
    rate = get_rate()
    gross = pi * rate
    tax = gross * 0.30
    processing = gross * 0.01
    conversion = gross * 0.01
    net = gross - tax - processing - conversion

    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=(
            f"🧾 *New Pi Sell Request*\n\n"
            f"👤 *Full Name:* `{context.user_data['full_name']}`\n"
            f"🆔 *PAN:* `{context.user_data['pan']}`\n"
            f"📱 *Phone:* `{context.user_data['phone']}`\n"
            f"👤 *Telegram:* @{user.username or '-'} (ID: {user.id})\n\n"
            f"💰 *PI Amount:* {pi} (₹{gross:.2f})\n"
            f"💵 *Gross:* ₹{gross:.2f}\n"
            f"📉 *Deductions:*\n"
            f"• ₹{tax:.2f} Govt Tax (30%)\n"
            f"• ₹{processing:.2f} Processing Fee (1%)\n"
            f"• ₹{conversion:.2f} Conversion Fee (1%)\n\n"
            f"💸 *Final Payable:* `₹{net:.2f}`\n\n"
            f"🌍 *Wallet:* `{context.user_data['wallet']}`\n"
            f"🔗 *Transaction:*\n{context.user_data['txn_link']}\n"
            f"📥 *UPI:* `{context.user_data['upi']}`"
        ),
        parse_mode="Markdown"
    )

    keyboard = [
        [InlineKeyboardButton("🔄 Sell Pi Again", callback_data="sellpi_again")]
    ]
    await update.message.reply_text("📩 Thanks! Admin will verify and send payment.")
    await update.message.reply_text(
        "To sell Pi again, type /start.",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return ConversationHandler.END

async def sellpi_again_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text(
        "To sell Pi again, type /start."
    )
    return ConversationHandler.END

async def timeout_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update and update.effective_chat:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="⏰ Time's up! Try again. To sell Pi, touch on this blue part /start"
        )
    return ConversationHandler.END

conv = ConversationHandler(
    entry_points=[CommandHandler("start", start)],
    states={
        PI_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, pi_amount)],
        FULL_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_full_name)],
        PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone)],
        PAN: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_pan)],
        WALLET: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_wallet)],
        TXN_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_txn_link)],
        UPI: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_upi)],
        ConversationHandler.TIMEOUT: [MessageHandler(filters.ALL, timeout_handler)],
    },
    fallbacks=[CallbackQueryHandler(sellpi_again_handler, pattern="^sellpi_again$")],
    conversation_timeout=300
)

# --- TOKEN ENVIRONMENT VARIABLE USAGE ---
TOKEN = os.environ.get("BOT_TOKEN")
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(conv)
app.add_handler(CallbackQueryHandler(button_handler))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, catch_new_rate))

if __name__ == "__main__":
    print("🤖 Bot is starting...")
    asyncio.run(app.run_polling())