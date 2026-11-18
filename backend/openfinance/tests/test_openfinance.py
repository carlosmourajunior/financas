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
        self.assertEqual(r.json(), {"contas": ["Nubank"], "cartoes": ["Nubank Platinum 5555"], "renomeadas": [], "conferir_datas": []})
        conta = Conta.objects.get(dono=self.usuario)
        self.assertEqual((conta.saldo_inicial, conta.tipo), (152_035, "corrente"))
        cartao = Cartao.objects.get(dono=self.usuario)
        self.assertEqual((cartao.final, cartao.limite, cartao.dia_fechamento, cartao.dia_vencimento), ("5555", 500_000, 8, 15))
        self.assertEqual(Vinculo.objects.get(conta=conta).pluggy_conta, "cc-1")
        # O estado já mostra cada conta da Pluggy ligada à do app.
        estado = self.client.get("/api/openfinance/").json()["contas"]
        self.assertEqual([(c["conta"], c["cartao"]) for c in estado], [(conta.id, None), (None, cartao.id)])

        r = self.client.post("/api/openfinance/trazer-contas/")
        self.assertEqual(r.json(), {"contas": [], "cartoes": [], "renomeadas": [], "conferir_datas": []})
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


# Como vieram as contas reais: BB com três contas de mesmo nome e cartões sem datas; Itaú com fatura.
CONTAS_REAIS = {
    "item-bb": [
        {"id": "bb1", "type": "BANK", "subtype": "CHECKING_ACCOUNT", "name": "BANCO DO BRASIL S/A", "number": "12345-6", "balance": 10,
         "bankData": {"transferNumber": "001/1234/12345-6"}},
        {"id": "bb2", "type": "BANK", "subtype": "CHECKING_ACCOUNT", "name": "BANCO DO BRASIL S/A", "number": "98765-4", "balance": 0},
        {"id": "bb3", "type": "BANK", "subtype": "SAVINGS_ACCOUNT", "name": "BANCO DO BRASIL S/A", "number": "555-1", "balance": 0},
        {"id": "bbc1", "type": "CREDIT", "subtype": "CREDIT_CARD", "name": "OUROCARD PLATINUM VISA", "number": "5085", "balance": 0, "creditData": {}},
        {"id": "bbc2", "type": "CREDIT", "subtype": "CREDIT_CARD", "name": "OUROCARD PLATINUM VISA", "number": "0099", "balance": 0, "creditData": {}},
    ],
    "item-itau": [
        {"id": "it1", "type": "BANK", "subtype": "CHECKING_ACCOUNT", "name": "Itau", "number": "1", "balance": 0},
        {"id": "itc1", "type": "CREDIT", "subtype": "CREDIT_CARD", "name": "AZUL ITAU VISA INFINITE", "number": "4321", "balance": 0, "creditData": {}},
    ],
}


def api_real(caminho, **params):
    if caminho == "/accounts":
        return {"results": CONTAS_REAIS[params["itemId"]]}
    if caminho.startswith("/items/"):
        return {"connector": {"name": "MeuPluggy"}}
    if caminho == "/bills":
        faturas = {"itc1": [{"id": "f1", "dueDate": "2026-11-03T00:00:00Z", "billClosingDate": "2026-10-24T00:00:00Z"}]}
        return {"results": faturas.get(params["accountId"], []), "totalPages": 1}
    raise AssertionError(caminho)


