import unittest

from fastapi.testclient import TestClient

from app import database
from app.main import app


class PaymentWorkflowTests(unittest.TestCase):
    def setUp(self):
        database.reset_state()
        self.client = TestClient(app)
        self.headers = {"X-User-ID": "user-1"}

    def test_checkout_captures_full_order_amount_and_notifies_user(self):
        order_response = self.client.post(
            "/orders",
            headers=self.headers,
            json={"product_id": "product-1", "quantity": 2},
        )

        self.assertEqual(order_response.status_code, 200)
        order = order_response.json()
        self.assertEqual(order["status"], "paid")
        self.assertEqual(order["total_cents"], 5000)

        payment_response = self.client.get(f"/payments/{order['payment_id']}", headers=self.headers)
        self.assertEqual(payment_response.status_code, 200)
        self.assertEqual(payment_response.json()["amount_cents"], order["total_cents"])

        notifications = self.client.get("/notifications", headers=self.headers).json()
        self.assertEqual(len(notifications), 1)
        self.assertEqual(notifications[0]["order_id"], order["id"])
