import unittest

from fastapi.testclient import TestClient

from app.database import db
from app.main import app


class PaymentWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        db.reset()
        self.client = TestClient(app)

    def test_checkout_completes_payment_and_notifies_the_user(self):
        checkout = self.client.post(
            "/orders/checkout",
            headers={"X-Demo-User": "user-demo"},
            json={"product_id": "product-demo", "quantity": 2},
        )

        self.assertEqual(checkout.status_code, 200)
        body = checkout.json()
        self.assertEqual(body["order"]["status"], "completed")
        self.assertEqual(body["payment"]["status"], "completed")
        self.assertEqual(body["payment"]["amount_cents"], body["order"]["total_cents"])
        self.assertEqual(body["order"]["total_cents"], 5000)

        notifications = self.client.get("/notifications", headers={"X-Demo-User": "user-demo"})
        self.assertEqual(notifications.status_code, 200)
        events = notifications.json()["notifications"]
        self.assertEqual(len(events), 1, "payment completion notification is missing")
        self.assertEqual(events[0]["event"], "payment_completed")
        self.assertEqual(events[0]["order_id"], body["order"]["order_id"])


if __name__ == "__main__":
    unittest.main()
