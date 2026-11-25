from ai_lead_assistant.config import AI_EXTRACTABLE_FIELDS
from ai_lead_assistant.framework.features import Feature


FEATURES = {
    "chat_assistant": Feature(
        label="AI Chat Assistant",
        description="Open a demo conversation with context from the current form.",
        icon="message",
    ),
    "form_assistant": Feature(
        label="AI Form Assistant",
        description="Fill draft forms from an uploaded document using OCR and AI.",
        icon="file",
        forms=frozenset(AI_EXTRACTABLE_FIELDS),
        unavailable_reason="Form Fill has no extraction mapping for this form.",
        default_enabled=True,
        requires_edit=True,
    ),
}
