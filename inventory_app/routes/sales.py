from datetime import datetime, timezone

from flask import Blueprint, flash, redirect, render_template, request, url_for

from inventory_app.extensions import db
from inventory_app.models import Product, Sale
from inventory_app.routes.auth import login_required

bp = Blueprint("sales", __name__, url_prefix="/sales")


def _parse_date_input(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value)
    return datetime(parsed.year, parsed.month, parsed.day, tzinfo=timezone.utc)


@bp.get("/")
@login_required
def index():
    product_id = request.args.get("product_id", type=int)
    query = db.select(Sale).order_by(Sale.sale_date.desc(), Sale.id.desc())
    if product_id:
        query = query.where(Sale.product_id == product_id)
    sales = db.session.execute(query).scalars().all()
    products = db.session.execute(db.select(Product).order_by(Product.product_name.asc())).scalars().all()
    return render_template("sales/index.html", sales=sales, products=products, selected_product_id=product_id)


@bp.route("/new", methods=["GET", "POST"])
@login_required
def create_sale():
    products = db.session.execute(db.select(Product).order_by(Product.product_name.asc())).scalars().all()

    if request.method == "POST":
        product_id = request.form.get("product_id", type=int)
        quantity = request.form.get("quantity", type=int)
        sale_date = _parse_date_input(request.form.get("sale_date"))
        product = db.session.get(Product, product_id)

        if not product:
            flash("Please select a valid product.", "danger")
        elif quantity is None or quantity <= 0:
            flash("Sale quantity must be greater than zero.", "danger")
        elif quantity > product.current_stock:
            flash("Not enough stock available for this sale.", "danger")
        else:
            unit_price = float(product.unit_price or 0)
            total_amount = quantity * unit_price
            sale = Sale(
                product_id=product.id,
                quantity=quantity,
                unit_price=unit_price,
                total_amount=total_amount,
                sale_date=sale_date or None,
            )
            product.current_stock -= quantity
            db.session.add(sale)
            db.session.commit()
            flash("Sale recorded successfully.", "success")
            return redirect(url_for("sales.index"))

    return render_template("sales/form.html", products=products, sale=None, action="Create")


@bp.post("/<int:sale_id>/delete")
@login_required
def delete_sale(sale_id):
    sale = db.session.get(Sale, sale_id)
    if sale is not None:
        if sale.product:
            sale.product.current_stock += sale.quantity
        db.session.delete(sale)
        db.session.commit()
        flash("Sale deleted successfully.", "success")
    else:
        flash("Sale not found.", "warning")
    return redirect(url_for("sales.index"))
