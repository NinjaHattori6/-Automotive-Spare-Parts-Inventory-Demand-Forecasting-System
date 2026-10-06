from datetime import date, datetime, timedelta, timezone

import pytest

from config import TestingConfig
from inventory_app import create_app
from inventory_app.extensions import db
from inventory_app.models import Product, Purchase, Sale, Supplier, User
from inventory_app.services.analytics import DateRange, build_analytics_context, demand_forecast, get_sales_dataframe


@pytest.fixture()
def app(tmp_path):
    class TestConfig(TestingConfig):
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{tmp_path / 'test.db'}"

    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
    yield app
    with app.app_context():
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


def register_and_login(client, username="demo", email="demo@example.com", credential="securepass"):
    client.post(
        "/register",
        data={
            "username": username,
            "email": email,
            "password": credential,
            "confirm_password": credential,
        },
        follow_redirects=True,
    )
    client.post(
        "/login",
        data={"identifier": username, "password": credential},
        follow_redirects=True,
    )


def seed_inventory_with_sales():
    supplier = Supplier(supplier_name="Main Supplier")
    brake = Product(
        product_name="Brake Pad",
        part_number="BP-100",
        category="Brakes",
        brand="AutoPro",
        unit_price=50,
        current_stock=40,
        reorder_level=10,
        supplier=supplier,
    )
    oil_filter = Product(
        product_name="Oil Filter",
        part_number="OF-200",
        category="Filters",
        brand="AutoPro",
        unit_price=20,
        current_stock=6,
        reorder_level=6,
        supplier=supplier,
    )
    no_sales = Product(
        product_name="Wiper Blade",
        part_number="WB-300",
        category="Accessories",
        brand="AutoPro",
        unit_price=15,
        current_stock=8,
        reorder_level=4,
        supplier=supplier,
    )
    db.session.add_all([supplier, brake, oil_filter, no_sales])
    db.session.flush()

    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    sales = [
        Sale(product_id=brake.id, quantity=2, unit_price=50, total_amount=100, sale_date=base),
        Sale(product_id=brake.id, quantity=3, unit_price=50, total_amount=150, sale_date=base + timedelta(days=1)),
        Sale(product_id=oil_filter.id, quantity=1, unit_price=20, total_amount=20, sale_date=base + timedelta(days=1)),
    ]
    db.session.add_all(sales)
    db.session.commit()
    return supplier, brake, oil_filter, no_sales


def test_registration_login_and_protected_pages(client, app):
    response = client.post(
        "/register",
        data={
            "username": "demo",
            "email": "demo@example.com",
            "password": "securepass",
            "confirm_password": "securepass",
        },
        follow_redirects=True,
    )
    assert b"Registration successful" in response.data

    for route in ["/", "/products/", "/suppliers/", "/sales/", "/purchases/", "/analytics/"]:
        protected = client.get(route)
        assert protected.status_code == 302
        assert "/login" in protected.headers["Location"]

    login = client.post("/login", data={"identifier": "demo", "password": "securepass"}, follow_redirects=True)
    assert login.status_code == 200
    assert b"Inventory dashboard" in login.data

    with app.app_context():
        assert db.session.scalar(db.select(db.func.count(User.id))) == 1


def test_model_imports_and_blueprint_registration(app):
    with app.app_context():
        assert User.__tablename__ == "users"
        assert Product.__tablename__ == "products"
        assert Supplier.__tablename__ == "suppliers"
        assert Sale.__tablename__ == "sales"
        assert Purchase.__tablename__ == "purchases"

    endpoints = {rule.endpoint for rule in app.url_map.iter_rules()}
    assert "auth.login" in endpoints
    assert "dashboard.index" in endpoints
    assert "products.index" in endpoints
    assert "suppliers.index" in endpoints
    assert "sales.index" in endpoints
    assert "purchases.index" in endpoints
    assert "analytics.index" in endpoints
    assert "analytics.export_forecast_csv" in endpoints
    assert "analytics.forecast_json" in endpoints


