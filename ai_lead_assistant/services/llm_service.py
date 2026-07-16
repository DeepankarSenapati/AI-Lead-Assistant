import json

from openai import OpenAI

from ai_lead_assistant.services.schema_service import build_json_schema
from ai_lead_assistant.config import get_openai_config
from ai_lead_assistant.services.prompt_service import (
    build_extraction_prompt,
)

_config = get_openai_config()

_client = OpenAI(api_key=_config["api_key"])


def extract_fields(doctype: str, ocr_text: str) -> dict:
    """
    Extract ERPNext fields from OCR text.
    """

    prompt = build_extraction_prompt(
        doctype,
        ocr_text,
    )

    schema = build_json_schema(doctype)

    response = _call_openai(
        prompt,
        schema,
    )

    return _parse_response(response)


def _call_openai(prompt: str,schema: dict) -> str:
    response = _client.responses.create(
        model=_config["model"],
        input=prompt,
        text={
            "format": {
                "type": "json_schema",
                "name": "erpnext_document",
                "schema": schema,
                "strict": True,
            }
        },
    )

    return response.output_text.strip()


def _parse_response(response: str) -> dict:
    try:
        data = json.loads(response)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON returned by OpenAI: {e}")

    return {
        key: value
        for key, value in data.items()
        if value not in ("", None)
    }