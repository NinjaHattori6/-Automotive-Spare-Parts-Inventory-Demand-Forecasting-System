from flask import Blueprint, flash, redirect, render_template, request, url_for
from sqlalchemy import or_

from inventory_app.extensions import db
from inventory_app.models import Product, Supplier
from inventory_app.routes.auth import login_required

bp = Blueprint("products", __name__, url_prefix="/products")


def _product_query(search=None, category=None):
    query = db.session.execute(db.select(Product).order_by(Product.created_at.desc())).scalars()
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                Product.product_name.ilike(search_term),
                Product.part_number.ilike(search_term),
                Product.brand.ilike(search_term),
            )
        )
    if category:
        query = query.filter(Product.category == category)
    return query


@bp.get("/")
@login_required
def index():
    search = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()
    products = _product_query(search=search, category=category).all()
    categories = [
        row[0]
        for row in db.session.execute(
            db.select(Product.category).distinct().order_by(Product.category)
        ).all()
    ]
    return render_template(
        "products/index.html",
        products=products,
        categories=categories,
        search=search,
        category=category,
    )


@bp.route("/new", methods=["GET", "POST"])
@login_required
def create_product():
    suppliers = db.session.execute(
        db.select(Supplier).order_by(Supplier.supplier_name.asc())
    ).scalars().all()

    if request.method == "POST":
        product_name = request.form.get("product_name", "").strip()
        part_number = request.form.get("part_number", "").strip()
        category = request.form.get("category", "").strip()
        brand = request.form.get("brand", "").strip()
        description = request.form.get("description", "").strip()
        supplier_id = request.form.get("supplier_id") or None
        try:
            unit_price = float(request.form.get("unit_price", 0) or 0)
            current_stock = int(request.form.get("current_stock", 0) or 0)
            minimum_stock = int(request.form.get("minimum_stock", 0) or 0)
            reorder_level = int(request.form.get("reorder_level", 0) or 0)
        except ValueError:
            flash("Product quantities and pricing must be valid numbers.", "danger")
            return render_template("products/form.html", product=None, suppliers=suppliers, action="Create")

        if not product_name or not part_number or not category or not brand:
            flash("Product name, part number, category, and brand are required.", "danger")
        elif db.session.execute(db.select(Product).where(Product.part_number == part_number)).scalar_one_or_none():
            flash("A product with that part number already exists.", "danger")
        else:
            product = Product(
                product_name=product_name,
                part_number=part_number,
                category=category,
                brand=brand,
                description=description,
                unit_price=unit_price,
                current_stock=current_stock,
                minimum_stock=minimum_stock,
                reorder_level=reorder_level,
                supplier_id=supplier_id,
            )
            db.session.add(product)
            db.session.commit()
            flash("Product created successfully.", "success")
            return redirect(url_for("products.index"))

    return render_template("products/form.html", product=None, suppliers=suppliers, action="Create")


@bp.route("/<int:product_id>", methods=["GET"])
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

    suppliers = db.session.execute(
        db.select(Supplier).order_by(Supplier.supplier_name.asc())
    ).scalars().all()

    if request.method == "POST":
        product.product_name = request.form.get("product_name", "").strip()
        product.part_number = request.form.get("part_number", "").strip()
        product.category = request.form.get("category", "").strip()
        product.brand = request.form.get("brand", "").strip()
        product.description = request.form.get("description", "").strip()
        product.supplier_id = request.form.get("supplier_id") or None

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


@bp.route("/<int:product_id>/delete", methods=["POST"])
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
