import os
import re
import asyncio
import time
import random
import string
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, Chat
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    filters, ContextTypes, CallbackQueryHandler, ConversationHandler
)
import qrcode
from io import BytesIO

# === CONFIGURATION ===
ADMIN_ID = 5795065284  # Change to your Telegram user ID
ADMIN_UPI_ID = "sajjanrohdiya@ybl"
ADMIN_UPI_NAME = "SAJJAN SINGH S/O KISHAN SINGH"
RATE_FILE = "rate.txt"  # For admin rate setting
ESCROW_RATE = 0.03

# Sell Pi states (private)
SELL_AMOUNT, SELL_NAME, SELL_PHONE, SELL_PAN, SELL_PI_TXN, SELL_UPI = range(6)
# Buy Pi states (private)
BUY_AMOUNT, BUY_NAME, BUY_PHONE, BUY_PAN, BUY_WALLET_ADDRESS, BUY_UPI_TXN = range(6, 12)

# Escrow status states (group)
(
    ESCROW_IDLE,  # not used, but for clarity
    ESCROW_WAIT_BUYER_PROOF,
    ESCROW_WAIT_SELLER_PROOF,
    ESCROW_WAIT_ADMIN_RELEASE,
) = range(4)

pending_transactions = {}  # For private trades
escrows = {}  # For group escrows

def get_sell_rate():
    if os.path.exists(RATE_FILE):
        try:
            with open(RATE_FILE, "r") as f:
                return float(f.read().strip())
        except Exception:
            return None
    return None

def get_buy_rate():
    sell_rate = get_sell_rate()
    if sell_rate is not None:
        return round(sell_rate + 1, 2)
    return None

def generate_txn_id(user_id=None):
    ts = time.strftime("%Y%m%d%H%M%S", time.gmtime())
    rand = ''.join(random.choices(string.ascii_uppercase + string.digits, k=3))
    uid = str(user_id)[-4:] if user_id else ''
    return f"TXN{ts}{uid}{rand}"

def commission_and_total(amount):
    comm = round(amount * ESCROW_RATE, 2)
    total = round(amount + comm, 2)
    return comm, total

async def send_upi_qr(context, chat_id, upi_id, name, amount, txnid):
    upi_link = (
        f"upi://pay?pa={upi_id}"
        f"&pn={name.replace(' ', '%20')}"
        f"&tr={txnid}"
        f"&mc=0000"
        f"&am={amount}"
        f"&mam={amount}"
        f"&cu=INR"
        f"&tn=Pay"
    )
    qr_img = qrcode.make(upi_link)
    bio = BytesIO()
    bio.name = 'upi_qr.png'
    qr_img.save(bio, 'PNG')
    bio.seek(0)
    await context.bot.send_photo(
        chat_id=chat_id,
        photo=bio,
        caption=f"Scan this QR to pay ₹{amount}\n\n{upi_link}"
    )

# --- GROUP ESCROW FLOW ---

async def group_sellpi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type not in [Chat.GROUP, Chat.SUPERGROUP]:
        return
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("Usage: /sellpi <amount> <upi_id>")
        return
    try:
        amount = float(args[0])
        upi_id = args[1]
    except Exception:
        await update.message.reply_text("Invalid format. Usage: /sellpi <amount> <upi_id>")
        return
    seller = update.effective_user
    context.bot_data.setdefault("sell_offers", []).append({
        "user_id": seller.id,
        "username": seller.username,
        "upi_id": upi_id,
        "amount": amount,
        "msg_id": update.message.message_id,
        "group_id": update.effective_chat.id,
    })
    await update.message.reply_text(
        f"🔔 Sell Offer: {amount} Pi for INR. UPI: {upi_id}\nPosted by @{seller.username or seller.id}.\n"
        "Buyers, use /buypi <amount> <wallet_address> to match this offer."
    )

