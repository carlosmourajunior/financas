from datetime import date
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APITestCase

from financas.models import Cartao, Categoria, Conta, Emprestimo, Lancamento, Natureza, PagamentoEmprestimo, PagamentoFatura
from importacao.leitores import FormatoDesconhecido, ler_extrato

ARQUIVO = Path(__file__).parent / "arquivos" / "extrato_bb.csv"
Usuario = get_user_model()


class LeitorBBTests(APITestCase):
    def test_le_e_confere_com_o_saldo(self):
        e = ler_extrato(ARQUIVO.read_bytes(), "extrato.csv")
        self.assertEqual((e.banco, e.saldo_anterior, e.saldo_final, e.data_final), ("Banco do Brasil", -10_000, 98_905, date(2026, 10, 30)))
        self.assertTrue(e.conferido)
        self.assertEqual(len(e.itens), 13)  # sem as linhas de saldo
        por_desc = {i.descricao: i for i in e.itens}
        # Data, hora e CPF/CNPJ saem do nome de quem pagou ou recebeu.
        self.assertEqual(por_desc["MARIA EXEMPLO"].valor, 105_000)
        self.assertEqual(por_desc["MARIA EXEMPLO"].origem, "Pix - Recebido")
        self.assertEqual(por_desc["Cobrança de I.O.F."].valor, -499)
        prof = por_desc["PROFESSOR EXEMPLO"]
        self.assertEqual((prof.parcela_atual, prof.parcela_total), (9, 10))
        self.assertIn("Pgto CDC 963821639", por_desc)
        self.assertTrue(por_desc["BB Rende Fácil"].aplicacao)

    def test_pdf_ainda_nao(self):
        with self.assertRaises(FormatoDesconhecido):
            ler_extrato(b"%PDF-1.4 ...", "extrato.pdf")


