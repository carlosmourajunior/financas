from datetime import date

from rest_framework import serializers

from .models import Cartao, Categoria, Conta, Emprestimo, Frequencia, Lancamento, PagamentoEmprestimo, Recorrencia
from .servicos import criar_parcelas, gerar_ocorrencias


class DoUsuarioSerializer(serializers.ModelSerializer):
    """Restringe as chaves estrangeiras aos registros do próprio usuário."""

    campos_do_usuario: dict[str, type] = {}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        dono = getattr(request, "user", None)
        for campo, modelo in self.campos_do_usuario.items():
            if campo in self.fields:
                self.fields[campo].queryset = modelo.objects.filter(dono=dono) if dono and dono.is_authenticated else modelo.objects.none()


class ContaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Conta
        fields = ["id", "nome", "tipo", "saldo_inicial"]


class CartaoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Cartao
        fields = ["id", "nome", "final", "limite", "dia_fechamento", "dia_vencimento"]

    def validate_final(self, valor):
        if valor and not (valor.isdigit() and len(valor) == 4):
            raise serializers.ValidationError("Use os 4 últimos números do cartão.")
        return valor


class CategoriaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Categoria
        fields = ["id", "nome", "natureza"]

    def validate(self, dados):
        dono = self.context["request"].user
        nome = dados.get("nome", getattr(self.instance, "nome", None))
        natureza = dados.get("natureza", getattr(self.instance, "natureza", None))
        qs = Categoria.objects.filter(dono=dono, nome__iexact=nome, natureza=natureza)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError({"nome": "Você já tem uma categoria com esse nome."})
        return dados


class LancamentoSerializer(DoUsuarioSerializer):
    campos_do_usuario = {"categoria": Categoria, "conta": Conta, "cartao": Cartao}

    # Só na criação: como gerar parcelas ou a recorrência.
    parcelas = serializers.IntegerField(write_only=True, required=False, min_value=2, max_value=72)
    frequencia = serializers.ChoiceField(choices=Frequencia.choices, write_only=True, required=False)
    fim = serializers.DateField(write_only=True, required=False, allow_null=True)
    pago = serializers.BooleanField(required=False)

    class Meta:
        model = Lancamento
        fields = [
            "id",
            "descricao",
            "valor",
            "natureza",
            "data",
            "categoria",
            "conta",
            "cartao",
            "tipo",
            "pago",
            "grupo",
            "parcela_atual",
            "parcela_total",
            "recorrencia",
            "parcelas",
            "frequencia",
            "fim",
        ]
        read_only_fields = ["grupo", "parcela_atual", "parcela_total", "recorrencia"]

    def validate(self, dados):
        conta = dados.get("conta", getattr(self.instance, "conta", None))
        cartao = dados.get("cartao", getattr(self.instance, "cartao", None))
        if conta and cartao:
            raise serializers.ValidationError("Escolha uma conta ou um cartão, não os dois.")
        natureza = dados.get("natureza", getattr(self.instance, "natureza", None))
        if cartao and natureza == "receita":
            raise serializers.ValidationError({"cartao": "Receitas entram em uma conta, não no cartão."})

        if self.instance is None:
            tipo = dados.get("tipo", Lancamento.Tipo.UNICA)
            if tipo == Lancamento.Tipo.PARCELADA and not dados.get("parcelas"):
                raise serializers.ValidationError({"parcelas": "Informe em quantas parcelas."})
            if tipo != Lancamento.Tipo.PARCELADA:
                dados.pop("parcelas", None)
        elif {"tipo", "parcelas", "frequencia"} & set(self.initial_data):
            raise serializers.ValidationError("O tipo não pode ser alterado depois de criado.")
        return dados

    def create(self, dados):
        dono = self.context["request"].user
        tipo = dados.pop("tipo", Lancamento.Tipo.UNICA)
        parcelas = dados.pop("parcelas", None)
        frequencia = dados.pop("frequencia", Frequencia.MENSAL)
        fim = dados.pop("fim", None)
        pago = dados.pop("pago", None)

        if tipo == Lancamento.Tipo.PARCELADA:
            # Aqui o valor informado é o total da compra.
            primeira = dados.pop("data")
            total = dados.pop("valor")
            return criar_parcelas(dono=dono, valor_total=total, parcelas=parcelas, primeira=primeira, **dados)[0]

        if tipo == Lancamento.Tipo.RECORRENTE:
            rec = Recorrencia.objects.create(
                dono=dono,
                descricao=dados["descricao"],
                valor=dados["valor"],
                natureza=dados["natureza"],
                categoria=dados.get("categoria"),
                conta=dados.get("conta"),
                cartao=dados.get("cartao"),
                frequencia=frequencia,
                inicio=dados["data"],
                fim=fim,
            )
            gerar_ocorrencias(dono, max(dados["data"], date.today()))
            return rec.ocorrencias.order_by("data").first()

        return Lancamento.objects.create(dono=dono, tipo=tipo, pago=dados["data"] <= date.today() if pago is None else pago, **dados)


class RecorrenciaSerializer(DoUsuarioSerializer):
    campos_do_usuario = {"categoria": Categoria, "conta": Conta, "cartao": Cartao}

    class Meta:
        model = Recorrencia
        fields = ["id", "descricao", "valor", "natureza", "categoria", "conta", "cartao", "frequencia", "inicio", "fim", "ativa", "gerada_ate"]
        read_only_fields = ["gerada_ate", "inicio", "frequencia"]


class PagamentoEmprestimoSerializer(DoUsuarioSerializer):
    campos_do_usuario = {"emprestimo": Emprestimo}

    class Meta:
        model = PagamentoEmprestimo
        fields = ["id", "emprestimo", "valor", "data"]


class EmprestimoSerializer(serializers.ModelSerializer):
    pagamentos = serializers.SerializerMethodField()
    pago = serializers.SerializerMethodField()
    saldo = serializers.SerializerMethodField()
    parcelas_pagas = serializers.SerializerMethodField()

    class Meta:
        model = Emprestimo
        fields = [
            "id",
            "direcao",
            "nome",
            "instituicao",
            "valor_total",
            "juros_mensal",
            "parcela_valor",
            "parcelas_total",
            "data",
            "prazo",
            "dia_vencimento",
            "pago",
            "saldo",
            "parcelas_pagas",
            "pagamentos",
        ]

    def _pago(self, e):
        return sum(p.valor for p in e.pagamentos.all())

    def get_pagamentos(self, e):
        return [{"id": p.id, "valor": p.valor, "data": p.data} for p in e.pagamentos.all()]

    def get_pago(self, e):
        return self._pago(e)

    def get_saldo(self, e):
        return max(0, e.valor_total - self._pago(e))

    def get_parcelas_pagas(self, e):
        return len(e.pagamentos.all()) if e.parcelas_total else None
