import os
import re
import asyncio
import time
import random
import string
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler, ConversationHandler
import qrcode
from io import BytesIO

ADMIN_ID = 5795065284
RATE_FILE = "rate.txt"
SELL_AMOUNT, SELL_NAME, SELL_PHONE, SELL_PAN, SELL_PI_TXN, SELL_UPI = range(6)
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
    keyboard = [[InlineKeyboardButton("Sell Pi", callback_data="sell_pi")]]
    sell_rate = get_sell_rate()
    msg = f"👋 Welcome!\n\n💸 Sell Pi Rate: ₹{sell_rate if sell_rate else '--'}"
    await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))

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
        await update.message.reply_text("🪪 Please enter your full name (as per government ID):")
        return SELL_NAME
    except:
        await update.message.reply_text("⚠️ Invalid amount. Please enter again:")
        return SELL_AMOUNT

async def sell_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['sell_name'] = update.message.text.strip()
    await update.message.reply_text("📱 Please enter your 10-digit mobile number:")
    return SELL_PHONE

async def sell_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phone = update.message.text.strip()
    if not phone.isdigit() or len(phone) != 10:
        await update.message.reply_text("⚠️ Invalid phone number. Please enter again:")
        return SELL_PHONE
    context.user_data['sell_phone'] = phone
    await update.message.reply_text("🤖 Please enter your PAN number (e.g., ABCDE1234F):")
    return SELL_PAN

async def sell_pan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pan = update.message.text.strip().upper()
    if not re.fullmatch(r"[A-Z]{5}[0-9]{4}[A-Z]", pan):
        await update.message.reply_text("⚠️ Invalid PAN format. Please enter again:")
        return SELL_PAN
    context.user_data['sell_pan'] = pan

    wallet_address = "GAP6UFB27DCORJA7LTGCCVVM2CD5VJJIHDRS34PIYUZNN663IDAEGNPL"
    await update.message.reply_text(f"✅ Please send your Pi now to the following wallet address:\n\n`{wallet_address}`", parse_mode="Markdown")

    qr_img = qrcode.make(wallet_address)
    bio = BytesIO()
    bio.name = 'wallet_qr.png'
    qr_img.save(bio, 'PNG')
    bio.seek(0)
    await update.message.reply_photo(photo=bio, caption="🔗 Scan this QR to send Pi.")

    await update.message.reply_text("🔗 After sending Pi, please paste your Pi transaction link:")
    return SELL_PI_TXN

async def sell_pi_txn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    link = update.message.text.strip()
    if not link.startswith("https://"):
        await update.message.reply_text("⚠️ Invalid link. Please enter again:")
        return SELL_PI_TXN
    context.user_data['sell_pi_txn'] = link
    await update.message.reply_text("💳 Please enter your UPI ID or Paytm number:")
    return SELL_UPI

async def sell_upi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['sell_upi'] = update.message.text.strip()
    user = update.effective_user
    txn_id = generate_txn_id(user.id)

    pi = context.user_data['sell_pi']
    rate = get_sell_rate()
    gross = pi * rate
    net = gross * 0.68

    pending_transactions[txn_id] = {
        "user_id": user.id,
        "pi": pi,
        "name": context.user_data['sell_name'],
        "phone": context.user_data['sell_phone'],
        "pan": context.user_data['sell_pan'],
        "pi_txn": context.user_data['sell_pi_txn'],
        "upi": context.user_data['sell_upi']
    }

    msg = (
        f"🧾 *New Pi Sell Request*\n"
        f"🆔 *Transaction ID:* `{txn_id}`\n"
        f"👤 *Name:* `{context.user_data['sell_name']}`\n"
        f"📱 *Phone:* `{context.user_data['sell_phone']}`\n"
        f"🆔 *PAN:* `{context.user_data['sell_pan']}`\n"
        f"💰 *Amount:* {pi} Pi (₹{gross:.2f})\n"
        f"💸 *Net Payable:* ₹{net:.2f}\n"
        f"🔗 *Txn:* {context.user_data['sell_pi_txn']}\n"
        f"💳 *UPI:* `{context.user_data['sell_upi']}`"
    )
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Approve", callback_data=f"approve_sell_{txn_id}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"reject_{txn_id}")
        ]
    ])
    await context.bot.send_message(chat_id=ADMIN_ID, text=msg, parse_mode="Markdown", reply_markup=keyboard)
    await update.message.reply_text("✅ Request sent to admin. You will be notified soon.")
    return ConversationHandler.END

async def admin_action_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    if data.startswith("approve_sell_"):
        txn_id = data.split("_", 2)[2]
        info = pending_transactions.get(txn_id)
        if info:
            await context.bot.send_message(info["user_id"], f"✅ Your sell request `{txn_id}` approved. Payment will be sent shortly.")
            await query.message.reply_text(f"Approved: {txn_id}")
            pending_transactions.pop(txn_id, None)
    elif data.startswith("reject_"):
        txn_id = data.split("_", 1)[1]
        info = pending_transactions.get(txn_id)
        if info:
            await context.bot.send_message(info["user_id"], f"❌ Your sell request `{txn_id}` rejected.")
            await query.message.reply_text(f"Rejected: {txn_id}")
            pending_transactions.pop(txn_id, None)

def main():
    TOKEN = os.getenv("BOT_TOKEN")
    app = ApplicationBuilder().token(TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start), CallbackQueryHandler(option_choice_handler, pattern="^sell_pi$")],
        states={
            SELL_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, sell_amount)],
            SELL_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, sell_name)],
            SELL_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, sell_phone)],
            SELL_PAN: [MessageHandler(filters.TEXT & ~filters.COMMAND, sell_pan)],
            SELL_PI_TXN: [MessageHandler(filters.TEXT & ~filters.COMMAND, sell_pi_txn)],
            SELL_UPI: [MessageHandler(filters.TEXT & ~filters.COMMAND, sell_upi)],
        },
        fallbacks=[],
        conversation_timeout=300
    )

    app.add_handler(conv)
    app.add_handler(CallbackQueryHandler(admin_action_handler, pattern="^(approve_sell_|reject_)", block=False))

    print("🤖 Bot starting...")
    asyncio.run(app.run_polling())

if __name__ == "__main__":
    main()