import anthropic
import base64
import json
import pandas as pd
import streamlit as st
import os
from data import snapshot_plate_costs

def get_client():
    api_key = os.environ.get("ANTHROPIC_API_KEY") or st.secrets.get("ANTHROPIC_API_KEY")
    return anthropic.Anthropic(api_key=api_key)


def extract_invoice(pdf_bytes: bytes, invoice_name: str) -> pd.DataFrame:
    """Send PDF to Claude, extract line items, return as DataFrame."""
    client = get_client()
    base64_pdf = base64.b64encode(pdf_bytes).decode("utf-8")

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "document",
                        "source": {
                            "type": "base64",
                            "media_type": "application/pdf",
                            "data": base64_pdf
                        }
                    },
                    {
                        "type": "text",
                        "text": """Extract all line items from this invoice and return ONLY a JSON array.
                        Each object must have:
                        - description (string)
                        - quantity (number)
                        - unit_price (number)
                        - total (number)
                        - date (string, format YYYY-MM-DD — extract from invoice date field, use today if not found)
                        - category: classify using these rules:
                          * COGS: raw materials, ingredients, packaging, stock, goods for resale,
                              production-related setup fees
                          * Packaging: boxes, bags, labels, containers
                          * Labour: staff, services, training, consulting
                          * Overhead: rent, utilities, equipment rental, admin fees, software
                          * Other: anything that doesn't fit above
                        No markdown, no explanation. Just the JSON array."""
                    }
                ]
            }
        ]
    )

    raw = response.content[0].text
    raw = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()

    try:
        items = json.loads(raw)
    except json.JSONDecodeError:
        raise ValueError(f"Could not parse Claude response: {raw}")

    df = pd.DataFrame(items)
    df["invoice"] = invoice_name
    return df

