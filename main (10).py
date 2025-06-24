from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler

PI_AMOUNT, FULL_NAME, PHONE, PAN, WALLET, TXN_LINK, UPI = range(7)
ADMIN_ID = 5795065284

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
        f"👋 Welcome to Pi-Guy Bot!\nCurrent rate: ₹{rate}/PI\nHow many PI would you like to sell?"
    )
    return PI_AMOUNT

async def pi_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        pi = float(update.message.text.strip())
        rate = get_rate()
        context.user_data['pi'] = pi
        context.user_data['gross'] = gross = pi * rate
        context.user_data['tax'] = gross * 0.30
        context.user_data['processing'] = gross * 0.01
        context.user_data['conversion'] = gross * 0.01
        context.user_data['net'] = gross - context.user_data['tax'] - context.user_data['processing'] - context.user_data['conversion']
        await update.message.reply_text("🪪 Enter your full name (as per government ID):")
        return FULL_NAME
    except:
        await update.message.reply_text("⚠️ Please enter a valid PI amount.")
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
    await update.message.reply_text("🆔 Enter your 10-character PAN (e.g., ABCDE1234F):")
    return PAN

async def get_pan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pan = update.message.text.strip().upper()
    import re
    if not re.fullmatch(r"[A-Z]{5}[0-9]{4}[A-Z]", pan):
        await update.message.reply_text("⚠️ Invalid PAN format.")
        return PAN
    context.user_data['pan'] = pan
    await update.message.reply_text("🔗 Enter your Pi Wallet username (e.g., @wallet):")
    return WALLET

async def get_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['wallet'] = update.message.text.strip()
    await update.message.reply_text(
        f"""✅ Please send {context.user_data['pi']} PI to the wallet below:\n✂️ *Tap and copy this address:*\n`MD5HGPHVL73EBDUD2Z4K2VDRLUBC4FFN7GOBLKPK6OPPXH6TED4TQAAAAGKTDJBVUS32G`\n\n📷 Scan this QR to send:""", parse_mode="Markdown"
    )
    with open("wallet_qr.png", "rb") as qr:
        await context.bot.send_photo(chat_id=update.effective_chat.id, photo=qr)
    await update.message.reply_text("📤 Paste your Pi transaction link (from blockexplorer):")
    return TXN_LINK


async def get_txn_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    link = update.message.text.strip()
    import re
    valid_prefixes = [
        "https://blockexplorer.minepi.com/mainnet/tx/",
        "https://blockexplorer.minepi.com/mainnet/transactions/"
    ]
    valid = any(link.startswith(p) and re.fullmatch(r"[a-fA-F0-9]{64}", link[len(p):]) for p in valid_prefixes)
    if not valid:
        await update.message.reply_text("⚠️ Invalid Pi transaction link. Please paste the full link from blockexplorer.", parse_mode="Markdown")
        return TXN_LINK
    context.user_data['txn_link'] = link
    await update.message.reply_text("💳 Enter your UPI ID or Paytm number:")
    return UPI
    context.user_data['txn_link'] = link
    await update.message.reply_text("💳 Enter your UPI ID or Paytm number:")
    return UPI

async def get_upi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['upi'] = update.message.text.strip()
    user = update.effective_user
    await context.bot.send_message(chat_id=ADMIN_ID, text=
        f"🧾 *New Pi Sell Request*\n"
        f"👤 *Full Name:* `{context.user_data['full_name']}`\n"
        f"🆔 *PAN:* `{context.user_data['pan']}`\n"
        f"📱 *Phone:* `{context.user_data['phone']}`\n"
        f"👤 User: @{user.username} (ID: {user.id})\n\n"
        f"💰 PI Amount: {context.user_data['pi']} (₹{context.user_data['gross']})\n\n"
        f"🪙 Wallet:\n`{context.user_data['wallet']}`\n\n"
        f"🔗 Transaction Link:\n`{context.user_data['txn_link']}`\n\n"
        f"📥 UPI:\n`{context.user_data['upi']}`\n\n"
        f"📉 Deductions:\n"
        f"  - ₹{context.user_data['tax']:.2f} Govt Tax\n"
        f"  - ₹{context.user_data['processing']:.2f} Processing Fee\n"
        f"  - ₹{context.user_data['conversion']:.2f} Conversion Fee\n\n"
        f"💸 Final Amount:\n`₹{context.user_data['net']:.2f}`",
        parse_mode="Markdown"
    )
    await update.message.reply_text("📩 Your request has been received. The admin will verify and send your payment soon.")
    return ConversationHandler.END

app = ApplicationBuilder().token("7844315421:AAHAhynkSnFnw8I-mYvHZkFeBaVYVqTnxT4").build()
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
    },
    fallbacks=[]
)
app.add_handler(conv)
app.run_polling()
