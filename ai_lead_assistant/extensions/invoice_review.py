"""Current-invoice line exception review for a saved Purchase Invoice.

Public entry point: analyze(doc, query=None) -> dict (plain text only).

Scope: ONLY this invoice and the PO / PR rows its lines explicitly reference.
No other invoices, returns or child tables are read or queried, and over-billing
tolerances are not applied. Nothing is guessed: a check runs only when both sides
carry the needed values. A clean result means "no exception found by these checks".
"""

from ai_lead_assistant.extensions.insight_access import readable_doc

MAX_LINES = 200
MAX_LINKED_DOCS = 25
MAX_FINDINGS = 15
QTY_EPS = 1e-6

REFS = (  # (label, doctype, parent field, row field)
	("PO", "Purchase Order", "purchase_order", "po_detail"),
	("PR", "Purchase Receipt", "purchase_receipt", "pr_detail"),
)

SCOPE = (
	"This review compares this invoice with its explicitly linked source rows. "
	"Prior billings, subsequent returns, taxes and supplier billing tolerances are outside this comparison."
)


def analyze(doc, query=None):
	if doc.doctype != "Purchase Invoice" or doc.is_new() or not doc.name:
		return _out("Save the Purchase Invoice first; this review needs a saved invoice.", [], SCOPE)
	if doc.docstatus == 2:
		return _out(f"{doc.name} is cancelled; no review performed.", [], SCOPE)
	r = _Review(doc)
	r.run()
	return r.result(query)


def _out(summary, findings, note):
	return {"summary": summary, "findings": findings, "note": note}


