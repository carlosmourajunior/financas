from datetime import date
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APITestCase

from financas.models import Cartao, Categoria, Lancamento, criar_categorias_padrao
from financas.servicos import fatura_que_fecha_em
from importacao.leitores import FormatoDesconhecido, Tipo, ler_fatura
from importacao.leitores import itau
from importacao.servicos import confirmar, previa

ARQUIVOS = Path(__file__).parent / "arquivos"
Usuario = get_user_model()


def ler(nome):
    return (ARQUIVOS / nome).read_bytes()


def itau_exemplo():
    texto = lambda n: (ARQUIVOS / n).read_text(encoding="utf-8")  # noqa: E731
    return itau.ler_texto(texto("itau_capa.txt"), [texto("itau_coluna1.txt"), texto("itau_coluna2.txt")])


class LeitoresTests(TestCase):
    def test_nubank(self):
        f = ler_fatura(ler("Nubank_2026-08-22.csv"), "Nubank_2026-08-22.csv")
        self.assertEqual(f.banco, "Nubank")
        self.assertEqual(f.vencimento, date(2026, 8, 22))
        self.assertIsNone(f.conferida)  # o CSV não traz o total
        self.assertEqual(f.total_calculado, 144_694)
        loja = next(i for i in f.itens if i.descricao.startswith("Loja Exemplo"))
        self.assertEqual((loja.descricao, loja.parcela_atual, loja.parcela_total), ("Loja Exemplo - NuPay", 1, 3))
        amazon = next(i for i in f.itens if i.descricao == "Amazon")
        self.assertEqual((amazon.parcela_atual, amazon.parcela_total, amazon.data), (9, 12, date(2026, 7, 15)))
        tipos = {i.descricao: i.tipo for i in f.itens}
        self.assertEqual(tipos["Pagamento recebido"], Tipo.PAGAMENTO)
        self.assertEqual(tipos["Valor pendente do mês anterior"], Tipo.SALDO_ANTERIOR)
        self.assertEqual(tipos["Multa por fatura atrasada"], Tipo.ENCARGO)
        self.assertEqual(tipos['Estorno de "Pg *Restaurante" (Restaurante)'], Tipo.CREDITO)

    def test_sicredi_confere_com_o_total(self):
        f = ler_fatura(ler("sicredi.csv"), "sicredi.csv")
        self.assertEqual((f.banco, f.final, f.vencimento), ("Sicredi", "9999", date(2026, 3, 10)))
        self.assertEqual(f.total, 136_034)
        self.assertTrue(f.conferida, f.total_calculado)
        casa = next(i for i in f.itens if i.descricao == "LOJA DE CASA")
        # A data no arquivo é a da compra; a parcela 2 cai um mês depois.
        self.assertEqual((casa.data, casa.parcela_atual, casa.parcela_total), (date(2026, 2, 20), 2, 10))
        self.assertIn(Tipo.SALDO_ANTERIOR, {i.tipo for i in f.itens})

    def test_itau_confere_com_o_total(self):
        f = itau_exemplo()
        self.assertEqual((f.banco, f.final, f.vencimento, f.total), ("Itaú", "0001", date(2026, 9, 1), 74_343))
        self.assertTrue(f.conferida, f.total_calculado)
        descricoes = [i.descricao for i in f.itens]
        self.assertIn("POSTO CENTRAL", descricoes)  # linha com a marca "L" da coluna vizinha
        self.assertEqual(descricoes.count("LOJA AZUL"), 1)  # próximas faturas ficam de fora
        azul = next(i for i in f.itens if i.descricao == "LOJA AZUL")
        # 02/11 sem ano, parcela 10 de 12: compra em novembro de 2025, cobrança em agosto de 2026.
        self.assertEqual(azul.data, date(2026, 8, 2))
        self.assertEqual(next(i for i in f.itens if i.descricao == "ACADEMIA").categoria, "lazer")
        self.assertEqual(next(i for i in f.itens if i.descricao == "CREDITO POR PARCELAMENT").tipo, Tipo.CREDITO)
        self.assertIn("IOF de compras internacionais", descricoes)

    def test_formato_desconhecido(self):
        with self.assertRaises(FormatoDesconhecido):
            ler_fatura(b"coluna1;coluna2\n1;2\n", "x.csv")


