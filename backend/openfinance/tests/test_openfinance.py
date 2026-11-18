from datetime import date
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import override_settings
from rest_framework.test import APITestCase

from financas.models import Cartao, Categoria, Conta, Lancamento, criar_categorias_padrao
from openfinance import conversao, pluggy
from openfinance.models import Vinculo

Usuario = get_user_model()

LIGADO = {
    "PLUGGY_CLIENT_ID": "id",
    "PLUGGY_CLIENT_SECRET": "segredo",
    "PLUGGY_ITEM_IDS": ["item-1"],
    "PLUGGY_USUARIOS": ["eu@exemplo.com"],
}

CONTAS = {
    "results": [
        {"id": "cc-1", "type": "BANK", "subtype": "CHECKING_ACCOUNT", "name": "Nu Pagamentos S.A. - Instituição de Pagamento", "number": "1234-5", "balance": 1520.35},
        {
            "id": "cartao-1",
            "type": "CREDIT",
            "subtype": "CREDIT_CARD",
            "name": "platinum",
            "number": "5555",
            "balance": 300,
            "creditData": {"creditLimit": 5000, "balanceDueDate": "2026-11-15T00:00:00.000Z", "balanceCloseDate": "2026-11-08T00:00:00.000Z"},
        },
    ]
}

FATURAS = {
    "page": 1,
    "totalPages": 1,
    "results": [
        {"id": "fat-out", "dueDate": "2026-10-15T00:00:00.000Z", "billClosingDate": "2026-10-08T00:00:00.000Z", "totalAmount": 450.9},
    ],
}


def tx(id, data, descricao, valor, tipo="DEBIT", **extra):
    return {"id": id, "date": f"{data}T12:00:00.000Z", "description": descricao, "amount": valor, "type": tipo, "status": "POSTED", **extra}


TRANSACOES_CARTAO = [
    tx("t1", "2026-09-20", "Supermercado Bom Preço", 200.5, category="Groceries", creditCardMetadata={"billId": "fat-out"}),
    tx(
        "t2",
        "2026-09-25",
        "Loja de Sapatos 03/10",
        100,
        creditCardMetadata={"billId": "fat-out", "installmentNumber": 3, "totalInstallments": 10},
    ),
    tx("t3", "2026-09-28", "IOF compra internacional", 150.4, creditCardMetadata={"billId": "fat-out"}),
    tx("t4", "2026-09-30", "Pagamento recebido", -800, tipo="CREDIT", creditCardMetadata={"billId": "fat-out"}),
    tx("t5", "2026-10-20", "Padaria do Zé", 30, status="PENDING"),
]

TRANSACOES_CONTA = [
    tx("m1", "2026-11-01", "Pix enviado", 85.9, paymentData={"receiver": {"name": "Maria Exemplo"}, "paymentMethod": "PIX"}),
    tx("m2", "2026-11-03", "Pix recebido", 1000, tipo="CREDIT", paymentData={"payer": {"name": "Empresa X"}}),
    tx("m3", "2026-11-05", "Agendamento boleto", 50, status="PENDING"),
]


def api_falsa(caminho, **params):
    if caminho == "/accounts":
        return CONTAS
    if caminho.startswith("/items/"):
        # Com o MeuPluggy o conector é sempre ele, não o banco.
        return {"id": caminho.split("/")[-1], "connector": {"name": "MeuPluggy"}}
    if caminho == "/bills":
        return FATURAS
    if caminho == "/v2/transactions":
        lista = TRANSACOES_CARTAO if params["accountId"] == "cartao-1" else TRANSACOES_CONTA
        return {"results": [t for t in lista if params["dateFrom"] <= t["date"][:10] <= params["dateTo"]], "next": None}
    raise AssertionError(caminho)


class ConversaoTests(APITestCase):
    def test_item_da_fatura_tira_a_parcela_da_descricao_e_ignora_pagamento(self):
        i = conversao.item_da_fatura(TRANSACOES_CARTAO[1])
        self.assertEqual((i.descricao, i.valor, i.parcela_atual, i.parcela_total), ("Loja de Sapatos", 10_000, 3, 10))
        self.assertIsNone(conversao.item_da_fatura(TRANSACOES_CARTAO[3]))
        self.assertEqual(conversao.item_da_fatura(TRANSACOES_CARTAO[0]).categoria, "supermercado")

    def test_movimento_usa_o_nome_de_quem_recebeu_e_o_sinal_do_tipo(self):
        m = conversao.movimento(TRANSACOES_CONTA[0])
        self.assertEqual((m.descricao, m.origem, m.valor, m.documento), ("Maria Exemplo", "Pix enviado", -8_590, "m1"))
        self.assertEqual(conversao.movimento(TRANSACOES_CONTA[1]).valor, 100_000)

    def test_extrato_deixa_pendentes_de_fora(self):
        self.assertEqual(len(conversao.extrato("BB", TRANSACOES_CONTA).itens), 2)

    def test_centavos_sem_erro_de_ponto_flutuante(self):
        self.assertEqual(pluggy.centavos(0.1 + 0.2), 30)
        self.assertEqual(pluggy.centavos(-1520.35), -152_035)


