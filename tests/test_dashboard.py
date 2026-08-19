class TestDashboard:
    def test_resumen_default(self, client, admin_headers):
        resp = client.get("/dashboard/resumen", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "fecha" in data
        assert "facturacion_total" in data
        assert "cantidad_atenciones" in data

    def test_resumen_fecha(self, client, admin_headers):
        resp = client.get("/dashboard/resumen?fecha=2026-01-15", headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["fecha"] == "2026-01-15"

    def test_metricas(self, client, admin_headers):
        resp = client.get("/dashboard/metricas", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "servicios_mas_pedidos" in data
        assert "horas_pico" in data
        assert "productos_mas_vendidos" in data

    def test_metricas_custom_dias(self, client, admin_headers):
        resp = client.get("/dashboard/metricas?dias=7", headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["periodo"] == "ultimos 7 dias"

    def test_no_auth(self, client):
        resp = client.get("/dashboard/resumen")
        assert resp.status_code == 401
