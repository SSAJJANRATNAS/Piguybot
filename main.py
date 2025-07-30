async def buy_pan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pan = update.message.text.strip().upper()
    if not re.fullmatch(r"[A-Z]{5}[0-9]{4}[A-Z]", pan):
        await update.message.reply_text("⚠️ Invalid PAN format. Please enter again:")
        return BUY_PAN
    context.user_data['buy_pan'] = pan

    # Send wallet details to user
    my_wallet_address = "GAP6UFB27DCORJA7LTGCCVVM2CD5VJJIHDRS34PIYUZNN663IDAEGNPL"
    await update.message.reply_text(
        f"✅ Please send your Pi *now* to the following wallet address:\n\n`{my_wallet_address}`",
        parse_mode="Markdown"
    )

    # Generate payment QR / link immediately
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
        "✅ After sending Pi to the wallet above, *also* pay the INR amount by scanning the QR or using the payment link above.\nThen enter your UPI Transaction ID (e.g., T2506250623580878760817):",
        parse_mode="Markdown"
    )
    return BUY_UPI_TXN