class DesligadoTests(APITestCase):
    def setUp(self):
        self.usuario = Usuario.objects.create_user(email="eu@exemplo.com", password="senha-forte-123")
        self.client.force_authenticate(self.usuario)

    def test_sem_credenciais_o_modulo_some(self):
        r = self.client.get("/api/openfinance/")
        self.assertEqual(r.json(), {"ativo": False, "contas": []})
        self.assertEqual(self.client.post("/api/openfinance/extrato/", {}, format="json").status_code, 403)

    @override_settings(**LIGADO)
    def test_outro_usuario_da_instancia_nao_ve_as_contas(self):
        outro = Usuario.objects.create_user(email="outro@exemplo.com", password="senha-forte-123")
        self.client.force_authenticate(outro)
        self.assertEqual(self.client.get("/api/openfinance/").json()["ativo"], False)
        self.assertEqual(self.client.get("/api/openfinance/faturas/?pluggy=cartao-1").status_code, 403)


@override_settings(**LIGADO)
@patch("openfinance.pluggy._get", side_effect=api_falsa)
class LigadoTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.usuario = Usuario.objects.create_user(email="Eu@Exemplo.com", password="senha-forte-123", nome="Eu Exemplo")
        criar_categorias_padrao(self.usuario)
        self.client.force_authenticate(self.usuario)
        self.conta = Conta.objects.create(dono=self.usuario, nome="BB")
        self.cartao = Cartao.objects.create(dono=self.usuario, nome="Nubank", final="5555", limite=500_000, dia_fechamento=8, dia_vencimento=15)

    def test_estado_lista_as_contas(self, _):
        r = self.client.get("/api/openfinance/").json()
        self.assertTrue(r["ativo"])
        self.assertEqual([(c["id"], c["tipo"], c["saldo"]) for c in r["contas"]], [("cc-1", "BANK", 152_035), ("cartao-1", "CREDIT", 30_000)])

    def test_fatura_fechada_vira_previa_e_confirma_pela_rota_de_sempre(self, _):
        faturas = self.client.get("/api/openfinance/faturas/?pluggy=cartao-1").json()
        self.assertEqual(faturas, [{"id": "fat-out", "vence": "2026-10-15", "total": 45_090}])

        r = self.client.post("/api/openfinance/fatura/", {"cartao": self.cartao.id, "pluggy": "cartao-1", "fatura": "fat-out"}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        p = r.json()
        self.assertEqual(p["ciclo"]["fecha"], "2026-10-08")
        self.assertEqual(p["total_lido"], 45_090)
        self.assertTrue(p["conferida"])
        self.assertTrue(p["final_confere"])
        # Pagamento da fatura anterior fica de fora; a compra da fatura aberta também.
        self.assertEqual([i["descricao"] for i in p["itens"]], ["Supermercado Bom Preço", "Loja de Sapatos", "IOF compra internacional"])
        mercado = Categoria.objects.get(dono=self.usuario, nome="Alimentação")
        self.assertEqual(p["itens"][0]["categoria"], mercado.id)
        self.assertEqual(Vinculo.objects.get(cartao=self.cartao).pluggy_conta, "cartao-1")

        r = self.client.post("/api/importar/fatura/confirmar/", {"cartao": self.cartao.id, "fecha": p["ciclo"]["fecha"], "itens": p["itens"]}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        # 2 únicas + parcela 3 e as 7 seguintes.
        self.assertEqual(Lancamento.objects.filter(cartao=self.cartao).count(), 10)

    def test_fatura_aberta(self, _):
        with patch("openfinance.views.date") as d:
            d.today.return_value = date(2026, 10, 25)
            d.fromisoformat = date.fromisoformat
            r = self.client.post("/api/openfinance/fatura/", {"cartao": self.cartao.id, "pluggy": "cartao-1"}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual([i["descricao"] for i in r.json()["itens"]], ["Padaria do Zé"])

    def test_extrato_vira_previa_e_nao_duplica(self, _):
        corpo = {"conta": self.conta.id, "pluggy": "cc-1", "desde": "2026-11-01", "ate": "2026-11-10"}
        p = self.client.post("/api/openfinance/extrato/", corpo, format="json").json()
        self.assertEqual([(i["descricao"], i["valor"], i["natureza"]) for i in p["itens"]], [("Maria Exemplo", 8_590, "despesa"), ("Empresa X", 100_000, "receita")])
        r = self.client.post("/api/importar/extrato/confirmar/", {"conta": self.conta.id, "itens": p["itens"]}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(Lancamento.objects.filter(conta=self.conta).count(), 2)
        # Buscar de novo: as mesmas linhas vêm desmarcadas como já importadas.
        p = self.client.post("/api/openfinance/extrato/", corpo, format="json").json()
        self.assertEqual([i["importar"] for i in p["itens"]], [False, False])

    def test_tipo_de_conta_errado(self, _):
        r = self.client.post("/api/openfinance/extrato/", {"conta": self.conta.id, "pluggy": "cartao-1", "desde": "2026-11-01"}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_cartao_de_outro_usuario(self, _):
        outro = Usuario.objects.create_user(email="x@exemplo.com", password="senha-forte-123")
        alheio = Cartao.objects.create(dono=outro, nome="X", limite=1, dia_fechamento=8, dia_vencimento=15)
        r = self.client.post("/api/openfinance/fatura/", {"cartao": alheio.id, "pluggy": "cartao-1"}, format="json")
        self.assertEqual(r.status_code, 400)


@override_settings(**LIGADO)
@patch("openfinance.pluggy._get", side_effect=api_falsa)
class TrazerContasTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.usuario = Usuario.objects.create_user(email="eu@exemplo.com", password="senha-forte-123")
        self.client.force_authenticate(self.usuario)

    def test_cria_conta_e_cartao_e_nao_repete(self, _):
        r = self.client.post("/api/openfinance/trazer-contas/")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json(), {"contas": ["Nubank"], "cartoes": ["Nubank Platinum 5555"]})
        conta = Conta.objects.get(dono=self.usuario)
        self.assertEqual((conta.saldo_inicial, conta.tipo), (152_035, "corrente"))
        cartao = Cartao.objects.get(dono=self.usuario)
        self.assertEqual((cartao.final, cartao.limite, cartao.dia_fechamento, cartao.dia_vencimento), ("5555", 500_000, 8, 15))
        self.assertEqual(Vinculo.objects.get(conta=conta).pluggy_conta, "cc-1")
        # O estado já mostra cada conta da Pluggy ligada à do app.
        estado = self.client.get("/api/openfinance/").json()["contas"]
        self.assertEqual([(c["conta"], c["cartao"]) for c in estado], [(conta.id, None), (None, cartao.id)])

        r = self.client.post("/api/openfinance/trazer-contas/")
        self.assertEqual(r.json(), {"contas": [], "cartoes": []})
        self.assertEqual(Conta.objects.filter(dono=self.usuario).count(), 1)

    def test_conta_ja_ligada_a_mao_nao_duplica(self, _):
        conta = Conta.objects.create(dono=self.usuario, nome="Minha conta")
        Vinculo.objects.create(dono=self.usuario, conta=conta, pluggy_conta="cc-1")
        self.assertEqual(self.client.post("/api/openfinance/trazer-contas/").json()["contas"], [])

    def test_renomeia_o_que_veio_com_o_nome_cru(self, _):
        cartao = Cartao.objects.create(dono=self.usuario, nome="platinum", limite=1, dia_fechamento=8, dia_vencimento=15)
        Vinculo.objects.create(dono=self.usuario, cartao=cartao, pluggy_conta="cartao-1")
        renomeado = Conta.objects.create(dono=self.usuario, nome="Minha conta")
        Vinculo.objects.create(dono=self.usuario, conta=renomeado, pluggy_conta="cc-1")
        self.client.post("/api/openfinance/trazer-contas/")
        cartao.refresh_from_db()
        renomeado.refresh_from_db()
        self.assertEqual((cartao.nome, renomeado.nome), ("Nubank Platinum", "Minha conta"))

    def test_outro_usuario_nao_pode(self, _):
        outro = Usuario.objects.create_user(email="outro@exemplo.com", password="senha-forte-123")
        self.client.force_authenticate(outro)
        self.assertEqual(self.client.post("/api/openfinance/trazer-contas/").status_code, 403)


class NomeDoBancoTests(APITestCase):
    def test_banco_pelo_numero_de_transferencia_e_pelo_nome(self):
        self.assertEqual(pluggy._banco_do_numero("0341/0001/12345-6"), "Itaú")
        self.assertEqual(pluggy._banco_no_texto("ITAÚ UNIBANCO S.A."), "Itaú")
        self.assertEqual(pluggy._banco_no_texto("platinum"), "")

    def test_nome_com_banco(self):
        C = pluggy.ContaPluggy
        self.assertEqual(pluggy.nome_com_banco(C("1", "BANK", "Banco Inter S.A.", "", 0, subtipo="SAVINGS_ACCOUNT", banco="Inter"), "Conta"), "Inter Poupança")
        self.assertEqual(pluggy.nome_com_banco(C("2", "CREDIT", "Black", "", 0, banco="Itaú"), "Cartão"), "Itaú Black")
        self.assertEqual(pluggy.nome_com_banco(C("3", "CREDIT", "Nubank Ultravioleta", "", 0, banco="Nubank"), "Cartão"), "Nubank Ultravioleta")
        # Sem conta corrente no item, a bandeira identifica o cartão.
        self.assertEqual(pluggy.nome_com_banco(C("4", "CREDIT", "platinum", "", 0, banco="Mastercard"), "Cartão"), "Mastercard Platinum")