@override_settings(**{**LIGADO, "PLUGGY_ITEM_IDS": ["item-bb", "item-itau"]})
@patch("openfinance.pluggy._get", side_effect=api_real)
class ContasReaisTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.usuario = Usuario.objects.create_user(email="eu@exemplo.com", password="senha-forte-123")
        self.client.force_authenticate(self.usuario)

    def test_nomes_e_datas(self, _):
        r = self.client.post("/api/openfinance/trazer-contas/").json()
        self.assertEqual(r["contas"], ["Banco do Brasil 12345-6", "Banco do Brasil 98765-4", "Banco do Brasil Poupança", "Itaú"])
        self.assertEqual(r["cartoes"], ["Banco do Brasil Ourocard Platinum Visa 5085", "Banco do Brasil Ourocard Platinum Visa 0099", "Itaú Azul Visa Infinite 4321"])
        # O Itaú tirou as datas da última fatura; o BB não informou nenhuma: não inventa, pede para conferir.
        azul = Cartao.objects.get(final="4321")
        self.assertEqual((azul.dia_fechamento, azul.dia_vencimento), (24, 3))
        self.assertEqual(len(r["conferir_datas"]), 2)
        estado = {c["id"]: c for c in self.client.get("/api/openfinance/").json()["contas"]}
        self.assertTrue(estado["bbc1"]["conferir_datas"])
        self.assertFalse(estado["itc1"]["conferir_datas"])

        ouro = Cartao.objects.get(final="5085")
        resp = self.client.post("/api/openfinance/datas-conferidas/", {"cartao": ouro.id, "dia_fechamento": 5, "dia_vencimento": 12}, format="json")
        self.assertEqual(resp.status_code, 200, resp.content)
        ouro.refresh_from_db()
        self.assertEqual((ouro.dia_fechamento, ouro.dia_vencimento), (5, 12))
        self.assertFalse(Vinculo.objects.get(cartao=ouro).conferir_datas)

    def test_melhora_o_que_a_versao_anterior_criou(self, _):
        # Como ficou na versão anterior: nome cru ou banco repetido, dias inventados, sem nome_dado.
        conta = Conta.objects.create(dono=self.usuario, nome="Itaú Itau")
        Vinculo.objects.create(dono=self.usuario, conta=conta, pluggy_conta="it1")
        bb = Conta.objects.create(dono=self.usuario, nome="BANCO DO BRASIL S/A")
        Vinculo.objects.create(dono=self.usuario, conta=bb, pluggy_conta="bb1")
        azul = Cartao.objects.create(dono=self.usuario, nome="Itaú AZUL ITAU VISA INFINITE", limite=1, dia_fechamento=3, dia_vencimento=10)
        Vinculo.objects.create(dono=self.usuario, cartao=azul, pluggy_conta="itc1")
        ouro = Cartao.objects.create(dono=self.usuario, nome="Banco do Brasil OUROCARD PLATINUM VISA", limite=1, dia_fechamento=3, dia_vencimento=10)
        Vinculo.objects.create(dono=self.usuario, cartao=ouro, pluggy_conta="bbc1")

        r = self.client.post("/api/openfinance/trazer-contas/").json()
        for obj in (conta, bb, azul, ouro):
            obj.refresh_from_db()
        self.assertEqual((conta.nome, bb.nome), ("Itaú", "Banco do Brasil 12345-6"))
        self.assertEqual((azul.nome, azul.final, azul.dia_fechamento, azul.dia_vencimento), ("Itaú Azul Visa Infinite", "4321", 24, 3))
        self.assertEqual((ouro.nome, ouro.final), ("Banco do Brasil Ourocard Platinum Visa", "5085"))
        self.assertTrue(Vinculo.objects.get(cartao=ouro).conferir_datas)
        self.assertEqual(len(r["renomeadas"]), 4)
        # Renomeado pelo usuário depois: fica.
        conta.nome = "Conta salário"
        conta.save()
        self.client.post("/api/openfinance/trazer-contas/")
        conta.refresh_from_db()
        self.assertEqual(conta.nome, "Conta salário")


@override_settings(**LIGADO)
@patch("openfinance.pluggy._get", side_effect=api_falsa)
class ImportarRecentesTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.usuario = Usuario.objects.create_user(email="eu@exemplo.com", password="senha-forte-123")
        criar_categorias_padrao(self.usuario)
        self.client.force_authenticate(self.usuario)
        with patch("openfinance.pluggy._get", side_effect=api_falsa):
            self.client.post("/api/openfinance/trazer-contas/")
        self.conta = Conta.objects.get(dono=self.usuario)
        self.cartao = Cartao.objects.get(dono=self.usuario)

    def importar(self):
        import sys

        modulo = sys.modules[__name__]
        pagamento = tx("m4", "2026-11-06", "Pagamento de fatura", 450.9)
        with patch.object(modulo, "TRANSACOES_CONTA", TRANSACOES_CONTA + [pagamento]), patch("openfinance.views.date") as d:
            d.today.return_value = date(2026, 11, 12)
            d.fromisoformat = date.fromisoformat
            return self.client.post("/api/openfinance/importar-recentes/", {"dias": 60}, format="json")

    def test_cartao_fica_no_cartao_e_conta_vira_lancamento(self, _):
        r = self.importar()
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()["pulados"], [])
        # Fatura de outubro: 2 únicas + parcela 3/10 e as 7 previstas; a padaria, ainda sem fatura no
        # banco, vai para a aberta.
        self.assertEqual(Lancamento.objects.filter(cartao=self.cartao).count(), 11)
        self.assertTrue(Lancamento.objects.filter(cartao=self.cartao, descricao="Padaria do Zé").exists())
        em_conta = Lancamento.objects.filter(conta=self.conta).order_by("data")
        self.assertEqual([(l.descricao, l.natureza) for l in em_conta], [("Maria Exemplo", "despesa"), ("Empresa X", "receita")])
        # O pagamento da fatura marca a fatura como paga, não vira despesa (seria contar duas vezes).
        from financas.models import PagamentoFatura

        self.assertTrue(PagamentoFatura.objects.filter(cartao=self.cartao, valor=45_090).exists())
        # O saldo de hoje continua o do banco.
        self.conta.refresh_from_db()
        self.assertEqual(self.conta.saldo_inicial + 100_000 - 8_590 - 45_090, 152_035)

        # De novo: nada duplica.
        self.importar()
        self.assertEqual(Lancamento.objects.filter(conta=self.conta).count(), 2)
        self.assertEqual(Lancamento.objects.filter(cartao=self.cartao).count(), 11)
        saldo = self.conta.saldo_inicial
        self.conta.refresh_from_db()
        self.assertEqual(self.conta.saldo_inicial, saldo)

    def test_cartao_sem_datas_fica_de_fora(self, _):
        Vinculo.objects.filter(cartao=self.cartao).update(conferir_datas=True)
        r = self.importar().json()
        self.assertEqual(Lancamento.objects.filter(cartao=self.cartao).count(), 0)
        self.assertEqual(len(r["pulados"]), 1)


