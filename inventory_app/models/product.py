from datetime import datetime, timezone

from inventory_app.extensions import db


class Product(db.Model):
    __tablename__ = "products"

    id = db.Column(db.Integer, primary_key=True)
    product_name = db.Column(db.String(150), nullable=False, index=True)
    part_number = db.Column(db.String(80), unique=True, nullable=False, index=True)
    category = db.Column(db.String(100), nullable=False, index=True)
    brand = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    unit_price = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    current_stock = db.Column(db.Integer, nullable=False, default=0)
    minimum_stock = db.Column(db.Integer, nullable=False, default=0)
    reorder_level = db.Column(db.Integer, nullable=False, default=0)
    supplier_id = db.Column(
        db.Integer, db.ForeignKey("suppliers.id"), nullable=True, index=True
    )
    created_at = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    supplier = db.relationship("Supplier", back_populates="products")

    __table_args__ = (
        db.CheckConstraint("unit_price >= 0", name="ck_product_unit_price_positive"),
        db.CheckConstraint("current_stock >= 0", name="ck_product_stock_positive"),
        db.CheckConstraint("minimum_stock >= 0", name="ck_product_minimum_stock_positive"),
        db.CheckConstraint("reorder_level >= 0", name="ck_product_reorder_level_positive"),
    )

    @property
    def stock_status(self) -> str:
        if self.current_stock == 0:
            return "Out of stock"
        if self.current_stock <= self.reorder_level:
            return "Low stock"
        return "In stock"

    def __repr__(self) -> str:
        return f"<Product {self.part_number!r}>"
