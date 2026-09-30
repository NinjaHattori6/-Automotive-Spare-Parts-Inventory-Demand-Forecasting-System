from flask import Blueprint, flash, redirect, render_template, request, url_for
from sqlalchemy import or_

from inventory_app.extensions import db
from inventory_app.models import Supplier
from inventory_app.routes.auth import login_required

bp = Blueprint("suppliers", __name__, url_prefix="/suppliers")


@bp.get("/")
@login_required
def index():
    search = request.args.get("q", "").strip()
    query = db.select(Supplier).order_by(Supplier.created_at.desc())
    if search:
        term = f"%{search}%"
        query = query.where(
            or_(
                Supplier.supplier_name.ilike(term),
                Supplier.contact_person.ilike(term),
                Supplier.email.ilike(term),
            )
        )
    suppliers = db.session.execute(query).scalars().all()
    return render_template("suppliers/index.html", suppliers=suppliers, search=search)


@bp.route("/new", methods=["GET", "POST"])
@login_required
def create_supplier():
    if request.method == "POST":
        supplier = Supplier(
            supplier_name=request.form.get("supplier_name", "").strip(),
            contact_person=request.form.get("contact_person", "").strip(),
            email=request.form.get("email", "").strip(),
            phone=request.form.get("phone", "").strip(),
            address=request.form.get("address", "").strip(),
            lead_time_days=request.form.get("lead_time_days", type=int) or 0,
        )
        if not supplier.supplier_name:
            flash("Supplier name is required.", "danger")
        else:
            db.session.add(supplier)
            db.session.commit()
            flash("Supplier created successfully.", "success")
            return redirect(url_for("suppliers.index"))

    return render_template("suppliers/form.html", supplier=None, action="Create")


@bp.get("/<int:supplier_id>")
@login_required
def supplier_detail(supplier_id):
    supplier = db.session.get(Supplier, supplier_id)
    if supplier is None:
        flash("Supplier not found.", "warning")
        return redirect(url_for("suppliers.index"))
    return render_template("suppliers/detail.html", supplier=supplier)


@bp.route("/<int:supplier_id>/edit", methods=["GET", "POST"])
@login_required
def edit_supplier(supplier_id):
    supplier = db.session.get(Supplier, supplier_id)
    if supplier is None:
        flash("Supplier not found.", "warning")
        return redirect(url_for("suppliers.index"))

    if request.method == "POST":
        supplier.supplier_name = request.form.get("supplier_name", "").strip()
        supplier.contact_person = request.form.get("contact_person", "").strip()
        supplier.email = request.form.get("email", "").strip()
        supplier.phone = request.form.get("phone", "").strip()
        supplier.address = request.form.get("address", "").strip()
        supplier.lead_time_days = request.form.get("lead_time_days", type=int) or 0
        if not supplier.supplier_name:
            flash("Supplier name is required.", "danger")
        else:
            db.session.commit()
            flash("Supplier updated successfully.", "success")
            return redirect(url_for("suppliers.supplier_detail", supplier_id=supplier.id))

    return render_template("suppliers/form.html", supplier=supplier, action="Edit")


@bp.post("/<int:supplier_id>/delete")
@login_required
def delete_supplier(supplier_id):
    supplier = db.session.get(Supplier, supplier_id)
    if supplier is None:
        flash("Supplier not found.", "warning")
    else:
        db.session.delete(supplier)
        db.session.commit()
        flash("Supplier deleted successfully.", "success")
    return redirect(url_for("suppliers.index"))
