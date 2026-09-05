#!/usr/bin/env python3
"""
TarkaRaksha Baseline API Smoke Verification Script (E0).
Verifies FastAPI endpoints: health, scenarios catalog & runner,
certification catalog & runner, replay validation, hero transaction runner & retrieval,
and natural language intent parsing.
"""
import sys
import os

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from backend.app.main import app

def main():
    client = TestClient(app)
    print("=== TarkaRaksha Baseline API Smoke Verification (E0) ===")

    # 1. Health endpoints
    r = client.get('/health')
    assert r.status_code == 200, f"GET /health failed: {r.status_code}"
    print("[✓] GET /health -> 200 OK")

    r = client.get('/api/v1/health')
    assert r.status_code == 200, f"GET /api/v1/health failed: {r.status_code}"
    print("[✓] GET /api/v1/health -> 200 OK")

    # 2. Scenarios endpoints
    r = client.get('/api/v1/scenarios')
    assert r.status_code == 200, f"GET /api/v1/scenarios failed: {r.status_code}"
    scenarios = r.json()
    assert len(scenarios) == 12, f"Expected 12 scenarios, got {len(scenarios)}"
    print(f"[✓] GET /api/v1/scenarios -> 200 OK ({len(scenarios)} scenarios)")

    r = client.post('/api/v1/scenarios/HAPPY_PATH/run')
    assert r.status_code == 200, f"POST /api/v1/scenarios/HAPPY_PATH/run failed: {r.status_code}"
    res = r.json()
    assert res.get('actual_verdict') == 'PASS', f"Expected actual_verdict=PASS, got {res.get('actual_verdict')}"
    print(f"[✓] POST /api/v1/scenarios/HAPPY_PATH/run -> 200 OK (actual_verdict={res['actual_verdict']})")

    # 3. Certifications endpoints
    r = client.get('/api/v1/certifications')
    assert r.status_code == 200, f"GET /api/v1/certifications failed: {r.status_code}"
    certifications = r.json()
    assert len(certifications) == 12, f"Expected 12 certifications, got {len(certifications)}"
    print(f"[✓] GET /api/v1/certifications -> 200 OK ({len(certifications)} certifications)")

    r = client.post('/api/v1/certifications/HAPPY_PATH/run')
    assert r.status_code == 200, f"POST /api/v1/certifications/HAPPY_PATH/run failed: {r.status_code}"
    c_res = r.json()
    assert c_res.get('overall_status') == 'CERTIFIED', f"Expected CERTIFIED, got {c_res.get('overall_status')}"
    print(f"[✓] POST /api/v1/certifications/HAPPY_PATH/run -> 200 OK (overall_status={c_res['overall_status']})")

    # 4. Replay endpoint validation
    r = client.post('/api/v1/replay', json={})
    assert r.status_code == 422, f"Expected 422 for malformed replay snapshot, got {r.status_code}"
    print("[✓] POST /api/v1/replay (validation check) -> 422 Unprocessable Entity")

    # 5. Hero transaction endpoint
    r = client.post('/api/v1/hero-transaction/run', json={'trigger': 'api_smoke'})
    assert r.status_code == 200, f"POST /api/v1/hero-transaction/run failed: {r.status_code}"
    hero_data = r.json()
    assert hero_data.get('current_stage') == 'COMPLETED', f"Expected COMPLETED hero transaction, got {hero_data.get('current_stage')}"
    assert hero_data.get('replay_result', {}).get('verdict') == 'MATCH', f"Expected MATCH replay, got {hero_data.get('replay_result', {}).get('verdict')}"
    assert hero_data.get('certification_status') == 'CERTIFIED', f"Expected CERTIFIED, got {hero_data.get('certification_status')}"
    print(f"[✓] POST /api/v1/hero-transaction/run -> 200 OK (hero_id={hero_data['hero_transaction_id']}, stage={hero_data['current_stage']}, replay={hero_data['replay_result']['verdict']})")

    # 6. Read hero transaction
    hero_id = hero_data['hero_transaction_id']
    r = client.get(f'/api/v1/hero-transaction/{hero_id}')
    assert r.status_code == 200, f"GET /api/v1/hero-transaction/{{id}} failed: {r.status_code}"
    print(f"[✓] GET /api/v1/hero-transaction/{hero_id} -> 200 OK")

    # 7. Intent parse endpoint validation
    r = client.post('/api/v1/intent/parse', json={'prompt': 'Buy 1TB SSD under 8000'})
    assert r.status_code == 200, f"POST /api/v1/intent/parse failed: {r.status_code}"
    print("[✓] POST /api/v1/intent/parse -> 200 OK")

    print("\n[✓] ALL BASELINE API SMOKE CHECKS PASSED")
    return 0

if __name__ == "__main__":
    sys.exit(main())
