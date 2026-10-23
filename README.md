# Airspace Monitor

Personal monitoring tool for airspace and airport events in Saudi Arabia and the region.
Alerts are sent to your phone through Telegram.

> **Note:** This is a supporting awareness tool only. It does not replace official
> operational sources (NOTAM office, ATC, company dispatch systems).

---

## What it monitors

| Alert | Source | Coverage |
|---|---|---|
| 🔴 FIR / airspace closed | NOTAMs | 15 FIRs |
| 🔴 Aerodrome closed | NOTAMs | 30 airports |
| 🔴 ATS route closed | NOTAMs | FIRs + airports |
| 🔴 Restricted / danger area active | NOTAMs | FIRs + airports |
| 🔴 GNSS / GPS interference | NOTAMs | FIRs + airports |
| 🟢 Reopened / resumed | NOTAMs | FIRs + airports |
| 🟠 Holding detected | Live ADS-B | 40 NM around each airport |
| 🟣 Possible diversion | Live ADS-B + route data | flynas (KNE) flights |
| 🚨 Squawk 7500 / 7600 / 7700 | Live ADS-B | Whole region |
| 💚 Daily check | System | Every day at 06:00 KSA |

All lists (FIRs, airports, airlines, categories) can be changed in `config.py`.

---

## Setup (about 15 minutes, one time only)

### Step 1 — Create the Telegram bot

1. Open Telegram and search for **@BotFather**.
2. Send `/newbot` and follow the steps (choose any name).
3. BotFather gives you a **token**. Copy it and keep it private.
4. Open your new bot and press **Start**, then send it any message (for example: `hi`).
5. In a browser, open this link (replace `<TOKEN>` with your token):

```
https://api.telegram.org/bot<TOKEN>/getUpdates
```

6. Find `"chat":{"id":` and copy the number after it. This is your **Chat ID**.

### Step 2 — Create a GitHub account and repository

1. Create a free account at github.com (if you do not have one).
2. Create a **new repository**, name it `airspace-monitor`, and set it to **Public**.
   - Public is required for unlimited free running time.
   - Your token and Chat ID are **not** visible; they are stored as secrets (Step 3).
3. Upload **all files** from this folder, including the hidden folder `.github`.
   - Easiest way: on the repository page choose **Add file → Upload files**, then drag the whole folder content.

### Step 3 — Add the secrets

In the repository: **Settings → Secrets and variables → Actions → New repository secret**

| Name | Value |
|---|---|
| `TELEGRAM_BOT_TOKEN` | the token from Step 1 |
| `TELEGRAM_CHAT_ID` | the Chat ID from Step 1 |

### Step 4 — Start it

1. Open the **Actions** tab and enable workflows if asked.
2. Choose **Airspace Monitor → Run workflow**.
3. Within a few minutes you receive a **"Airspace Monitor started"** message with a summary of all currently active closures.
4. After that it runs automatically every 10 minutes and sends **new** events only.

---

## Good to know

- **Free data limits:** live traffic comes from volunteer ADS-B receivers. Coverage in Saudi Arabia and the Gulf is weaker than in Europe, so some aircraft may be missed.
- **Holding detection** needs the aircraft to be seen for at least 6 minutes. A very short hold may not be detected.
- **Diversion alerts** use a public route database. If the route data is old, a false alert is possible. Always confirm.
- **Gaps:** GitHub may delay scheduled runs by a few minutes at busy times.
- **60-day rule:** GitHub pauses scheduled workflows in a repository with no activity for 60 days. If you receive an email about this, open the repository and click **Enable**.
- **Too many alerts?** Set a category to `False` in `config.py` (for example `RUNWAY CLOSED`, which is off by default).

## Files

| File | Purpose |
|---|---|
| `config.py` | Everything you may want to change |
| `monitor.py` | Main program |
| `detectors.py` | Holding, NOTAM and diversion logic |
| `sources.py` | Data sources (NOTAMs, ADS-B, routes) |
| `notify.py` | Telegram messages |
| `test_detectors.py` | Self-tests for the detection logic |
| `.github/workflows/monitor.yml` | Automatic schedule |
