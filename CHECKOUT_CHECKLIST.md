# Presale checkout readiness — beat the clock legitimately

For a human buying for himself, **account readiness beats a faster bot almost
every time.** A presale alert is useless if you then spend 90 seconds typing
your address while stock evaporates. This checklist closes that gap. None of it
breaks any retailer's terms — it's just being prepared.

## Do once, ahead of time (per store)

- [ ] **Create the account** at each store you buy from (EB Games, JB Hi-Fi,
      Big W, plus any others your Discord links to). Don't be guest-checking
      under time pressure.
- [ ] **Save your shipping address** in the account profile.
- [ ] **Save a payment method** if the store offers it (or have PayPal /
      Google Pay / Apple Pay linked — these skip card entry entirely and are
      the single biggest time saver).
- [ ] **Verify your email + phone** so no verification step ambushes you mid-checkout.
- [ ] **Stay logged in** on the device/browser you'll use to buy. Tick
      "remember me". A logged-out cart is where most people lose the race.

## When an alert fires

1. **Tap the product link in the alert** (the bot puts it right in the embed).
2. If you added a `cart_url`, tap **Quick add to cart** — it pre-fills the cart
   and drops you at the normal checkout. You still confirm and pay.
3. **Don't over-deliberate on quantity.** Decide your limit in advance (e.g.
   "1 box, max $80") so you're not doing maths while it sells out.
4. **Have a backup store.** Your Discord posts a mix — if EB sells out, the
   same set is often still up at JB or Big W minutes later.

## Knowing WHEN drops happen (pattern, not luck)

- Many EB Games TCG presales go live at **predictable times** — often business
  hours AEST, and often the same weekday for a given wave. Keep a simple note
  of when *your* sets historically dropped; you'll start seeing the cadence.
- The bot's run log (in the GitHub Actions tab) is a free timestamp record of
  when each item flipped to pre-order. Over a few drops, that's your data.

## What this setup does and doesn't do

- **Does:** alert you the instant a watched set hits pre-order, with a direct
  link and a one-tap path to a pre-filled cart, so your *human* checkout is as
  fast as it can legitimately be.
- **Doesn't:** auto-buy, auto-fill payment, or check out without you. That's
  the line — it breaks ToS and it's the exact behaviour that makes presales
  hell for collectors. You're competing as a fast, prepared human, not a bot.