async def group_buypi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type not in [Chat.GROUP, Chat.SUPERGROUP]:
        return
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("Usage: /buypi <amount> <wallet_address>")
        return
    try:
        amount = float(args[0])
        wallet_address = args[1]
    except Exception:
        await update.message.reply_text("Invalid format. Usage: /buypi <amount> <wallet_address>")
        return
    buyer = update.effective_user
    sell_offers = context.bot_data.get("sell_offers", [])
    match = None
    for offer in sell_offers:
        if abs(offer["amount"] - amount) < 0.0001:
            match = offer
            break
    if not match:
        await update.message.reply_text("No matching sell offer found for this amount.")
        return
    sell_offers.remove(match)
    txn_id = generate_txn_id()
    comm, total = commission_and_total(amount)
    escrows[txn_id] = {
        "buyer_id": buyer.id,
        "buyer_username": buyer.username,
        "buyer_wallet": wallet_address,
        "seller_id": match["user_id"],
        "seller_username": match.get("username"),
        "seller_upi": match["upi_id"],
        "amount": amount,
        "commission": comm,
        "total_inr": total,
        "status": ESCROW_WAIT_BUYER_PROOF,
        "buyer_payment_proof": None,
        "seller_transfer_proof": None,
        "group_id": update.effective_chat.id,
    }
    await update.message.reply_text(
        f"🔗 Escrow Trade Matched!\n"
        f"@{buyer.username or buyer.id} (Buyer) ↔️ @{match.get('username') or match['user_id']} (Seller)\n"
        f"Amount: {amount} Pi\n"
        f"Buyer pays: ₹{total} (incl. ₹{comm} commission)\n"
        f"Escrow Transaction ID: {txn_id}\n"
        f"Bot will DM both for next steps."
    )
    buyer_msg = (
        f"Hi! You are buyer in escrow trade `{txn_id}` for {amount} Pi.\n"
        f"Pay ₹{total} (includes ₹{comm} commission) to admin UPI via QR or link below.\n"
        "After payment, reply here with your UPI Transaction ID or screenshot."
    )
    await context.bot.send_message(buyer.id, buyer_msg)
    await send_upi_qr(context, buyer.id, ADMIN_UPI_ID, ADMIN_UPI_NAME, total, txn_id)
    seller_msg = (
        f"Hi! You are seller in escrow trade `{txn_id}` for {amount} Pi.\n"
        f"Bot will notify you when buyer payment received in escrow. Then you must transfer {amount} Pi to buyer's wallet:\n{wallet_address}\n"
        "Wait for bot instruction before sending Pi."
    )
    await context.bot.send_message(match["user_id"], seller_msg)

