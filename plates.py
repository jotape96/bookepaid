import json
import pandas as pd
import anthropic
import streamlit as st
import os
from database import get_client
import base64
from rapidfuzz import fuzz, process

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
    return json.loads(raw)


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
    """Calculate cost of a plate based on latest ingredient prices."""
    total_cost = 0.0
    breakdown = []
    for ingredient in plate["ingredients"]:
        key = ingredient["description"].lower().strip()
        qty = ingredient["quantity_kg"]
        # Fuzzy match with minimum 80% similarity threshold
        matches = process.extract(
            key,
            prices.keys(),
            scorer=fuzz.token_sort_ratio,
            limit=5
        )
        candidates = [
            (match[0], prices[match[0]])
            for match in matches
            if match[1] >= 80  # minimum 80% similarity
        ]
        candidates.sort(key=lambda x: x[1], reverse=True)
        if candidates:
            selected_price = candidates[0][1]
            cost = round(selected_price * qty, 4)
            total_cost += cost
            breakdown.append({
                "ingredient": ingredient["description"],
                "qty_g": round(qty * 1000, 1),
                "candidates": candidates,
                "unit_price": selected_price,
                "cost": cost,
                "matched": True
            })
        else:
            breakdown.append({
                "ingredient": ingredient["description"],
                "qty_g": round(qty * 1000, 1),
                "candidates": [],
                "unit_price": None,
                "cost": None,
                "matched": False
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
For each item generate typical ingredients needed to make it.
Return ONLY a JSON array, no markdown, no explanation.
Each object must have:
- name (string): the exact menu item name as shown
- selling_price (number): the price shown on the menu in numeric form, 0 if not found
- ingredients (array): list of ingredient objects, each with:
  - description (string): ingredient name as it would appear on a supplier invoice
  - quantity_kg (number): typical quantity in kg used per serving be as realistic as possible (e.g. 0.15 for 150g)
Only include food and drink items, skip descriptions, prices, and categories.
Only return the JSON array."""
    })

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        messages=[{"role": "user", "content": content}]
    )

    raw = response.content[0].text
    raw = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return json.loads(raw)