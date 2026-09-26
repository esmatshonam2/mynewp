# Telegram setup (admin bot + shop bot)

One bot serves both modes from a single token.

## Connect

1. Talk to `@BotFather` → `/newbot` → copy the token.
2. Start your bot once (press Start), get your numeric id from
   `@userinfobot`.
3. Panel → Telegram: paste token + Chat ID → Save → **Send test**.
   The bot username is stored for referral links.

## Modes

- **Your Chat ID** → admin commands (`/stats /users /user /sub`
  with real data + QR, `/create /reset /delete`, top-up approve buttons).
- **Everyone else** → shop menu (buy with wallet, free test, orders,
  wallet + top-up requests, referrals, daily wheel, support).
- Polling is long-poll in-process (no webhook/domain needed); status is
  shown in the Telegram view.

## Shop knobs (Telegram → Shop card)

`shop_enabled`, `support_username`, free-test GB/days, referral bonus.
Plans carry a `price` (0 = free). Top-up amounts are fixed
(50k/100k/200k) and require admin approval (button or Shop view).

## Notifications (per-type toggles)

New user, quota/expiry warnings, panel logins, server up/down.
The token is stored in the DB and shown masked; rotate via BotFather +
re-save when staff changes.
