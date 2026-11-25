"""Similar resolved/closed Issues for support agents (Frappe v15).

Local BM25 retrieval over Issue subject, description and resolution details.
Candidates come from frappe.get_list only (role/user permissions apply), and every
selected, filtered or sorted field is also checked against the permitted fieldnames.
"""

import math
import re
from collections import Counter

import frappe

from ai_lead_assistant.extensions.insight_access import plain_text

DONE_STATUSES = ["Resolved", "Closed"]
TEXT_FIELDS = ("subject", "description", "resolution_details")
BASE_FIELDS = ("name", "subject", "description", "resolution_details", "status", "modified")
MAX_QUERY_CHARS = 3000
TERM_CANDIDATE_LIMIT = 120
RECENT_LIMIT = 40
MAX_LIKE_TERMS = 8
MAX_RESULTS = 5
MAX_SHOWN_TERMS = 5
EXCERPT_CHARS = 400
WEIGHTS = {"subject": 3.0, "description": 1.0, "resolution_details": 0.7}
K1, B, ID_BOOST = 1.5, 0.75, 1.5

STOPWORDS = frozenset(
	"""
a about after again all also am an and any are as at be been before but by can cannot could did do does
doing done for from get got had has have having he her here how i if in into is it its just may me more
my no not of off on once only or our out over please same she should so some such than that the their
them then there these they this those to too under until up us was we were what when where which while
who why will with would you your hi hello thanks thank regards dear issue issues ticket support team
error errors problem problems fail failed failing failure unable cannot working work help need urgent
""".split()
)

TOKEN_RE = re.compile(r"\w+(?:[.\-/:@]\w+)*")
SPLIT_RE = re.compile(r"[\W_]+")
LIKE_SAFE_RE = re.compile(r"^\w[\w.\-]*$")


def stem(word):
	"""Light suffix normalisation for ASCII words (not a full stemmer)."""
	if not word.isascii() or word.endswith("ss"):
		return word
	for suffix, repl, min_len in (
		("ies", "y", 5),
		("ing", "", 6),
		("ed", "", 5),
		("es", "", 5),
		("s", "", 4),
	):
		if word.endswith(suffix) and len(word) >= min_len:
			return word[: -len(suffix)] + repl
	return word


def tokenize(text):
	"""Return (term, surface, is_identifier) tuples.

	Identifiers such as ERR-4021, app.py, 10.0.0.1, a@b.com or snake_case are kept
	whole and also split into parts; stopwords and bare short numbers are dropped.
	"""
	out = []
	for raw in TOKEN_RE.findall(text or ""):
		low = raw.lower()
		parts = [p for p in SPLIT_RE.split(low) if p]
		has_digit = any(c.isdigit() for c in low)
		if len(low) > 2 and not low.isdigit() and (has_digit or "_" in low or len(parts) > 1):
			out.append((low, low, True))
		for part in parts:
			if part in STOPWORDS or len(part) < 2 or (part.isdigit() and len(part) < 3):
				continue
			out.append((stem(part), part, False))
	return out


def _source_text(doc, query):
	if isinstance(query, str) and query.strip():
		return query.strip()[:MAX_QUERY_CHARS], "your search text"
	text = f"{plain_text(doc.get('subject'), 500)} {plain_text(doc.get('description'), MAX_QUERY_CHARS)}"
	return text.strip()[:MAX_QUERY_CHARS], "this Issue's subject and description"


def _fetch_candidates(query_terms, exclude, allowed):
	"""Distinctive-term matches plus a recent baseline, using permitted fields only."""
	fields = [f for f in BASE_FIELDS if f in allowed]
	filters = [["Issue", "status", "in", DONE_STATUSES]]
	if exclude:
		filters.append(["Issue", "name", "!=", exclude])

	like_terms = sorted(
		{s for _, s, _ in query_terms if len(s) >= 3 and "_" not in s and LIKE_SAFE_RE.match(s)},
		key=lambda s: (not any(c.isdigit() for c in s), -len(s), s),
	)[:MAX_LIKE_TERMS]
	searchable = [f for f in TEXT_FIELDS if f in allowed]

	pool, truncated = {}, False
	if like_terms and searchable:
		or_filters = [["Issue", f, "like", f"%{t}%"] for t in like_terms for f in searchable]
		rows = frappe.get_list(
			"Issue",
			fields=fields,
			filters=filters,
			or_filters=or_filters,
			order_by="modified desc",
			limit_page_length=TERM_CANDIDATE_LIMIT,
		)
		truncated = len(rows) >= TERM_CANDIDATE_LIMIT
		pool.update({r["name"]: r for r in rows})
	recent = frappe.get_list(
		"Issue",
		fields=fields,
		filters=filters,
		order_by="modified desc",
		limit_page_length=RECENT_LIMIT,
	)
	pool.update({r["name"]: r for r in recent})
	return list(pool.values()), {row["name"] for row in recent}, truncated