async def buyer_payment_proof(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text or ""
    proof = text.strip()
    for txn_id, esc in escrows.items():
        if esc["buyer_id"] == user.id and esc["status"] == ESCROW_WAIT_BUYER_PROOF:
            esc["buyer_payment_proof"] = proof or "screenshot"
            esc["status"] = ESCROW_WAIT_SELLER_PROOF
            await context.bot.send_message(
                ADMIN_ID,
                f"Buyer proof uploaded for escrow `{txn_id}`.\nAmount: ₹{esc['total_inr']}\nProof: {proof}\n"
                f"Check UPI and use /adminrelease {txn_id} after confirming both sides."
            )
            await context.bot.send_message(
                esc["seller_id"],
                f"Buyer has paid to escrow for trade `{txn_id}`.\nNow send {esc['amount']} Pi to wallet: {esc['buyer_wallet']} and reply with your Pi transfer proof (txn ID or link)."
            )
            await update.message.reply_text("Payment proof received. Waiting for seller to transfer Pi.")
            return

async def seller_transfer_proof(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text or ""
    proof = text.strip()
    for txn_id, esc in escrows.items():
        if esc["seller_id"] == user.id and esc["status"] == ESCROW_WAIT_SELLER_PROOF:
            esc["seller_transfer_proof"] = proof or "screenshot"
            esc["status"] = ESCROW_WAIT_ADMIN_RELEASE
            await context.bot.send_message(
                ADMIN_ID,
                f"Seller proof uploaded for escrow `{txn_id}`.\nAmount: {esc['amount']} Pi\nProof: {proof}\n"
                f"Use /adminrelease {txn_id} to release payment."
            )
            await context.bot.send_message(
                esc["buyer_id"],
                f"Seller has transferred {esc['amount']} Pi to your wallet for trade `{txn_id}`.\nBot will notify you after admin confirms and releases payment to seller."
            )
            await update.message.reply_text("Pi transfer proof received. Waiting for admin to release INR to seller.")
            return

async def admin_release(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("Only admin can use this command.")
        return
    args = update.message.text.strip().split()
    if len(args) < 2:
        await update.message.reply_text("Usage: /adminrelease <txn_id>")
        return
    txn_id = args[1]
    esc = escrows.get(txn_id)
    if not esc:
        await update.message.reply_text("Escrow transaction not found.")
        return
    if esc["status"] != ESCROW_WAIT_ADMIN_RELEASE:
        await update.message.reply_text("Not ready for release (both proofs not uploaded).")
        return
    esc["status"] = "complete"
    await context.bot.send_message(
        esc["buyer_id"],
        f"✅ Escrow trade `{txn_id}` complete.\nSeller has transferred Pi. If any problem, contact admin."
    )
    await context.bot.send_message(
        esc["seller_id"],
        f"✅ Escrow trade `{txn_id}` complete. Admin will now send you INR (₹{esc['amount']}) to your UPI ({esc['seller_upi']})."
    )
    await update.message.reply_text(f"Escrow `{txn_id}` marked complete. Pay seller INR minus commission.")
    if esc.get("group_id"):
        await context.bot.send_message(
            esc["group_id"],
            f"✅ Escrow trade `{txn_id}` between @{esc.get('buyer_username')} (buyer) and @{esc.get('seller_username')} (seller) is complete!"
        )

# --- PRIVATE DIRECT BUY/SELL FLOW ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    user_id = update.effective_user.id
    if update.message.chat.type == Chat.PRIVATE:
        if user_id == ADMIN_ID:
            keyboard = [
                [
                    InlineKeyboardButton("💰 Show Sell Rate", callback_data="show_rate"),
                    InlineKeyboardButton("✏️ Set Sell Rate", callback_data="set_rate")
                ]
            ]
            await update.message.reply_text("🛠 Admin Panel", reply_markup=InlineKeyboardMarkup(keyboard))
            return ConversationHandler.END
        keyboard = [
            [InlineKeyboardButton("Sell Pi", callback_data="sell_pi")],
            [InlineKeyboardButton("Buy Pi", callback_data="buy_pi")]
        ]
        sell_rate = get_sell_rate()
        buy_rate = get_buy_rate()
        msg = "👋 Welcome! Please choose an option:\n"
        msg += f"\n💸 Sell Pi Rate: ₹{sell_rate if sell_rate else '--'}"
        msg += f"\n🪙 Buy Pi Rate: ₹{buy_rate if buy_rate else '--'} (always ₹1 more than sell rate)"
        await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))
        return ConversationHandler.END

async def admin_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "show_rate":
        sell_rate = get_sell_rate()
        buy_rate = get_buy_rate()
        await query.edit_message_text(
            f"💸 Sell Pi Rate: ₹{sell_rate if sell_rate is not None else '--'}\n"
            f"🪙 Buy Pi Rate: ₹{buy_rate if buy_rate is not None else '--'} (auto ₹1 more)"
        )
    elif query.data == "set_rate":
        await query.edit_message_text("✏️ Please send the new selling rate (numbers only):")
        context.user_data["awaiting_rate"] = True

async def catch_new_rate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("awaiting_rate") and update.effective_user.id == ADMIN_ID:
        try:
            new_rate = float(update.message.text.strip())
            with open(RATE_FILE, "w") as f:
                f.write(str(new_rate))
            await update.message.reply_text(f"✅ Sell rate updated to ₹{new_rate}\nBuy rate is now ₹{new_rate + 1} (auto)")
        except Exception:
            await update.message.reply_text("⚠️ Please send a valid number.")
        context.user_data["awaiting_rate"] = False
        return ConversationHandler.END
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
    elif query.data == "buy_pi":
        buy_rate = get_buy_rate()
        if buy_rate is None:
            await query.message.reply_text("❌ Buy rate not available. Please try again later.")
            return ConversationHandler.END
        await query.message.reply_text(f"🪙 Current Buy Rate: ₹{buy_rate}\nHow many Pi do you want to buy?")
        return BUY_AMOUNT

# --------- SELL PI FLOW (PRIVATE) ----------
async def sell_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        pi = float(update.message.text.strip())
        if pi <= 0:
            raise ValueError
        context.user_data['sell_pi'] = pi
        await update.message.reply_text("🪪 Please enter your full name (as per government ID):")
        return SELL_NAME
    except Exception:
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
    await update.message.reply_text("🔗 Please paste your Pi transaction link (https://blockexplorer.minepi.com/mainnet/tx/...):")
    return SELL_PI_TXN

async def sell_pi_txn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    link = update.message.text.strip()
    valid = any(
        link.startswith(p) and re.fullmatch(r"[a-fA-F0-9]{64}", link[len(p):])
        for p in [
            "https://blockexplorer.minepi.com/mainnet/tx/",
            "https://blockexplorer.minepi.com/mainnet/transactions/"
        ]
    )
    if not valid:
        await update.message.reply_text("⚠️ Invalid Pi transaction link. Please enter again:")
        return SELL_PI_TXN
    context.user_data['sell_pi_txn'] = link
    await update.message.reply_text("💳 Please enter your UPI ID or Paytm number (to receive payment):")
    return SELL_UPI

async def sell_upi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['sell_upi'] = update.message.text.strip()
    user = update.effective_user
    txn_id = generate_txn_id(user.id)
    context.user_data['transaction_id'] = txn_id

    pi = context.user_data['sell_pi']
    rate = get_sell_rate()
    gross = pi * rate
    tax = gross * 0.30
    processing = gross * 0.01
    conversion = gross * 0.01
    net = gross - tax - processing - conversion

    pending_transactions[txn_id] = {
        "user_id": user.id,
        "type": "sell",
        "pi": pi,
        "name": context.user_data['sell_name'],
        "phone": context.user_data['sell_phone'],
        "pan": context.user_data['sell_pan'],
        "pi_txn": context.user_data['sell_pi_txn'],
        "upi": context.user_data['sell_upi']
    }

    msg = (
        f"🧾 *New Pi Sell Request*\n"
        f"🆔 *Transaction ID:* `{txn_id}`\n\n"
        f"👤 *Full Name:* `{context.user_data['sell_name']}`\n"
        f"🆔 *PAN:* `{context.user_data['sell_pan']}`\n"
        f"📱 *Phone:* `{context.user_data['sell_phone']}`\n"
        f"👤 *Telegram:* @{user.username or '-'} (ID: {user.id})\n\n"
        f"💰 *PI Amount:* {pi} (₹{gross:.2f})\n"
        f"💵 *Gross:* ₹{gross:.2f}\n"
        f"📉 *Deductions:*\n"
        f"• ₹{tax:.2f} Govt Tax (30%)\n"
        f"• ₹{processing:.2f} Processing Fee (1%)\n"
        f"• ₹{conversion:.2f} Conversion Fee (1%)\n\n"
        f"💸 *Final Payable:* `₹{net:.2f}`\n\n"
        f"🔗 *Transaction:*\n{context.user_data['sell_pi_txn']}\n"
        f"📥 *UPI:* `{context.user_data['sell_upi']}`"
    )
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Approve", callback_data=f"approve_sell_{txn_id}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"reject_{txn_id}")
        ]
    ])
    await context.bot.send_message(chat_id=ADMIN_ID, text=msg, parse_mode="Markdown", reply_markup=keyboard)
    await update.message.reply_text(
        f"✅ Request sent!\nYour Transaction ID: `{txn_id}`\n"
        "Admin will verify your details and pay you soon.\nTo sell or buy again, type /start.",
        parse_mode="Markdown"
    )
    return ConversationHandler.END

