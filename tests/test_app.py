import pytest

from inventory_app import create_app
from inventory_app.extensions import db
from inventory_app.models import Product, Supplier, User
from config import TestingConfig


@pytest.fixture()
def app():
    app = create_app(TestingConfig)
    with app.app_context():
        db.create_all()
    yield app
    with app.app_context():
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


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
        assert Product.query.count() == 0
        assert Supplier.query.count() == 0