class ServicosTests(TestCase):
    def setUp(self):
        self.usuario = Usuario.objects.create_user(email="a@exemplo.com", password="senha-forte-123", nome="A")
        criar_categorias_padrao(self.usuario)
        self.cartao = Cartao.objects.create(dono=self.usuario, nome="Itaú", final="0001", limite=1_000_000, dia_fechamento=24, dia_vencimento=1)

    def test_previa_prende_as_linhas_no_ciclo_e_traz_o_saldo_nao_pago(self):
        p = previa(self.cartao, itau_exemplo())
        self.assertEqual((p["ciclo"]["abre"], p["ciclo"]["fecha"], p["ciclo"]["vence"]), (date(2026, 7, 25), date(2026, 8, 24), date(2026, 9, 1)))
        self.assertTrue(all(p["ciclo"]["abre"] <= i["data"] <= p["ciclo"]["fecha"] for i in p["itens"]))
        saldo = p["itens"][0]
        self.assertEqual((saldo["tipo"], saldo["valor"]), (Tipo.SALDO_ANTERIOR, 20_000))
        # Pagamentos não viram lançamento.
        self.assertNotIn("Pagamento via conta", [i["descricao"] for i in p["itens"]])
        # Tudo que será importado soma o total da fatura do banco.
        soma = sum(i["valor"] if i["natureza"] == "despesa" else -i["valor"] for i in p["itens"])
        self.assertEqual(soma, 74_343)
        taxas = Categoria.objects.get(dono=self.usuario, nome="Taxas")
        self.assertEqual(next(i for i in p["itens"] if i["descricao"].startswith("IOF"))["categoria"], taxas.id)

    def test_confirmar_cria_parcelas_futuras_e_a_fatura_fica_igual_a_do_banco(self):
        fecha = date(2026, 8, 24)
        p = previa(self.cartao, itau_exemplo())
        confirmar(self.cartao, fecha, [i for i in p["itens"] if i["importar"]])
        self.assertEqual(fatura_que_fecha_em(self.cartao, fecha).total, 74_343)
        azul = Lancamento.objects.filter(descricao="LOJA AZUL").order_by("parcela_atual")
        self.assertEqual([l.parcela_atual for l in azul], [10, 11, 12])
        self.assertEqual(azul[2].data, date(2026, 10, 2))

    def test_importar_de_novo_substitui_e_mantem_o_que_foi_lancado_a_mao(self):
        fecha = date(2026, 8, 24)
        manual = Lancamento.objects.create(dono=self.usuario, cartao=self.cartao, descricao="Feira", valor=3_000, natureza="despesa", data=date(2026, 8, 5))
        p = previa(self.cartao, itau_exemplo())
        self.assertEqual(p["ja_importados"], 0)
        confirmar(self.cartao, fecha, [i for i in p["itens"] if i["importar"]])
        total = Lancamento.objects.count()

        de_novo = previa(self.cartao, itau_exemplo())
        self.assertGreater(de_novo["ja_importados"], 0)
        self.assertTrue(all(i["importar"] for i in de_novo["itens"]))
        r = confirmar(self.cartao, fecha, de_novo["itens"])
        self.assertGreater(r["substituidos"], 0)
        # Nada duplicado, nem as parcelas futuras; o lançamento feito à mão continua.
        self.assertEqual(Lancamento.objects.count(), total)
        self.assertEqual(fatura_que_fecha_em(self.cartao, fecha).total, 74_343 + manual.valor)
        self.assertTrue(Lancamento.objects.filter(pk=manual.pk).exists())

    def test_linha_igual_a_lancamento_feito_a_mao_vem_desmarcada(self):
        Lancamento.objects.create(dono=self.usuario, cartao=self.cartao, descricao="POSTO CENTRAL", valor=2_000, natureza="despesa", data=date(2026, 8, 21))
        p = previa(self.cartao, itau_exemplo())
        posto = next(i for i in p["itens"] if i["descricao"] == "POSTO CENTRAL")
        self.assertTrue(posto["repetido"])
        self.assertFalse(posto["importar"])

    def test_fatura_seguinte_troca_a_parcela_prevista_sem_duplicar(self):
        f = ler_fatura(ler("Nubank_2026-08-22.csv"), "Nubank_2026-08-22.csv")
        nubank = Cartao.objects.create(dono=self.usuario, nome="Nubank", limite=500_000, dia_fechamento=15, dia_vencimento=22)
        p = previa(nubank, f)
        confirmar(nubank, p["ciclo"]["fecha"], [i for i in p["itens"] if i["importar"]])
        loja = Lancamento.objects.get(descricao="Loja Exemplo - NuPay", parcela_atual=2)
        f.itens = [i for i in f.itens if i.descricao == "Loja Exemplo - NuPay"]
        f.itens[0].parcela_atual, f.itens[0].data, f.vencimento = 2, loja.data, date(2026, 9, 22)
        p = previa(nubank, f)
        confirmar(nubank, p["ciclo"]["fecha"], p["itens"])
        parcelas = Lancamento.objects.filter(descricao="Loja Exemplo - NuPay").order_by("parcela_atual")
        self.assertEqual([l.parcela_atual for l in parcelas], [1, 2, 3])


