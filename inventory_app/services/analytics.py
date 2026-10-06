from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import pandas as pd
from sqlalchemy import func

from inventory_app.extensions import db
from inventory_app.models import Product, Sale

FORECAST_HORIZON_WEEKS = 4
FORECAST_SEASONAL_PERIOD_WEEKS = 4


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


def _week_start_series(sale_dates: pd.Series) -> pd.Series:
    normalized = sale_dates.dt.tz_convert("UTC").dt.floor("D")
    return normalized - pd.to_timedelta(normalized.dt.weekday, unit="D")


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


def _seasonal_naive_forecast(history_values: list[float], horizon_weeks: int, seasonal_period_weeks: int) -> list[float]:
    history = [max(float(value), 0.0) for value in history_values]
    if not history:
        return [0.0 for _ in range(horizon_weeks)]

    forecasts: list[float] = []
    for _ in range(horizon_weeks):
        if len(history) >= seasonal_period_weeks:
            next_value = history[-seasonal_period_weeks]
        else:
            next_value = sum(history) / len(history)
        next_value = max(next_value, 0.0)
        forecasts.append(next_value)
        history.append(next_value)
    return forecasts


def _seasonal_naive_mae(history_values: list[float], seasonal_period_weeks: int) -> float | None:
    if len(history_values) <= seasonal_period_weeks:
        return None
    errors = [
        abs(float(history_values[index]) - float(history_values[index - seasonal_period_weeks]))
        for index in range(seasonal_period_weeks, len(history_values))
    ]
    if not errors:
        return None
    return round(sum(errors) / len(errors), 2)


def demand_forecast(
    df: pd.DataFrame,
    horizon_weeks: int = FORECAST_HORIZON_WEEKS,
    seasonal_period_weeks: int = FORECAST_SEASONAL_PERIOD_WEEKS,
) -> dict:
    products = db.session.execute(db.select(Product.id, Product.product_name).order_by(Product.product_name.asc())).all()
    generated_at = pd.Timestamp.now(tz="UTC")
    current_week_start = generated_at.normalize() - pd.to_timedelta(generated_at.weekday(), unit="D")

    if df.empty:
        weekly = pd.DataFrame(columns=["product_id", "week_start", "units"])
    else:
        weekly = (
            df.assign(week_start=_week_start_series(df["sale_date"]))
            .groupby(["product_id", "week_start"], as_index=False)["quantity"]
            .sum()
            .rename(columns={"quantity": "units"})
        )

    forecast_products = []
    forecast_rows = []
    for product in products:
        product_weeks = weekly[weekly["product_id"] == product.id].sort_values("week_start")
        if product_weeks.empty:
            history = pd.Series(dtype=float)
            last_observed_week = None
        else:
            product_series = product_weeks.set_index("week_start")["units"].astype(float)
            full_index = pd.date_range(
                start=product_series.index.min(),
                end=product_series.index.max(),
                freq="W-MON",
            )
            history = product_series.reindex(full_index, fill_value=0.0)
            last_observed_week = history.index.max()

        anchor_week = max(current_week_start, last_observed_week) if last_observed_week is not None else current_week_start
        future_weeks = [anchor_week + pd.DateOffset(weeks=step) for step in range(1, horizon_weeks + 1)]
        history_values = history.tolist()
        forecast_values = _seasonal_naive_forecast(history_values, horizon_weeks, seasonal_period_weeks)
        backtest_mae = _seasonal_naive_mae(history_values, seasonal_period_weeks)

        week_rows = []
        for week_start, forecast_value in zip(future_weeks, forecast_values):
            row = {
                "product_id": int(product.id),
                "product_name": product.product_name,
                "week_start": week_start.strftime("%Y-%m-%d"),
                "forecast_units": int(round(forecast_value)),
                "history_weeks": int(len(history_values)),
                "has_sales_history": bool(history_values),
                "backtest_mae": backtest_mae,
            }
            week_rows.append(row)
            forecast_rows.append(row)

        forecast_products.append(
            {
                "product_id": int(product.id),
                "product_name": product.product_name,
                "history_weeks": int(len(history_values)),
                "has_sales_history": bool(history_values),
                "backtest_mae": backtest_mae,
                "total_forecast_units": int(sum(row["forecast_units"] for row in week_rows)),
                "weeks": week_rows,
            }
        )

    return {
        "model_name": "Seasonal-naive weekly baseline",
        "horizon_weeks": int(horizon_weeks),
        "seasonal_period_weeks": int(seasonal_period_weeks),
        "generated_at": generated_at.isoformat(),
        "limitations": [
            "Baseline forecast intended for sparse transactional data; it does not learn causal drivers.",
            "Products without sales history forecast zero demand until transactions are recorded.",
            "Use this as an operational planning baseline and recalibrate with domain events.",
        ],
        "products": forecast_products,
        "rows": forecast_rows,
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
        "forecast": demand_forecast(sales_df),
    }
