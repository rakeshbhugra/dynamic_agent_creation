import uuid
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

import utils

app = FastAPI(title="Platform Patient API")

API_KEY = "secret-api-key-123"


# --- Middleware ---

@app.middleware("http")
async def api_key_middleware(request: Request, call_next):
    if request.headers.get("X-API-Key") != API_KEY:
        return JSONResponse(status_code=401, content={"detail": "Invalid or missing API key"})
    return await call_next(request)


# --- Models ---

class PatientCreate(BaseModel):
    name: str
    age: int
    gender: str
    diagnosis: str


class PatientUpdate(BaseModel):
    name: str | None = None
    age: int | None = None
    gender: str | None = None
    diagnosis: str | None = None


# --- Routes ---

@app.get("/patients")
def list_patients():
    return utils.get_all_patients()


@app.get("/patients/{patient_id}")
def get_patient(patient_id: str):
    patient = utils.get_patient_by_id(patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    return patient


@app.post("/patients", status_code=201)
def create_patient(body: PatientCreate):
    patient = {
        "id": str(uuid.uuid4()),
        "name": body.name,
        "age": body.age,
        "gender": body.gender,
        "diagnosis": body.diagnosis,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    return utils.create_patient(patient)


@app.put("/patients/{patient_id}")
def update_patient(patient_id: str, body: PatientUpdate):
    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    patient = utils.update_patient(patient_id, updates)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    return patient


@app.delete("/patients/{patient_id}", status_code=204)
def delete_patient(patient_id: str):
    deleted = utils.delete_patient(patient_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Patient not found")
