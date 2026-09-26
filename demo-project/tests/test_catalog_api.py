def test_catalog_contains_only_seeded_synthetic_products(client):
    response = client.get("/products")

    assert response.status_code == 200
    products = response.json()["products"]
    assert {product["product_id"] for product in products} == {"product-keyboard", "product-notebook"}
    assert all(product["unit_price_cents"] > 0 for product in products)


def test_product_detail_returns_not_found_for_unknown_product(client):
    response = client.get("/products/missing-product")

    assert response.status_code == 404
