import json
import pandas as pd
import anthropic
import streamlit as st
import os
from database import get_client
import base64
from rapidfuzz import fuzz, process
import re

RESTAURANT_TYPES = [
    "Specialty Coffee Shop",
    "Bakery & Pastry",
    "Juice & Smoothie Bar",
    "Breakfast & Brunch Café",
    "Italian Restaurant",
    "Mexican Restaurant",
    "Asian Restaurant",
    "Pizza Shop",
    "Burger & Grill",
    "Vegan & Healthy Food",
    "Sandwich & Deli",
    "Ice Cream & Desserts"
]


def plates_exist(business_id: str) -> bool:
    """Check if this business has any plates in Supabase."""
    db = get_client()
    result = db.table("plates").select("id")\
        .eq("business_id", business_id)\
        .execute()
    return len(result.data) > 0



def load_plates(business_id: str) -> list:
    """Load all plates with ingredients for a business."""
    db = get_client()
    plates_result = db.table("plates").select("*")\
        .eq("business_id", business_id)\
        .execute()
    plates = []
    for plate in plates_result.data:
        ingredients_result = db.table("ingredients").select("*")\
            .eq("plate_id", plate["id"])\
            .execute()
        plates.append({
            "id": plate["id"],
            "name": plate["name"],
            "selling_price": plate.get("selling_price", 0),
            "ingredients": [
                {
                    "description": i["description"],
                    "quantity_kg": i["quantity_kg"]
                }
                for i in ingredients_result.data
            ]
        })
    return plates

def clean_ingredient_description(description: str) -> str:
    """Clean ingredient description by removing extra whitespace and punctuation."""
    if not description:
        return ""
    # 1. Delete any content in parentheses or brackets
    description = re.sub(r'\(.*?\)', '', description)
    #2. Delete non desired characters and extra duplicate spaces
    description = "".join(description.splitlines())  # Replace newlines with space
    description = description.lower().strip()
    description = re.sub(r'[^\w\s]', '', description)  # Remove punctuation
    description = re.sub(r'\s+', ' ', description)  # Replace multiple spaces with single space
    return description


def save_plate(plate: dict, business_id: str) -> str:
    """Insert a new plate with ingredients, return plate id."""
    db = get_client()
    plate_result = db.table("plates").insert({
        "business_id": business_id,
        "name": plate["name"],
        "selling_price": plate.get("selling_price", 0)
    }).execute()
    plate_id = plate_result.data[0]["id"]
    ingredients = [
        {
            "plate_id": plate_id,
            "description": ing["description"],
            "quantity_kg": ing["quantity_kg"]
        }
        for ing in plate["ingredients"]
    ]
    db.table("ingredients").insert(ingredients).execute()
    return plate_id


def update_plate(plate_id: str, name: str, selling_price: float,
                 ingredients: list, business_id: str):
    """Update plate details and replace ingredients."""
    db = get_client()
    db.table("plates").update({
        "name": name,
        "selling_price": selling_price
    }).eq("id", plate_id).eq("business_id", business_id).execute()
    db.table("ingredients").delete().eq("plate_id", plate_id).execute()
    new_ingredients = [
        {
            "plate_id": plate_id,
            "description": ing["description"],
            "quantity_kg": ing["quantity_kg"]
        }
        for ing in ingredients
    ]
    if new_ingredients:
        db.table("ingredients").insert(new_ingredients).execute()


def delete_plate(plate_id: str, business_id: str):
    """Delete a plate and its ingredients."""
    db = get_client()
    db.table("ingredients").delete().eq("plate_id", plate_id).execute()
    db.table("plates").delete()\
        .eq("id", plate_id)\
        .eq("business_id", business_id).execute()


def generate_plates_for_restaurant(restaurant_type: str) -> list:
    """Call Claude to generate typical dishes for a restaurant type."""
    api_key = os.environ.get("ANTHROPIC_API_KEY") or st.secrets.get("ANTHROPIC_API_KEY")
    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        messages=[
            {
                "role": "user",
                "content": f"""You are helping set up a food cost tracking app for a {restaurant_type}.
Generate 8 typical menu items for this type of business.
Return ONLY a JSON array, no markdown, no explanation.
Each object must have:
- name (string): the menu item name
- ingredients (array): list of ingredient objects, each with:
  - description (string): ingredient name as it would appear on a supplier invoice
  - quantity_kg (number): typical quantity in kg used per serving
Only return the JSON array."""
            }
        ]
    )
    raw = response.content[0].text
    raw = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    plates = json.loads(raw)

    for plate in plates:
        for ing in plate.get("ingredients", []):
            ing["description"] = clean_ingredient_description(ing.get("description", ""))

    return plates



def get_latest_prices(df: pd.DataFrame) -> dict:
    """Extract latest unit price per ingredient from invoice data."""
    if df.empty:
        return {}
    cogs_df = df[df["category"] == "COGS"].copy()
    if cogs_df.empty:
        return {}
    cogs_df["description_lower"] = cogs_df["description"].str.lower().str.strip()
    cogs_df["date"] = pd.to_datetime(cogs_df["date"], errors="coerce")
    latest = cogs_df.sort_values("date").groupby("description_lower")["unit_price"].last()
    return latest.to_dict()


def calculate_plate_cost(plate: dict, prices: dict) -> dict:
    import re
from rapidfuzz import fuzz, process

COMMON_INVOICE_NOISE = {
    "kg", "g", "l", "ml", "ctn", "box", "pkt", "pk", "bag", "tub", "tray",
    "fresh", "frozen", "chilled", "prem", "premium", "bulk", "rnd", "approx",
    "grade", "ea", "each", "imported", "local", "aus"
}

