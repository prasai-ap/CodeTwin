def test_completed_payment_emits_payment_completed_notification(client):
    headers = {"X-Demo-User": "user-ada"}
    placed = client.post(
        "/orders",
        headers=headers,
        json={"product_id": "product-keyboard", "quantity": 2},
    )
    payment_id = placed.json()["payment"]["payment_id"]
    order_id = placed.json()["order"]["order_id"]

    completed = client.post(f"/payments/{payment_id}/complete", headers=headers)
    assert completed.status_code == 200
    assert completed.json()["payment"]["status"] == "completed"
    assert completed.json()["order"]["status"] == "completed"

    notifications = client.get("/notifications", headers=headers).json()["notifications"]
    assert any(
        event["event"] == "payment_completed" and event["order_id"] == order_id
        for event in notifications
    ), "completed payment should produce a payment_completed notification"
