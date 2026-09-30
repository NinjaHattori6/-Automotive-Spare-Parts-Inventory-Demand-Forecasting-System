from flask import Blueprint, flash, redirect, render_template, request, url_for
from sqlalchemy import or_

from inventory_app.extensions import db
from inventory_app.models import Product, Supplier
from inventory_app.routes.auth import login_required

bp = Blueprint("products", __name__, url_prefix="/products")


@bp.get("/")
@login_required
def index():
    search = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()

    query = db.select(Product).order_by(Product.created_at.desc())
    if search:
        term = f"%{search}%"
        query = query.where(
            or_(
                Product.product_name.ilike(term),
                Product.part_number.ilike(term),
                Product.brand.ilike(term),
            )
        )
    if category:
        query = query.where(Product.category == category)

    products = db.session.execute(query).scalars().all()
    categories = [
        row[0]
        for row in db.session.execute(
            db.select(Product.category).where(Product.category.is_not(None)).distinct().order_by(Product.category.asc())
        ).all()
    ]
    return render_template("products/index.html", products=products, categories=categories, search=search, category=category)


@bp.route("/new", methods=["GET", "POST"])
@login_required
def create_product():
    suppliers = db.session.execute(db.select(Supplier).order_by(Supplier.supplier_name.asc())).scalars().all()
    if request.method == "POST":
        product = Product(
            product_name=request.form.get("product_name", "").strip(),
            part_number=request.form.get("part_number", "").strip(),
            category=request.form.get("category", "").strip(),
            brand=request.form.get("brand", "").strip(),
            description=request.form.get("description", "").strip(),
            supplier_id=request.form.get("supplier_id", type=int),
        )
        try:
            product.unit_price = float(request.form.get("unit_price", 0) or 0)
            product.current_stock = int(request.form.get("current_stock", 0) or 0)
            product.minimum_stock = int(request.form.get("minimum_stock", 0) or 0)
            product.reorder_level = int(request.form.get("reorder_level", 0) or 0)
        except ValueError:
            flash("Product quantities and pricing must be valid numbers.", "danger")
            return render_template("products/form.html", product=None, suppliers=suppliers, action="Create")

        if not product.product_name or not product.part_number or not product.category or not product.brand:
            flash("Product name, part number, category, and brand are required.", "danger")
        elif db.session.execute(db.select(Product).where(Product.part_number == product.part_number)).scalar_one_or_none():
            flash("A product with that part number already exists.", "danger")
        else:
            db.session.add(product)
            db.session.commit()
            flash("Product created successfully.", "success")
            return redirect(url_for("products.index"))

    return render_template("products/form.html", product=None, suppliers=suppliers, action="Create")


@bp.get("/<int:product_id>")
@login_required
def product_detail(product_id):
    product = db.session.get(Product, product_id)
    if product is None:
        flash("Product not found.", "warning")
        return redirect(url_for("products.index"))
    return render_template("products/detail.html", product=product)


@bp.route("/<int:product_id>/edit", methods=["GET", "POST"])
@login_required
def edit_product(product_id):
    product = db.session.get(Product, product_id)
    if product is None:
        flash("Product not found.", "warning")
        return redirect(url_for("products.index"))

    suppliers = db.session.execute(db.select(Supplier).order_by(Supplier.supplier_name.asc())).scalars().all()
    if request.method == "POST":
        product.product_name = request.form.get("product_name", "").strip()
        product.part_number = request.form.get("part_number", "").strip()
        product.category = request.form.get("category", "").strip()
        product.brand = request.form.get("brand", "").strip()
        product.description = request.form.get("description", "").strip()
        product.supplier_id = request.form.get("supplier_id", type=int)
        try:
            product.unit_price = float(request.form.get("unit_price", 0) or 0)
            product.current_stock = int(request.form.get("current_stock", 0) or 0)
            product.minimum_stock = int(request.form.get("minimum_stock", 0) or 0)
            product.reorder_level = int(request.form.get("reorder_level", 0) or 0)
        except ValueError:
            flash("Product quantities and pricing must be valid numbers.", "danger")
            return render_template("products/form.html", product=product, suppliers=suppliers, action="Edit")

        if not product.product_name or not product.part_number or not product.category or not product.brand:
            flash("Product name, part number, category, and brand are required.", "danger")
        else:
            db.session.commit()
            flash("Product updated successfully.", "success")
            return redirect(url_for("products.product_detail", product_id=product.id))

    return render_template("products/form.html", product=product, suppliers=suppliers, action="Edit")


@bp.post("/<int:product_id>/delete")
@login_required
def delete_product(product_id):
    product = db.session.get(Product, product_id)
    if product is None:
        flash("Product not found.", "warning")
    else:
        db.session.delete(product)
        db.session.commit()
        flash("Product deleted successfully.", "success")
    return redirect(url_for("products.index"))