def test_product_and_supplier_crud_paths(client, app):
    register_and_login(client)

    create_supplier = client.post(
        "/suppliers/new",
        data={
            "supplier_name": "ACME Supply",
            "contact_person": "Alex",
            "email": "alex@acme.test",
            "phone": "1234",
            "address": "Line 1",
            "lead_time_days": "3",
        },
        follow_redirects=True,
    )
    assert b"Supplier created successfully" in create_supplier.data

    with app.app_context():
        supplier = db.session.execute(db.select(Supplier).where(Supplier.supplier_name == "ACME Supply")).scalar_one()

    create_product = client.post(
        "/products/new",
        data={
            "product_name": "Spark Plug",
            "part_number": "SP-001",
            "category": "Ignition",
            "brand": "Moto",
            "description": "Premium plug",
            "supplier_id": str(supplier.id),
            "unit_price": "12.50",
            "current_stock": "14",
            "minimum_stock": "2",
            "reorder_level": "5",
        },
        follow_redirects=True,
    )
    assert b"Product created successfully" in create_product.data

    with app.app_context():
        product = db.session.execute(db.select(Product).where(Product.part_number == "SP-001")).scalar_one()

    assert client.get("/products/").status_code == 200
    assert client.get(f"/products/{product.id}").status_code == 200
    edit_product = client.post(
        f"/products/{product.id}/edit",
        data={
            "product_name": "Spark Plug X",
            "part_number": "SP-001",
            "category": "Ignition",
            "brand": "Moto",
            "description": "Updated",
            "supplier_id": str(supplier.id),
            "unit_price": "14.00",
            "current_stock": "10",
            "minimum_stock": "2",
            "reorder_level": "4",
        },
        follow_redirects=True,
    )
    assert b"Product updated successfully" in edit_product.data

    delete_product = client.post(f"/products/{product.id}/delete", follow_redirects=True)
    assert b"Product deleted successfully" in delete_product.data
    delete_supplier = client.post(f"/suppliers/{supplier.id}/delete", follow_redirects=True)
    assert b"Supplier deleted successfully" in delete_supplier.data


def test_sale_stock_deduction_and_delete_restoration(client, app):
    register_and_login(client)
    with app.app_context():
        supplier = Supplier(supplier_name="S1")
        product = Product(
            product_name="Disc",
            part_number="D-100",
            category="Brakes",
            brand="Brand",
            unit_price=25,
            current_stock=10,
            reorder_level=2,
            supplier=supplier,
        )
        db.session.add_all([supplier, product])
        db.session.commit()
        product_id = product.id

    create_sale = client.post(
        "/sales/new",
        data={"product_id": str(product_id), "quantity": "4", "sale_date": "2026-01-10"},
        follow_redirects=True,
    )
    assert b"Sale recorded successfully" in create_sale.data

    with app.app_context():
        product = db.session.get(Product, product_id)
        sale = db.session.execute(db.select(Sale).where(Sale.product_id == product_id)).scalar_one()
        assert product.current_stock == 6
        sale_id = sale.id

    delete_sale = client.post(f"/sales/{sale_id}/delete", follow_redirects=True)
    assert b"Sale deleted successfully" in delete_sale.data

    with app.app_context():
        product = db.session.get(Product, product_id)
        assert product.current_stock == 10
        assert db.session.execute(db.select(Sale).where(Sale.id == sale_id)).scalar_one_or_none() is None