# --------- BUY PI FLOW (PRIVATE) ----------
async def buy_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        pi = float(update.message.text.strip())
        if pi <= 0:
            raise ValueError
        context.user_data['buy_pi'] = pi
        await update.message.reply_text("🪪 Please enter your full name (as per government ID):")
        return BUY_NAME
    except Exception:
        await update.message.reply_text("⚠️ Invalid amount. Please enter again:")
        return BUY_AMOUNT

async def buy_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['buy_name'] = update.message.text.strip()
    await update.message.reply_text("📱 Please enter your 10-digit mobile number:")
    return BUY_PHONE

async def buy_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phone = update.message.text.strip()
    if not phone.isdigit() or len(phone) != 10:
        await update.message.reply_text("⚠️ Invalid phone number. Please enter again:")
        return BUY_PHONE
    context.user_data['buy_phone'] = phone
    await update.message.reply_text("🤖 Please enter your PAN number (e.g., ABCDE1234F):")
    return BUY_PAN

async def buy_pan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pan = update.message.text.strip().upper()
    if not re.fullmatch(r"[A-Z]{5}[0-9]{4}[A-Z]", pan):
        await update.message.reply_text("⚠️ Invalid PAN format. Please enter again:")
        return BUY_PAN
    context.user_data['buy_pan'] = pan
    await update.message.reply_text(
        "🌍 Please enter your Pi wallet address (should look like: GAP6UFB27DCORJA7LTGCCVVM2CD5VJJIHDRS34PIYUZNN663IDAEGNPL):"
    )
    return BUY_WALLET_ADDRESS

