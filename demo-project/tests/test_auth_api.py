def test_demo_session_requires_a_seeded_identity(client):
    missing = client.post("/auth/session")
    valid = client.post("/auth/session", headers={"X-Demo-User": "user-ada"})

    assert missing.status_code == 401
    assert valid.status_code == 200
    assert valid.json()["mode"] == "synthetic_demo"
    assert valid.json()["user_id"] == "user-ada"
