from datetime import date

from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Cartao, Categoria, Conta, Emprestimo, Lancamento, PagamentoEmprestimo, Recorrencia
from .serializers import (
    CartaoSerializer,
    CategoriaSerializer,
    ContaSerializer,
    EmprestimoSerializer,
    LancamentoSerializer,
    PagamentoEmprestimoSerializer,
    RecorrenciaSerializer,
)
from .servicos import detalhe_cartao, fim_do_mes, gerar_ocorrencias, resumo


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


class CartaoViewSet(DoUsuarioViewSet):
    model = Cartao
    serializer_class = CartaoSerializer

    @action(detail=True)
    def detalhe(self, request, pk=None):
        """Fatura aberta, próximas faturas e parcelas em andamento."""
        return Response(detalhe_cartao(self.get_object(), date.today()))


class CategoriaViewSet(DoUsuarioViewSet):
    model = Categoria
    serializer_class = CategoriaSerializer


class RecorrenciaViewSet(DoUsuarioViewSet):
    model = Recorrencia
    serializer_class = RecorrenciaSerializer
    http_method_names = ["get", "patch", "delete", "head", "options"]


class LancamentoViewSet(DoUsuarioViewSet):
    model = Lancamento
    serializer_class = LancamentoSerializer

    def perform_create(self, serializer):
        # O serializer cuida do dono porque pode criar vários registros.
        serializer.save()

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


class ResumoView(APIView):
    """Números do Início: quanto ainda pode gastar, contas do mês, faturas e empréstimos."""

    def get(self, request):
        return Response(resumo(request.user, date.today()))
