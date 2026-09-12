class TestLegalPages:
    def test_terminos_beta_responde_200(self, client):
        resp = client.get("/legal/terminos-beta")
        assert resp.status_code == 200

    def test_terminos_beta_contiene_clausulas(self, client):
        resp = client.get("/legal/terminos-beta")
        assert "Beta" in resp.text
        assert "responsabilidad" in resp.text
        assert "privacidad" in resp.text
        assert "Naturaleza del software en etapa Beta" in resp.text

    def test_terminos_beta_no_muestra_navbar_staff(self, client):
        resp = client.get("/legal/terminos-beta")
        assert "menu-btn" not in resp.text
        assert "/page/turnos" not in resp.text

    def test_terminos_beta_footer_contiene_enlace(self, client):
        resp = client.get("/legal/terminos-beta")
        assert resp.text.count("/legal/terminos-beta") >= 1

    def test_login_muestra_enlace_terminos(self, client):
        resp = client.get("/login")
        assert resp.status_code == 200
        assert "/legal/terminos-beta" in resp.text