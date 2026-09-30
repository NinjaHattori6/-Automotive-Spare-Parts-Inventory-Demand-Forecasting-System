from flask import Blueprint, render_template

from inventory_app.extensions import db
from inventory_app.models import Product, Supplier, User
from inventory_app.routes.auth import login_required

bp = Blueprint("dashboard", __name__)


@bp.get("/")
@login_required
def index():
    return render_template(
        "dashboard.html",
        user_count=db.session.scalar(db.select(db.func.count(User.id))) or 0,
        product_count=db.session.scalar(db.select(db.func.count(Product.id))) or 0,
        supplier_count=db.session.scalar(db.select(db.func.count(Supplier.id))) or 0,
    )
