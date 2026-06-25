#!/usr/bin/env python3
"""
TCG presale + stock monitor for Australian retailers
(EB Games, JB Hi-Fi, Big W, and generic fallback for others).

Built for collectors who keep missing One Piece / Pokemon presales.

What it does:
  - Reads a watchlist of products from watchlist.json. You can watch a
    specific URL, OR watch a search/category page by keyword (e.g. catch
    any new "One Piece OP-11" listing the moment it appears).
  - Opens each page in a real browser (Playwright) so JS-rendered
    price/stock/pre-order content actually loads.
  - Detects three states that matter for presales:
      in_stock  -> buyable right now
      preorder  -> pre-order / coming soon live (THIS is the presale moment)
      oos       -> out of stock / sold out
  - Compares against the last run (state.json).
  - Sends a rich Discord alert ONLY when something changes, with a direct
    product link and an optional one-tap "go to cart" link.

What it deliberately does NOT do:
  - It does not add to cart for you, log in, check out, or buy anything.
  - The "cart link" just pre-fills the cart and hands YOU to the normal
    checkout page. You log in and confirm the purchase yourself.
  - Automated purchasing breaks these retailers' terms and is the scalping
    mechanism that makes presales miserable for real collectors. Hard no.

Be a good citizen: keep the interval reasonable and the watchlist modest.
"""

import json
import os
import sys
import asyncio
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import urlparse

import httpx
from playwright.async_api import async_playwright

ROOT = Path(__file__).parent
WATCHLIST_FILE = ROOT / "watchlist.json"
STATE_FILE = ROOT / "state.json"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
NAV_TIMEOUT = 30000

# Status constants
IN_STOCK = "in_stock"
PREORDER = "preorder"
OOS = "oos"
UNKNOWN = None

# Which statuses are "actionable" (worth pinging you to go act)
ACTIONABLE = {IN_STOCK, PREORDER}


# --------------------------------------------------------------------------
# Site detection
# --------------------------------------------------------------------------
def detect_site(url: str) -> str:
    host = urlparse(url).netloc.lower()
    if "ebgames" in host:
        return "ebgames"
    if "jbhifi" in host:
        return "jbhifi"
    if "bigw" in host:
        return "bigw"
    return "generic"


# --------------------------------------------------------------------------
# Status classification from page text
#
# Order matters: preorder is checked before in_stock, because a presale page
# often ALSO contains an "add to cart" button. For a collector, "pre-order is
# live" is the signal you care about, so it wins.
# --------------------------------------------------------------------------
PREORDER_SIGNALS = ["pre-order", "preorder", "pre order", "coming soon", "available for pre"]
OOS_SIGNALS = ["out of stock", "sold out", "currently unavailable", "unavailable", "notify me when"]
INSTOCK_SIGNALS = ["add to cart", "add to bag", "add to trolley", "in stock", "buy now"]


def classify(body: str) -> str:
    b = body.lower()
    # Pre-order takes priority for presale watching.
    if any(s in b for s in PREORDER_SIGNALS):
        return PREORDER
    if any(s in b for s in OOS_SIGNALS):
        return OOS
    if any(s in b for s in INSTOCK_SIGNALS):
        return IN_STOCK
    return UNKNOWN


# --------------------------------------------------------------------------
# Per-site detail extraction (title + price). Status uses classify().
# --------------------------------------------------------------------------
PRICE_SELECTORS = {
    "ebgames": '[class*="price"], .price, [data-price]',
    "jbhifi": '[data-testid*="price"], [class*="PriceTag"], [class*="price"]',
    "bigw": '[class*="price"], [data-testid*="price"]',
    "generic": '[class*="price"], [data-testid*="price"], [itemprop="price"]',
}


async def _text(page, selector):
    try:
        el = await page.query_selector(selector)
        if el:
            txt = (await el.inner_text()).strip()
            return txt or None
    except Exception:
        pass
    return None


