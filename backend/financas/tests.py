from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APITestCase

from .models import Cartao, Conta, Emprestimo, Lancamento, PagamentoFatura, Recorrencia
from .servicos import (
    detalhe_cartao,
    fatura_aberta,
    fim_do_mes,
    gerar_ocorrencias,
    quitar_faturas_vencidas,
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


class PagamentoDeFaturaTests(ApiBase):
    def setUp(self):
        super().setUp()
        # Fatura fechada em 03/09 venceu em 10/09; a aberta fecha em 03/11.
        Lancamento.objects.create(dono=self.usuario, cartao=self.cartao, descricao="Antiga", valor=5_000, natureza="despesa", data=date(2026, 9, 1))
        Lancamento.objects.create(dono=self.usuario, cartao=self.cartao, descricao="Nova", valor=7_000, natureza="despesa", data=date(2026, 10, 20))

    def test_fatura_vencida_sem_pagamento_fica_vencida(self):
        r = resumo(self.usuario, date(2026, 10, 27))
        self.assertEqual(r["saldo_em_conta"], 100_000)
        self.assertEqual([(v["tipo"], v["valor"], v["data"]) for v in r["vencidas"]], [("fatura", 5_000, date(2026, 9, 10))])
        # Vencida de mês anterior também entra no que ainda vai sair.
        self.assertEqual(r["a_vencer"], 5_000)

    def test_pagar_fatura_tira_do_saldo_e_das_vencidas(self):
        r = self.client.post("/api/pagamentos-fatura/", {"cartao": self.cartao.id, "fecha": "2026-09-03"}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data["valor"], 5_000)
        r = resumo(self.usuario, date(2026, 10, 27))
        self.assertEqual(r["saldo_em_conta"], 100_000 - 5_000)
        self.assertEqual(r["vencidas"], [])
        # A mesma fatura duas vezes, ou um dia que não é de fechamento, não.
        self.assertEqual(self.client.post("/api/pagamentos-fatura/", {"cartao": self.cartao.id, "fecha": "2026-09-03"}, format="json").status_code, 400)
        self.assertEqual(self.client.post("/api/pagamentos-fatura/", {"cartao": self.cartao.id, "fecha": "2026-09-04"}, format="json").status_code, 400)

    def test_desfazer_pagamento(self):
        pid = self.client.post("/api/pagamentos-fatura/", {"cartao": self.cartao.id, "fecha": "2026-09-03"}, format="json").data["id"]
        self.assertEqual(self.client.delete(f"/api/pagamentos-fatura/{pid}/").status_code, 204)
        self.assertEqual(len(resumo(self.usuario, date(2026, 10, 27))["vencidas"]), 1)

    def test_nao_paga_fatura_de_cartao_alheio(self):
        outro = criar_usuario("b@exemplo.com")
        self.client.force_authenticate(outro)
        r = self.client.post("/api/pagamentos-fatura/", {"cartao": self.cartao.id, "fecha": "2026-09-03"}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_quitar_faturas_vencidas_registra_as_antigas(self):
        self.assertEqual(quitar_faturas_vencidas(self.cartao, date(2026, 10, 27)), 1)
        self.assertEqual(quitar_faturas_vencidas(self.cartao, date(2026, 10, 27)), 0)
        self.assertEqual(resumo(self.usuario, date(2026, 10, 27))["saldo_em_conta"], 95_000)


class FaturaAtualTests(ApiBase):
    def test_abre_na_fechada_sem_pagamento_e_depois_na_aberta(self):
        # Visa fecha dia 3 e vence dia 10. Em 05/10 a de 03/10 já fechou e vence em 10/10.
        Lancamento.objects.create(dono=self.usuario, cartao=self.cartao, descricao="Mercado", valor=5_000, natureza="despesa", data=date(2026, 9, 20))
        Lancamento.objects.create(dono=self.usuario, cartao=self.cartao, descricao="Posto", valor=7_000, natureza="despesa", data=date(2026, 10, 4))
        hoje = date(2026, 10, 5)
        d = detalhe_cartao(self.cartao, hoje)
        self.assertEqual((d["fatura"]["fecha"], d["fatura"]["total"], d["fatura"]["aberta"]), (date(2026, 10, 3), 5_000, False))
        self.assertEqual(resumo(self.usuario, hoje)["faturas"][0]["total"], 5_000)

        PagamentoFatura.objects.create(dono=self.usuario, cartao=self.cartao, fecha=date(2026, 10, 3), valor=5_000, data=hoje)
        d = detalhe_cartao(self.cartao, hoje)
        self.assertEqual((d["fatura"]["fecha"], d["fatura"]["total"], d["fatura"]["aberta"]), (date(2026, 11, 3), 7_000, True))
        self.assertEqual(resumo(self.usuario, hoje)["faturas"][0]["total"], 7_000)


class SaiuDoMesTests(ApiBase):
    def test_saiu_conta_a_fatura_inteira_no_mes_em_que_fecha(self):
        # Fecha dia 3: a fatura que fecha em 03/10 (compras de 04/09 a 03/10) é o gasto de outubro.
        Lancamento.objects.create(dono=self.usuario, cartao=self.cartao, descricao="Mercado", valor=5_000, natureza="despesa", data=date(2026, 9, 20))
        Lancamento.objects.create(dono=self.usuario, cartao=self.cartao, descricao="Estorno", valor=1_000, natureza="receita", data=date(2026, 9, 25))
        Lancamento.objects.create(dono=self.usuario, cartao=self.cartao, descricao="Posto", valor=7_000, natureza="despesa", data=date(2026, 10, 20))
        Lancamento.objects.create(dono=self.usuario, conta=self.conta, descricao="Luz", valor=9_000, natureza="despesa", data=date(2026, 10, 8))
        r = resumo(self.usuario, date(2026, 10, 27))
        self.assertEqual(r["saiu"], 9_000 + 5_000 - 1_000)
        # As categorias usam as mesmas compras; a de 20/10 é da fatura de novembro.
        self.assertEqual(sum(c["valor"] for c in r["categorias"]), 9_000 + 5_000)

    def test_parcelas_de_compras_anteriores_aparecem_separadas(self):
        self.lancar(descricao="TV", valor=40_000, tipo="parcelada", parcelas=4, cartao=self.cartao.id, data="2026-08-10")
        r = resumo(self.usuario, date(2026, 10, 27))
        self.assertEqual(r["parcelas_anteriores"], 10_000)


class ExcluirTests(ApiBase):
    def test_excluir_um_e_os_seguintes_da_recorrencia(self):
        self.lancar(descricao="Salário", valor=500_000, natureza="receita", tipo="recorrente", conta=self.conta.id, data="2026-10-05")
        self.client.get("/api/lancamentos/?mes=2026-12")  # gera até dezembro
        nov = Lancamento.objects.get(descricao="Salário", data=date(2026, 11, 5))
        # Só este: o de novembro some e não volta.
        self.assertEqual(self.client.delete(f"/api/lancamentos/{nov.id}/").status_code, 204)
        self.assertEqual(self.client.get("/api/lancamentos/?mes=2026-11").data["results"], [])
        # Este e os próximos: a partir de dezembro, para de gerar.
        dez = Lancamento.objects.get(descricao="Salário", data=date(2026, 12, 5))
        self.assertEqual(self.client.delete(f"/api/lancamentos/{dez.id}/?seguintes=1").status_code, 204)
        self.assertEqual(self.client.get("/api/lancamentos/?mes=2027-02").data["results"], [])
        self.assertEqual(len(self.client.get("/api/lancamentos/?mes=2026-10").data["results"]), 1)

    def test_resumo_preve_recebimentos_do_proximo_mes(self):
        self.lancar(descricao="Salário", valor=500_000, natureza="receita", tipo="recorrente", conta=self.conta.id, data="2026-10-05")
        self.assertEqual(resumo(self.usuario, date(2026, 10, 27))["entradas_proximo_mes"], 500_000)

    def test_excluir_parcelas_seguintes(self):
        self.lancar(descricao="TV", valor=40_000, tipo="parcelada", parcelas=4, conta=self.conta.id, data="2026-10-10")
        terceira = Lancamento.objects.get(descricao="TV", parcela_atual=3)
        self.client.delete(f"/api/lancamentos/{terceira.id}/?seguintes=1")
        self.assertEqual(sorted(Lancamento.objects.filter(descricao="TV").values_list("parcela_atual", flat=True)), [1, 2])

    def test_nao_exclui_de_outro_usuario(self):
        l = self.lancar(descricao="Luz", conta=self.conta.id).data
        self.client.force_authenticate(criar_usuario("b@exemplo.com"))
        self.assertEqual(self.client.delete(f"/api/lancamentos/{l['id']}/").status_code, 404)


class VencidasTests(ApiBase):
    def test_conta_nao_paga_vence_hoje_e_depois_fica_vencida(self):
        luz = Lancamento.objects.create(
            dono=self.usuario, conta=self.conta, descricao="Luz", valor=9_000, natureza="despesa", data=date(2026, 10, 27), pago=False
        )
        r = resumo(self.usuario, date(2026, 10, 27))
        self.assertEqual([v["id"] for v in r["vencem_hoje"]], [luz.id])
        self.assertEqual(r["vencidas"], [])
        r = resumo(self.usuario, date(2026, 10, 28))
        self.assertEqual([v["nome"] for v in r["vencidas"]], ["Luz"])

        # Marcar como pago pela API tira das vencidas e do saldo.
        self.assertEqual(self.client.patch(f"/api/lancamentos/{luz.id}/", {"pago": True}, format="json").status_code, 200)
        r = resumo(self.usuario, date(2026, 10, 28))
        self.assertEqual(r["vencidas"], [])
        self.assertEqual(r["saldo_em_conta"], 100_000 - 9_000)

    def test_receita_nao_e_conta_vencida(self):
        Lancamento.objects.create(
            dono=self.usuario, conta=self.conta, descricao="Salário", valor=9_000, natureza="receita", data=date(2026, 10, 5), pago=False
        )
        self.assertEqual(resumo(self.usuario, date(2026, 10, 27))["vencidas"], [])


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

    def test_parcela_importada_no_meio_mostra_o_numero_da_fatura(self):
        # Importada como 7 de 10: o app só tem da 7 à 10, mas está na 7, não na 1.
        grupo = Lancamento.novo_grupo()
        for k in range(7, 11):
            Lancamento.objects.create(
                dono=self.usuario, cartao=self.cartao, descricao="Comercial Tamo", valor=29_624, natureza="despesa",
                data=somar_meses(date(2026, 10, 20), k - 7), tipo="parcelada", grupo=grupo, parcela_atual=k, parcela_total=10,
            )
        p = detalhe_cartao(self.cartao, date(2026, 10, 27))["parcelas"][0]
        self.assertEqual((p["atual"], p["total"]), (7, 10))
        # Um mês depois, a da fatura aberta é a 8.
        p = detalhe_cartao(self.cartao, date(2026, 11, 27))["parcelas"][0]
        self.assertEqual(p["atual"], 8)

    def test_assinatura_no_cartao_entra_nas_proximas_faturas(self):
        self.lancar(descricao="Streaming", valor=4_000, tipo="recorrente", cartao=self.cartao.id, data=str(date.today()))
        d = detalhe_cartao(self.cartao, date.today())
        self.assertEqual([p["total"] for p in d["proximas"]], [4_000, 4_000, 4_000])

    def test_detalhe_de_cartao_alheio_e_404(self):
        outro = criar_usuario("b@exemplo.com")
        self.client.force_authenticate(outro)
        self.assertEqual(self.client.get(f"/api/cartoes/{self.cartao.id}/detalhe/").status_code, 404)


class FaturasNaListaTests(ApiBase):
    def test_lancamentos_sem_cartao_e_fatura_como_uma_linha(self):
        self.lancar(descricao="Mercado", valor=5_000, cartao=self.cartao.id, data="2026-09-20")
        self.lancar(descricao="Farmácia", valor=2_000, cartao=self.cartao.id, data="2026-10-02")
        self.lancar(descricao="Luz", valor=9_000, conta=self.conta.id, data="2026-10-08")

        r = self.client.get("/api/lancamentos/?mes=2026-10&sem_cartao=1")
        self.assertEqual([l["descricao"] for l in r.data["results"]], ["Luz"])

        # Fecha dia 3 e vence dia 10: compras de 04/09 a 03/10 vencem em 10/10.
        f = self.client.get("/api/faturas/?mes=2026-10").data
        self.assertEqual(len(f), 1)
        self.assertEqual((f[0]["total"], f[0]["compras"], str(f[0]["vence"])), (7_000, 2, "2026-10-10"))

    def test_detalhe_de_uma_fatura_passada_traz_as_compras(self):
        self.lancar(descricao="Mercado", valor=5_000, cartao=self.cartao.id, data="2026-09-20")
        r = self.client.get(f"/api/cartoes/{self.cartao.id}/detalhe/?fecha=2026-10-03")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["fatura"]["total"], 5_000)
        self.assertEqual([c["descricao"] for c in r.data["compras"]], ["Mercado"])
        self.assertEqual(str(r.data["fatura"]["anterior"]), "2026-09-03")
        self.assertEqual(self.client.get(f"/api/cartoes/{self.cartao.id}/detalhe/?fecha=ontem").status_code, 400)
