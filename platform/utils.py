import json
from pathlib import Path
from typing import Optional

DB_PATH = Path(__file__).parent / "db.json"


def load_db() -> dict:
    with open(DB_PATH, "r") as f:
        return json.load(f)


def save_db(data: dict) -> None:
    with open(DB_PATH, "w") as f:
        json.dump(data, f, indent=2)


def get_all_patients() -> list:
    return load_db()["patients"]


def get_patient_by_id(patient_id: str) -> Optional[dict]:
    return next((p for p in get_all_patients() if p["id"] == patient_id), None)


def create_patient(patient: dict) -> dict:
    db = load_db()
    db["patients"].append(patient)
    save_db(db)
    return patient


def update_patient(patient_id: str, updates: dict) -> Optional[dict]:
    db = load_db()
    for patient in db["patients"]:
        if patient["id"] == patient_id:
            patient.update(updates)
            save_db(db)
            return patient
    return None


def delete_patient(patient_id: str) -> bool:
    db = load_db()
    original_count = len(db["patients"])
    db["patients"] = [p for p in db["patients"] if p["id"] != patient_id]
    if len(db["patients"]) == original_count:
        return False
    save_db(db)
    return True
