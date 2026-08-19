class TestVentasFlujo:
    def _crear_producto(self, client, admin_headers, stock=10):
        r = client.post("/productos/", headers=admin_headers, json={
            "nombre": "Producto Venta",
            "precio_venta": 1500.0,
            "stock_actual": stock,
        })
        return r.json()["id"]

    def _crear_servicio(self, client, admin_headers):
        from tests.conftest import TestingSessionLocal
        from app.models.servicio import Servicio
        db = TestingSessionLocal()
        svc = Servicio(nombre="Corte de Pelo", precio_base=5000.0, duracion_minutos=30)
        db.add(svc)
        db.commit()
        db.refresh(svc)
        sid = svc.id
        db.close()
        return sid

    def test_crear_venta_producto(self, client, admin_headers):
        pid = self._crear_producto(client, admin_headers, stock=10)
        resp = client.post("/ventas/", headers=admin_headers, json={
            "medio_pago": "efectivo",
            "detalles": [{"tipo": "PRODUCTO", "producto_id": pid, "cantidad": 2, "precio_unitario": 1500.0}],
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["total"] == 3000.0
        assert data["estado"] == "COBRADA"
        assert len(data["detalles"]) == 1

    def test_stock_se_descuenta(self, client, admin_headers):
        pid = self._crear_producto(client, admin_headers, stock=10)
        client.post("/ventas/", headers=admin_headers, json={
            "medio_pago": "efectivo",
            "detalles": [{"tipo": "PRODUCTO", "producto_id": pid, "cantidad": 3, "precio_unitario": 1500.0}],
        })
        resp = client.get(f"/productos/{pid}", headers=admin_headers)
        assert resp.json()["stock_actual"] == 7

    def test_stock_insuficiente(self, client, admin_headers):
        pid = self._crear_producto(client, admin_headers, stock=2)
        resp = client.post("/ventas/", headers=admin_headers, json={
            "medio_pago": "debito",
            "detalles": [{"tipo": "PRODUCTO", "producto_id": pid, "cantidad": 5, "precio_unitario": 1500.0}],
        })
        assert resp.status_code == 400

    def test_venta_con_descuento(self, client, admin_headers):
        pid = self._crear_producto(client, admin_headers, stock=10)
        resp = client.post("/ventas/", headers=admin_headers, json={
            "medio_pago": "credito",
            "descuento": 500.0,
            "detalles": [{"tipo": "PRODUCTO", "producto_id": pid, "cantidad": 4, "precio_unitario": 1500.0}],
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["subtotal"] == 6000.0
        assert data["descuento"] == 500.0
        assert data["total"] == 5500.0

    def test_venta_mixta_producto_servicio(self, client, admin_headers):
        pid = self._crear_producto(client, admin_headers, stock=5)
        sid = self._crear_servicio(client, admin_headers)
        resp = client.post("/ventas/", headers=admin_headers, json={
            "medio_pago": "transferencia",
            "detalles": [
                {"tipo": "PRODUCTO", "producto_id": pid, "cantidad": 1, "precio_unitario": 1500.0},
                {"tipo": "SERVICIO", "servicio_id": sid, "cantidad": 1, "precio_unitario": 5000.0},
            ],
        })
        assert resp.status_code == 201
        assert resp.json()["total"] == 6500.0

    def test_anular_venta(self, client, admin_headers):
        pid = self._crear_producto(client, admin_headers, stock=10)
        r = client.post("/ventas/", headers=admin_headers, json={
            "medio_pago": "efectivo",
            "detalles": [{"tipo": "PRODUCTO", "producto_id": pid, "cantidad": 2, "precio_unitario": 1500.0}],
        })
        vid = r.json()["id"]
        resp = client.post(f"/ventas/{vid}/anular", headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["estado"] == "ANULADA"

    def test_stock_se_repone_al_anular(self, client, admin_headers):
        pid = self._crear_producto(client, admin_headers, stock=10)
        r = client.post("/ventas/", headers=admin_headers, json={
            "medio_pago": "efectivo",
            "detalles": [{"tipo": "PRODUCTO", "producto_id": pid, "cantidad": 3, "precio_unitario": 1500.0}],
        })
        assert client.get(f"/productos/{pid}", headers=admin_headers).json()["stock_actual"] == 7
        client.post(f"/ventas/{r.json()['id']}/anular", headers=admin_headers)
        assert client.get(f"/productos/{pid}", headers=admin_headers).json()["stock_actual"] == 10

    def test_venta_sin_items(self, client, admin_headers):
        resp = client.post("/ventas/", headers=admin_headers, json={
            "medio_pago": "efectivo",
            "detalles": [],
        })
        assert resp.status_code == 400

    def test_listar_ventas(self, client, admin_headers):
        pid = self._crear_producto(client, admin_headers, stock=10)
        client.post("/ventas/", headers=admin_headers, json={
            "medio_pago": "qr",
            "detalles": [{"tipo": "PRODUCTO", "producto_id": pid, "cantidad": 1, "precio_unitario": 1000.0}],
        })
        resp = client.get("/ventas/", headers=admin_headers)
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    def test_no_auth(self, client):
        resp = client.get("/ventas/")
        assert resp.status_code == 401