# --------------------------------------------------------------------------
# Keyword watch: scan a search/category page for matching product links.
# Returns True if any keyword appears in the page text (a new listing showed
# up). This is how you catch "any new One Piece OP-11" without a URL yet.
# --------------------------------------------------------------------------
def keyword_hit(body: str, keywords) -> bool:
    if not keywords:
        return False
    b = body.lower()
    return all(k.lower() in b for k in keywords) if isinstance(keywords, list) else keywords.lower() in b


# --------------------------------------------------------------------------
# Fetch + analyse one watchlist item
# --------------------------------------------------------------------------
async def check_item(context, item):
    url = item["url"]
    site = detect_site(url)
    keywords = item.get("keywords")  # optional list for keyword/search watching

    result = {
        "url": url,
        "name": item.get("name") or url,
        "site": site,
        "status": UNKNOWN,
        "price": None,
        "cart_url": item.get("cart_url"),
        "image": item.get("image"),
        "error": None,
        "keyword_found": None,
    }

    page = await context.new_page()
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=NAV_TIMEOUT)
        await page.wait_for_timeout(2500)
        body = await page.content()

        if keywords:
            # Keyword/search-page mode: did a matching listing appear?
            result["keyword_found"] = keyword_hit(body, keywords)
            # If found, also classify the page so we know if it's preorder/instock
            result["status"] = classify(body) if result["keyword_found"] else OOS
        else:
            result["status"] = classify(body)

        result["price"] = await _text(page, PRICE_SELECTORS.get(site, PRICE_SELECTORS["generic"]))
        if not result["name"] or result["name"] == url:
            t = await _text(page, "h1")
            if t:
                result["name"] = t

        if os.getenv("DEBUG"):
            snippet = (await page.inner_text("body"))[:1500]
            print(f"\n--- DEBUG {url} ---\n{snippet}\n--- end ---\n", file=sys.stderr)

    except Exception as e:
        result["error"] = str(e)[:200]
    finally:
        await page.close()

    return result


# --------------------------------------------------------------------------
# State + change detection
# --------------------------------------------------------------------------
def load_json(path, default):
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:
            return default
    return default


STATUS_LABEL = {
    IN_STOCK: "🟢 IN STOCK",
    PREORDER: "🟣 PRE-ORDER LIVE",
    OOS: "🔴 Out of stock",
    UNKNOWN: "⚪ Unknown",
}


def diff_state(old, new):
    """Return a list of alert dicts for actionable changes."""
    alerts = []
    for url, cur in new.items():
        prev = old.get(url)
        status = cur["status"]

        if status is UNKNOWN:
            continue  # never alert on an uncertain read

        prev_status = prev.get("status") if prev else None

        # Fire when an item BECOMES actionable (in stock or preorder),
        # i.e. it wasn't actionable before but is now.
        became_actionable = status in ACTIONABLE and prev_status not in ACTIONABLE
        first_seen_actionable = prev is None and status in ACTIONABLE

        if became_actionable or first_seen_actionable:
            alerts.append({
                "name": cur["name"],
                "status": status,
                "price": cur.get("price"),
                "url": url,
                "cart_url": cur.get("cart_url"),
                "image": cur.get("image"),
                "site": cur.get("site"),
            })

        # Price drop on something already actionable
        elif (status in ACTIONABLE and prev and cur.get("price")
              and prev.get("price") and cur["price"] != prev["price"]):
            alerts.append({
                "name": cur["name"],
                "status": status,
                "price": cur.get("price"),
                "prev_price": prev.get("price"),
                "url": url,
                "cart_url": cur.get("cart_url"),
                "image": cur.get("image"),
                "site": cur.get("site"),
                "price_change": True,
            })

    return alerts


