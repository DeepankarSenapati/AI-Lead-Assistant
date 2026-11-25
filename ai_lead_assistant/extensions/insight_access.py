import frappe


def readable_doc(doctype, name):
	"""Return a related document with the same visibility as opening its form."""
	if not name:
		return None
	try:
		doc = frappe.get_doc(doctype, name)
	except (frappe.DoesNotExistError, frappe.PermissionError):
		return None
	if not doc.has_permission("read"):
		return None
	doc.apply_fieldlevel_read_permissions()
	return doc


def plain_text(value, limit=500):
	"""Extract a bounded, readable excerpt from a Desk text editor field."""
	from html import unescape

	from bs4 import BeautifulSoup

	text = str(value or "")[: limit * 8]
	if "<" in text and ">" in text:
		soup = BeautifulSoup(text, "html.parser")
		for element in soup(["script", "style"]):
			element.decompose()
		text = soup.get_text(" ", strip=True)
	return " ".join(unescape(text).split())[:limit]
