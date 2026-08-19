class TestCajaFlujo:
    def test_abrir_caja(self, client, admin_headers):
        resp = client.post("/caja/abrir", headers=admin_headers, json={
            "monto_inicial": 50000.0,
            "notas": "Apertura del dia",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["estado"] == "ABIERTA"
        assert data["monto_inicial"] == 50000.0

    def test_no_dos_cajas_abiertas(self, client, admin_headers):
        client.post("/caja/abrir", headers=admin_headers, json={"monto_inicial": 50000.0})
        resp = client.post("/caja/abrir", headers=admin_headers, json={"monto_inicial": 10000.0})
        assert resp.status_code == 400

    def test_caja_actual(self, client, admin_headers):
        client.post("/caja/abrir", headers=admin_headers, json={"monto_inicial": 30000.0})
        resp = client.get("/caja/actual", headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["estado"] == "ABIERTA"

    def test_no_caja_abierta(self, client, admin_headers):
        resp = client.get("/caja/actual", headers=admin_headers)
        assert resp.status_code == 404

    def test_agregar_movimiento(self, client, admin_headers):
        client.post("/caja/abrir", headers=admin_headers, json={"monto_inicial": 50000.0})
        resp = client.post("/caja/movimiento", headers=admin_headers, json={
            "tipo": "EGRESO",
            "monto": 5000.0,
            "descripcion": "Compra de insumos",
        })
        assert resp.status_code == 201
        assert resp.json()["tipo"] == "EGRESO"
        assert resp.json()["monto"] == 5000.0

    def test_cerrar_caja(self, client, admin_headers):
        client.post("/caja/abrir", headers=admin_headers, json={"monto_inicial": 50000.0})
        client.post("/caja/movimiento", headers=admin_headers, json={
            "tipo": "INGRESO",
            "monto": 20000.0,
            "descripcion": "Venta del dia",
        })
        client.post("/caja/movimiento", headers=admin_headers, json={
            "tipo": "EGRESO",
            "monto": 5000.0,
            "descripcion": "Gasto varios",
        })
        resp = client.post("/caja/cerrar", headers=admin_headers, json={
            "monto_final_real": 65000.0,
            "notas": "Cierre OK",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["estado"] == "CERRADA"
        assert data["monto_final_esperado"] == 65000.0
        assert data["monto_final_real"] == 65000.0

    def test_cerrar_caja_con_diferencia(self, client, admin_headers):
        client.post("/caja/abrir", headers=admin_headers, json={"monto_inicial": 50000.0})
        client.post("/caja/movimiento", headers=admin_headers, json={
            "tipo": "INGRESO",
            "monto": 10000.0,
            "descripcion": "Venta",
        })
        resp = client.post("/caja/cerrar", headers=admin_headers, json={
            "monto_final_real": 59500.0,
        })
        data = resp.json()
        assert data["monto_final_esperado"] == 60000.0
        assert data["monto_final_real"] == 59500.0

    def test_detalle_caja(self, client, admin_headers):
        r = client.post("/caja/abrir", headers=admin_headers, json={"monto_inicial": 50000.0})
        caja_id = r.json()["id"]
        client.post("/caja/movimiento", headers=admin_headers, json={
            "tipo": "INGRESO", "monto": 10000.0, "descripcion": "Venta 1",
        })
        client.post("/caja/movimiento", headers=admin_headers, json={
            "tipo": "EGRESO", "monto": 3000.0, "descripcion": "Gasto",
        })
        resp = client.get(f"/caja/{caja_id}", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["movimientos"]) == 2
        assert data["total_ingresos"] == 10000.0
        assert data["total_egresos"] == 3000.0

    def test_historial(self, client, admin_headers):
        client.post("/caja/abrir", headers=admin_headers, json={"monto_inicial": 50000.0})
        client.post("/caja/cerrar", headers=admin_headers, json={"monto_final_real": 50000.0})
        resp = client.get("/caja/historial", headers=admin_headers)
        assert resp.status_code == 200
        assert len(resp.json()) == 1
        assert resp.json()[0]["estado"] == "CERRADA"

    def test_no_auth(self, client):
        resp = client.get("/caja/actual")
        assert resp.status_code == 401
