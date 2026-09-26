import unittest

from fastapi.testclient import TestClient

from app.database import db
from app.main import app


class ShopApiTests(unittest.TestCase):
    def setUp(self) -> None:
        db.reset()
        self.client = TestClient(app)

    def test_health_and_product_catalog_are_public(self):
        self.assertEqual(self.client.get("/health").json(), {"status": "ok"})
        catalog = self.client.get("/products")
        self.assertEqual(catalog.status_code, 200)
        self.assertEqual(catalog.json()["products"][0]["product_id"], "product-demo")

    def test_demo_identity_is_required_for_user_data(self):
        self.assertEqual(self.client.get("/users/me").status_code, 401)
        response = self.client.get("/users/me", headers={"X-Demo-User": "user-demo"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["user"]["name"], "Demo Developer")

    def test_auth_route_accepts_only_the_synthetic_demo_identity(self):
        accepted = self.client.post("/auth/session", json={"user_id": "user-demo"})
        rejected = self.client.post("/auth/session", json={"user_id": "unknown"})
        self.assertTrue(accepted.json()["authenticated"])
        self.assertEqual(rejected.status_code, 401)

    def test_checkout_rejects_quantity_above_inventory(self):
        response = self.client.post(
            "/orders/checkout",
            headers={"X-Demo-User": "user-demo"},
            json={"product_id": "product-demo", "quantity": 100},
        )
        self.assertEqual(response.status_code, 409)


if __name__ == "__main__":
    unittest.main()
