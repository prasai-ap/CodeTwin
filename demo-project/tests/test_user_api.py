def test_user_profile_requires_and_returns_demo_identity(client):
    missing = client.get("/users/me")
    profile = client.get("/users/me", headers={"X-Demo-User": "user-grace"})

    assert missing.status_code == 401
    assert profile.status_code == 200
    assert profile.json()["user"] == {
        "user_id": "user-grace",
        "name": "Grace Example",
        "email": "grace@example.test",
    }
