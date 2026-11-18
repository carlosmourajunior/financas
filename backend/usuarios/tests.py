from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import override_settings
from rest_framework.test import APITestCase

from financas.models import Categoria


class CadastroELoginTests(APITestCase):
    def setUp(self):
        cache.clear()  # o cadastro tem limite por IP

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


class SegurancaDaContaTests(APITestCase):
    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_eu_nao_troca_o_email(self):
        r = self.client.post("/api/auth/cadastro/", {"nome": "A", "email": "a@exemplo.com", "senha": "senha-forte-123"}, format="json")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {r.data['access']}")
        r = self.client.patch("/api/auth/eu/", {"email": "DONO@exemplo.com", "nome": "Novo"}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["email"], "a@exemplo.com")
        self.assertEqual(r.data["nome"], "Novo")

    @override_settings(PLUGGY_CLIENT_ID="x", PLUGGY_CLIENT_SECRET="y", PLUGGY_ITEM_IDS=["i"], PLUGGY_USUARIOS=["dono@exemplo.com"])
    def test_open_finance_exige_o_email_exato(self):
        from openfinance import pluggy

        Usuario = get_user_model()
        dono = Usuario.objects.create_user(email="dono@exemplo.com", password="senha-forte-123", nome="Dono")
        outro = Usuario.objects.create_user(email="x@exemplo.com", password="senha-forte-123", nome="X")
        Usuario.objects.filter(pk=outro.pk).update(email="DONO@exemplo.com")
        outro.refresh_from_db()
        self.assertTrue(pluggy.liberado_para(dono))
        self.assertFalse(pluggy.liberado_para(outro))

    def test_login_tem_limite_por_ip(self):
        get_user_model().objects.create_user(email="b@exemplo.com", password="senha-forte-123", nome="B")
        codigos = [
            self.client.post("/api/auth/token/", {"email": "b@exemplo.com", "password": "errada"}, format="json", HTTP_CF_CONNECTING_IP="203.0.113.9").status_code
            for _ in range(11)
        ]
        self.assertEqual(codigos[:10], [401] * 10)
        self.assertEqual(codigos[10], 429)
        # outro IP continua entrando
        r = self.client.post("/api/auth/token/", {"email": "b@exemplo.com", "password": "senha-forte-123"}, format="json", HTTP_CF_CONNECTING_IP="203.0.113.10")
        self.assertEqual(r.status_code, 200)


class CadastroFechadoTests(APITestCase):
    def setUp(self):
        cache.clear()

    @override_settings(CADASTRO_ABERTO=False)
    def test_cadastro_fechado_nao_cria_conta(self):
        self.assertEqual(self.client.get("/api/auth/cadastro/").data, {"aberto": False})
        r = self.client.post("/api/auth/cadastro/", {"nome": "X", "email": "x@exemplo.com", "senha": "senha-forte-123"}, format="json")
        self.assertEqual(r.status_code, 403)
        self.assertFalse(get_user_model().objects.filter(email="x@exemplo.com").exists())

    def test_cadastro_aberto_por_padrao_fora_da_producao(self):
        self.assertEqual(self.client.get("/api/auth/cadastro/").data, {"aberto": True})

    @override_settings(CADASTRO_ABERTO=False)
    def test_comando_criar_usuario(self):
        from unittest import mock

        from django.core.management import call_command

        with mock.patch("getpass.getpass", return_value="senha-forte-123"):
            call_command("criar_usuario", email="Novo@Exemplo.com", nome="Novo", stdout=open("/dev/null", "w"))
        u = get_user_model().objects.get(email="novo@exemplo.com")
        self.assertTrue(u.check_password("senha-forte-123"))
        self.assertTrue(Categoria.objects.filter(dono=u).exists())
        r = self.client.post("/api/auth/token/", {"email": "novo@exemplo.com", "password": "senha-forte-123"}, format="json")
        self.assertEqual(r.status_code, 200)
