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
        f"👋 Pi Seller Bot mein swagat hai!\nAaj ka rate hai: ₹{rate}/PI\nAap kitni PI bechna chahenge?"
    )
    return PI_AMOUNT

async def pi_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        pi = float(update.message.text.strip())
        context.user_data['pi'] = pi
        context.user_data['total'] = pi * get_rate()
        await update.message.reply_text("Apna Pi Wallet username bhejiye (jaise @example):")
        return WALLET
    except:
        await update.message.reply_text("⚠️ Kripya valid sankhya bhejein.")
        return PI_AMOUNT

async def get_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['wallet'] = update.message.text.strip()
    await update.message.reply_text(
        f"✅ Kripya {context.user_data['pi']} PI bhejiye is wallet par:\n👉 @MD5HGPHVL73EBDUD2Z4K2VDRLUBC4FFN7GOBLKPK6OPPXH6TED4TQAAAAGKTDJBVUS32G\n\nPI bhejne ke baad, kripya Transaction ID bhejiye."
    )
    return TXN

async def get_txn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['txn'] = update.message.text.strip()
    await update.message.reply_text("Ab apna UPI ID ya Paytm number bhejiye:")
    return UPI

async def get_upi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['upi'] = update.message.text.strip()
    user = update.effective_user
    await context.bot.send_message(chat_id=ADMIN_ID, text=
        f"🧾 *New Pi Sell Request*\n"
        f"👤 User: @{user.username} (ID: {user.id})\n"
        f"💰 PI Amount: {context.user_data['pi']} (₹{context.user_data['total']})\n"
        f"🪙 Wallet: {context.user_data['wallet']}\n"
        f"🔁 TXN ID: {context.user_data['txn']}\n"
        f"📥 UPI: {context.user_data['upi']}"
    )
    await update.message.reply_text(
        f"📩 Dhanyavaad! Aapki jankari prapt ho gayi.\nAdmin verify karke aapko ₹{context.user_data['total']} bhej dega."
    )
    return ConversationHandler.END

async def rate_command(update, context):
    await update.message.reply_text(f"💰 Current Pi Rate: ₹{get_rate()}/PI")

async def setrate_command(update, context):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Aap authorize nahi hain.")
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
