# Automotive Spare Parts Inventory Demand Forecasting System

A staged Flask application for automotive spare-parts operations.

## Current scope (Stage 1-4)
- Authentication (register/login/logout)
- Product CRUD with stock indicators
- Supplier CRUD
- Sales recording with automatic stock deduction
- Purchase recording/receiving with inventory updates
- Dashboard KPIs and quick links
- **Stage 4 analytics**:
  - Pandas-based analytics service (`inventory_app/services/analytics.py`)
  - Daily/weekly/monthly sales aggregation
  - 7-day and 30-day moving averages
  - Product trends, top-selling and slow-moving products
  - Revenue and category performance trends
  - Inventory stock-status distribution
  - Protected `/analytics` page with Chart.js dashboards
  - Date-range filtering (`start_date`, `end_date`)
  - CSV export endpoint: `/analytics/export.csv`

## Setup
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run
```bash
flask --app app.py init-db
flask --app app.py run
```

Open:
- Dashboard: `http://127.0.0.1:5000/`
- Analytics: `http://127.0.0.1:5000/analytics`

## Tests
```bash
python -m pytest -q
```

## Analytics implementation notes
- Sales data is loaded through SQLAlchemy ORM joins and converted to Pandas DataFrames in the analytics service.
- Aggregation and chart payload generation stay in service code, not Jinja templates.
- Chart datasets are passed with Jinja `tojson` to avoid unsafe string interpolation.
- CSV export is streamed via Flask response; no generated files are written into the repository.
