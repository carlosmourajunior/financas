from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APITestCase

from .models import Cartao, Conta, Emprestimo, Lancamento, Recorrencia
from .servicos import (
    fatura_aberta,
    fim_do_mes,
    gerar_ocorrencias,
    resumo,
    somar_meses,
)

Usuario = get_user_model()


def criar_usuario(email="a@exemplo.com"):
    return Usuario.objects.create_user(email=email, password="senha-forte-123", nome="Teste")


class DatasTests(TestCase):
    def test_somar_meses_respeita_fim_do_mes(self):
        self.assertEqual(somar_meses(date(2026, 1, 31), 1), date(2026, 2, 28))
        self.assertEqual(somar_meses(date(2026, 11, 15), 3), date(2027, 2, 15))
        self.assertEqual(somar_meses(date(2026, 3, 10), -3), date(2025, 12, 10))


class ApiBase(APITestCase):
    def setUp(self):
        self.usuario = criar_usuario()
        self.client.force_authenticate(self.usuario)
        self.conta = Conta.objects.create(dono=self.usuario, nome="Corrente", saldo_inicial=100_000)
        self.cartao = Cartao.objects.create(dono=self.usuario, nome="Visa", final="4321", limite=600_000, dia_fechamento=3, dia_vencimento=10)

    def lancar(self, **dados):
        base = {"descricao": "Teste", "valor": 10_000, "natureza": "despesa", "data": str(date.today())}
        base.update(dados)
        return self.client.post("/api/lancamentos/", base, format="json")


class IsolamentoTests(ApiBase):
    def test_um_usuario_nao_ve_dados_do_outro(self):
        self.lancar(conta=self.conta.id)
        outro = criar_usuario("b@exemplo.com")
        self.client.force_authenticate(outro)
        self.assertEqual(self.client.get("/api/lancamentos/").data["count"], 0)
        self.assertEqual(self.client.get("/api/contas/").data["count"], 0)
        self.assertEqual(self.client.get(f"/api/contas/{self.conta.id}/").status_code, 404)

    def test_nao_aceita_conta_de_outro_usuario(self):
        outro = criar_usuario("b@exemplo.com")
        conta_alheia = Conta.objects.create(dono=outro, nome="Alheia")
        r = self.lancar(conta=conta_alheia.id)
        self.assertEqual(r.status_code, 400)
        self.assertIn("conta", r.data)


class LancamentoTests(ApiBase):
    def test_parcelada_divide_o_total_e_guarda_os_centavos_na_primeira(self):
        r = self.lancar(descricao="Notebook", valor=100_000, tipo="parcelada", parcelas=3, cartao=self.cartao.id)
        self.assertEqual(r.status_code, 201, r.data)
        parcelas = list(Lancamento.objects.filter(grupo=r.data["grupo"]).order_by("parcela_atual"))
        self.assertEqual([p.valor for p in parcelas], [33_334, 33_333, 33_333])
        self.assertEqual(sum(p.valor for p in parcelas), 100_000)
        self.assertEqual(parcelas[2].data, somar_meses(date.today(), 2))
        self.assertEqual(parcelas[1].parcela_total, 3)

    def test_parcelada_exige_numero_de_parcelas(self):
        r = self.lancar(tipo="parcelada")
        self.assertEqual(r.status_code, 400)

    def test_conta_e_cartao_juntos_nao_pode(self):
        r = self.lancar(conta=self.conta.id, cartao=self.cartao.id)
        self.assertEqual(r.status_code, 400)

    def test_lancamento_futuro_fica_como_nao_pago(self):
        r = self.lancar(conta=self.conta.id, data=str(date.today() + timedelta(days=3)))
        self.assertFalse(r.data["pago"])

    def test_recorrente_gera_ocorrencias_sem_duplicar(self):
        inicio = somar_meses(date.today(), -2)
        r = self.lancar(descricao="Aluguel", valor=220_000, tipo="recorrente", conta=self.conta.id, data=str(inicio))
        self.assertEqual(r.status_code, 201, r.data)
        rec = Recorrencia.objects.get()
        self.assertEqual(rec.ocorrencias.count(), 3)  # dois meses atrás, mês passado e este
        gerar_ocorrencias(self.usuario, date.today())
        self.assertEqual(rec.ocorrencias.count(), 3)
        mes = somar_meses(date.today(), 1).strftime("%Y-%m")
        self.client.get(f"/api/lancamentos/?mes={mes}")
        self.assertEqual(rec.ocorrencias.count(), 4)

    def test_filtro_por_mes(self):
        self.lancar(data="2026-01-15")
        self.lancar(data="2026-02-15")
        r = self.client.get("/api/lancamentos/?mes=2026-02")
        self.assertEqual(r.data["count"], 1)
        self.assertEqual(self.client.get("/api/lancamentos/?mes=fevereiro").status_code, 400)


