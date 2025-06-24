
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler, CallbackQueryHandler

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
    if update.effective_user.id == ADMIN_ID:
        keyboard = [
            [InlineKeyboardButton("💰 Show Rate", callback_data="rate_show"),
             InlineKeyboardButton("✏️ Set Rate", callback_data="rate_set")]
        ]
        markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("🛠 Admin Panel", reply_markup=markup)
        return ConversationHandler.END
    rate = get_rate()
    await update.message.reply_text(f"""👋 Welcome to Pi-Guy Bot!
Current rate: ₹{rate}/PI
How many PI would you like to sell?""")
    return PI_AMOUNT

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
            set_rate(new_rate)
            await update.message.reply_text(f"✅ Rate updated to ₹{new_rate}/PI")
        except:
            await update.message.reply_text("⚠️ Please send a valid number.")
        context.user_data["awaiting_rate"] = False
        return ConversationHandler.END
    return ConversationHandler.END

# all main bot logic (pi_amount, get_full_name, etc.) would go here...
# skipping for brevity since your logic already includes that part

app = ApplicationBuilder().token("7844315421:AAHAhynkSnFnw8I-mYvHZkFeBaVYVqTnxT4").build()

# Add existing handlers
# (Assuming 'conv' handler already exists from previous logic)
# app.add_handler(conv)

app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(button_handler))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, catch_new_rate))