class ImportarExtratoTests(APITestCase):
    def setUp(self):
        self.usuario = Usuario.objects.create_user(email="a@exemplo.com", password="senha-forte-123", nome="Fulano de Tal Exemplo")
        self.client.force_authenticate(self.usuario)
        self.conta = Conta.objects.create(dono=self.usuario, nome="BB")
        self.taxas = Categoria.objects.create(dono=self.usuario, nome="Taxas")
        self.aulas = Categoria.objects.create(dono=self.usuario, nome="Educação")
        self.cartao = Cartao.objects.create(dono=self.usuario, nome="CartaoX", limite=1_000_000, dia_fechamento=28, dia_vencimento=5)
        self.emprestimo = Emprestimo.objects.create(
            dono=self.usuario, direcao="devo", nome="CDC", valor_total=391_190, parcela_valor=39_119, parcelas_total=10, data=date(2026, 1, 7)
        )
        self.luz = Lancamento.objects.create(
            dono=self.usuario, descricao="Conta de luz", valor=15_000, natureza=Natureza.DESPESA, data=date(2026, 10, 10), pago=False
        )

    def previa(self):
        r = self.client.post(
            "/api/importar/extrato/", {"arquivo": SimpleUploadedFile("extrato.csv", ARQUIVO.read_bytes()), "conta": self.conta.id}, format="multipart"
        )
        self.assertEqual(r.status_code, 200, r.data)
        return r.data

    def confirmar(self, itens):
        corpo = {"conta": self.conta.id, "itens": [{**i, "data": str(i["data"])} for i in itens if i["importar"]]}
        r = self.client.post("/api/importar/extrato/confirmar/", corpo, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        return r.data

    def test_previa_sugere_a_classe_de_cada_linha(self):
        p = self.previa()
        self.assertTrue(p["conferido"])
        por_desc = {i["descricao"]: i for i in p["itens"]}
        self.assertEqual(por_desc["MARIA EXEMPLO"]["classe"], "receita")
        self.assertEqual(por_desc["LOJA EXEMPLO LTDA"]["classe"], "despesa")
        self.assertEqual(por_desc["Cobrança de I.O.F."]["categoria"], self.taxas.id)
        # Aplicação automática e Pix do próprio titular são transferências e vêm desmarcadas.
        self.assertEqual((por_desc["BB Rende Fácil"]["classe"], por_desc["BB Rende Fácil"]["importar"]), ("transferencia", False))
        self.assertEqual((por_desc["FULANO DE T"]["classe"], por_desc["FULANO DE T"]["importar"]), ("transferencia", False))
        self.assertEqual((por_desc["BANCO CARTAOX S.A."]["classe"], por_desc["BANCO CARTAOX S.A."]["cartao"]), ("fatura", self.cartao.id))
        cdc = por_desc["Pgto CDC 963821639"]
        self.assertEqual((cdc["classe"], cdc["emprestimo"]), ("emprestimo", self.emprestimo.id))
        prof = por_desc["PROFESSOR EXEMPLO"]
        self.assertEqual((prof["tipo"], prof["parcela_atual"], prof["parcela_total"]), ("parcelada", 9, 10))
        # A conta de luz lançada à mão e ainda não paga é o mesmo movimento.
        self.assertEqual(por_desc["CONTA DE LUZ SA"]["lancamento"], self.luz.id)
        # Dois seguros iguais no mesmo dia são linhas diferentes.
        seguros = [i["chave"] for i in p["itens"] if i["descricao"] == "Seguro Crédito Protegido"]
        self.assertEqual(len(set(seguros)), 2)

    def test_confirmar_grava_cada_classe_e_nao_duplica(self):
        itens = self.previa()["itens"]
        for i in itens:
            if i["descricao"] == "Brasilprev":
                i["tipo"] = "recorrente"
            if i["descricao"] == "PROFESSOR EXEMPLO":
                i["categoria"] = self.aulas.id
        feito = self.confirmar(itens)
        self.assertEqual(feito["faturas"], 1)
        self.assertEqual(feito["emprestimos"], 1)
        self.assertEqual(feito["pagos"], 1)

        self.luz.refresh_from_db()
        self.assertTrue(self.luz.pago)
        self.assertEqual(self.luz.conta, self.conta)
        self.assertTrue(PagamentoFatura.objects.filter(cartao=self.cartao, valor=40_629).exists())
        self.assertTrue(PagamentoEmprestimo.objects.filter(emprestimo=self.emprestimo, valor=39_119).exists())
        prof = Lancamento.objects.filter(dono=self.usuario, descricao="PROFESSOR EXEMPLO").order_by("parcela_atual")
        self.assertEqual([p.parcela_atual for p in prof], [9, 10])
        self.assertEqual(prof[0].categoria, self.aulas)
        self.assertTrue(Lancamento.objects.get(descricao="MARIA EXEMPLO").natureza == Natureza.RECEITA)
        self.assertFalse(Lancamento.objects.filter(descricao__in=["BB Rende Fácil", "FULANO DE T"]).exists())
        brasilprev = Lancamento.objects.get(descricao="Brasilprev", data=date(2026, 10, 6))
        self.assertIsNotNone(brasilprev.recorrencia)

        total = Lancamento.objects.filter(dono=self.usuario).count()
        # Importar o mesmo extrato de novo: a prévia mostra tudo como já importado e nada se repete.
        de_novo = self.previa()["itens"]
        self.assertFalse(any(i["importar"] for i in de_novo if i["classe"] in ("despesa", "receita")))
        self.confirmar(itens)
        self.assertEqual(Lancamento.objects.filter(dono=self.usuario).count(), total)
        self.assertEqual(PagamentoFatura.objects.filter(cartao=self.cartao).count(), 1)

    def test_categoria_precisa_ser_da_mesma_natureza(self):
        itens = [i for i in self.previa()["itens"] if i["descricao"] == "MARIA EXEMPLO"]
        itens[0]["categoria"] = self.taxas.id
        r = self.client.post(
            "/api/importar/extrato/confirmar/", {"conta": self.conta.id, "itens": [{**itens[0], "data": str(itens[0]["data"])}]}, format="json"
        )
        self.assertEqual(r.status_code, 400)

    def test_conta_de_outro_usuario(self):
        outro = Usuario.objects.create_user(email="b@exemplo.com", password="senha-forte-123", nome="B")
        alheia = Conta.objects.create(dono=outro, nome="X")
        r = self.client.post(
            "/api/importar/extrato/", {"arquivo": SimpleUploadedFile("e.csv", ARQUIVO.read_bytes()), "conta": alheia.id}, format="multipart"
        )
        self.assertEqual(r.status_code, 400)
