from datetime import datetime, timezone

from inventory_app.extensions import db


class Supplier(db.Model):
    __tablename__ = "suppliers"

    id = db.Column(db.Integer, primary_key=True)
    supplier_name = db.Column(db.String(150), nullable=False, index=True)
    contact_person = db.Column(db.String(120))
    email = db.Column(db.String(255))
    phone = db.Column(db.String(40))
    address = db.Column(db.Text)
    lead_time_days = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    products = db.relationship("Product", back_populates="supplier", lazy=True)

    __table_args__ = (
        db.CheckConstraint("lead_time_days >= 0", name="ck_supplier_lead_time_positive"),
    )

    def __repr__(self) -> str:
        return f"<Supplier {self.supplier_name!r}>"