async def buy_wallet_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    address = update.message.text.strip()
    if not re.fullmatch(r"[A-Z2-7]{56}", address):
        await update.message.reply_text(
            "⚠️ Invalid Pi wallet address. Please enter again (should look like: GAP6UFB27DCORJA7LTGCCVVM2CD5VJJIHDRS34PIYUZNN663IDAEGNPL):"
        )
        return BUY_WALLET_ADDRESS
    context.user_data['buy_wallet_address'] = address
    pi = context.user_data['buy_pi']
    buy_rate = get_buy_rate()
    total = round(pi * buy_rate, 2)
    txn_id = generate_txn_id(update.effective_user.id)
    context.user_data['transaction_id'] = txn_id

    await send_upi_qr(
        context,
        update.effective_chat.id,
        ADMIN_UPI_ID,
        ADMIN_UPI_NAME,
        total,
        txn_id
    )

    await update.message.reply_text(
        "✅ After making payment, please enter your UPI Transaction ID (e.g., T2506250623580878760817):"
    )
    return BUY_UPI_TXN

async def buy_upi_txn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txn_id = update.message.text.strip()
    if not txn_id.startswith("T") or len(txn_id) < 16:
        await update.message.reply_text("⚠️ Please enter a valid UPI Transaction ID (e.g., T2506250623580878760817):")
        return BUY_UPI_TXN
    context.user_data['buy_upi_txn'] = txn_id
    user = update.effective_user
    my_txn_id = context.user_data.get('transaction_id') or generate_txn_id(user.id)

    pi = context.user_data['buy_pi']
    buy_rate = get_buy_rate()
    total = round(pi * buy_rate, 2)

    pending_transactions[my_txn_id] = {
        "user_id": user.id,
        "type": "buy",
        "pi": pi,
        "name": context.user_data['buy_name'],
        "phone": context.user_data['buy_phone'],
        "pan": context.user_data['buy_pan'],
        "wallet_address": context.user_data['buy_wallet_address'],
        "upi_txn_id": context.user_data['buy_upi_txn']
    }

    msg = (
        f"🧾 *New Pi Buy Request*\n"
        f"🆔 *Transaction ID:* `{my_txn_id}`\n\n"
        f"👤 *Full Name:* `{context.user_data['buy_name']}`\n"
        f"🆔 *PAN:* `{context.user_data['buy_pan']}`\n"
        f"📱 *Phone:* `{context.user_data['buy_phone']}`\n"
        f"👤 *Telegram:* @{user.username or '-'} (ID: {user.id})\n\n"
        f"🪙 *PI Amount:* {pi} (₹{total:.2f})\n"
        f"💰 *Total Payment:* ₹{total:.2f} (at ₹{buy_rate}/Pi)\n"
        f"🌍 *Wallet Address:* `{context.user_data['buy_wallet_address']}`\n"
        f"💸 *User UPI Txn ID:* `{context.user_data['buy_upi_txn']}`"
    )
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Approve", callback_data=f"approve_buy_{my_txn_id}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"reject_{my_txn_id}")
        ]
    ])
    await context.bot.send_message(chat_id=ADMIN_ID, text=msg, parse_mode="Markdown", reply_markup=keyboard)
    await update.message.reply_text(
        f"✅ Request submitted!\nYour Transaction ID: `{my_txn_id}`\n"
        "Admin will verify your details and transfer Pi soon.\nTo sell or buy again, type /start.",
        parse_mode="Markdown"
    )
    return ConversationHandler.END

