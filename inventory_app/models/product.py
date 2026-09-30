from datetime import datetime, timezone

from inventory_app.extensions import db


class Purchase(db.Model):
    __tablename__ = "purchases"

    id = db.Column(db.Integer, primary_key=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey("suppliers.id"), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False, index=True)
    quantity = db.Column(db.Integer, nullable=False)
    unit_cost = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    total_cost = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    purchase_date = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    status = db.Column(db.String(30), nullable=False, default="Pending")
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    supplier = db.relationship("Supplier", back_populates="purchases")
    product = db.relationship("Product", back_populates="purchases")

    __table_args__ = (
        db.CheckConstraint("quantity > 0", name="ck_purchase_quantity_positive"),
        db.CheckConstraint("total_cost >= 0", name="ck_purchase_total_non_negative"),
    )

    def __repr__(self):
        return f"<Purchase {self.id}>"