def clean_for_matching(text: str) -> str:
    """Strip numbers, symbols, and standard packaging/spec noise."""
    if not text:
        return ""
    # Lowercase and remove punctuation/special characters
    text = re.sub(r'[^a-zA-Z\s]', ' ', text.lower())
    # Remove isolated numbers or common package units
    tokens = [
        word for word in text.split()
        if word not in COMMON_INVOICE_NOISE and len(word) > 1
    ]
    return " ".join(tokens)


def calculate_plate_cost(plate: dict, prices: dict) -> dict:
    """Calculate cost of a plate based on latest ingredient prices using tuned fuzzy matching."""
    total_cost = 0.0
    breakdown = []

    # Pre-clean the invoice price keys mapping: {cleaned_text: original_key}
    cleaned_price_map = {}
    for raw_desc in prices.keys():
        cleaned = clean_for_matching(raw_desc)
        if cleaned:
            cleaned_price_map[cleaned] = raw_desc

    cleaned_invoice_keys = list(cleaned_price_map.keys())

    for ingredient in plate["ingredients"]:
        raw_ing_desc = ingredient["description"]
        clean_ing_key = clean_for_matching(raw_ing_desc)
        qty = ingredient["quantity_kg"]

        candidates = []

        if clean_ing_key and cleaned_invoice_keys:
            # 1. token_set_ratio checks subset matches (handles "Pork Belly" inside "Pork Belly Skinless 15kg")
            # 2. partial_token_set_ratio / token_set_ratio blend
            matches = process.extract(
                clean_ing_key,
                cleaned_invoice_keys,
                scorer=fuzz.token_set_ratio,
                limit=5
            )

            # Filter with a calibrated 70% threshold
            for cleaned_match, score, _ in matches:
                if score >= 70:
                    original_invoice_desc = cleaned_price_map[cleaned_match]
                    candidates.append((original_invoice_desc, prices[original_invoice_desc], round(score, 1)))

        if candidates:
            # Pick the highest scoring candidate (match score first, then price)
            candidates.sort(key=lambda x: x[2], reverse=True)
            best_match = candidates[0]
            selected_price = best_match[1]
            cost = round(selected_price * qty, 4)
            total_cost += cost

            breakdown.append({
                "ingredient": raw_ing_desc,
                "qty_g": round(qty * 1000, 1),
                "candidates": [(c[0], c[1]) for c in candidates],
                "unit_price": selected_price,
                "cost": cost,
                "matched": True,
                "score": best_match[2]
            })
        else:
            breakdown.append({
                "ingredient": raw_ing_desc,
                "qty_g": round(qty * 1000, 1),
                "candidates": [],
                "unit_price": None,
                "cost": None,
                "matched": False,
                "score": 0
            })

    selling_price = plate.get("selling_price", 0)
    margin = round(selling_price - total_cost, 4) if selling_price > 0 else None
    margin_pct = round((margin / selling_price) * 100, 1) if selling_price and selling_price > 0 else None

    return {
        "name": plate["name"],
        "total_cost": total_cost,
        "selling_price": selling_price,
        "margin": margin,
        "margin_pct": margin_pct,
        "breakdown": breakdown,
        "has_unmatched": any(not b["matched"] for b in breakdown)
    }
def extract_plates_from_menu(file_bytes: bytes, file_type: str) -> list:
    """Read a menu photo or PDF and extract dishes with typical ingredients."""
    api_key = os.environ.get("ANTHROPIC_API_KEY") or st.secrets.get("ANTHROPIC_API_KEY")
    client = anthropic.Anthropic(api_key=api_key)

    if file_type == "application/pdf":
        content = [
            {
                "type": "document",
                "source": {
                    "type": "base64",
                    "media_type": "application/pdf",
                    "data": base64.b64encode(file_bytes).decode("utf-8")
                }
            }
        ]
    else:
        content = [
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": file_type,
                    "data": base64.b64encode(file_bytes).decode("utf-8")
                }
            }
        ]

    content.append({
        "type": "text",
        "text": """This is a restaurant or café menu. Extract all food and drink items.
For each item generate typical raw ingredients needed to make it.
Return ONLY a valid JSON array, without markdown code fences or conversational text.

Each object must follow this structure:
- name (string): exact menu item name
- selling_price (number): numeric price shown on the menu, 0 if not found
- ingredients (array): list of raw ingredient objects, each containing:
  - description (string): standard wholesale ingredient name (MAX 3 words, e.g. "Rice Noodles", "Barramundi Fillet", "Chicken Breast", "Tamarind Paste").
  - quantity_kg (number): realistic quantity in kg per serving (e.g. 0.15 for 150g)

CRITICAL INGREDIENT RULES:
- NEVER include dimensions, measurements, or cuts in parentheses (e.g., write "Rice Noodles", NEVER "Flat Noodles (3mm wide)").
- NEVER include preparation methods (e.g., write "Pork Belly", NEVER "Crispy roasted pork belly").
PROTEIN OPTIONS RULE:
- If a menu item states "Choice of chicken, beef, prawns or tofu", DO NOT create a single generic dish.
- Instead, create separate dish entries for each option (e.g. "Pad Thai - Chicken", "Pad Thai - Beef", "Pad Thai - Prawns").
- Keep base ingredients identical across these variants, changing only the protein item and adjusting the selling price if the menu specifies a surcharge."""
    })

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        messages=[{"role": "user", "content": content}]
    )

    raw = response.content[0].text
    raw = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    plates = json.loads(raw)

    # Post-procesamiento para garantizar limpieza de descripciones
    for plate in plates:
        for ing in plate.get("ingredients", []):
            ing["description"] = clean_ingredient_description(ing.get("description", ""))

    return plates