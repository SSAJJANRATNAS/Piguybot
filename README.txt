
📘 Pi Buyer Bot - Setup Guide

1. Install required packages:
   pip install python-telegram-bot --upgrade

2. Files:
   - main.py       → Bot logic
   - rate.txt      → Set current rate (default 100)
   - README.txt    → You're reading it

3. To run the bot:
   python main.py

4. Admin Commands:
   /rate          → View current rate
   /setrate 105   → Update rate to ₹105 (admin only)

5. Transactions:
   - Users send PI to your wallet
   - Provide TXN ID and UPI
   - Bot sends details to admin (you)

Make sure to keep your bot token and admin ID safe.