def test_purchase_receiving_idempotency(client, app):
    register_and_login(client)
    with app.app_context():
        supplier = Supplier(supplier_name="S2")
        product = Product(
            product_name="Bearing",
            part_number="B-200",
            category="Engine",
            brand="Brand",
            unit_price=8,
            current_stock=5,
            reorder_level=2,
            supplier=supplier,
        )
        db.session.add_all([supplier, product])
        db.session.commit()
        supplier_id = supplier.id
        product_id = product.id

    create_purchase = client.post(
        "/purchases/new",
        data={
            "supplier_id": str(supplier_id),
            "product_id": str(product_id),
            "quantity": "3",
            "unit_cost": "4.5",
            "status": "Pending",
            "purchase_date": "2026-01-10",
        },
        follow_redirects=True,
    )
    assert b"Purchase order recorded successfully" in create_purchase.data

    with app.app_context():
        product = db.session.get(Product, product_id)
        purchase = db.session.execute(db.select(Purchase).where(Purchase.product_id == product_id)).scalar_one()
        assert product.current_stock == 5
        purchase_id = purchase.id

    first_receive = client.post(f"/purchases/{purchase_id}/receive", follow_redirects=True)
    assert b"Purchase received and inventory updated" in first_receive.data
    second_receive = client.post(f"/purchases/{purchase_id}/receive", follow_redirects=True)
    assert b"already received" in second_receive.data

    with app.app_context():
        product = db.session.get(Product, product_id)
        purchase = db.session.get(Purchase, purchase_id)
        assert product.current_stock == 8
        assert purchase.status == "Received"


def test_analytics_empty_and_non_empty_behavior(app):
    with app.app_context():
        empty = build_analytics_context(DateRange())
        assert empty["summary"]["total_revenue"] == 0.0
        assert empty["summary"]["units_sold"] == 0
        assert empty["daily_sales"] == []
        assert empty["monthly_sales"] == []
        assert empty["top_products"] == []
        assert empty["forecast"]["rows"] == []

        _, _, _, no_sales_product = seed_inventory_with_sales()
        all_data = build_analytics_context(DateRange())
        assert all_data["summary"]["total_revenue"] == 270.0
        assert all_data["summary"]["units_sold"] == 6
        assert any(item["product_name"] == no_sales_product.product_name for item in all_data["slow_products"])

        filtered = build_analytics_context(DateRange(start_date=date(2026, 1, 2), end_date=date(2026, 1, 2)))
        assert filtered["summary"]["units_sold"] == 4
        assert len(filtered["daily_sales"]) == 1
        assert filtered["daily_sales"][0]["date"] == "2026-01-02"


def test_forecast_output_shape_and_edge_cases(app):
    with app.app_context():
        seed_inventory_with_sales()
        df = get_sales_dataframe(DateRange())
        forecast = demand_forecast(df)

        assert forecast["model_name"].startswith("Seasonal-naive")
        assert forecast["horizon_weeks"] == 4
        assert len(forecast["limitations"]) >= 2
        assert len(forecast["products"]) == 3
        assert len(forecast["rows"]) == 12

        no_history_rows = [row for row in forecast["rows"] if row["product_name"] == "Wiper Blade"]
        assert len(no_history_rows) == 4
        assert all(row["forecast_units"] == 0 for row in no_history_rows)
        assert all(row["history_weeks"] == 0 for row in no_history_rows)

        for row in forecast["rows"]:
            assert {"product_id", "product_name", "week_start", "forecast_units"} <= set(row.keys())
            datetime.fromisoformat(row["week_start"])
            assert row["forecast_units"] >= 0


def test_analytics_forecast_routes_protection_and_exports(client, app):
    for route in ["/analytics", "/analytics/export.csv", "/analytics/forecast.csv", "/analytics/forecast.json"]:
        response = client.get(route)
        assert response.status_code == 302
        assert "/login" in response.headers["Location"]

    with app.app_context():
        seed_inventory_with_sales()

    register_and_login(client)

    page = client.get("/analytics")
    assert page.status_code == 200
    assert b"Sales and inventory analytics" in page.data
    assert b"Demand forecast" in page.data

    sales_csv = client.get("/analytics/export.csv")
    assert sales_csv.status_code == 200
    assert sales_csv.mimetype == "text/csv"
    assert b"sale_date,product_name,category,quantity,revenue" in sales_csv.data

    forecast_csv = client.get("/analytics/forecast.csv")
    assert forecast_csv.status_code == 200
    assert forecast_csv.mimetype == "text/csv"
    assert b"product_id,product_name,week_start,forecast_units" in forecast_csv.data

    forecast_json = client.get("/analytics/forecast.json")
    assert forecast_json.status_code == 200
    payload = forecast_json.get_json()
    assert payload["horizon_weeks"] == 4
    assert len(payload["rows"]) > 0