class FaturaTests(TestCase):
    def setUp(self):
        self.usuario = criar_usuario()
        self.cartao = Cartao.objects.create(dono=self.usuario, nome="Visa", limite=600_000, dia_fechamento=3, dia_vencimento=10)

    def compra(self, data, valor):
        Lancamento.objects.create(dono=self.usuario, cartao=self.cartao, descricao="x", valor=valor, natureza="despesa", data=data)

    def test_fatura_aberta_pega_so_compras_do_ciclo(self):
        self.compra(date(2026, 10, 3), 1_000)  # fatura que fechou em 03/10
        self.compra(date(2026, 10, 4), 2_000)
        self.compra(date(2026, 11, 3), 4_000)
        self.compra(date(2026, 11, 4), 8_000)  # próxima fatura
        f = fatura_aberta(self.cartao, date(2026, 10, 27))
        self.assertEqual((f.abre, f.fecha, f.vence), (date(2026, 10, 4), date(2026, 11, 3), date(2026, 11, 10)))
        self.assertEqual(f.total, 6_000)

    def test_vencimento_antes_do_fechamento_vai_para_o_mes_seguinte(self):
        self.cartao.dia_fechamento, self.cartao.dia_vencimento = 25, 5
        f = fatura_aberta(self.cartao, date(2026, 10, 27))
        self.assertEqual((f.fecha, f.vence), (date(2026, 11, 25), date(2026, 12, 5)))


class ResumoTests(ApiBase):
    def test_livre_para_gastar_desconta_o_que_ainda_vence(self):
        hoje = date.today()
        self.lancar(natureza="receita", valor=500_000, conta=self.conta.id, data=str(hoje.replace(day=1)))
        self.lancar(descricao="Mercado", valor=30_000, conta=self.conta.id, data=str(hoje))
        a_vencer = Lancamento.objects.create(
            dono=self.usuario, conta=self.conta, descricao="Condomínio", valor=68_000, natureza="despesa", data=fim_do_mes(hoje), pago=False
        )
        r = resumo(self.usuario, hoje)
        self.assertEqual(r["saldo_em_conta"], 100_000 + 500_000 - 30_000)
        self.assertGreaterEqual(r["a_vencer"], a_vencer.valor)
        self.assertEqual(r["livre_para_gastar"], r["saldo_em_conta"] - r["a_vencer"])
        self.assertEqual(r["entrou"], 500_000)
        self.assertIn({"dia": a_vencer.data.day, "nome": "Condomínio", "valor": 68_000, "paga": False}, r["contas_do_mes"])

    def test_emprestimos_no_resumo(self):
        e = Emprestimo.objects.create(
            dono=self.usuario, direcao="devo", nome="Pessoal", valor_total=1_000_000, parcela_valor=61_240, data=date(2026, 1, 1)
        )
        self.client.post("/api/pagamentos-emprestimo/", {"emprestimo": e.id, "valor": 200_000, "data": "2026-02-01"}, format="json")
        Emprestimo.objects.create(dono=self.usuario, direcao="devem", nome="João", valor_total=80_000, data=date(2026, 9, 10))
        r = self.client.get("/api/resumo/")
        self.assertEqual(r.status_code, 200)
        emp = r.data["emprestimos"]
        self.assertEqual(emp["devo_total"], 800_000)
        self.assertEqual(emp["devo_por_mes"], 61_240)
        self.assertEqual(emp["devem_pessoas"], ["João"])


class SaldoComFaturaTests(ApiBase):
    def test_fatura_vencida_sai_do_saldo(self):
        # Fatura fechada em 03/09 venceu em 10/09: já saiu da conta em 27/10.
        Lancamento.objects.create(dono=self.usuario, cartao=self.cartao, descricao="Antiga", valor=5_000, natureza="despesa", data=date(2026, 9, 1))
        # Fatura aberta (fecha 03/11): ainda não saiu.
        Lancamento.objects.create(dono=self.usuario, cartao=self.cartao, descricao="Nova", valor=7_000, natureza="despesa", data=date(2026, 10, 20))
        r = resumo(self.usuario, date(2026, 10, 27))
        self.assertEqual(r["saldo_em_conta"], 100_000 - 5_000)


class DetalheCartaoTests(ApiBase):
    def test_detalhe_mostra_fatura_proximas_e_parcelas(self):
        self.lancar(descricao="Notebook", valor=100_000, tipo="parcelada", parcelas=4, cartao=self.cartao.id)
        r = self.client.get(f"/api/cartoes/{self.cartao.id}/detalhe/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["fatura"]["total"], 25_000)
        self.assertEqual(len(r.data["proximas"]), 3)
        self.assertEqual([p["total"] for p in r.data["proximas"]], [25_000, 25_000, 25_000])
        self.assertEqual(r.data["parcelas"][0]["atual"], 1)
        self.assertEqual(r.data["parcelas"][0]["total"], 4)
        self.assertEqual(r.data["disponivel"], 600_000 - 100_000)

    def test_detalhe_de_cartao_alheio_e_404(self):
        outro = criar_usuario("b@exemplo.com")
        self.client.force_authenticate(outro)
        self.assertEqual(self.client.get(f"/api/cartoes/{self.cartao.id}/detalhe/").status_code, 404)
