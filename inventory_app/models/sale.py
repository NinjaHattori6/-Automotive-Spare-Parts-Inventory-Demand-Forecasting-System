from flask import Blueprint, flash, redirect, render_template, request, url_for

from inventory_app.extensions import db
from inventory_app.models import Product, Purchase, Supplier
from inventory_app.routes.auth import login_required

bp = Blueprint("purchases", __name__, url_prefix="/purchases")


@bp.get("/")
@login_required
def index():
    purchases = db.session.execute(
        db.select(Purchase).order_by(Purchase.purchase_date.desc(), Purchase.id.desc())
    ).scalars().all()
    return render_template("purchases/index.html", purchases=purchases)


@bp.route("/new", methods=["GET", "POST"])
@login_required
def create_purchase():
    products = db.session.execute(db.select(Product).order_by(Product.product_name.asc())).scalars().all()
    suppliers = db.session.execute(db.select(Supplier).order_by(Supplier.supplier_name.asc())).scalars().all()

    if request.method == "POST":
        supplier_id = request.form.get("supplier_id", type=int)
        product_id = request.form.get("product_id", type=int)
        quantity = request.form.get("quantity", type=int)
        unit_cost = request.form.get("unit_cost", type=float)
        purchase_date = request.form.get("purchase_date") or None
        status = request.form.get("status", "Pending")

        if not supplier_id or not product_id:
            flash("Please select a supplier and product.", "danger")
        elif quantity is None or quantity <= 0:
            flash("Quantity must be greater than zero.", "danger")
        elif unit_cost is None or unit_cost <= 0:
            flash("Unit cost must be greater than zero.", "danger")
        else:
            total_cost = quantity * unit_cost
            product = db.session.get(Product, product_id)
            purchase = Purchase(
                supplier_id=supplier_id,
                product_id=product_id,
                quantity=quantity,
                unit_cost=unit_cost,
                total_cost=total_cost,
                purchase_date=purchase_date or None,
                status=status,
            )
            db.session.add(purchase)
            if status.lower() == "received":
                product.current_stock += quantity
            db.session.commit()
            flash("Purchase order recorded successfully.", "success")
            return redirect(url_for("purchases.index"))

    return render_template("purchases/form.html", suppliers=suppliers, products=products, purchase=None, action="Create")


@bp.route("/<int:purchase_id>/receive", methods=["POST"])
@login_required
def receive_purchase(purchase_id):
    purchase = db.session.get(Purchase, purchase_id)
    if purchase is None:
        flash("Purchase not found.", "warning")
        return redirect(url_for("purchases.index"))

    if purchase.product is not None:
        purchase.product.current_stock += purchase.quantity
    purchase.status = "Received"
    db.session.commit()
    flash("Purchase received and inventory updated.", "success")
    return redirect(url_for("purchases.index"))
