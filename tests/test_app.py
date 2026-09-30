from datetime import datetime, timedelta, timezone

import pytest

from config import TestingConfig
from inventory_app import create_app
from inventory_app.extensions import db
from inventory_app.models import Product, Sale, Supplier, User
from inventory_app.services.analytics import DateRange, build_analytics_context


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


def register_and_login(client):
    client.post(
        "/register",
        data={
            "username": "demo",
            "email": "demo@example.com",
            "password": "securepass",
            "confirm_password": "securepass",
        },
        follow_redirects=True,
    )
    client.post(
        "/login",
        data={"identifier": "demo", "password": "securepass"},
        follow_redirects=True,
    )


def seed_sales_data():
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
    filter_product = Product(
        product_name="Oil Filter",
        part_number="OF-200",
        category="Filters",
        brand="AutoPro",
        unit_price=20,
        current_stock=5,
        reorder_level=6,
        supplier=supplier,
    )
    db.session.add_all([supplier, brake, filter_product])
    db.session.flush()

    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    sales = [
        Sale(product_id=brake.id, quantity=2, unit_price=50, total_amount=100, sale_date=base),
        Sale(product_id=brake.id, quantity=3, unit_price=50, total_amount=150, sale_date=base + timedelta(days=1)),
        Sale(product_id=filter_product.id, quantity=1, unit_price=20, total_amount=20, sale_date=base + timedelta(days=1)),
    ]
    db.session.add_all(sales)
    db.session.commit()


def test_registration_login_and_protected_dashboard(client, app):
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

    response = client.get("/")
    assert response.status_code == 302

    response = client.post(
        "/login",
        data={"identifier": "demo", "password": "securepass"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Inventory dashboard" in response.data

    with app.app_context():
        assert db.session.scalar(db.select(db.func.count(User.id))) == 1


def test_analytics_route_requires_login(client):
    response = client.get("/analytics")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_analytics_service_handles_empty_dataset(app):
    with app.app_context():
        data = build_analytics_context(DateRange())
        assert data["summary"]["total_revenue"] == 0.0
        assert data["summary"]["units_sold"] == 0
        assert data["daily_sales"] == []
        assert data["monthly_sales"] == []
        assert data["top_products"] == []


def test_analytics_service_aggregations_with_data(app):
    with app.app_context():
        seed_sales_data()
        data = build_analytics_context(DateRange())

        assert data["summary"]["total_revenue"] == 270.0
        assert data["summary"]["units_sold"] == 6
        assert data["summary"]["best_selling_product"] == "Brake Pad"
        assert len(data["daily_sales"]) == 2
        assert data["daily_sales"][1]["revenue"] == 170.0
        assert data["monthly_sales"][0]["month"] == "2026-01"
        assert data["category_performance"][0]["category"] == "Brakes"


def test_logged_in_user_can_view_analytics_and_export(client, app):
    with app.app_context():
        seed_sales_data()

    register_and_login(client)

    page = client.get("/analytics")
    assert page.status_code == 200
    assert b"Sales and inventory analytics" in page.data

    export = client.get("/analytics/export.csv")
    assert export.status_code == 200
    assert export.mimetype == "text/csv"
    assert b"sale_date,product_name,category,quantity,revenue" in export.data
