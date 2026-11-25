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

    def supports(self, doctype):
        return self.forms is None or doctype in self.forms
