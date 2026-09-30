from datetime import datetime, timezone

from inventory_app.extensions import db


class Sale(db.Model):
    __tablename__ = "sales"

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False, index=True)
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    total_amount = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    sale_date = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    product = db.relationship("Product", back_populates="sales")

    __table_args__ = (
        db.CheckConstraint("quantity > 0", name="ck_sale_quantity_positive"),
        db.CheckConstraint("total_amount >= 0", name="ck_sale_total_non_negative"),
    )

    def __repr__(self):
        return f"<Sale {self.id}>"
