# Automotive Spare Parts Inventory Demand Forecasting System

Flask + SQLite inventory system for automotive spare parts, with protected operational workflows and analytics/forecasting views.

## Features
- Authentication: register, login, logout, protected routes
- Inventory entities: products, suppliers, sales, purchases
- Stock controls:
  - sales deduct stock
  - sale deletion restores stock
  - purchase receiving is idempotent (receiving twice does not double-count stock)
- Analytics dashboard (`/analytics`) with date filtering and CSV export
- Demand forecast baseline:
  - seasonal-naive weekly forecast with 4-week horizon
  - includes products with no sales history (zero baseline)
  - CSV and JSON export endpoints

## Setup
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Configuration
Copy `.env.example` to `.env` and set values as needed:
```dotenv
SECRET_KEY=replace-with-a-long-random-value
DATABASE_URL=sqlite:///instance/inventory.db
FLASK_DEBUG=1
```

## Database initialization
```bash
flask --app app.py init-db
```

## Run
```bash
flask --app app.py run
```

Open:
- App/dashboard: `http://127.0.0.1:5000/`
- Analytics: `http://127.0.0.1:5000/analytics`

## Test
```bash
python -m pytest -q
```

## Analytics and forecast endpoints
- Sales analytics page: `GET /analytics`
- Sales CSV export: `GET /analytics/export.csv`
- Forecast CSV export: `GET /analytics/forecast.csv`
- Forecast JSON export: `GET /analytics/forecast.json`

All analytics and forecast endpoints require login.

## Forecasting method and limitations
The forecast is a transparent **seasonal-naive baseline** over weekly units sold (not a machine-learning model). For each product, it reuses demand from the prior seasonal period (4 weeks); if insufficient history exists, it falls back to the product's historical mean.

Limitations:
- Does not model promotions, supply shocks, or external demand drivers.
- Products with no sales history forecast zero demand until transactions exist.
- Intended as a planning baseline; verify with domain knowledge before purchasing decisions.
