from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.core.credentials import AzureKeyCredential

from ai_lead_assistant.config import (
    get_azure_document_intelligence_config,
)


def extract_text(file_bytes: bytes) -> str:
    """
    Extract text from a document using Azure Document Intelligence.
    """

    config = get_azure_document_intelligence_config()

    client = DocumentIntelligenceClient(
        endpoint=config["endpoint"],
        credential=AzureKeyCredential(config["api_key"]),
    )

    poller = client.begin_analyze_document(
        "prebuilt-read",
        body=file_bytes,
    )

    result = poller.result()

    lines = []

    for page in result.pages:
        for line in page.lines:
            lines.append(line.content)

    return "\n".join(lines)