class ApiTests(APITestCase):
    def setUp(self):
        self.usuario = Usuario.objects.create_user(email="a@exemplo.com", password="senha-forte-123", nome="A")
        criar_categorias_padrao(self.usuario)
        self.client.force_authenticate(self.usuario)
        self.cartao = Cartao.objects.create(dono=self.usuario, nome="Sicredi", final="9999", limite=1_000_000, dia_fechamento=27, dia_vencimento=10)

    def enviar(self, nome, cartao=None):
        arquivo = SimpleUploadedFile(nome, ler(nome))
        return self.client.post("/api/importar/fatura/", {"arquivo": arquivo, "cartao": cartao or self.cartao.id}, format="multipart")

    def test_previa_e_confirmacao(self):
        r = self.enviar("sicredi.csv")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertTrue(r.data["conferida"])
        self.assertTrue(r.data["final_confere"])
        self.assertNotIn(0, [i["valor"] for i in r.data["itens"]])
        itens = [{**i, "data": str(i["data"])} for i in r.data["itens"] if i["importar"]]
        corpo = {"cartao": self.cartao.id, "fecha": str(r.data["ciclo"]["fecha"]), "itens": itens}
        c = self.client.post("/api/importar/fatura/confirmar/", corpo, format="json")
        self.assertEqual(c.status_code, 201, c.data)
        self.assertEqual(Lancamento.objects.filter(dono=self.usuario, descricao="LOJA DE CASA").count(), 9)  # parcelas 2 a 10
        # Importar de novo substitui em vez de duplicar.
        self.client.post("/api/importar/fatura/confirmar/", corpo, format="json")
        self.assertEqual(Lancamento.objects.filter(dono=self.usuario, descricao="LOJA DE CASA").count(), 9)
        errado = self.client.post("/api/importar/fatura/confirmar/", {**corpo, "fecha": "2026-02-13"}, format="json")
        self.assertEqual(errado.status_code, 400)

    def test_cartao_de_outro_usuario(self):
        outro = Usuario.objects.create_user(email="b@exemplo.com", password="senha-forte-123", nome="B")
        alheio = Cartao.objects.create(dono=outro, nome="X", limite=1, dia_fechamento=1, dia_vencimento=8)
        self.assertEqual(self.enviar("sicredi.csv", alheio.id).status_code, 400)

    def test_arquivo_desconhecido(self):
        arquivo = SimpleUploadedFile("x.csv", b"a;b\n1;2\n")
        r = self.client.post("/api/importar/fatura/", {"arquivo": arquivo, "cartao": self.cartao.id}, format="multipart")
        self.assertEqual(r.status_code, 400)
        self.assertIn("arquivo", r.data)
