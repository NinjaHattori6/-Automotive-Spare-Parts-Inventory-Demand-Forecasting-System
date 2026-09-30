from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import pandas as pd
from sqlalchemy import func

from inventory_app.extensions import db
from inventory_app.models import Product, Sale


@dataclass
class DateRange:
    start_date: date | None = None
    end_date: date | None = None


def _to_float(value: Decimal | float | int | None) -> float:
    if value is None:
        return 0.0
    return float(value)


def get_sales_dataframe(date_range: DateRange | None = None) -> pd.DataFrame:
    query = (
        db.select(
            Sale.id,
            Sale.sale_date,
            Sale.quantity,
            Sale.total_amount,
            Product.id.label("product_id"),
            Product.product_name,
            Product.category,
        )
        .join(Product, Product.id == Sale.product_id)
        .order_by(Sale.sale_date.asc(), Sale.id.asc())
    )
    rows = db.session.execute(query).all()
    data = [
        {
            "sale_id": row.id,
            "sale_date": row.sale_date,
            "quantity": int(row.quantity or 0),
            "revenue": _to_float(row.total_amount),
            "product_id": row.product_id,
            "product_name": row.product_name,
            "category": row.category or "Uncategorized",
        }
        for row in rows
    ]

    if not data:
        return pd.DataFrame(
            columns=["sale_id", "sale_date", "quantity", "revenue", "product_id", "product_name", "category"]
        )

    df = pd.DataFrame(data)
    df["sale_date"] = pd.to_datetime(df["sale_date"], errors="coerce", utc=True)
    df = df.dropna(subset=["sale_date"])
    if date_range and date_range.start_date:
        df = df[df["sale_date"].dt.date >= date_range.start_date]
    if date_range and date_range.end_date:
        df = df[df["sale_date"].dt.date <= date_range.end_date]
    return df.sort_values("sale_date")


def _group_sales(df: pd.DataFrame, freq: str) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["period", "units", "revenue"])

    grouped = (
        df.set_index("sale_date")
        .resample(freq)
        .agg(units=("quantity", "sum"), revenue=("revenue", "sum"))
        .reset_index()
        .rename(columns={"sale_date": "period"})
    )
    grouped["units"] = grouped["units"].astype(int)
    grouped["revenue"] = grouped["revenue"].round(2)
    return grouped


def daily_sales_aggregation(df: pd.DataFrame) -> list[dict]:
    daily = _group_sales(df, "D")
    if daily.empty:
        return []
    daily["ma_7"] = daily["revenue"].rolling(window=7, min_periods=1).mean().round(2)
    daily["ma_30"] = daily["revenue"].rolling(window=30, min_periods=1).mean().round(2)
    return [
        {
            "date": row.period.strftime("%Y-%m-%d"),
            "units": int(row.units),
            "revenue": float(row.revenue),
            "ma_7": float(row.ma_7),
            "ma_30": float(row.ma_30),
        }
        for row in daily.itertuples(index=False)
    ]


def weekly_sales_aggregation(df: pd.DataFrame) -> list[dict]:
    weekly = _group_sales(df, "W-MON")
    return [
        {
            "week_start": row.period.strftime("%Y-%m-%d"),
            "units": int(row.units),
            "revenue": float(row.revenue),
        }
        for row in weekly.itertuples(index=False)
    ]


def monthly_sales_aggregation(df: pd.DataFrame) -> list[dict]:
    monthly = _group_sales(df, "MS")
    return [
        {
            "month": row.period.strftime("%Y-%m"),
            "units": int(row.units),
            "revenue": float(row.revenue),
        }
        for row in monthly.itertuples(index=False)
    ]


def product_sales_trends(df: pd.DataFrame, limit: int = 5) -> list[dict]:
    if df.empty:
        return []
    top_products = (
        df.groupby(["product_id", "product_name"], as_index=False)["quantity"].sum().sort_values("quantity", ascending=False).head(limit)
    )
    return [
        {
            "product_id": int(row.product_id),
            "product_name": row.product_name,
            "units": int(row.quantity),
        }
        for row in top_products.itertuples(index=False)
    ]


