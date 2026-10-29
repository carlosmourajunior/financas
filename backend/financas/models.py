"""Modelos financeiros. Valores em centavos (inteiros) para não perder precisão."""

import uuid

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Natureza(models.TextChoices):
    DESPESA = "despesa", "Despesa"
    RECEITA = "receita", "Receita"


class DoUsuario(models.Model):
    """Base de todo registro que pertence a um usuário."""

    dono = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Conta(DoUsuario):
    class Tipo(models.TextChoices):
        CORRENTE = "corrente", "Conta corrente"
        POUPANCA = "poupanca", "Poupança"
        DINHEIRO = "dinheiro", "Dinheiro"

    nome = models.CharField(max_length=80)
    tipo = models.CharField(max_length=20, choices=Tipo.choices, default=Tipo.CORRENTE)
    saldo_inicial = models.BigIntegerField(default=0)

    class Meta:
        ordering = ["nome"]

    def __str__(self):
        return self.nome


class Cartao(DoUsuario):
    nome = models.CharField(max_length=40)
    final = models.CharField(max_length=4, blank=True)
    limite = models.BigIntegerField(validators=[MinValueValidator(0)])
    dia_fechamento = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(28)])
    dia_vencimento = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(28)])

    class Meta:
        ordering = ["nome"]
        verbose_name_plural = "cartões"

    def __str__(self):
        return f"{self.nome} {self.final}".strip()


class Categoria(DoUsuario):
    nome = models.CharField(max_length=60)
    natureza = models.CharField(max_length=10, choices=Natureza.choices, default=Natureza.DESPESA)

    class Meta:
        ordering = ["nome"]
        constraints = [models.UniqueConstraint(fields=["dono", "nome", "natureza"], name="categoria_unica_por_usuario")]

    def __str__(self):
        return self.nome


CATEGORIAS_PADRAO = {
    Natureza.DESPESA: ["Moradia", "Alimentação", "Transporte", "Saúde", "Lazer", "Educação", "Vestuário", "Eletrônicos", "Taxas", "Outros"],
    Natureza.RECEITA: ["Salário", "Freelance", "Rendimentos", "Outras receitas"],
}


def criar_categorias_padrao(usuario):
    Categoria.objects.bulk_create(
        [Categoria(dono=usuario, nome=nome, natureza=natureza) for natureza, nomes in CATEGORIAS_PADRAO.items() for nome in nomes],
        ignore_conflicts=True,
    )


class Frequencia(models.TextChoices):
    MENSAL = "mensal", "Todo mês"
    SEMANAL = "semanal", "Toda semana"
    ANUAL = "anual", "Todo ano"


class Recorrencia(DoUsuario):
    """Regra de um lançamento que se repete. As ocorrências viram Lancamento conforme os meses chegam."""

    descricao = models.CharField(max_length=120)
    valor = models.BigIntegerField(validators=[MinValueValidator(1)])
    natureza = models.CharField(max_length=10, choices=Natureza.choices)
    categoria = models.ForeignKey(Categoria, null=True, blank=True, on_delete=models.SET_NULL)
    conta = models.ForeignKey(Conta, null=True, blank=True, on_delete=models.SET_NULL)
    cartao = models.ForeignKey(Cartao, null=True, blank=True, on_delete=models.SET_NULL)
    frequencia = models.CharField(max_length=10, choices=Frequencia.choices, default=Frequencia.MENSAL)
    inicio = models.DateField()
    fim = models.DateField(null=True, blank=True)
    ativa = models.BooleanField(default=True)
    # Última data já transformada em lançamento, para gerar sem duplicar.
    gerada_ate = models.DateField(null=True, blank=True)

    def __str__(self):
        return self.descricao


