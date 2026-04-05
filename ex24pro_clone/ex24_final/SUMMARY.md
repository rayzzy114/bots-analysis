# Summary of Changes (Exchange24 Bot Clone)

## 1. Admin Panel Adaptation
- **Renamed "Commission" to "Spread (%)"**: The term "Commission" was replaced with "Spread" throughout the admin interface to match the bot's logic of adding a percentage spread to exchange rates.
- **Linked to `.env`**: Changing the Spread in the admin panel now correctly updates the `RATE_SPREAD_PERCENT` variable in the `.env` file.
- **Removed "Sell Wallets"**: All references, buttons, handlers, and states related to "Sell Wallets" (кошельки продажи) were removed from the `admin_kit` as they are not relevant to this bot.
- **UI Cleanup**: Removed "Orders" and "Users" mentions from the main admin panel to keep it focused on Links and Rates.
- **Fixed Formatting**: Fixed raw HTML tags (like `\n`) showing up in the admin panel text.

## 2. Media & UI Consistency
- **Offices Screen Banner**: Added the `welcome.jpg` photo as a banner for the "Offices" screen. This ensures visual consistency ("аналогично") with the start screen.
- **Main Menu Banners**: Added the same banner to other main menu screens (Rates, China, Dubai, Bali) to provide a professional, branded look.
- **Link Previews**: Ensure links in text messages have proper formatting for Telegram.
- **Improved Welcome Flow**: Changed the sequence of welcome messages. Now the bot first asks "💛 Подскажите, пожалуйста, как вы узнали о боте?" and only after the user's answer sends "Спасибо! А можно поподробнее? 😊". This makes the conversation feel more natural.

## 3. Admin Notifications & Tracking
- **Menu Interaction Tracking**: Added automated notifications to the admin chat whenever a user clicks a menu button (e.g., `Client #123 -> Offices`).
- **Ticket ID Consistency**: Ensured the `ticket_id` generated at `/start` is persisted and included in all admin notifications for better session tracking.
- **Admin Reply from Any Notification**: Enabled tracking of all admin notifications (starts, menu clicks) so that admins can reply directly to any of these messages in the group to initiate a chat with the user.
- **Improved `/close` Command**:
    - Supports `/close <user_id>` for direct usage.
    - Supports `/close` as a **Reply** to any client message or notification.
    - Supports `/close` without arguments to show a **Selection Menu** of up to 10 recently active users.
    - Updated rating buttons with emojis matching the requested design (☹️, 🫤, 😐, 🙂, 🤩).

## 4. Broadcasting Feature
- **User Persistence**: Enabled `UsersStore` to automatically record all user IDs when they start the bot.
- **Mass Mailing Tool**: Added a "📢 Рассылка всем" button to the `/admin` panel. 
- **Broadcast Handler**: Admins can now send a text or photo message to all users who have ever used the bot, with built-in rate-limiting to avoid Telegram flood restrictions.

## 5. Code Quality
- **Cleaned `admin_kit`**: Removed dead code and unused states from the copied `admin_kit` module.
- **Proper Parse Mode**: Configured the bot to use `HTML` parse mode by default for all messages.