def top_selling_products(df: pd.DataFrame, limit: int = 5) -> list[dict]:
    return product_sales_trends(df, limit=limit)


def slow_moving_products(df: pd.DataFrame, threshold_units: int = 5) -> list[dict]:
    products = db.session.execute(db.select(Product.id, Product.product_name)).all()
    if not products:
        return []

    totals = df.groupby("product_id", as_index=False)["quantity"].sum() if not df.empty else pd.DataFrame(columns=["product_id", "quantity"])
    totals = totals.rename(columns={"quantity": "units"})
    product_df = pd.DataFrame([{"product_id": p.id, "product_name": p.product_name} for p in products])
    merged = product_df.merge(totals, on="product_id", how="left").fillna({"units": 0})
    slow = merged[merged["units"] <= threshold_units].sort_values(["units", "product_name"])
    return [
        {"product_id": int(row.product_id), "product_name": row.product_name, "units": int(row.units)}
        for row in slow.itertuples(index=False)
    ]


def revenue_trends(df: pd.DataFrame) -> list[dict]:
    return monthly_sales_aggregation(df)


def category_performance(df: pd.DataFrame) -> list[dict]:
    if df.empty:
        return []
    grouped = (
        df.groupby("category", as_index=False)
        .agg(units=("quantity", "sum"), revenue=("revenue", "sum"))
        .sort_values("revenue", ascending=False)
    )
    return [
        {
            "category": row.category,
            "units": int(row.units),
            "revenue": float(round(row.revenue, 2)),
        }
        for row in grouped.itertuples(index=False)
    ]


def inventory_distribution() -> list[dict]:
    products = db.session.execute(db.select(Product.id, Product.current_stock, Product.reorder_level)).all()
    counts = {"In stock": 0, "Low stock": 0, "Out of stock": 0}
    for product in products:
        stock = int(product.current_stock or 0)
        reorder = int(product.reorder_level or 0)
        if stock <= 0:
            counts["Out of stock"] += 1
        elif stock <= reorder:
            counts["Low stock"] += 1
        else:
            counts["In stock"] += 1
    return [{"status": key, "count": value} for key, value in counts.items()]


def analytics_summary(df: pd.DataFrame) -> dict:
    total_revenue = float(df["revenue"].sum()) if not df.empty else 0.0
    units_sold = int(df["quantity"].sum()) if not df.empty else 0
    avg_order_value = round(total_revenue / len(df), 2) if len(df) else 0.0
    top_products = top_selling_products(df, limit=1)
    slow_products = slow_moving_products(df)
    active_products = db.session.scalar(db.select(func.count(Product.id)).where(Product.current_stock > 0)) or 0

    return {
        "total_revenue": round(total_revenue, 2),
        "units_sold": units_sold,
        "average_order_value": avg_order_value,
        "best_selling_product": top_products[0]["product_name"] if top_products else "N/A",
        "slow_moving_product_count": len(slow_products),
        "active_product_count": int(active_products),
    }


def build_analytics_context(date_range: DateRange | None = None) -> dict:
    sales_df = get_sales_dataframe(date_range)
    return {
        "summary": analytics_summary(sales_df),
        "daily_sales": daily_sales_aggregation(sales_df),
        "weekly_sales": weekly_sales_aggregation(sales_df),
        "monthly_sales": monthly_sales_aggregation(sales_df),
        "product_trends": product_sales_trends(sales_df),
        "top_products": top_selling_products(sales_df),
        "slow_products": slow_moving_products(sales_df),
        "revenue_trends": revenue_trends(sales_df),
        "category_performance": category_performance(sales_df),
        "inventory_distribution": inventory_distribution(),
    }
