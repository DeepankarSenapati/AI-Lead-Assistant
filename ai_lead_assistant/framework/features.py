from dataclasses import dataclass


@dataclass(frozen=True)
class Feature:
	label: str
	description: str
	icon: str
	forms: frozenset[str] | None = None
	unavailable_reason: str = ""
	default_enabled: bool = False
	requires_edit: bool = False
	analyzer: str = ""
	query_label: str = ""
	needs_saved: bool = False
	draft_method: str = ""

	def supports(self, doctype):
		return self.forms is None or doctype in self.forms

	def client_spec(self, key):
		return {
			"id": key,
			"label": self.label,
			"description": self.description,
			"icon": self.icon,
			"forms": sorted(self.forms) if self.forms is not None else None,
			"reason": self.unavailable_reason,
			"default_enabled": self.default_enabled,
			"local_analysis": bool(self.analyzer),
			"query_label": self.query_label,
			"needs_saved": self.needs_saved,
			"draft_method": self.draft_method,
		}
