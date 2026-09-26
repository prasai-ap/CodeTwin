def test_payment_completion_updates_payment_and_order(client):
    placed = client.post(
        "/orders",
        headers={"X-Demo-User": "user-ada"},
        json={"product_id": "product-keyboard", "quantity": 2},
    )
    payment_id = placed.json()["payment"]["payment_id"]
    order_id = placed.json()["order"]["order_id"]

    completed = client.post(
        f"/payments/{payment_id}/complete",
        headers={"X-Demo-User": "user-ada"},
    )

    assert completed.status_code == 200
    body = completed.json()
    assert body["payment"]["status"] == "completed"
    assert body["order"]["status"] == "completed"
    assert body["payment"]["amount_cents"] == body["order"]["total_cents"]
    assert body["order"]["order_id"] == order_id

def test_payment_cannot_be_completed_twice(client):
    placed = client.post(
        "/orders",
        headers={"X-Demo-User": "user-ada"},
        json={"product_id": "product-notebook", "quantity": 1},
    )
    payment_id = placed.json()["payment"]["payment_id"]
    headers = {"X-Demo-User": "user-ada"}

    assert client.post(f"/payments/{payment_id}/complete", headers=headers).status_code == 200
    assert client.post(f"/payments/{payment_id}/complete", headers=headers).status_code == 409


def test_payment_is_not_visible_to_a_different_demo_user(client):
    placed = client.post(
        "/orders",
        headers={"X-Demo-User": "user-ada"},
        json={"product_id": "product-notebook", "quantity": 1},
    )
    payment_id = placed.json()["payment"]["payment_id"]

    response = client.post(
        f"/payments/{payment_id}/complete",
        headers={"X-Demo-User": "user-grace"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Payment not found"
