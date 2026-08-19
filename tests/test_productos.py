class TestProductosCRUD:
    def test_crear_producto(self, client, admin_headers):
        resp = client.post("/productos/", headers=admin_headers, json={
            "nombre": "Croquetas Dog Chow",
            "descripcion": "Bolsa 15kg",
            "precio_compra": 8000.0,
            "precio_venta": 12000.0,
            "stock_actual": 50,
            "stock_minimo": 10,
            "unidad_medida": "un",
            "categoria": "ALIMENTOS",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["nombre"] == "Croquetas Dog Chow"
        assert data["precio_venta"] == 12000.0
        assert data["stock_actual"] == 50
        assert data["activo"] is True

    def test_listar_productos(self, client, admin_headers):
        client.post("/productos/", headers=admin_headers, json={"nombre": "Shampoo", "precio_venta": 3000.0})
        resp = client.get("/productos/", headers=admin_headers)
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_listar_por_categoria(self, client, admin_headers):
        client.post("/productos/", headers=admin_headers, json={"nombre": "Croquetas", "categoria": "ALIMENTOS"})
        client.post("/productos/", headers=admin_headers, json={"nombre": "Shampoo", "categoria": "COSMETICA"})
        resp = client.get("/productos/?categoria=COSMETICA", headers=admin_headers)
        assert len(resp.json()) == 1
        assert resp.json()[0]["nombre"] == "Shampoo"

    def test_obtener_producto(self, client, admin_headers):
        r = client.post("/productos/", headers=admin_headers, json={"nombre": "Juguete", "precio_venta": 500.0})
        pid = r.json()["id"]
        resp = client.get(f"/productos/{pid}", headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["nombre"] == "Juguete"

    def test_actualizar_producto(self, client, admin_headers):
        r = client.post("/productos/", headers=admin_headers, json={"nombre": "Old Name", "precio_venta": 100.0})
        pid = r.json()["id"]
        resp = client.put(f"/productos/{pid}", headers=admin_headers, json={"nombre": "New Name"})
        assert resp.status_code == 200
        assert resp.json()["nombre"] == "New Name"

    def test_eliminar_producto(self, client, admin_headers):
        r = client.post("/productos/", headers=admin_headers, json={"nombre": "Borrar"})
        pid = r.json()["id"]
        resp = client.delete(f"/productos/{pid}", headers=admin_headers)
        assert resp.status_code == 204
        resp = client.get(f"/productos/{pid}", headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["activo"] is False

    def test_ajustar_stock(self, client, admin_headers):
        r = client.post("/productos/", headers=admin_headers, json={"nombre": "Stock Test", "stock_actual": 10})
        pid = r.json()["id"]
        resp = client.post(f"/productos/{pid}/stock", headers=admin_headers, json={"cantidad": 5, "motivo": "Reposición"})
        assert resp.status_code == 200
        assert resp.json()["stock_anterior"] == 10
        assert resp.json()["stock_nuevo"] == 15

    def test_ajustar_stock_negativo(self, client, admin_headers):
        r = client.post("/productos/", headers=admin_headers, json={"nombre": "Low Stock", "stock_actual": 3})
        pid = r.json()["id"]
        resp = client.post(f"/productos/{pid}/stock", headers=admin_headers, json={"cantidad": -5})
        assert resp.status_code == 400

    def test_no_auth(self, client):
        resp = client.get("/productos/")
        assert resp.status_code == 401

    def test_busqueda(self, client, admin_headers):
        client.post("/productos/", headers=admin_headers, json={"nombre": "Pipeta Frontline"})
        client.post("/productos/", headers=admin_headers, json={"nombre": "Croquetas Dog Chow"})
        resp = client.get("/productos/?busqueda=Frontline", headers=admin_headers)
        assert len(resp.json()) == 1
        assert "Frontline" in resp.json()[0]["nombre"]
