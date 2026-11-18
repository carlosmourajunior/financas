from datetime import date

from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Cartao, Categoria, Conta, Emprestimo, Frequencia, Lancamento, PagamentoEmprestimo, PagamentoFatura, Recorrencia
from .serializers import (
    CartaoSerializer,
    CategoriaSerializer,
    ContaSerializer,
    EmprestimoSerializer,
    LancamentoSerializer,
    PagamentoEmprestimoSerializer,
    PagamentoFaturaSerializer,
    RecorrenciaSerializer,
)
from .servicos import detalhe_cartao, detalhe_conta, faturas_do_mes, fim_do_mes, gerar_ocorrencias, repetir_lancamento, resumo, visao_geral


def ler_mes(valor: str | None) -> date | None:
    """Aceita ?mes=AAAA-MM."""
    if not valor:
        return None
    try:
        ano, mes = map(int, valor.split("-"))
        return date(ano, mes, 1)
    except ValueError as exc:
        raise ValidationError({"mes": "Use o formato AAAA-MM."}) from exc


class DoUsuarioViewSet(viewsets.ModelViewSet):
    """Cada usuário só lista, vê e altera os próprios registros."""

    model = None

    def get_queryset(self):
        return self.model.objects.filter(dono=self.request.user)

    def perform_create(self, serializer):
        serializer.save(dono=self.request.user)


class ContaViewSet(DoUsuarioViewSet):
    model = Conta
    serializer_class = ContaSerializer

    @action(detail=False, url_path="visao-geral")
    def visao_geral(self, request):
        """Todas as contas e cartões juntos, com os lançamentos em conta do mês (?mes=AAAA-MM, ?sem_poupanca=1)."""
        sem_poupanca = request.query_params.get("sem_poupanca") in ("1", "true")
        return Response(visao_geral(request.user, date.today(), ler_mes(request.query_params.get("mes")), sem_poupanca=sem_poupanca))

    @action(detail=True)
    def detalhe(self, request, pk=None):
        """Saldo da conta e os lançamentos do mês (?mes=AAAA-MM, padrão o atual)."""
        return Response(detalhe_conta(self.get_object(), date.today(), ler_mes(request.query_params.get("mes"))))


class CartaoViewSet(DoUsuarioViewSet):
    model = Cartao
    serializer_class = CartaoSerializer

    @action(detail=True)
    def detalhe(self, request, pk=None):
        """Fatura (a aberta, ou ?fecha=AAAA-MM-DD) com as compras, próximas faturas e parcelas em andamento."""
        fecha = request.query_params.get("fecha")
        try:
            fecha = date.fromisoformat(fecha) if fecha else None
        except ValueError as exc:
            raise ValidationError({"fecha": "Use o formato AAAA-MM-DD."}) from exc
        return Response(detalhe_cartao(self.get_object(), date.today(), fecha=fecha))


class CategoriaViewSet(DoUsuarioViewSet):
    model = Categoria
    serializer_class = CategoriaSerializer


class RecorrenciaViewSet(DoUsuarioViewSet):
    model = Recorrencia
    serializer_class = RecorrenciaSerializer
    http_method_names = ["get", "patch", "delete", "head", "options"]


class RepetirSerializer(serializers.Serializer):
    tipo = serializers.ChoiceField(choices=[Lancamento.Tipo.RECORRENTE, Lancamento.Tipo.PARCELADA])
    frequencia = serializers.ChoiceField(choices=Frequencia.choices, default=Frequencia.MENSAL)
    parcela_atual = serializers.IntegerField(min_value=1, max_value=99, default=1)
    parcela_total = serializers.IntegerField(min_value=1, max_value=99, default=1)

    def validate(self, dados):
        if dados["tipo"] == Lancamento.Tipo.PARCELADA:
            if dados["parcela_total"] < 2 or dados["parcela_atual"] > dados["parcela_total"]:
                raise serializers.ValidationError({"parcela_total": "Informe a parcela e o total, por exemplo 3 de 10."})
        else:
            dados.pop("parcela_atual")
            dados.pop("parcela_total")
        return dados


class LancamentoViewSet(DoUsuarioViewSet):
    model = Lancamento
    serializer_class = LancamentoSerializer

    def perform_create(self, serializer):
        # O serializer cuida do dono porque pode criar vários registros.
        serializer.save()

    def perform_destroy(self, instance):
        """`?seguintes=1` apaga também as próximas parcelas ou ocorrências; a recorrência para de gerar."""
        if self.request.query_params.get("seguintes") not in ("1", "true"):
            instance.delete()
            return
        if instance.recorrencia_id:
            rec = instance.recorrencia
            rec.ativa = False
            rec.save(update_fields=["ativa", "atualizado_em"])
            rec.ocorrencias.filter(data__gte=instance.data).delete()
        elif instance.grupo:
            Lancamento.objects.filter(dono=instance.dono, grupo=instance.grupo, data__gte=instance.data).delete()
        else:
            instance.delete()

    @action(detail=True, methods=["post"])
    def repetir(self, request, pk=None):
        """Marca um lançamento único como recorrente ({"tipo": "recorrente", "frequencia"}) ou como
        parcela ({"tipo": "parcelada", "parcela_atual", "parcela_total"})."""
        lanc = self.get_object()
        if lanc.tipo != Lancamento.Tipo.UNICA:
            raise ValidationError("Só um lançamento único pode virar recorrente ou parcelado.")
        s = RepetirSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        criados = repetir_lancamento(lanc, **s.validated_data)
        lanc.refresh_from_db()
        return Response({"lancamento": LancamentoSerializer(lanc, context={"request": request}).data, "criados": criados})

    def get_queryset(self):
        qs = super().get_queryset().select_related("categoria", "conta", "cartao")
        p = self.request.query_params
        mes = ler_mes(p.get("mes"))
        if mes:
            gerar_ocorrencias(self.request.user, fim_do_mes(mes))
            qs = qs.filter(data__gte=mes, data__lte=fim_do_mes(mes))
        for campo in ("natureza", "tipo", "cartao", "conta", "categoria"):
            if p.get(campo):
                qs = qs.filter(**{campo: p[campo]})
        if p.get("sem_cartao") in ("1", "true"):
            # Compras no cartão aparecem pela fatura, não uma a uma.
            qs = qs.filter(cartao__isnull=True)
        return qs


class EmprestimoViewSet(DoUsuarioViewSet):
    model = Emprestimo
    serializer_class = EmprestimoSerializer

    def get_queryset(self):
        qs = super().get_queryset().prefetch_related("pagamentos")
        direcao = self.request.query_params.get("direcao")
        return qs.filter(direcao=direcao) if direcao else qs


class PagamentoEmprestimoViewSet(DoUsuarioViewSet):
    model = PagamentoEmprestimo
    serializer_class = PagamentoEmprestimoSerializer


class PagamentoFaturaViewSet(DoUsuarioViewSet):
    model = PagamentoFatura
    serializer_class = PagamentoFaturaSerializer


class FaturasView(APIView):
    """Faturas que vencem no mês (?mes=AAAA-MM, padrão o mês atual), uma linha por cartão."""

    def get(self, request):
        mes = ler_mes(request.query_params.get("mes")) or date.today()
        return Response(faturas_do_mes(request.user, mes, date.today()))


class ResumoView(APIView):
    """Números do Início: quanto ainda pode gastar, contas do mês, faturas e empréstimos."""

    def get(self, request):
        return Response(resumo(request.user, date.today()))
