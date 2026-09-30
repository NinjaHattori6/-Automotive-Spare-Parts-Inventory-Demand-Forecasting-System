from datetime import datetime, timezone

from flask import Blueprint, render_template

from inventory_app.extensions import db
from inventory_app.models import Product, Sale, Supplier, User
from inventory_app.routes.auth import login_required
from inventory_app.services.analytics import DateRange, build_analytics_context

bp = Blueprint("dashboard", __name__)


@bp.get("/")
@login_required
def index():
    context = build_analytics_context(DateRange())
    summary = context["summary"]
    today = datetime.now(timezone.utc).date()
    todays_sales = sum(item["revenue"] for item in context["daily_sales"] if item["date"] == today.isoformat())

    return render_template(
        "dashboard.html",
        user_count=db.session.scalar(db.select(db.func.count(User.id))) or 0,
        product_count=db.session.scalar(db.select(db.func.count(Product.id))) or 0,
        supplier_count=db.session.scalar(db.select(db.func.count(Supplier.id))) or 0,
        total_inventory_units=db.session.scalar(db.select(db.func.coalesce(db.func.sum(Product.current_stock), 0))) or 0,
        total_inventory_value=float(
            db.session.scalar(db.select(db.func.coalesce(db.func.sum(Product.current_stock * Product.unit_price), 0))) or 0
        ),
        todays_sales=todays_sales,
        recent_sales=db.session.execute(db.select(Sale).order_by(Sale.sale_date.desc()).limit(5)).scalars().all(),
        top_products=context["top_products"][:5],
        total_revenue=summary["total_revenue"],
        units_sold=summary["units_sold"],
    )
