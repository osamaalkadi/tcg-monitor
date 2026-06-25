# TCG presale + stock monitor (EB Games / JB Hi-Fi / Big W + others)

A free, scheduled **monitor** built for collectors who keep missing One Piece /
Pokemon presales. It watches the products you choose and **alerts you on
Discord** the instant something hits **pre-order** or comes **in stock**, with a
direct link and an optional one-tap "go to cart" jump.

It does **not** add to cart on its own, log in, check out, or buy anything. It
watches and tells you; you buy it yourself as a fast, prepared human. Automated
purchasing breaks these retailers' terms and is the scalping behaviour that
makes presales miserable for real collectors — so this tool stops at the alert.

Runs entirely free on **GitHub Actions** (unlimited minutes on public repos).

---

## Why this helps if you're already on a monitor Discord

A public monitor Discord pings on *everything* and you still lose the checkout
race. This gives you:

- **Targeted, low-noise alerts** — only the exact sets you care about, pinging
  only you.
- **Presale-aware detection** — it treats "Pre-order" / "Coming soon" as the
  signal to act, not just "in stock now".
- **A one-tap path to a pre-filled cart** (optional `cart_url`), so your human
  checkout is as fast as it legitimately can be.
- See `CHECKOUT_CHECKLIST.md` — getting your accounts/payment ready beats a
  faster bot almost every time.

---

## How it works

1. A scheduled GitHub Action runs on your chosen interval.
2. It reads `watchlist.json`.
3. For each item it opens the page in a real headless browser (Playwright) so
   JS-rendered pre-order/stock/price content loads.
4. It classifies status as **in stock**, **pre-order live**, **out of stock**,
   or **unknown**.
5. It compares against the last run (`state.json`, committed back to the repo).
6. On any actionable change it sends a rich Discord embed. Otherwise, silence.

---

## watchlist.json — three ways to watch

```json
[
  {
    "name": "Mega Lucario ex League Battle Deck",
    "url": "https://www.ebgames.com.au/product/REAL-PAGE",
    "cart_url": "https://www.ebgames.com.au/cart/add?sku=REAL-SKU",
    "image": "https://.../optional-thumb.jpg"
  },
  {
    "name": "One Piece OP-11 box (JB Hi-Fi)",
    "url": "https://www.jbhifi.com.au/products/REAL-PAGE"
  },
  {
    "name": "Catch ANY new One Piece OP-11 listing",
    "url": "https://www.ebgames.com.au/search?q=one+piece+op-11",
    "keywords": ["one piece", "op-11"]
  }
]
```

- **`url`** (required): the page to check. A product page, or a search/category
  page if you're using `keywords`.
- **`cart_url`** (optional): a direct add-to-cart link for that store, if you
  can find one. The alert turns this into a one-tap "Quick add to cart" button
  that pre-fills your cart and drops you at the normal checkout. You still log
  in and confirm — it does not buy for you.
- **`image`** (optional): thumbnail shown in the Discord embed.
- **`keywords`** (optional list): watch a *search* page and fire when ALL these
  words appear — i.e. a matching listing showed up. Great for "alert me the
  moment any OP-11 product is listed", before you even have the product URL.

### Finding a cart_url
Some stores support a URL that adds a SKU straight to the cart. Add a product to
your cart manually, watch the network request or the resulting URL, and copy the
pattern. If you can't find one, just leave `cart_url` out — the product link
still works fine.

---

## Setup (about 10 minutes)

1. **Create a new public GitHub repo** and upload these files, keeping
   `.github/workflows/monitor.yml` in that path.
2. **Edit `watchlist.json`** with your real product/search URLs.
3. **Add a Discord webhook**: Discord -> Server Settings -> Integrations ->
   Webhooks -> New Webhook -> copy URL. Then in GitHub: Settings -> Secrets and
   variables -> Actions -> New repository secret named `DISCORD_WEBHOOK_URL`.
   (Optional second secret `WEBHOOK_URL` for Slack/IFTTT/your own endpoint.)
4. **Actions tab -> Stock monitor -> Run workflow** to test now.
5. Work through **`CHECKOUT_CHECKLIST.md`** so you're ready when an alert lands.

---

## Tuning the schedule

`.github/workflows/monitor.yml` defaults to every 15 min. For presale waves you
expect on a known day, you can temporarily tighten it — but `*/5` is a sensible
floor. GitHub's cron lags a few minutes regardless, and very frequent runs get
throttled and risk blocks. Don't point a huge watchlist at a 1-minute cron.

---

## Testing locally first

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
python -m playwright install chromium

DEBUG=1 python monitor.py       # dumps page text to help fix a parser
python monitor.py               # normal run
```

First run just records a baseline; alerts start from the second run.

---

## Known limitations (please read)

- **These sites discourage scraping.** JB Hi-Fi and Big W may sometimes serve a
  bot-check page. The item logs as "unknown" and retries next run — it won't
  fire a false alert. Expected, not a bug.
- **Selectors break** when a retailer reshuffles their HTML. Run `DEBUG=1`,
  find the new wording, update the `*_SIGNALS` lists or `PRICE_SELECTORS` in
  `monitor.py`. Normal scraper maintenance.
- **Cron isn't exact.** Fine for "tell me when it's live", not for guaranteeing
  you beat every other buyer to the millisecond. Your readiness (checklist)
  matters more.
- **Be polite.** Modest watchlist, sane interval. Hammering gets you blocked.

---

## Adding another retailer

1. Add a host match in `detect_site()`.
2. Add a price selector to `PRICE_SELECTORS`.
3. If the site uses unusual wording for stock states, extend `PREORDER_SIGNALS`
   / `OOS_SIGNALS` / `INSTOCK_SIGNALS`. The generic parser handles most stores
   out of the box.
