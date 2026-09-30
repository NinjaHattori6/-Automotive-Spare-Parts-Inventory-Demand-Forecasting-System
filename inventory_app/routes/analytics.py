from __future__ import annotations

from datetime import date
from io import StringIO

from flask import Blueprint, Response, render_template, request

from inventory_app.routes.auth import login_required
from inventory_app.services.analytics import DateRange, build_analytics_context, get_sales_dataframe

bp = Blueprint("analytics", __name__, url_prefix="/analytics")


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    return date.fromisoformat(value)


@bp.get("")
@bp.get("/")
@login_required
def index():
    start_date = _parse_date(request.args.get("start_date"))
    end_date = _parse_date(request.args.get("end_date"))
    data = build_analytics_context(DateRange(start_date=start_date, end_date=end_date))
    return render_template(
        "analytics/index.html",
        analytics=data,
        start_date=start_date.isoformat() if start_date else "",
        end_date=end_date.isoformat() if end_date else "",
    )


@bp.get("/export.csv")
@login_required
def export_csv():
    start_date = _parse_date(request.args.get("start_date"))
    end_date = _parse_date(request.args.get("end_date"))
    df = get_sales_dataframe(DateRange(start_date=start_date, end_date=end_date))

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
