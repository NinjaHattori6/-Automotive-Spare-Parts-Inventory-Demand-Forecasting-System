# Automotive Spare Parts Inventory & Demand Forecasting System

A modular Flask foundation for managing automotive spare parts inventory and forecasting demand. This repository is being built incrementally as a portfolio project demonstrating Python, Flask, SQLAlchemy, authentication, analytics, and machine learning.

## Stage 1 completed

This stage includes:

- Flask application factory and modular package structure
- Environment-based configuration with SQLite development storage
- Flask-SQLAlchemy initialization
- `User`, `Product`, and `Supplier` models with relationships and constraints
- Password hashing with Werkzeug
- Registration, login, logout, protected dashboard, and Admin/Staff role field
- Minimal responsive Bootstrap UI with flash messages
- Safe `flask init-db` database initialization command
- Smoke tests for registration, login, database tables, and protected access

Sales, purchases, analytics, forecasting, and product/supplier CRUD screens are intentionally not included yet.

## Requirements

- Python 3.12 or newer
- pip

## Installation

### macOS/Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
```

### Windows PowerShell

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `.env` and replace `SECRET_KEY` with a long random value. The default database is created at `instance/inventory.db`; this directory is ignored by Git.

## Initialize and run

From the repository root, with the virtual environment active:

```bash
flask --app app.py init-db
flask --app app.py run --debug
```

Open `http://127.0.0.1:5000`, create an account, and sign in. You can also run the application directly with `python app.py`.

To run tests:

```bash
pytest
```

## Project structure

```text
.
├── app.py                    # WSGI entry point
├── config.py                 # Environment-aware configuration
├── requirements.txt
├── inventory_app/
│   ├── __init__.py           # Application factory and CLI commands
│   ├── extensions.py         # SQLAlchemy extension
│   ├── models/               # User, Product, Supplier models
│   ├── routes/               # Authentication and dashboard blueprints
│   ├── templates/            # Jinja templates
│   └── static/               # CSS and JavaScript
└── tests/
```

## Configuration

- `SECRET_KEY`: Flask session signing key. Set this in `.env`.
- `DATABASE_URL`: Optional SQLAlchemy URI. If omitted, local SQLite is used.
- `FLASK_DEBUG`: Set to `1` for local debug mode.

## Planned next stages

1. Product and supplier CRUD with search, filters, and stock indicators.
2. Sales and purchase workflows with stock updates and CSV export.
3. Dashboard KPIs and Chart.js visualizations.
4. Pandas analytics and realistic seed data.
5. Time-aware demand forecasting with baseline and regression models.
6. Reorder-point and recommended-order calculations.
7. Production hardening, CSRF protection, migrations, and deployment documentation.