def _rank(rows, query_terms, baseline_names):
	"""Weight terms by frequency in recent cases sampled independently of the query."""
	q_tf = Counter(t for t, _, _ in query_terms)
	surface = {t: s for t, s, _ in query_terms}
	ids = {t for t, _, ident in query_terms if ident}

	docs = []
	for row in rows:
		tf, where = Counter(), {}
		for field, weight in WEIGHTS.items():
			for term, _, _ in tokenize(plain_text(row.get(field), 500 if field == "subject" else 2400)):
				tf[term] += weight
				where.setdefault(term, set()).add(field)
		docs.append((row, tf, sum(tf.values()), where))
	if not docs:
		return []

	baseline = [d for d in docs if d[0]["name"] in baseline_names] or docs
	n = len(baseline)
	avg_len = sum(d[2] for d in baseline) / n or 1.0
	df = Counter(t for _, tf, _, _ in baseline for t in q_tf if t in tf)

	ranked = []
	for row, tf, length, where in docs:
		score, matched = 0.0, []
		for term, qn in q_tf.items():
			f = tf.get(term)
			if not f:
				continue
			idf = math.log(1 + (n - df[term] + 0.5) / (df[term] + 0.5))
			part = (
				(ID_BOOST if term in ids else 1.0)
				* idf
				* f
				* (K1 + 1)
				/ (f + K1 * (1 - B + B * length / avg_len))
			)
			score += part * (1 + 0.25 * math.log(qn))
			matched.append((part, surface[term], term in ids, where[term]))
		# Require an identifier hit or at least two distinct terms: one generic word is not a match.
		if matched and (len(matched) >= 2 or matched[0][2]):
			matched.sort(key=lambda m: m[0], reverse=True)
			ranked.append((score, row, matched))
	ranked.sort(key=lambda r: r[0], reverse=True)
	return ranked


def _finding(row, matched, allowed):
	resolution = plain_text(row.get("resolution_details"), EXCERPT_CHARS)
	if resolution:
		res_line = f"Resolution: {resolution}"
	elif "resolution_details" in allowed:
		res_line = "Resolution: none recorded on this Issue."
	else:
		res_line = "Resolution: not visible to your role."
	places = sorted({w for m in matched for w in m[3]}, key=list(WEIGHTS).index)
	terms = ", ".join(m[1] for m in matched[:MAX_SHOWN_TERMS])
	subject = plain_text(row.get("subject"), 120) or "(no subject)"
	return {
		"title": f"{subject} ({row['name']})",
		"detail": (
			f"Matched: {terms} — in {', '.join(p.replace('_details', '') for p in places)}. "
			f"Status: {row.get('status')}. {res_line}"
		),
		"doctype": "Issue",
		"name": row["name"],
		"level": "success" if resolution else "warning",
	}


def analyze(doc, query=None):
	source, source_label = _source_text(doc, query)
	query_terms = tokenize(source)
	if not query_terms:
		return {
			"summary": "No searchable text. Enter a query or fill in the subject/description.",
			"findings": [],
		}

	if not frappe.has_permission("Issue", "read"):
		return {"summary": "You need Issue read access to search case history.", "findings": []}

	allowed = set(frappe.get_meta("Issue").get_permitted_fieldnames()) | {"name", "modified"}
	if "status" not in allowed:
		return {
			"summary": "Status is hidden from your role, so no similar-issue search was run.",
			"findings": [],
		}

	try:
		rows, baseline, truncated = _fetch_candidates(query_terms, doc.get("name"), allowed)
	except frappe.PermissionError:
		return {"summary": "You do not have permission to read Issues, so no search was run.", "findings": []}

	scope = (
		f"Compared {len(rows)} resolved or closed {'case' if len(rows) == 1 else 'cases'} using words from {source_label}. "
		"Older Issues sharing none of the key terms were not checked."
	)
	if truncated:
		scope += " Matches hit the row cap (newest first); add specific terms to narrow."

	ranked = _rank(rows, query_terms, baseline)
	if not ranked:
		return {"summary": "No similar resolved or closed Issues found.", "findings": [], "note": scope}

	findings = [_finding(row, matched, allowed) for _, row, matched in ranked[:MAX_RESULTS]]
	with_fix = sum(f["level"] == "success" for f in findings)
	return {
		"summary": (
			f"Found {len(findings)} related {'case' if len(findings) == 1 else 'cases'}. "
			f"Recorded resolutions: {with_fix}."
		),
		"findings": findings,
		"note": scope,
	}
