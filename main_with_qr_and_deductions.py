from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    filters, ContextTypes, ConversationHandler
)

PI_AMOUNT, WALLET, TXN, UPI = range(4)
ADMIN_ID = 5795065284  # Your Telegram ID

def get_rate():
    try:
        with open("rate.txt", "r") as f:
            return int(f.read().strip())
    except:
        return 100

def set_rate(new_rate):
    with open("rate.txt", "w") as f:
        f.write(str(new_rate))

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rate = get_rate()
    await update.message.reply_text(
        f"👋 Welcome to Pi Seller Bot!\nCurrent rate: ₹{rate}/PI\nHow many PI coins would you like to sell?"
    )
    return PI_AMOUNT

async def pi_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        pi = float(update.message.text.strip())
        context.user_data['pi'] = pi
        context.user_data['gross'] = gross = pi * get_rate()
        context.user_data['tax'] = tax = gross * 0.30
        context.user_data['processing'] = processing = gross * 0.01
        context.user_data['conversion'] = conversion = gross * 0.01
        context.user_data['net'] = net = gross - (tax + processing + conversion)
        await update.message.reply_text("Please enter your Pi Wallet username (e.g., @example):")
        return WALLET
    except:
        await update.message.reply_text("⚠️ Please enter a valid number.")
        return PI_AMOUNT

async def get_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['wallet'] = update.message.text.strip()
    await update.message.reply_text(
        f"✅ Please send {context.user_data['pi']} PI to this wallet:\n👉 MD5HGPHVL73EBDUD2Z4K2VDRLUBC4FFN7GOBLKPK6OPPXH6TED4TQAAAAGKTDJBVUS32G\n\n📷 Scan this QR to send:"
    )
    # Send QR code image
    with open("wallet_qr.png", "rb") as qr:
        await context.bot.send_photo(chat_id=update.effective_chat.id, photo=qr)
    await update.message.reply_text("After sending, please provide the transaction ID.")
    return TXN

async def get_txn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['txn'] = update.message.text.strip()
    await update.message.reply_text("Now please enter your UPI ID or Paytm number to receive payment:")
    return UPI

async def get_upi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['upi'] = update.message.text.strip()
    user = update.effective_user
    await context.bot.send_message(chat_id=ADMIN_ID, text=
        f"🧾 *New Pi Sell Request*\n"
        f"👤 User: @{user.username} (ID: {user.id})\n"
        f"💰 PI Amount: {context.user_data['pi']} (₹{context.user_data['gross']})\n"
        f"🪙 Wallet: {context.user_data['wallet']}\n"
        f"🔁 TXN ID: {context.user_data['txn']}\n"
        f"📥 UPI: {context.user_data['upi']}\n"
        f"📉 Deductions:\n"
        f"   - ₹{context.user_data['tax']:.2f} Govt Tax\n"
        f"   - ₹{context.user_data['processing']:.2f} Processing Fee\n"
        f"   - ₹{context.user_data['conversion']:.2f} USD to INR Conversion\n"
        f"💸 Final Amount: ₹{context.user_data['net']:.2f}"
    )
    await update.message.reply_text(
        f"📩 Thank you! Your request has been received.\n\n"
        f"🧾 You sold {context.user_data['pi']} PI for ₹{context.user_data['gross']:.2f}\n"
        f"📉 Deductions:\n"
        f"  • ₹{context.user_data['tax']:.2f} Govt Tax (30%)\n"
        f"  • ₹{context.user_data['processing']:.2f} Processing Fee (1%)\n"
        f"  • ₹{context.user_data['conversion']:.2f} USD→INR Conversion Fee (1%)\n\n"
        f"💸 Final amount you'll receive: ₹{context.user_data['net']:.2f}\n\n"
        f"The admin will verify your transaction and send your payment shortly."
    )
    return ConversationHandler.END

async def rate_command(update, context):
    await update.message.reply_text(f"💰 Current Pi Rate: ₹{get_rate()}/PI")

async def setrate_command(update, context):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ You are not authorized.")
        return
    try:
        new_rate = int(context.args[0])
        set_rate(new_rate)
        await update.message.reply_text(f"✅ Rate updated to ₹{new_rate}/PI")
    except:
        await update.message.reply_text("⚠️ Usage: /setrate 105")

app = ApplicationBuilder().token("7844315421:AAHW-zAQJjXRGEr_lItZNeugulELYb8d4").build()

conv_handler = ConversationHandler(
    entry_points=[CommandHandler("start", start)],
    states={
        PI_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, pi_amount)],
        WALLET: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_wallet)],
        TXN: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_txn)],
        UPI: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_upi)],
    },
    fallbacks=[]
)

app.add_handler(conv_handler)
app.add_handler(CommandHandler("rate", rate_command))
app.add_handler(CommandHandler("setrate", setrate_command))
app.run_polling()
