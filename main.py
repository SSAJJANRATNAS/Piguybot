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

ADMIN_ID = 5795065284  # Your Telegram user ID
ADMIN_UPI_ID = "sajjanrohdiya@ybl"  # Your UPI
ADMIN_UPI_NAME = "SAJJAN SINGH S/O KISHAN SINGH"
ESCROW_RATE = 0.03

# Escrow status states
(
    ESCROW_IDLE,  # not used, but for clarity
    ESCROW_WAIT_BUYER_PROOF,
    ESCROW_WAIT_SELLER_PROOF,
    ESCROW_WAIT_ADMIN_RELEASE,
) = range(4)

# In-memory store: txn_id -> escrow info
escrows = {}

def generate_txn_id():
    ts = time.strftime("%Y%m%d%H%M%S", time.gmtime())
    rand = ''.join(random.choices(string.ascii_uppercase + string.digits, k=3))
    return f"TXN{ts}{rand}"

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
        f"&tn=Escrow%20Payment"
    )
    qr_img = qrcode.make(upi_link)
    bio = BytesIO()
    bio.name = 'upi_qr.png'
    qr_img.save(bio, 'PNG')
    bio.seek(0)
    await context.bot.send_photo(
        chat_id=chat_id,
        photo=bio,
        caption=f"Pay ₹{amount} (includes 3% commission) to escrow:\n\n{upi_link}"
    )

# --- GROUP COMMANDS ---

async def group_sellpi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Usage: /sellpi <amount> <upi_id>"""
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
    """Usage: /buypi <amount> <wallet_address>"""
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
    # Try to find a matching sell offer
    sell_offers = context.bot_data.get("sell_offers", [])
    match = None
    for offer in sell_offers:
        if abs(offer["amount"] - amount) < 0.0001:  # Match exact or near
            match = offer
            break
    if not match:
        await update.message.reply_text("No matching sell offer found for this amount.")
        return
    # Remove matched offer
    sell_offers.remove(match)
    # Create escrow
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
    # Announce in group
    await update.message.reply_text(
        f"🔗 Escrow Trade Matched!\n"
        f"@{buyer.username or buyer.id} (Buyer) ↔️ @{match.get('username') or match['user_id']} (Seller)\n"
        f"Amount: {amount} Pi\n"
        f"Buyer pays: ₹{total} (incl. ₹{comm} commission)\n"
        f"Escrow Transaction ID: {txn_id}\n"
        f"Bot will DM both for next steps."
    )
    # DM Buyer: pay to escrow
    buyer_msg = (
        f"Hi! You are buyer in escrow trade `{txn_id}` for {amount} Pi.\n"
        f"Pay ₹{total} (includes ₹{comm} commission) to admin UPI via QR or link below.\n"
        "After payment, reply here with your UPI Transaction ID or screenshot."
    )
    await context.bot.send_message(buyer.id, buyer_msg)
    await send_upi_qr(context, buyer.id, ADMIN_UPI_ID, ADMIN_UPI_NAME, total, txn_id)
    # DM Seller: wait for buyer payment, then send Pi after bot confirmation
    seller_msg = (
        f"Hi! You are seller in escrow trade `{txn_id}` for {amount} Pi.\n"
        f"Bot will notify you when buyer payment received in escrow. Then you must transfer {amount} Pi to buyer's wallet:\n{wallet_address}\n"
        "Wait for bot instruction before sending Pi."
    )
    await context.bot.send_message(match["user_id"], seller_msg)

# --- BUYER/SELLER UPLOAD PROOFS ---

async def buyer_payment_proof(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text or ""
    proof = text.strip()
    # Find matching escrow where this user is buyer & status is waiting
    for txn_id, esc in escrows.items():
        if esc["buyer_id"] == user.id and esc["status"] == ESCROW_WAIT_BUYER_PROOF:
            esc["buyer_payment_proof"] = proof or "screenshot"
            esc["status"] = ESCROW_WAIT_SELLER_PROOF
            # Notify admin and seller
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

# --- ADMIN RELEASE ---

async def admin_release(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("Only admin can use this command.")
        return
    args = context.args
    if not args:
        await update.message.reply_text("Usage: /adminrelease <txn_id>")
        return
    txn_id = args[0]
    esc = escrows.get(txn_id)
    if not esc:
        await update.message.reply_text("Escrow transaction not found.")
        return
    if esc["status"] != ESCROW_WAIT_ADMIN_RELEASE:
        await update.message.reply_text("Not ready for release (both proofs not uploaded).")
        return
    # Mark as complete
    esc["status"] = "complete"
    # Notify both parties
    await context.bot.send_message(
        esc["buyer_id"],
        f"✅ Escrow trade `{txn_id}` complete.\nSeller has transferred Pi. If any problem, contact admin."
    )
    await context.bot.send_message(
        esc["seller_id"],
        f"✅ Escrow trade `{txn_id}` complete. Admin will now send you INR (₹{esc['amount']}) to your UPI ({esc['seller_upi']})."
    )
    await update.message.reply_text(f"Escrow `{txn_id}` marked complete. Pay seller INR minus commission.")
    # Announce in group
    if esc.get("group_id"):
        await context.bot.send_message(
            esc["group_id"],
            f"✅ Escrow trade `{txn_id}` between @{esc.get('buyer_username')} (buyer) and @{esc.get('seller_username')} (seller) is complete!"
        )
    # Remove from escrows (optional: keep for logs)
    # del escrows[txn_id]


# --- HANDLER SETUP ---

def main():
    TOKEN = os.getenv("BOT_TOKEN")
    app = ApplicationBuilder().token(TOKEN).build()
    # Group commands
    app.add_handler(CommandHandler("sellpi", group_sellpi))
    app.add_handler(CommandHandler("buypi", group_buypi))
    app.add_handler(CommandHandler("adminrelease", admin_release))
    # Buyer uploads UPI txn or screenshot
    app.add_handler(MessageHandler(
        filters.TEXT & filters.ChatType.PRIVATE & filters.Regex(re.compile(r"^T\d{14,}|^upi|^payment|screenshot", re.I)),
        buyer_payment_proof
    ))
    # Seller uploads Pi transfer proof
    app.add_handler(MessageHandler(
        filters.TEXT & filters.ChatType.PRIVATE & ~filters.Regex(re.compile(r"^T\d{14,}|^upi|^payment|screenshot", re.I)),
        seller_transfer_proof
    ))
    print("🤖 Escrow bot running!")
    asyncio.run(app.run_polling())

if __name__ == "__main__":
    main()