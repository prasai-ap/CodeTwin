def test_order_creation_reserves_stock_and_leaves_payment_pending(client):
    response = client.post(
        "/orders",
        headers={"X-Demo-User": "user-ada"},
        json={"product_id": "product-keyboard", "quantity": 2},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["order"]["status"] == "pending"
    assert body["order"]["total_cents"] == 17_800
    assert body["payment"]["status"] == "pending"
    assert body["payment"]["order_id"] == body["order"]["order_id"]
    assert client.get("/products/product-keyboard").json()["product"]["stock"] == 10


def test_order_creation_rejects_insufficient_stock(client):
    response = client.post(
        "/orders",
        headers={"X-Demo-User": "user-ada"},
        json={"product_id": "product-keyboard", "quantity": 15},
    )

    assert response.status_code == 409
