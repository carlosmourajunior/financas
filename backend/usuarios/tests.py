from rest_framework.test import APITestCase

from financas.models import Categoria


class CadastroELoginTests(APITestCase):
    def cadastrar(self, email="carlos@exemplo.com", senha="senha-forte-123"):
        return self.client.post("/api/auth/cadastro/", {"nome": "Carlos", "email": email, "senha": senha}, format="json")

    def test_cadastro_devolve_tokens_e_cria_categorias(self):
        r = self.cadastrar()
        self.assertEqual(r.status_code, 201, r.data)
        self.assertIn("access", r.data)
        self.assertEqual(r.data["usuario"]["email"], "carlos@exemplo.com")
        self.assertTrue(Categoria.objects.filter(dono__email="carlos@exemplo.com", nome="Moradia").exists())

    def test_email_repetido_nao_cadastra(self):
        self.cadastrar()
        r = self.cadastrar(email="CARLOS@exemplo.com")
        self.assertEqual(r.status_code, 400)
        self.assertIn("email", r.data)

    def test_senha_fraca_nao_cadastra(self):
        r = self.cadastrar(senha="12345678")
        self.assertEqual(r.status_code, 400)

    def test_login_e_eu(self):
        self.cadastrar()
        r = self.client.post("/api/auth/token/", {"email": "carlos@exemplo.com", "password": "senha-forte-123"}, format="json")
        self.assertEqual(r.status_code, 200)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {r.data['access']}")
        eu = self.client.get("/api/auth/eu/")
        self.assertEqual(eu.data["nome"], "Carlos")

    def test_api_exige_login(self):
        self.assertEqual(self.client.get("/api/lancamentos/").status_code, 401)
