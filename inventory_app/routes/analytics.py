from __future__ import annotations

from datetime import date
from io import StringIO

import pandas as pd
from flask import Blueprint, Response, flash, jsonify, render_template, request

from inventory_app.routes.auth import login_required
from inventory_app.services.analytics import (
    DateRange,
    build_analytics_context,
    demand_forecast,
    get_sales_dataframe,
)

bp = Blueprint("analytics", __name__, url_prefix="/analytics")


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _extract_date_range() -> tuple[DateRange, str, str]:
    raw_start_date = request.args.get("start_date", "").strip()
    raw_end_date = request.args.get("end_date", "").strip()
    start_date = _parse_date(raw_start_date)
    end_date = _parse_date(raw_end_date)

    if raw_start_date and start_date is None:
        flash("Invalid start date format. Use YYYY-MM-DD.", "warning")
    if raw_end_date and end_date is None:
        flash("Invalid end date format. Use YYYY-MM-DD.", "warning")
    if start_date and end_date and start_date > end_date:
        flash("Start date was after end date; the dates were swapped.", "warning")
        start_date, end_date = end_date, start_date

    return DateRange(start_date=start_date, end_date=end_date), (start_date.isoformat() if start_date else ""), (
        end_date.isoformat() if end_date else ""
    )


@bp.get("")
@bp.get("/")
@login_required
def index():
    date_range, start_date, end_date = _extract_date_range()
    data = build_analytics_context(date_range)
    return render_template(
        "analytics/index.html",
        analytics=data,
        start_date=start_date,
        end_date=end_date,
    )


@bp.get("/export.csv")
@login_required
def export_csv():
    date_range, _, _ = _extract_date_range()
    df = get_sales_dataframe(date_range)

    csv_df = df[["sale_date", "product_name", "category", "quantity", "revenue"]].copy() if not df.empty else df
    if not csv_df.empty:
        csv_df["sale_date"] = csv_df["sale_date"].dt.strftime("%Y-%m-%d")

    def generate():
        buffer = StringIO()
        csv_df.to_csv(buffer, index=False)
        yield buffer.getvalue()

    return Response(
        generate(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=analytics.csv"},
    )


@bp.get("/forecast.csv")
@login_required
def export_forecast_csv():
    date_range, _, _ = _extract_date_range()
    forecast = demand_forecast(get_sales_dataframe(date_range))
    csv_df = pd.DataFrame(forecast["rows"])

    def generate():
        buffer = StringIO()
        if csv_df.empty:
            buffer.write("product_id,product_name,week_start,forecast_units,history_weeks,has_sales_history,backtest_mae\n")
        else:
            csv_df.to_csv(buffer, index=False)
        yield buffer.getvalue()

    return Response(
        generate(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=demand-forecast.csv"},
    )


@bp.get("/forecast.json")
@login_required
def forecast_json():
    date_range, _, _ = _extract_date_range()
    return jsonify(demand_forecast(get_sales_dataframe(date_range)))