async def admin_action_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    if data.startswith("approve_buy_") or data.startswith("approve_sell_"):
        txn_id = data.split("_", 2)[2]
        info = pending_transactions.get(txn_id)
        if not info:
            await query.message.reply_text("Transaction info not found or expired.")
            await query.edit_message_reply_markup(reply_markup=None)
            return
        await query.edit_message_reply_markup(reply_markup=None)
        user_id = info["user_id"]
        if info["type"] == "buy":
            msg = (
                f"✅ Your transaction `{txn_id}` has been *approved*.\n"
                "Your details have been verified. You will receive your Pi within 25 minutes."
            )
        else:
            msg = (
                f"✅ Your transaction `{txn_id}` has been *approved*.\n"
                "Your details have been verified. You will receive your payment within 25 minutes."
            )
        await context.bot.send_message(chat_id=user_id, text=msg, parse_mode="Markdown")
        await query.message.reply_text(f"User notified for transaction `{txn_id}`.")
        pending_transactions.pop(txn_id, None)
    elif data.startswith("reject_"):
        txn_id = data.split("_", 1)[1]
        info = pending_transactions.get(txn_id)
        if not info:
            await query.message.reply_text("Transaction info not found or expired.")
            await query.edit_message_reply_markup(reply_markup=None)
            return
        await query.edit_message_reply_markup(reply_markup=None)
        user_id = info["user_id"]
        msg = (
            f"❌ Your transaction `{txn_id}` has been *rejected*.\n"
            "Your credentials were not verified. Please send all details correctly."
        )
        await context.bot.send_message(chat_id=user_id, text=msg, parse_mode="Markdown")
        await query.message.reply_text(f"User notified for transaction `{txn_id}`.")
        pending_transactions.pop(txn_id, None)

def main():
    TOKEN = os.getenv("BOT_TOKEN")
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("sellpi", group_sellpi))
    app.add_handler(CommandHandler("buypi", group_buypi))
    app.add_handler(CommandHandler("adminrelease", admin_release))
    conv = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CallbackQueryHandler(option_choice_handler, pattern="^(sell_pi|buy_pi)$")
        ],
        states={
            SELL_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, sell_amount)],
            SELL_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, sell_name)],
            SELL_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, sell_phone)],
            SELL_PAN: [MessageHandler(filters.TEXT & ~filters.COMMAND, sell_pan)],
            SELL_PI_TXN: [MessageHandler(filters.TEXT & ~filters.COMMAND, sell_pi_txn)],
            SELL_UPI: [MessageHandler(filters.TEXT & ~filters.COMMAND, sell_upi)],
            BUY_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, buy_amount)],
            BUY_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, buy_name)],
            BUY_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, buy_phone)],
            BUY_PAN: [MessageHandler(filters.TEXT & ~filters.COMMAND, buy_pan)],
            BUY_WALLET_ADDRESS: [MessageHandler(filters.TEXT & ~filters.COMMAND, buy_wallet_address)],
            BUY_UPI_TXN: [MessageHandler(filters.TEXT & ~filters.COMMAND, buy_upi_txn)],
        },
        fallbacks=[],
        conversation_timeout=300
    )
    app.add_handler(conv)
    app.add_handler(CallbackQueryHandler(admin_button_handler, pattern="^(show_rate|set_rate)$"))
    app.add_handler(CallbackQueryHandler(admin_action_handler, pattern="^(approve_buy_|approve_sell_|reject_)"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, catch_new_rate))
    app.add_handler(MessageHandler(
        filters.TEXT & filters.ChatType.PRIVATE & filters.Regex(re.compile(r"^T\d{14,}|^upi|^payment|screenshot", re.I)),
        buyer_payment_proof
    ))
    app.add_handler(MessageHandler(
        filters.TEXT & filters.ChatType.PRIVATE & ~filters.Regex(re.compile(r"^T\d{14,}|^upi|^payment|screenshot", re.I)),
        seller_transfer_proof
    ))
    print("🤖 Bot is starting...")
    asyncio.run(app.run_polling())

if __name__ == "__main__":
    main()