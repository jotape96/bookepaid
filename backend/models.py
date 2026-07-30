from database import get_client
import hashlib
import pandas as pd

class Business:
    def __init__(self, id: str, name: str, type: str):
        self.id = id
        self.name = name
        self.type = type

    @staticmethod
    def create(name: str, type: str) -> "Business":
        db = get_client()
        result = db.table("businesses").insert({
            "name": name,
            "type": type
        }).execute()
        data = result.data[0]
        return Business(data["id"], data["name"], data["type"])

    @staticmethod
    def get(business_id: str) -> "Business":
        db = get_client()
        result = db.table("businesses").select("*").eq("id", business_id).execute()
        if result.data:
            data = result.data[0]
            return Business(data["id"], data["name"], data["type"])
        return None

    def summary(self) -> dict:
        db = get_client()
        items = db.table("line_items").select("*").eq("business_id", self.id).execute()
        return {
            "total_spend": sum(i["total"] for i in items.data),
            "invoice_count": len(set(i["description"] for i in items.data)),
            "line_items": len(items.data)
        }


class User:
    def __init__(self, id: str, name: str, email: str, role: str, business_id: str):
        self.id = id
        self.name = name
        self.email = email
        self.role = role
        self.business_id = business_id

    @staticmethod
    def _hash_password(password: str) -> str:
        return hashlib.sha256(password.encode()).hexdigest()

    @staticmethod
    def login(email: str, password: str):
        db = get_client()
        hashed = User._hash_password(password)
        result = db.table("users").select("*").eq("email", email).eq("password", hashed).execute()
        if not result.data:
            return None
        data = result.data[0]
        if data["role"] == "owner":
            return Owner(data["id"], data["name"], data["email"], data["business_id"])
        else:
            return Manager(data["id"], data["name"], data["email"], data["business_id"])

    @staticmethod
    def create(name: str, email: str, password: str, role: str, business_id: str):
        db = get_client()
        hashed = User._hash_password(password)
        result = db.table("users").insert({
            "name": name,
            "email": email,
            "password": hashed,
            "role": role,
            "business_id": business_id
        }).execute()
        return result.data[0]

    def logout(self):
        import streamlit as st
        st.session_state.clear()


class Owner(User):
    def __init__(self, id, name, email, business_id):
        super().__init__(id, name, email, "owner", business_id)

    def export_csv(self, date_from, date_to) -> bytes:
        db = get_client()
        result = db.table("line_items").select("*")\
            .eq("business_id", self.business_id)\
            .gte("date", str(date_from))\
            .lte("date", str(date_to))\
            .execute()
        df = pd.DataFrame(result.data)
        return df.to_csv(index=False).encode("utf-8")

    def set_selling_price(self, plate_id: str, price: float):
        db = get_client()
        db.table("plates").update({"selling_price": price})\
            .eq("id", plate_id).execute()

    def manage_users(self) -> list:
        db = get_client()
        result = db.table("users").select("*")\
            .eq("business_id", self.business_id).execute()
        return result.data


class Manager(User):
    def __init__(self, id, name, email, business_id):
        super().__init__(id, name, email, "manager", business_id)

    def upload_invoice(self, invoice_data: dict):
        db = get_client()
        return db.table("invoices").insert(invoice_data).execute()

    def edit_plates(self, plate_id: str, updates: dict):
        db = get_client()
        return db.table("plates").update(updates)\
            .eq("id", plate_id)\
            .eq("business_id", self.business_id).execute()