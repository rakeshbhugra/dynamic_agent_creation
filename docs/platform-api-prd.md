# Platform API — Product Requirements Document

## Overview

A lightweight FastAPI server providing a mock patient management API for the Qure dynamic agent creation platform. It uses a local JSON file as the data store and enforces API key authentication via middleware.

---

## Goals

- Expose a simple REST API for patient CRUD operations
- Serve as a mock backend for agent development and testing
- Keep the implementation minimal and self-contained (no external DB)

---

## File Structure

```
platform/
├── main.py          # FastAPI app, routes, middleware
├── utils.py         # JSON DB helper functions
└── db.json          # Mock database with sample patient records
```

---

## API Endpoints

| Method | Path                    | Description           |
|--------|-------------------------|-----------------------|
| GET    | `/patients`             | List all patients     |
| GET    | `/patients/{id}`        | Get a single patient  |
| POST   | `/patients`             | Create a new patient  |
| PUT    | `/patients/{id}`        | Update a patient      |
| DELETE | `/patients/{id}`        | Delete a patient      |

---

## Data Model

### Patient

| Field       | Type   | Required | Notes                        |
|-------------|--------|----------|------------------------------|
| id          | string | auto     | UUID, generated on create    |
| name        | string | yes      |                              |
| age         | int    | yes      |                              |
| gender      | string | yes      | "male" / "female" / "other"  |
| diagnosis   | string | yes      |                              |
| created_at  | string | auto     | ISO 8601 timestamp           |

---

## Middleware

**API Key Authentication**

- All requests must include the header `X-API-Key`
- A single hardcoded key is used for the mock: `secret-api-key-123`
- Returns `401 Unauthorized` if the header is missing or the key is invalid

---

## Utils (JSON DB)

Functions to be implemented in `utils.py`:

- `load_db()` — read and return all records from `db.json`
- `save_db(data)` — write updated data back to `db.json`
- `get_all_patients()` — return list of all patients
- `get_patient_by_id(id)` — return a single patient or `None`
- `create_patient(patient)` — append and persist a new patient
- `update_patient(id, updates)` — update fields and persist
- `delete_patient(id)` — remove and persist

---

## Sample Data

`db.json` will be pre-seeded with 3–4 patient records covering varied diagnoses, ages, and genders.

---

## Out of Scope

- User authentication / roles
- Real database integration
- Pagination, filtering, or search
- Input sanitisation beyond Pydantic validation
