import json
import os

DB_FILE = "data.json"

def load_data():
    if not os.path.exists(DB_FILE):
        default_data = {
            "COMMISION": 0.05,
            "BANK_DETAILS": {
                "card": {
                    "name": "Банковская карта",
                    "details": " "
                },
                "sbp": {
                    "name": "СБП",
                    "details": " "
                },
                "sim": {
                    "name": "SIM (Мобильная связь)",
                    "details": " "
                }
            }
        }
        save_data(default_data)
        return default_data
    
    try:
        with open(DB_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {}

def save_data(data):
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_commission():
    data = load_data()
    env_commission = os.getenv("COMMISSION")
    if env_commission is not None:
        try:
            return float(env_commission)
        except ValueError:
            pass
    return data.get("COMMISION", 0.20)

def get_bank_details():
    data = load_data()
    return data.get("BANK_DETAILS", {})

def update_commission(new_commission):
    data = load_data()
    data["COMMISION"] = float(new_commission)
    save_data(data)
    return True

def update_bank_detail(bank_type, new_details):
    data = load_data()
    if "BANK_DETAILS" not in data:
        data["BANK_DETAILS"] = {}
    
    if bank_type in data["BANK_DETAILS"]:
        data["BANK_DETAILS"][bank_type]["details"] = new_details
        save_data(data)
        return True
    return False