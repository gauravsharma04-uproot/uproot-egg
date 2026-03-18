
# Uproot Easter Egg App

A production-style starter app for your Easter egg campaign.

## What it includes
- Guest flow: enter name + Instagram handle -> tap egg -> get weighted random prize
- Unique claim codes stored in SQLite
- Admin login + control panel
- Change prizes, weights, titles, and instructions later
- Staff redemption workflow
- Simple JSON API to verify a claim code

## Important limitation
Instagram does **not** let the app automatically verify that someone tagged 3 friends. For that part, the realistic options are:
1. staff manually checks the post/comments
2. use Instagram automation such as ManyChat and trigger the egg link from a comment like `EGG`

## Local run
```bash
python -m venv .venv
source .venv/bin/activate   # on Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Open:
- Guest site: http://127.0.0.1:5001/
- Admin: http://127.0.0.1:5001/admin/login

## Default admin password
Set an environment variable in production. Local default is:
`uproot123`

## Recommended production deployment
- Render
- Railway
- Fly.io
- A small VPS

## Production environment variables
- `SECRET_KEY`
- `ADMIN_PASSWORD`

## Change prizes later
Open the admin panel and edit:
- prize title
- subtitle
- weight
- active/inactive

Changes apply immediately.

## Verify a claim code
GET `/api/claim/<CODE>`

## Next upgrades you may want
- PostgreSQL instead of SQLite
- image/logo upload
- coupon expiry dates
- prize inventory caps
- ManyChat / Instagram DM automation
- Twilio SMS follow-up