# --------------------------------------------------------------------------
# Notifications — rich Discord embeds
# --------------------------------------------------------------------------
def build_discord_embed(a):
    fields = [
        {"name": "Status", "value": STATUS_LABEL.get(a["status"], "?"), "inline": True},
    ]
    if a.get("price"):
        price_val = a["price"]
        if a.get("price_change") and a.get("prev_price"):
            price_val = f"~~{a['prev_price']}~~ → **{a['price']}**"
        fields.append({"name": "Price", "value": price_val, "inline": True})
    if a.get("site"):
        fields.append({"name": "Store", "value": a["site"], "inline": True})

    links = f"[Open product page]({a['url']})"
    if a.get("cart_url"):
        links += f"  •  [⚡ Quick add to cart]({a['cart_url']})"
    fields.append({"name": "Links", "value": links, "inline": False})

    color = 0x9B59B6 if a["status"] == PREORDER else 0x2ECC71  # purple preorder / green instock
    embed = {
        "title": a["name"][:240],
        "url": a["url"],
        "color": color,
        "fields": fields,
        "footer": {"text": "Personal stock monitor • verify before buying"},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if a.get("image"):
        embed["thumbnail"] = {"url": a["image"]}
    return embed


def notify(alerts):
    if not alerts:
        return

    # Console log
    print("=== ALERTS ===")
    for a in alerts:
        tag = "PRICE" if a.get("price_change") else STATUS_LABEL.get(a["status"], "?")
        print(f"  {tag}: {a['name'][:60]} {a.get('price') or ''} {a['url']}")

    discord = os.getenv("DISCORD_WEBHOOK_URL")
    if discord:
        # Discord allows up to 10 embeds per message.
        for i in range(0, len(alerts), 10):
            batch = alerts[i:i + 10]
            payload = {
                "content": "🔔 New TCG drop(s)!" if any(x["status"] == PREORDER for x in batch) else "🔔 Stock update",
                "embeds": [build_discord_embed(a) for a in batch],
            }
            try:
                r = httpx.post(discord, json=payload, timeout=15)
                r.raise_for_status()
            except Exception as e:
                print(f"Discord send failed: {e}", file=sys.stderr)
        print(f"Sent {len(alerts)} alert(s) to Discord.")

    generic = os.getenv("WEBHOOK_URL")
    if generic:
        text = "\n".join(
            f"{STATUS_LABEL.get(a['status'],'?')} {a['name']} {a.get('price') or ''} {a['url']}"
            for a in alerts
        )
        try:
            httpx.post(generic, json={"text": text}, timeout=15)
        except Exception as e:
            print(f"Webhook send failed: {e}", file=sys.stderr)


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------
async def main():
    watchlist = load_json(WATCHLIST_FILE, [])
    if not watchlist:
        print("watchlist.json is empty or missing. Add some products first.")
        return

    old_state = load_json(STATE_FILE, {})
    new_state = {}

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=USER_AGENT,
            viewport={"width": 1366, "height": 900},
            locale="en-AU",
        )

        for item in watchlist:
            res = await check_item(context, item)
            label = STATUS_LABEL.get(res["status"], "⚪ Unknown")
            err = f" [error: {res['error']}]" if res["error"] else ""
            kw = ""
            if res["keyword_found"] is not None:
                kw = " [keyword match]" if res["keyword_found"] else " [no keyword match]"
            print(f"[{res['site']:8}] {res['name'][:45]:45} {label:18} {res.get('price') or '':>10}{kw}{err}")

            new_state[res["url"]] = {
                "name": res["name"],
                "status": res["status"],
                "price": res["price"],
                "site": res["site"],
                "cart_url": res.get("cart_url"),
                "image": res.get("image"),
                "checked_at": datetime.now(timezone.utc).isoformat(),
            }

        await browser.close()

    alerts = diff_state(old_state, new_state)
    notify(alerts)

    # Persist state; preserve last-known on uncertain reads.
    merged = dict(old_state)
    for url, cur in new_state.items():
        if cur["status"] is UNKNOWN and url in old_state:
            prev = old_state[url]
            prev["checked_at"] = cur["checked_at"]
            merged[url] = prev
        else:
            merged[url] = cur
    STATE_FILE.write_text(json.dumps(merged, indent=2))
    print(f"\nState written ({len(merged)} items). {len(alerts)} alert(s).")


if __name__ == "__main__":
    asyncio.run(main())
