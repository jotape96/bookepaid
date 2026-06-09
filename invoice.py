import anthropic
import base64
import json
import pandas as pd
import streamlit as st
import os


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
                        - description (string): ingredient name ONLY, no quantities or units.
                        Examples: "Onion 3 Kg" → "Onion", "Eggs x 30" → "Eggs", "Ham 500gr" → "Ham"
                        - quantity (number): numeric quantity ordered
                        - unit (string): unit of measurement after normalisation:
                        * For weight items: always normalise to "kg"
                        * For liquid items: always normalise to "L"  
                        * For countable items (eggs, bread rolls, buns): use "unit"
                        - unit_price (number): normalised price per kg, per litre, or per unit.
                        Examples:
                        * $3.00 for 3kg bag of onions → unit_price: 1.00, unit: "kg"
                        * $8.00 for 30 eggs (avg 60g each) → unit_price: 4.44, unit: "kg"
                        * $5.00 for 2L milk → unit_price: 2.50, unit: "L"
                        - total (number): original line item total from invoice
                        - date (string, format YYYY-MM-DD — extract from invoice date, use today if not found)
                        - category: classify using these rules:
                        * COGS: raw materials, ingredients, stock, goods for resale
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

