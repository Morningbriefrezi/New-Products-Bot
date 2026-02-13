# 🔥 Alibaba Scout Bot

Daily automated bot that scrapes Chinese wholesale suppliers (Alibaba, DHgate) for trending products, ranks them using OpenAI, and sends you a **Top 10 viral products** digest on Telegram every morning.

**Categories tracked:** Lamps · Telescopes · Binoculars · Kids Toys · Electronics

---

## How It Works

```
Scrape suppliers  →  AI ranks by viral potential  →  Telegram daily digest
(Alibaba, DHgate)     (OpenAI gpt-4o-mini)           (formatted top 10)
```

Each product includes: **name, price, MOQ, supplier, link, and AI score (1-100)**.

---

## 🚀 Setup Guide (Step by Step)

### Step 1 — Get Your API Keys

You need 3 things: an OpenAI key, a Telegram bot, and your chat ID.

#### 1A. OpenAI API Key
1. Go to [platform.openai.com/api-keys](https://platform.openai.com/api-keys)
2. Click **"Create new secret key"**
3. Copy it (starts with `sk-`)
4. Add a few dollars of credit at [platform.openai.com/settings/organization/billing](https://platform.openai.com/settings/organization/billing)
   - Each daily run costs about **$0.01–0.03** (using gpt-4o-mini)

#### 1B. Telegram Bot Token
1. Open Telegram and search for **@BotFather**
2. Send `/newbot`
3. Follow the prompts (give it a name like "My Product Scout")
4. BotFather gives you a token like `123456789:ABCdefGHI...` — copy it

#### 1C. Your Telegram Chat ID
1. Search for **@userinfobot** on Telegram
2. Send it any message
3. It replies with your **ID** (a number like `987654321`) — copy it
4. **Important:** Open your new bot and send it any message (like "hello") so it can message you back

---

### Step 2 — Upload to GitHub

#### 2A. Create a GitHub Repository
1. Go to [github.com/new](https://github.com/new)
2. Name it `alibaba-scout` (or whatever you like)
3. Set to **Private** (recommended since it's your business tool)
4. Click **Create repository**

#### 2B. Upload Files
**Option A — Upload via GitHub website (easiest):**
1. On your new repo page, click **"uploading an existing file"**
2. Drag & drop ALL these files/folders:
   ```
   main.py
   requirements.txt
   .env.example
   .gitignore
   src/
     __init__.py
     scraper.py
     ranker.py
     notifier.py
   .github/
     workflows/
       daily-scout.yml
   ```
3. Click **"Commit changes"**

**Option B — Using Git CLI:**
```bash
git clone https://github.com/YOUR_USERNAME/alibaba-scout.git
cd alibaba-scout
# Copy all the bot files into this folder
git add .
git commit -m "Initial commit"
git push origin main
```

---

### Step 3 — Add Secrets to GitHub

This is how GitHub Actions gets your API keys **securely** (they're encrypted).

1. Go to your repo → **Settings** → **Secrets and variables** → **Actions**
2. Click **"New repository secret"** and add these one by one:

| Secret Name | Value |
|---|---|
| `OPENAI_API_KEY` | `sk-xxxxxxxx...` (your OpenAI key) |
| `TELEGRAM_BOT_TOKEN` | `123456789:ABCdef...` (from BotFather) |
| `TELEGRAM_CHAT_ID` | `987654321` (your chat ID number) |

---

### Step 4 — Test It

1. Go to your repo → **Actions** tab
2. Click **"Daily Product Scout"** in the left sidebar
3. Click **"Run workflow"** → **"Run workflow"** (green button)
4. Wait 1-2 minutes — check your Telegram for the message! 🎉

---

### Step 5 — It Runs Automatically

The bot is already configured to run **every day at 12:00 PM Tbilisi time** (8:00 AM UTC).

To change the schedule, edit `.github/workflows/daily-scout.yml`:
```yaml
schedule:
  - cron: "0 8 * * *"  # UTC time — change this
```

Common schedules:
- `"0 5 * * *"` = 9:00 AM Tbilisi
- `"0 8 * * *"` = 12:00 PM Tbilisi (default)
- `"0 14 * * *"` = 6:00 PM Tbilisi

---

## 🖥️ Running Locally (Optional)

If you want to test on your own computer:

```bash
# Clone the repo
git clone https://github.com/YOUR_USERNAME/alibaba-scout.git
cd alibaba-scout

# Install Python dependencies
pip install -r requirements.txt

# Create your .env file
cp .env.example .env
# Edit .env and paste your keys

# Run it
python main.py              # Full run
python main.py --dry-run    # Skip Telegram, just print results
python main.py --scrape-only  # Just scrape, no AI ranking
```

---

## 📁 Project Structure

```
alibaba-scout/
├── main.py                  # Entry point — run this
├── requirements.txt         # Python dependencies
├── .env.example             # Template for your API keys
├── .gitignore               # Keeps secrets out of git
├── src/
│   ├── __init__.py
│   ├── scraper.py           # Scrapes Alibaba + DHgate
│   ├── ranker.py            # OpenAI viral potential ranking
│   └── notifier.py          # Telegram message formatting & sending
├── .github/
│   └── workflows/
│       └── daily-scout.yml  # GitHub Actions daily schedule
└── output/                  # Auto-created, stores daily JSON results
```

---

## ⚙️ Customization

### Change Product Categories

Edit the `CATEGORIES` dict in `src/scraper.py`:

```python
CATEGORIES = {
    "lamps": ["led lamp", "desk lamp", "moon lamp"],
    "telescopes": ["telescope", "astronomical telescope"],
    "binoculars": ["binoculars", "night vision binoculars"],
    "kids_toys": ["kids toys", "rc car toy", "building blocks"],
    "electronics": ["wireless earbuds", "smart watch", "led strip"],
    # Add your own:
    "home_decor": ["wall art", "floating shelf", "led mirror"],
    "pet_supplies": ["automatic pet feeder", "dog toy viral"],
}
```

### Change AI Model

In `.env`, change `OPENAI_MODEL`:
- `gpt-4o-mini` — cheapest, works great (default, ~$0.01/run)
- `gpt-4o` — better analysis (~$0.10/run)

---

## 💰 Cost

| Service | Cost |
|---|---|
| GitHub Actions | **Free** (2,000 min/month on free plan) |
| OpenAI (gpt-4o-mini) | **~$0.01–0.03/day** (~$1/month) |
| Telegram Bot | **Free** |

**Total: ~$1/month**

---

## ⚠️ Important Notes

- **Scraping limits:** Alibaba/DHgate may occasionally block requests. The bot handles this gracefully and retries with different user agents. If scraping consistently fails, the bot sends you an error alert on Telegram.
- **No Taobao:** Taobao requires Chinese phone verification and has aggressive anti-bot. The bot uses Alibaba (international) and DHgate instead, which have the same products at wholesale prices.
- **Results vary:** Some days may return fewer products depending on site availability. The bot saves all results as JSON in the `output/` folder.
- **Rate limits:** The bot adds random delays between requests to be respectful to the supplier sites.
