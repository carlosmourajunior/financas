"""Cria um usuário de demonstração com os dados do protótipo: python manage.py criar_demo"""

from datetime import date

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from financas.models import Cartao, Categoria, Conta, Emprestimo, Lancamento, PagamentoEmprestimo, Recorrencia, criar_categorias_padrao
from financas.servicos import criar_parcelas, gerar_ocorrencias, somar_meses


class Command(BaseCommand):
    help = "Cria (ou recria) o usuário demo@financas.local com dados de exemplo."

    def add_arguments(self, parser):
        parser.add_argument("--senha", default="demo-financas-2026")

    @transaction.atomic
    def handle(self, *args, senha, **opts):
        Usuario = get_user_model()
        Usuario.objects.filter(email="demo@financas.local").delete()
        u = Usuario.objects.create_user(email="demo@financas.local", password=senha, nome="Carlos")
        criar_categorias_padrao(u)
        cat = {c.nome: c for c in Categoria.objects.filter(dono=u)}
        hoje = date.today()
        mes = hoje.replace(day=1)

        conta = Conta.objects.create(dono=u, nome="Conta corrente", saldo_inicial=150_000)
        visa = Cartao.objects.create(dono=u, nome="Visa", final="4321", limite=600_000, dia_fechamento=3, dia_vencimento=10)
        master = Cartao.objects.create(dono=u, nome="Master", final="8890", limite=400_000, dia_fechamento=15, dia_vencimento=22)

        def rec(descricao, valor, natureza, categoria, dia, **onde):
            Recorrencia.objects.create(
                dono=u, descricao=descricao, valor=valor, natureza=natureza, categoria=cat[categoria],
                inicio=somar_meses(mes, -2, dia), **onde,
            )

        rec("Salário", 1_050_000, "receita", "Salário", 5, conta=conta)
        rec("Aluguel", 220_000, "despesa", "Moradia", 5, conta=conta)
        rec("Condomínio", 68_000, "despesa", "Moradia", 28, conta=conta)
        rec("Academia", 12_900, "despesa", "Saúde", 20, conta=conta)
        rec("Streaming", 3_990, "despesa", "Lazer", 25, cartao=master)
        gerar_ocorrencias(u, somar_meses(mes, 1) )

        unicas = [
            ("Mercado", 31_245, "Alimentação", visa, None, 0),
            ("Uber", 2_780, "Transporte", None, conta, -2),
            ("Posto de gasolina", 21_000, "Transporte", visa, None, -9),
            ("Farmácia", 6_430, "Saúde", visa, None, -11),
        ]
        for descricao, valor, categoria, cartao, c, dias in unicas:
            data = date.fromordinal(hoje.toordinal() + dias)
            Lancamento.objects.create(dono=u, descricao=descricao, valor=valor, natureza="despesa", categoria=cat[categoria], cartao=cartao, conta=c, data=data)
        Lancamento.objects.create(dono=u, descricao="Freelance", valor=150_000, natureza="receita", categoria=cat["Freelance"], conta=conta, data=date.fromordinal(hoje.toordinal() - 3))

        criar_parcelas(dono=u, valor_total=450_000, parcelas=10, primeira=somar_meses(hoje, -2), descricao="Notebook", natureza="despesa", categoria=cat["Eletrônicos"], cartao=visa)
        criar_parcelas(dono=u, valor_total=35_960, parcelas=4, primeira=somar_meses(hoje, -1), descricao="Tênis", natureza="despesa", categoria=cat["Vestuário"], cartao=master)

        pessoal = Emprestimo.objects.create(dono=u, direcao="devo", nome="Empréstimo pessoal", instituicao="Banco do Brasil", valor_total=1_469_760, juros_mensal="2.1", parcela_valor=61_240, parcelas_total=24, data=somar_meses(mes, -8, 12), dia_vencimento=12)
        for i in range(8):
            PagamentoEmprestimo.objects.create(dono=u, emprestimo=pessoal, valor=61_240, data=somar_meses(pessoal.data, i + 1))
        joao = Emprestimo.objects.create(dono=u, direcao="devem", nome="João", valor_total=80_000, data=somar_meses(hoje, -1), prazo=somar_meses(hoje, 1))
        PagamentoEmprestimo.objects.create(dono=u, emprestimo=joao, valor=20_000, data=hoje)
        Emprestimo.objects.create(dono=u, direcao="devem", nome="Ana", valor_total=55_000, data=somar_meses(hoje, -1))

        self.stdout.write(self.style.SUCCESS(f"Usuário demo@financas.local criado (senha: {senha})."))