@override_settings(**{**LIGADO, "PLUGGY_ITEM_IDS": ["item-bb", "item-itau"]})
@patch("openfinance.pluggy._get", side_effect=api_real)
class CartaoDesativadoTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.usuario = Usuario.objects.create_user(email="eu@exemplo.com", password="senha-forte-123")
        self.client.force_authenticate(self.usuario)

    def test_desativado_nao_volta_nem_pede_datas(self, _):
        self.client.post("/api/openfinance/trazer-contas/")
        ouro = Cartao.objects.get(final="5085")
        r = self.client.patch(f"/api/cartoes/{ouro.id}/", {"ativo": False}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        ouro.refresh_from_db()
        self.assertFalse(ouro.ativo)
        ouro.nome = "BANCO DO BRASIL S/A"  # se fosse ativo, seria renomeado
        ouro.save()

        r = self.client.post("/api/openfinance/trazer-contas/").json()
        self.assertEqual((r["cartoes"], r["renomeadas"]), ([], []))
        self.assertEqual(Cartao.objects.filter(dono=self.usuario).count(), 3)
        estado = {c["id"]: c for c in self.client.get("/api/openfinance/").json()["contas"]}
        self.assertFalse(estado["bbc1"]["conferir_datas"])
        self.assertTrue(estado["bbc2"]["conferir_datas"])

        # Reativar é o mesmo PATCH.
        self.client.patch(f"/api/cartoes/{ouro.id}/", {"ativo": True}, format="json")
        self.assertTrue(self.client.get("/api/openfinance/").json()["contas"][3]["conferir_datas"])


class ParcelasNaFaturaAbertaTests(APITestCase):
    def test_a_proxima_parcela_de_cada_compra_entra_mesmo_com_data_fora_do_ciclo(self):
        meta = lambda k, n, fat=None: {"installmentNumber": k, "totalInstallments": n, "purchaseDate": "2026-06-02", **({"billId": fat} if fat else {})}
        transacoes = [
            tx("a3", "2026-10-02", "TV 3/10", 100, creditCardMetadata=meta(3, 10, "fat-out")),
            # Sem fatura: a 4/10 (data projetada em dezembro, fora do ciclo aberto) e as seguintes.
            tx("a4", "2026-12-02", "TV 4/10", 100, status="PENDING", creditCardMetadata=meta(4, 10)),
            tx("a5", "2027-01-02", "TV 5/10", 100, status="PENDING", creditCardMetadata=meta(5, 10)),
            tx("n1", "2026-11-20", "Mercado", 50, creditCardMetadata={}),
            tx("n0", "2026-10-05", "Já na fatura", 10, creditCardMetadata={"billId": "fat-out"}),
        ]
        lida = conversao.fatura_aberta("Nubank", "", {"fat-out"}, date(2026, 10, 9), date(2026, 12, 8), date(2026, 12, 15), transacoes)
        self.assertEqual(sorted((i.descricao, i.parcela_atual) for i in lida.itens), [("Mercado", None), ("TV", 4)])
