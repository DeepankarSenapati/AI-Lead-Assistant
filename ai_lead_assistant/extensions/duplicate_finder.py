"""Duplicate finder for Lead, Customer, Supplier and Item (Frappe v15).

Suggests possible duplicates inside one DocType using exact identifiers (email,
phone, tax id, part codes) and local fuzzy name matching (stdlib only).

`doc` may be a fresh frappe._dict(doctype=...), so only doc.get() is used and
permissions come from meta, never from Document methods. Only fields the user
may read are queried, compared and shown; records come from frappe.get_list.
Nothing is merged or changed: results are suggestions to review.
"""

import re
import unicodedata
from difflib import SequenceMatcher

import frappe

FETCH_LIMIT = 100  # rows per query
MAX_FINDINGS = 10
MAX_QUERY_LEN = 140
MAX_TOKENS = 3  # distinctive words used to pull candidates per name field
WARN_SCORE = 0.92
INFO_SCORE = 0.80

CONFIG = {
	"Lead": {
		"names": ["lead_name", "company_name"],
		"ids": {"email_id": "email", "mobile_no": "phone", "phone": "phone", "whatsapp_no": "phone"},
	},
	"Customer": {
		"names": ["customer_name"],
		"ids": {"tax_id": "code", "email_id": "email", "mobile_no": "phone"},
	},
	"Supplier": {
		"names": ["supplier_name"],
		"ids": {"tax_id": "code", "email_id": "email", "mobile_no": "phone"},
	},
	"Item": {
		"names": ["item_name"],
		"ids": {"item_code": "code", "default_manufacturer_part_no": "code", "customer_code": "code"},
	},
}

GENERIC_WORDS = set(
	"""a an and the of for co company corp corporation inc incorporated ltd limited llc llp lp plc pvt private
	public gmbh ag sa sarl srl spa bv nv oy ab as pte sdn bhd pty kg ug eg group holding holdings trading trade
	traders enterprise enterprises industries industry international global services service solutions systems
	technologies technology sales supply supplies agency associates sons brothers bros mr mrs ms dr new old
	general standard item product products part parts spare spares material materials set kit pcs nos unit
	units piece pieces pack box""".split()
)
PLACEHOLDERS = {"NA", "NONE", "NULL", "NIL", "TBD", "UNKNOWN", "TEST", "DEFAULT"}


# ---------------------------------------------------------------- normalising


def _fold(text):
	"""Case/accent-insensitive words: 'Café  Müller & Co.' -> 'cafe muller and co'."""
	text = unicodedata.normalize("NFKD", str(text or "").replace("&", " and "))
	text = "".join(c for c in text if not unicodedata.combining(c)).casefold()
	return " ".join(re.sub(r"[\W_]+", " ", text).split())


def _wide(tok):
	return any(ord(c) >= 0x2E80 for c in tok)  # CJK/kana/hangul: short words are meaningful


def _words(text):
	"""Distinctive words only: drops generic words, 1-2 letter words and weak numbers (<3 digits)."""
	out = []
	for tok in _fold(text).split():
		if tok in GENERIC_WORDS or (len(tok) < 3 and not (_wide(tok) and len(tok) >= 2)):
			continue
		if tok.isdigit() and len(tok) < 4:
			continue
		out.append(tok)
	return list(dict.fromkeys(out))


def _numbers(text):
	return {t for t in _fold(text).split() if any(c.isdigit() for c in t)}


def _key(kind, raw):
	"""Canonical key of an identifier, or None when empty, malformed or placeholder."""
	raw = str(raw or "").strip()
	if kind == "email":
		raw = raw.casefold()
		return raw if re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", raw) else None
	if kind == "phone":
		digits = "".join(c for c in raw if c.isdigit())
		return digits if len(digits) >= 7 and len(set(digits)) > 1 else None
	key = "".join(c for c in raw if c.isalnum()).upper()
	return key if len(key) >= 4 and key not in PLACEHOLDERS and len(set(key)) > 1 else None


def _query_kinds(query):
	"""Identifier kinds a free-text query could be, and whether it may also be a name."""
	if "@" in query and " " not in query:
		return {"email"}, False
	if re.fullmatch(r"[\d\s+\-().]+", query):
		return {"phone", "code"}, False
	if " " not in query and any(c.isdigit() for c in query):
		return {"code"}, True
	return ({"code"} if " " not in query else set()), True


# ------------------------------------------------------------------- matching


def _name_match(own, other):
	"""Return (score, shared words); score 0 means not a plausible duplicate."""
	a, b = _words(own), _words(other)
	if not a or not b or _numbers(own) != _numbers(other):  # "Plant 1" != "Plant 2"
		return 0.0, []
	shared, total = [], 0.0
	for tok in a:
		best = max(b, key=lambda o: SequenceMatcher(None, tok, o).ratio())
		sim = 1.0 if tok == best else (SequenceMatcher(None, tok, best).ratio() if min(len(tok), len(best)) >= 4 else 0.0)
		if sim >= 0.85:
			shared.append(tok if tok == best else f"{tok}~{best}")
			total += sim
	if not shared:
		return 0.0, []
	score = max(total / max(len(a), len(b)), SequenceMatcher(None, " ".join(sorted(a)), " ".join(sorted(b))).ratio())
	# A single distinctive word is weak evidence: demand near-identity.
	return (score, shared) if score >= (WARN_SCORE if min(len(a), len(b)) == 1 else INFO_SCORE) else (0.0, [])


