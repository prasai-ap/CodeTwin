import unittest

from fastapi.testclient import TestClient

from app import database
from app.main import app


class ShopApiTests(unittest.TestCase):
    def setUp(self):
        database.reset_state()
        self.client = TestClient(app)

    def test_product_catalog_is_public(self):
        response = self.client.get("/products")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 2)

    def test_user_routes_require_a_known_identity(self):
        self.assertEqual(self.client.get("/users/me").status_code, 401)
        self.assertEqual(
            self.client.get("/users/me", headers={"X-User-ID": "unknown"}).status_code,
            401,
        )
        response = self.client.get("/auth/session", headers={"X-User-ID": "user-1"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["authenticated"], "true")

    def test_checkout_rejects_requests_above_available_stock(self):
        response = self.client.post(
            "/orders",
            headers={"X-User-ID": "user-1"},
            json={"product_id": "product-1", "quantity": 9},
        )

        self.assertEqual(response.status_code, 409)
