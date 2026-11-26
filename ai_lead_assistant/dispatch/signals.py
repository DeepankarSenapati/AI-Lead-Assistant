"""The V1 signal is a stock-item dispatch commitment, in the order row's UOM."""

from datetime import timedelta

from frappe.utils import flt, getdate

WINDOW = 7  # Includes the site-local observation date.
OVERDUE_DAYS = 30
ACTIVE_ORDER_STATES = ("To Deliver", "To Deliver and Bill")
FEATURE = "dispatch_watchlist"


def progress_band(ordered, delivered):
	if delivered <= 0:
		return "Unstarted"
	return "Below half" if delivered < ordered / 2 else "At least half"


def lines_for_order(doc, day, *, overdue=True):
	"""Input is a field-redacted order for Desk, or a complete order for the scheduler."""
	if (
		doc.docstatus != 1
		or doc.get("status") not in ACTIVE_ORDER_STATES
		or doc.get("skip_delivery_note") != 0
	):
		return []
	result = []
	for row in doc.get("items") or []:
		if row.get("is_stock_item") != 1 or row.get("delivered_by_supplier") != 0:
			continue
		if not all(
			row.get(k) for k in ("delivery_date", "item_code", "qty", "uom", "conversion_factor", "stock_uom")
		):
			continue
		if (
			row.get("delivered_qty") is None
			or row.qty <= 0
			or row.delivered_qty < 0
			or row.conversion_factor <= 0
		):
			continue
		due = getdate(row.delivery_date)
		days = (due - day).days
		precision = row.precision("qty")
		remaining = flt(row.qty - row.delivered_qty, precision)
		if remaining <= 0 or not (-(OVERDUE_DAYS if overdue else 0) <= days < WINDOW):
			continue
		priority = "Upcoming"
		if days < 0:
			priority = "Overdue"
		elif days == 0:
			priority = "Due today"
		elif days <= 2:
			priority = "Due soon"
		promise = f"{format_qty(remaining, precision)} {row.uom} remain of {format_qty(row.qty, precision)} ordered."
		unit = "day" if abs(days) == 1 else "days"
		if days < 0:
			reason = f"{promise} The dispatch promise was {abs(days)} calendar {unit} ago."
		elif days == 0:
			reason = f"{promise} The promised dispatch date is today."
		else:
			reason = f"{promise} The promised dispatch date is in {days} calendar {unit}."
		result.append(
			dict(
				order=doc.name,
				line=row.name,
				item=row.item_code,
				company=doc.get("company"),
				customer=doc.get("customer") or "",
				warehouse=row.get("warehouse") or "",
				uom=row.uom,
				qty=row.qty,
				delivered=row.delivered_qty,
				remaining=remaining,
				due_date=due.isoformat(),
				days=days,
				priority=priority,
				reason=reason,
				precision=precision,
				stock_uom=row.stock_uom,
				factor=row.conversion_factor,
				band=progress_band(row.qty, row.delivered_qty),
			)
		)
	return result


def rank(row):
	return (row["due_date"], row["order"], row["line"])


def format_qty(value, precision):
	number = f"{value:.{precision}f}"
	return number.rstrip("0").rstrip(".") if "." in number else number


def candidate_filters(day, *, overdue):
	return [
		["Sales Order", "docstatus", "=", 1],
		["Sales Order", "status", "in", ACTIVE_ORDER_STATES],
		["Sales Order", "skip_delivery_note", "=", 0],
		["Sales Order Item", "is_stock_item", "=", 1],
		["Sales Order Item", "delivered_by_supplier", "=", 0],
		["Sales Order Item", "qty", ">", 0],
		[
			"Sales Order Item",
			"delivery_date",
			"between",
			[day - timedelta(days=OVERDUE_DAYS if overdue else 0), day + timedelta(days=WINDOW - 1)],
		],
	]
