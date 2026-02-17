# Dynamic Agent Creation

## Platform API

A mock patient management REST API built with FastAPI.

### Setup

```bash
uv add fastapi uvicorn
```

### Start the server

```bash
uvicorn platform.main:app --reload
```

### API Key

All requests require the header:

```
X-API-Key: secret-api-key-123
```

---

### Endpoints

**List all patients**
```bash
curl http://localhost:8000/patients \
  -H "X-API-Key: secret-api-key-123"
```

**Get a patient by ID**
```bash
curl http://localhost:8000/patients/a1b2c3d4-0001 \
  -H "X-API-Key: secret-api-key-123"
```

**Create a patient**
```bash
curl -X POST http://localhost:8000/patients \
  -H "X-API-Key: secret-api-key-123" \
  -H "Content-Type: application/json" \
  -d '{"name": "Eve Adams", "age": 41, "gender": "female", "diagnosis": "Migraine"}'
```

**Update a patient**
```bash
curl -X PUT http://localhost:8000/patients/a1b2c3d4-0001 \
  -H "X-API-Key: secret-api-key-123" \
  -H "Content-Type: application/json" \
  -d '{"diagnosis": "Type 1 Diabetes"}'
```

**Delete a patient**
```bash
curl -X DELETE http://localhost:8000/patients/a1b2c3d4-0004 \
  -H "X-API-Key: secret-api-key-123"
```
