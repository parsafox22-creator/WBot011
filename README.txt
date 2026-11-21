Version 30.0.0

Bot 31 - Railway version.
BOT_TOKEN and ADMIN_ID are read from environment variables.

Version 30 - Dashboard added; all previous features preserved:
- Dedicated Admin panel button: مدیریت سفارش‌ها.
- Separate lists for approved, pending, and rejected orders.
- Rejected orders can be re-approved by owner or an admin with the dedicated permission.
- Order tracking for owner/admins can expose re-approval for rejected orders when permitted.
- New granular admin permissions for re-approving rejected orders and increasing/decreasing wallet balance.
- Every wallet top-up gets a unique DEP tracking ID and can be tracked like an order code.
- Existing developer/admin permission system, Ghost mode, private chat, tickets, packages and other features are preserved.

Run:
pip install -r requirements.txt
python bot.py

Railway:
Set BOT_TOKEN and ADMIN_ID in Variables / Variables and Secrets.

Messaging reliability fixes:
- Ticket replies are transactional: the ticket remains open until the admin explicitly closes it.
- Ticket/admin/user messages escape HTML safely.
- Private chats use stable PV conversation IDs for reply/close buttons; no message-markup edit race.
- Private admin/user replies preserve the previous message text and conversation state.
- Broadcast delivery reports success/failure and includes pacing for Telegram flood limits.
- Failed sends do not corrupt the ticket/private conversation state.


User lookup (v28/v29):
- Admin panel includes user lookup by CRV or numeric Telegram ID.
- Displays stored account data plus Telegram first/last name and username when available.
- Lookup actions include block/restrict, remove restrictions, Ghost, and private messaging.
- Owner/developer can grant or revoke the user-lookup permission per admin.


Dashboard (v30):
- Management dashboard with users, finance, orders, support and wallet summaries.
- Today and 7-day metrics.
- Quick-access buttons for lookup, tickets, private messages, deposits and orders.
- Refresh button recalculates all values from the current local database.
