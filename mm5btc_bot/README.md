# mm5_btc_clone_bot

Telegram bot clone based on `output/mm5_btc_bot` flow with 1:1 text formatting for key user messages.

## Run

```bash
pip install -r requirements.txt
cp .env.example .env
python main.py
```

## Dev (hot reload)

```bash
python dev.py
```

## Admin

Use `/admin` from user IDs listed in `ADMIN_IDS`.

Admin can:
- change fee percent
- change deposit BTC address
- QR is generated automatically from the current deposit wallet
