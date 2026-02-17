#!/usr/bin/env bash

BASE="http://localhost:8000"
KEY="secret-api-key-123"

echo "==========================================="
echo " Platform Patient API — Endpoint Tests"
echo "==========================================="

echo ""
echo ">>> GET /patients (list all)"
curl -s "$BASE/patients" -H "X-API-Key: $KEY" | python3 -m json.tool

echo ""
echo ">>> GET /patients/a1b2c3d4-0001 (single patient)"
curl -s "$BASE/patients/a1b2c3d4-0001" -H "X-API-Key: $KEY" | python3 -m json.tool

echo ""
echo ">>> POST /patients (create)"
NEW=$(curl -s -X POST "$BASE/patients" \
  -H "X-API-Key: $KEY" \
  -H "Content-Type: application/json" \
  -d '{"name": "Eve Adams", "age": 41, "gender": "female", "diagnosis": "Migraine"}')
echo "$NEW" | python3 -m json.tool
NEW_ID=$(echo "$NEW" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

echo ""
echo ">>> PUT /patients/a1b2c3d4-0001 (update diagnosis)"
curl -s -X PUT "$BASE/patients/a1b2c3d4-0001" \
  -H "X-API-Key: $KEY" \
  -H "Content-Type: application/json" \
  -d '{"diagnosis": "Type 1 Diabetes"}' | python3 -m json.tool

echo ""
echo ">>> DELETE /patients/$NEW_ID (delete newly created patient)"
STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X DELETE "$BASE/patients/$NEW_ID" \
  -H "X-API-Key: $KEY")
echo "HTTP $STATUS (expect 204)"

echo ""
echo ">>> GET /patients (no API key — expect 401)"
curl -s "$BASE/patients" | python3 -m json.tool

echo ""
echo "==========================================="
echo " Done"
echo "==========================================="
