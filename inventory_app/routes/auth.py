from functools import wraps

from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError

from inventory_app.extensions import db
from inventory_app.models import User

bp = Blueprint("auth", __name__)


def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if session.get("user_id") is None:
            flash("Please log in to continue.", "warning")
            return redirect(url_for("auth.login", next=request.path))
        return view(*args, **kwargs)

    return wrapped_view


@bp.route("/register", methods=["GET", "POST"])
def register():
    if session.get("user_id"):
        return redirect(url_for("dashboard.index"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")
        errors = []

        if not username or not email or not password:
            errors.append("Username, email, and password are required.")
        if password != confirm_password:
            errors.append("Passwords do not match.")
        if len(password) < 8:
            errors.append("Password must contain at least 8 characters.")
        if db.session.execute(db.select(User).where(or_(User.username == username, User.email == email))).scalar_one_or_none():
            errors.append("That username or email is already registered.")

        if not errors:
            user = User(username=username, email=email)
            user.set_password(password)
            db.session.add(user)
            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                flash("That username or email is already registered.", "danger")
            else:
                flash("Registration successful. Please log in.", "success")
                return redirect(url_for("auth.login"))
        for error in errors:
            flash(error, "danger")

    return render_template("auth/register.html")


@bp.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("dashboard.index"))

    if request.method == "POST":
        identifier = request.form.get("identifier", "").strip()
        password = request.form.get("password", "")
        user = db.session.execute(
            db.select(User).where(or_(User.username == identifier, User.email == identifier.lower()))
        ).scalar_one_or_none()

        if user is None or not user.check_password(password):
            flash("Invalid username/email or password.", "danger")
        else:
            session.clear()
            session["user_id"] = user.id
            session["role"] = user.role
            next_url = request.args.get("next")
            if not next_url or not next_url.startswith("/"):
                next_url = url_for("dashboard.index")
            return redirect(next_url)

    return render_template("auth/login.html")


@bp.get("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))