class Lancamento(DoUsuario):
    class Tipo(models.TextChoices):
        UNICA = "unica", "Única"
        PARCELADA = "parcelada", "Parcelada"
        RECORRENTE = "recorrente", "Recorrente"

    descricao = models.CharField(max_length=120)
    valor = models.BigIntegerField(validators=[MinValueValidator(1)])
    natureza = models.CharField(max_length=10, choices=Natureza.choices)
    data = models.DateField()
    categoria = models.ForeignKey(Categoria, null=True, blank=True, on_delete=models.SET_NULL)
    conta = models.ForeignKey(Conta, null=True, blank=True, on_delete=models.SET_NULL)
    cartao = models.ForeignKey(Cartao, null=True, blank=True, on_delete=models.SET_NULL)
    tipo = models.CharField(max_length=10, choices=Tipo.choices, default=Tipo.UNICA)
    pago = models.BooleanField(default=True)

    # Parcelas de uma mesma compra compartilham o grupo.
    grupo = models.UUIDField(null=True, blank=True, db_index=True)
    parcela_atual = models.PositiveSmallIntegerField(null=True, blank=True)
    parcela_total = models.PositiveSmallIntegerField(null=True, blank=True)
    recorrencia = models.ForeignKey(Recorrencia, null=True, blank=True, on_delete=models.SET_NULL, related_name="ocorrencias")
    # Veio de uma fatura importada: importar de novo o mesmo período substitui estas linhas.
    importado = models.BooleanField(default=False)
    # Parcela importada: identifica a compra em qualquer fatura (descrição, parcelas e mês da 1ª parcela).
    chave = models.CharField(max_length=200, blank=True, default="")

    class Meta:
        ordering = ["-data", "-id"]
        indexes = [models.Index(fields=["dono", "data"])]
        constraints = [
            models.UniqueConstraint(fields=["recorrencia", "data"], name="ocorrencia_unica_por_data"),
            models.UniqueConstraint(fields=["cartao", "chave", "parcela_atual"], condition=~models.Q(chave=""), name="parcela_unica_por_compra"),
        ]

    def __str__(self):
        return f"{self.descricao} ({self.data})"

    @staticmethod
    def novo_grupo():
        return uuid.uuid4()


class Emprestimo(DoUsuario):
    class Direcao(models.TextChoices):
        DEVO = "devo", "Eu devo"
        DEVEM = "devem", "Me devem"

    direcao = models.CharField(max_length=5, choices=Direcao.choices)
    nome = models.CharField(max_length=120, help_text="O empréstimo (ex.: Financiamento do carro) ou a pessoa.")
    instituicao = models.CharField(max_length=80, blank=True)
    valor_total = models.BigIntegerField(validators=[MinValueValidator(1)], help_text="Total a pagar ou a receber.")
    juros_mensal = models.DecimalField(max_digits=6, decimal_places=3, null=True, blank=True)
    parcela_valor = models.BigIntegerField(null=True, blank=True)
    parcelas_total = models.PositiveSmallIntegerField(null=True, blank=True)
    data = models.DateField()
    prazo = models.DateField(null=True, blank=True)
    dia_vencimento = models.PositiveSmallIntegerField(null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(28)])

    class Meta:
        ordering = ["direcao", "data"]

    def __str__(self):
        return self.nome


class PagamentoEmprestimo(DoUsuario):
    emprestimo = models.ForeignKey(Emprestimo, on_delete=models.CASCADE, related_name="pagamentos")
    valor = models.BigIntegerField(validators=[MinValueValidator(1)])
    data = models.DateField()

    class Meta:
        ordering = ["data"]


class PagamentoFatura(DoUsuario):
    """Registro de que a fatura do cartão que fecha em `fecha` foi paga."""

    cartao = models.ForeignKey(Cartao, on_delete=models.CASCADE, related_name="pagamentos")
    fecha = models.DateField()
    valor = models.BigIntegerField(validators=[MinValueValidator(1)])
    data = models.DateField()

    class Meta:
        ordering = ["fecha"]
        constraints = [models.UniqueConstraint(fields=["cartao", "fecha"], name="um_pagamento_por_fatura")]

    def __str__(self):
        return f"{self.cartao} {self.fecha}"