def _readable(meta, fieldnames):
	"""Fields that exist, are visible, are not passwords and are readable at the user's permlevels."""
	permitted = set(meta.get_permitted_fieldnames())
	return [
		f
		for f in fieldnames
		if (df := meta.get_field(f)) and not df.hidden and df.fieldtype != "Password" and f in permitted
	]


def _id_filters(field, kind, raw, key):
	"""Retrieve formatted identifiers; full canonical equality is checked after lookup."""
	filters = [[field, "=", raw]]
	if kind in ("phone", "code") and 4 <= len(key) <= 32:
		filters.append([field, "like", "%" + "%".join(key) + "%"])
	return filters


# ----------------------------------------------------------------------- main


def analyze(doc, query=None):
	doctype = doc.get("doctype")
	cfg = CONFIG.get(doctype)
	if not cfg:
		return {"summary": "Duplicate finder supports Lead, Customer, Supplier and Item only.", "findings": []}

	if not frappe.has_permission(doctype, "read"):
		return {"summary": "You need read access to search these records.", "findings": []}
	meta = frappe.get_meta(doctype)
	query = " ".join(str(query or "").split())[:MAX_QUERY_LEN]
	name_fields = _readable(meta, cfg["names"])
	id_fields = _readable(meta, list(cfg["ids"]))
	notes = []
	# What are we looking for?
	own_names, own_ids = {}, {}  # field -> text ; (kind, key) -> raw value
	if query:
		kinds, may_be_name = _query_kinds(query)
		own_names = {f: query for f in name_fields} if may_be_name else {}
		for f in id_fields:
			if cfg["ids"][f] in kinds and (k := _key(cfg["ids"][f], query)):
				own_ids[(f, k)] = query
	else:
		own_names = {f: str(doc.get(f)) for f in name_fields if doc.get(f)}
		for f in id_fields:
			if k := _key(cfg["ids"][f], doc.get(f)):
				own_ids[(f, k)] = str(doc.get(f)).strip()
	own_names = {f: v for f, v in own_names.items() if _words(v)}

	if not own_names and not own_ids:
		return {
			"summary": (
				"Nothing usable to compare. Generic words, legal suffixes, 1-2 letter words, short numbers "
				"and placeholder codes are ignored; enter a fuller name, email, phone or code."
			),
			"findings": [],
			"note": " ".join(notes) or None,
		}

	# Candidates: only permitted fields are queried or fetched.
	fields = ["name"] + name_fields + id_fields
	if meta.has_field("disabled") and _readable(meta, ["disabled"]):
		fields.append("disabled")
	or_filters = [f for (field, key), raw in own_ids.items() for f in _id_filters(field, cfg["ids"][field], raw, key)]
	for field, text in own_names.items():
		for tok in sorted(_words(text), key=len, reverse=True)[:MAX_TOKENS]:
			or_filters.append([field, "like", f"%{tok[:2] if _wide(tok) else tok[:4]}%"])
	filters = [["name", "!=", doc.get("name")]] if doc.get("name") else []

	try:
		rows, truncated = {}, False
		for order in ("modified desc", "creation asc"):  # newest and oldest, not just recent
			found = frappe.get_list(
				doctype, fields=fields, filters=filters, or_filters=or_filters, order_by=order, limit_page_length=FETCH_LIMIT
			)
			truncated = truncated or len(found) >= FETCH_LIMIT
			rows.update({r["name"]: r for r in found})
	except frappe.PermissionError:
		return {"summary": f"You do not have permission to list {doctype} records.", "findings": []}

	# Score candidates.
	matches = []
	for row in rows.values():
		id_hits = {meta.get_label(f) or f for (f, k) in own_ids if _key(cfg["ids"][f], row.get(f)) == k}
		name_hits = []
		for f, text in own_names.items():
			score, shared = _name_match(text, row.get(f))
			if score:
				name_hits.append((meta.get_label(f) or f, score, shared, row.get(f)))
		if id_hits or name_hits:
			matches.append((row, sorted(id_hits), name_hits, max((h[1] for h in name_hits), default=0.0)))
	matches.sort(key=lambda m: (bool(m[1]), m[3]), reverse=True)

	findings = []
	for row, id_hits, name_hits, best in matches[:MAX_FINDINGS]:
		parts = []
		if id_hits:
			parts.append(f"Matching identifier: {', '.join(id_hits)}.")
		for label, score, shared, other in name_hits:
			parts.append(f"{label} '{other}' is {round(score * 100)}% similar (shared: {', '.join(shared)}).")
		if row.get("disabled"):
			parts.append("This record is disabled.")
		if doctype == "Item" and id_hits:
			parts.append("Variants may legitimately share codes; check before acting.")
		display = next((row.get(f) for f in name_fields if row.get(f)), None) or row["name"]
		findings.append(
			{
				"title": f"Possible duplicate: {display}"[:140],
				"detail": " ".join(parts),
				"doctype": doctype,
				"name": row["name"],
				"level": "warning" if id_hits or best >= WARN_SCORE else "info",
			}
		)

	notes.append(f"Compared {len(rows)} readable {doctype} records; records you cannot read are not checked.")
	if truncated:
		notes.append(f"A search hit the {FETCH_LIMIT}-row limit, so further matches may exist.")
	if len(matches) > MAX_FINDINGS:
		notes.append(f"Showing the best {MAX_FINDINGS} of {len(matches)} matches.")
	notes.append("Candidates are found by exact identifiers and the first letters of distinctive words, so other spellings can be missed.")

	summary = (
		f"{len(matches)} possible duplicate{'s' if len(matches) != 1 else ''} found; please review."
		if findings
		else f"No likely duplicates found among the {doctype} records you can read."
	)
	return {"summary": summary, "findings": findings, "note": " ".join(notes)}
