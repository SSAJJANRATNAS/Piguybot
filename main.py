from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    filters, ContextTypes, ConversationHandler, CallbackQueryHandler
)
import asyncio
import re

# Conversation states
PI_AMOUNT, FULL_NAME, PHONE, PAN, WALLET, TXN_LINK, UPI = range(7)
ADMIN_ID = 5795065284

def get_rate():
    try:
        with open("rate.txt", "r") as f:
            return int(f.read().strip())
    except Exception:
        return 100

def set_rate(new_rate):
    with open("rate.txt", "w") as f:
        f.write(str(new_rate))

# ==== START COMMAND ====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        f"👋 Welcome to Pi-Guy Bot!\nCurrent rate: ₹{rate}/PI\n\nHow many PI would you like to sell?"
    )
    return PI_AMOUNT

# ==== ADMIN CALLBACK HANDLER ====
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "rate_show":
        await query.edit_message_text(f"💰 Current Pi Rate: ₹{get_rate()}/PI")
    elif query.data == "rate_set":
        await query.edit_message_text("✏️ Please send the new rate:")
        context.user_data["awaiting_rate"] = True

# ==== SET NEW RATE ====
async def catch_new_rate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("awaiting_rate") and update.effective_user.id == ADMIN_ID:
        try:
            new_rate = int(update.message.text.strip())
            set_rate(new_rate)
            await update.message.reply_text(f"✅ Rate updated to ₹{new_rate}/PI")
        except Exception:
            await update.message.reply_text("⚠️ Please send a valid number.")
        context.user_data["awaiting_rate"] = False
        return ConversationHandler.END
    return ConversationHandler.END

# ==== SELL FLOW ====
async def pi_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        pi = float(update.message.text.strip())
        rate = get_rate()
        context.user_data['pi'] = pi
        context.user_data['gross'] = pi * rate
        await update.message.reply_text("🪪 Enter full name (as per govt. ID):")
        return FULL_NAME
    except Exception:
        await update.message.reply_text("⚠️ Invalid PI amount.")
        return PI_AMOUNT

async def get_full_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['full_name'] = update.message.text.strip()
    await update.message.reply_text("📱 Enter your 10-digit mobile number:")
    return PHONE

async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phone = update.message.text.strip()
    if not phone.isdigit() or len(phone) != 10:
        await update.message.reply_text("⚠️ Invalid phone number.")
        return PHONE
    context.user_data['phone'] = phone
    await update.message.reply_text("🤖 Enter your PAN number (e.g., ABCDE1234F):")
    return PAN

async def get_pan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pan = update.message.text.strip().upper()
    if not re.fullmatch(r"[A-Z]{5}[0-9]{4}[A-Z]", pan):
        await update.message.reply_text("⚠️ Invalid PAN format.")
        return PAN
    context.user_data['pan'] = pan
    await update.message.reply_text("🔗 Enter your Pi wallet username (e.g., @piuser):")
    return WALLET

async def get_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['wallet'] = update.message.text.strip()
    # 1. User sees instruction
    await update.message.reply_text("Send Pi token to this address")
    # 2. Send QR
    with open("wallet_qr.png", "rb") as qr:
        await context.bot.send_photo(chat_id=update.effective_chat.id, photo=qr)
    # 3. Send wallet address in code block
    await update.message.reply_text(
        "✂️ Touch and copy this address:\n"
        "`MD5HGPHVL73EBDUD2Z4K2VDRLUBC4FFN7GOBLKPK6OPPXH6TED4TQAAAAGKTDJBVUS32G`",
        parse_mode="Markdown"
    )
    await update.message.reply_text("📤 Paste the Pi transaction link:")
    return TXN_LINK

async def get_txn_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    context.user_data['upi'] = update.message.text.strip()
    user = update.effective_user

    pi = context.user_data['pi']
    rate = get_rate()
    gross = pi * rate
    tax = gross * 0.30
    processing = gross * 0.01
    conversion = gross * 0.01
    net = gross - tax - processing - conversion

    # 1. Overview (for admin)
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
    # 2. Send each field for one-touch copy
    await context.bot.send_message(chat_id=ADMIN_ID, text=f"👤 Full Name:\n`{context.user_data['full_name']}`", parse_mode="Markdown")
    await context.bot.send_message(chat_id=ADMIN_ID, text=f"🆔 PAN:\n`{context.user_data['pan']}`", parse_mode="Markdown")
    await context.bot.send_message(chat_id=ADMIN_ID, text=f"📱 Phone:\n`{context.user_data['phone']}`", parse_mode="Markdown")
    await context.bot.send_message(chat_id=ADMIN_ID, text=f"👤 Telegram:\n`@{user.username or '-'} (ID: {user.id})`", parse_mode="Markdown")
    await context.bot.send_message(chat_id=ADMIN_ID, text=f"💰 PI Amount:\n`{pi}`", parse_mode="Markdown")
    await context.bot.send_message(chat_id=ADMIN_ID, text=f"💵 Gross:\n`₹{gross:.2f}`", parse_mode="Markdown")
    await context.bot.send_message(chat_id=ADMIN_ID, text=f"💸 Final Payable:\n`₹{net:.2f}`", parse_mode="Markdown")
    await context.bot.send_message(chat_id=ADMIN_ID, text=f"🌍 Wallet:\n`{context.user_data['wallet']}`", parse_mode="Markdown")
    await context.bot.send_message(chat_id=ADMIN_ID, text=f"🔗 Transaction:\n`{context.user_data['txn_link']}`", parse_mode="Markdown")
    await context.bot.send_message(chat_id=ADMIN_ID, text=f"📥 UPI:\n`{context.user_data['upi']}`", parse_mode="Markdown")

    # 3. Thank You message for seller
    await update.message.reply_text("📩 Thanks! Admin will verify and send payment.")

    # 4. Sell Pi Again button for seller
    keyboard = [
        [InlineKeyboardButton("🔄 Sell Pi Again", callback_data="sellpi_again")]
    ]
    await update.message.reply_text(
        "Do you want to sell more Pi?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return ConversationHandler.END

# ==== SELL AGAIN HANDLER ====
async def sellpi_again_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    return await start(update, context)

# ==== BUILD APP ====
app = ApplicationBuilder().token("7844315421:AAHAhynkSnFnw8I-mYvHZkFeBaVYVqTnxT4").build()

conv = ConversationHandler(
    entry_points=[CommandHandler("start", start)],
    states={
        PI_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, pi_amount)],
        FULL_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_full_name)],(filters.TEXT & ~filters.COMMAND, get_pan)],
        WALLET: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_wallet)],
        TXN_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_txn_link)],
        UPI: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_upi)],
    },
    fallbacks=[]
)

app.add_handler(conv)
app.add_handler(CallbackQueryHandler(button_handler))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, catch_new_rate))
app.add_handler(CallbackQueryHandler(sellpi_again_handler, pattern="^sellpi_again$"))

# ==== RUN BOT ====
if __name__ == "__main__":
    asyncio.run(app.run_polling())