class _Review:
	def __init__(self, doc):
		self.doc = doc
		self.is_return = bool(doc.get("is_return"))
		items = list(doc.get("items") or [])
		self.lines = items[:MAX_LINES]
		self.lines_cut = len(items) - len(self.lines)
		self.cache = {}  # (doctype, name) -> doc or None; each linked doc is read once
		self.docs_skipped = set()
		self.issues = []
		self.no_ref = self.po_only = self.pr_only = 0
		self.price_skipped = self.qty_skipped = self.hidden = 0
		self.checked = 0

	def add(self, title, detail, doctype=None, name=None):
		item = {"title": title, "detail": detail, "level": "warning"}
		if doctype and name:
			item["doctype"], item["name"] = doctype, name
		self.issues.append(item)

	def load(self, doctype, name):
		key = (doctype, name)
		if key in self.cache:
			return self.cache[key]
		if len(self.cache) >= MAX_LINKED_DOCS:
			self.docs_skipped.add(key)
			return "skipped"
		self.cache[key] = readable_doc(doctype, name)
		return self.cache[key]

	def run(self):
		groups = {}  # (label, doctype, parent, detail) -> [lines]
		for l in self.lines:
			has = {}
			for label, dt, pf, df in REFS:
				p, d = l.get(pf), l.get(df)
				has[label] = bool(p or d)
				if p and d:
					groups.setdefault((label, dt, p, d), []).append(l)
				elif p or d:
					self.add(
						f"{label} reference incomplete (row {l.idx})",
						f"{pf}={p or 'empty'}, {df}={d or 'empty'}; cannot be matched to a source row.",
					)
			if not has["PO"] and not has["PR"]:
				self.no_ref += 1
			elif has["PO"] and not has["PR"]:
				self.po_only += 1
			elif has["PR"] and not has["PO"]:
				self.pr_only += 1
		for key, lines in groups.items():
			self.review(key, lines)

	def review(self, key, lines):
		label, dt, pname, detail = key
		rows = ", ".join(str(l.idx) for l in lines)
		parent = self.load(dt, pname)
		if parent == "skipped":
			return
		if parent is None:
			self.add(
				f"{label} {pname} not readable",
				f"Rows {rows}: the linked record could not be opened with your permissions.",
			)
			return
		ref = next((r for r in (parent.get("items") or []) if r.name == detail), None)
		if ref is None:
			self.add(
				f"{label} row not found",
				f"Rows {rows} cite row {detail}, absent from {pname} (or hidden by permissions).",
				dt,
				pname,
			)
			return
		d, bad = self.doc, []

		if parent.get("docstatus") != 1:
			state = {0: "draft", 2: "cancelled"}.get(parent.get("docstatus"), "not submitted")
			self.add(
				f"{label} source is {state}",
				f"Rows {rows} refer to {pname}. Check the document status before comparing quantities.",
				dt,
				pname,
			)
			return
		self.checked += 1
		for f in ("company", "supplier"):
			a, b = d.get(f), parent.get(f)
			if a and b and a != b:
				bad.append(f"{f} {a} on invoice vs {b} on source")
			elif not (a and b):
				self.hidden += 1
		if (
			label == "PR"
			and parent.get("is_return") is not None
			and bool(parent.get("is_return")) != self.is_return
		):
			bad.append(f"return flag: invoice {self.is_return}, receipt {bool(parent.get('is_return'))}")
		if label == "PR" and d.get("update_stock"):
			bad.append(
				"Update Stock is on while billing a Purchase Receipt; stock effect is not evaluated "
				"here, please verify manually"
			)

		same_cur = bool(d.get("currency")) and d.get("currency") == parent.get("currency")
		ref_q, ref_u = norm_qty(ref), ref.get("stock_uom")
		comparable = not self.is_return and ref_q and ref_q > 0 and ref_u
		mine = 0.0
		for line in lines:
			keys_match = True
			for field, title in (("item_code", "item"), ("stock_uom", "stock unit")):
				left, right = line.get(field), ref.get(field)
				if not left or not right:
					self.hidden += 1
					keys_match = False
				elif left != right:
					bad.append(f"row {line.idx}: {title} {left} on invoice, {right} on source")
					keys_match = False
			q = norm_qty(line)
			if not keys_match or q is None or q <= 0:
				comparable = False
			else:
				mine += q
			self.price_check(line, ref, same_cur and keys_match, bad)
		if comparable:
			if mine > ref_q + QTY_EPS:
				bad.append(
					"this invoice alone bills more than the source row: "
					+ "; ".join(f"row {l.idx} {fmt_qty(l)}" for l in lines)
					+ f" = {mine:g} {ref_u} vs source {fmt_qty(ref)}"
				)
		else:
			self.qty_skipped += 1
		if bad:
			self.add(f"{label} exception on {pname}", f"Rows {rows}: " + "; ".join(bad) + ".", dt, pname)

	def price_check(self, l, ref, same_cur, bad):
		if not same_cur:
			self.price_skipped += 1
			return
		a, b = unit_price(l), unit_price(ref)
		if a is None or b is None:
			self.price_skipped += 1
		elif (
			abs(a - b)
			> max(
				0.5 * 10 ** -l.precision("rate") / l.conversion_factor,
				0.5 * 10 ** -ref.precision("rate") / ref.conversion_factor,
			)
			+ 1e-12
		):
			bad.append(
				f"row {l.idx} unit price {a:.6g} vs source {b:.6g} {self.doc.currency}/{ref.stock_uom} "
				f"(invoice rate {l.get('rate')} per {l.get('uom') or '?'})"
			)

	def result(self, query):
		n, shown = len(self.issues), self.issues[:MAX_FINDINGS]
		if n > MAX_FINDINGS:
			shown = shown[: MAX_FINDINGS - 1] + [
				{
					"title": f"{n - MAX_FINDINGS + 1} more finding(s) omitted",
					"detail": "Output is capped.",
					"level": "info",
				}
			]
		lines = "line" if len(self.lines) == 1 else "lines"
		rows = "row" if self.checked == 1 else "rows"
		summary = f"Reviewed {len(self.lines)} invoice {lines} against {self.checked} linked order or receipt {rows}."
		if n:
			summary += f" Findings to review: {n}."
		if self.no_ref or self.po_only or self.pr_only:
			shown.append(
				{
					"title": "Link coverage",
					"level": "info",
					"detail": (
						f"Without order or receipt links: {self.no_ref}. Order only: {self.po_only}. "
						f"Receipt only: {self.pr_only}. Unlinked quantities cannot be compared."
					),
				}
			)
		if self.checked and not any(
			(n, self.qty_skipped, self.price_skipped, self.hidden, self.docs_skipped, self.lines_cut)
		):
			shown.append(
				{
					"title": "No variance on the compared rows",
					"level": "success",
					"detail": "Billed quantities fit within the linked rows and comparable unit prices agree.",
				}
			)
		notes = [SCOPE]
		if self.is_return:
			notes.append("Return invoice: quantity comparison not performed (negative quantities).")
		if self.qty_skipped:
			notes.append(
				f"{self.qty_skipped} source group(s) not quantity-compared (incompatible UOM/item, "
				"non-positive or missing quantity); no arithmetic was done on them."
			)
		if self.price_skipped:
			notes.append(
				f"{self.price_skipped} line(s) not price-compared (different/unknown currency, UOM or values)."
			)
		if self.hidden:
			notes.append(
				f"{self.hidden} comparison(s) skipped because a field was empty or hidden by permissions."
			)
		if self.lines_cut:
			notes.append(f"{self.lines_cut} line(s) beyond the {MAX_LINES}-line cap were not reviewed.")
		if self.docs_skipped:
			notes.append(
				f"{len(self.docs_skipped)} linked document(s) beyond the {MAX_LINKED_DOCS}-document cap were not opened."
			)
		return _out(summary, shown, " ".join(notes))


def norm_qty(row):
	"""Quantity in stock UOM: stock_qty, else qty * conversion_factor."""
	q = row.get("stock_qty")
	if q is None and row.get("qty") is not None and row.get("conversion_factor"):
		q = row.qty * row.conversion_factor
	return q


def unit_price(row):
	"""Price per stock UOM in document currency."""
	rate, cf = row.get("rate"), row.get("conversion_factor")
	return rate / cf if rate is not None and cf and cf > 0 else None


def fmt_qty(row):
	"""Show actual entered quantity/UOM and the stock-UOM equivalent."""
	q = norm_qty(row)
	return (
		f"{row.get('qty'):g} {row.get('uom') or '?'} ({q:g} {row.get('stock_uom') or '?'})"
		if row.get("qty") is not None and q is not None
		else "quantity unavailable"
	)
