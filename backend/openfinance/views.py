"""Buscar fatura e extrato direto do banco, pela Pluggy, e devolver a mesma prévia da importação de arquivo.

A gravação continua nas rotas de importação (/api/importar/.../confirmar/): o que vem do banco passa
pela mesma revisão e pela mesma regra de repetidos.
"""

from datetime import date, timedelta

from django.db import transaction
from rest_framework import serializers
from rest_framework.exceptions import APIException, PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from financas.models import Cartao, Conta
from financas.servicos import fatura_aberta
from importacao.extrato import previa_extrato
from importacao.servicos import previa
from importacao.views import cartao_do_usuario, conta_do_usuario

from . import conversao, pluggy
from .models import Vinculo

ABERTA = "aberta"
# O extrato de uma vez cobre no máximo este período, para a busca não ficar lenta.
MAXIMO_DIAS = 180


class PluggyIndisponivel(APIException):
    status_code = 502
    default_code = "pluggy"


def _exigir_liberado(request):
    if not pluggy.liberado_para(request.user):
        raise PermissionDenied("O Open Finance não está ligado para a sua conta.")


def _conta_pluggy(conta_id: str, tipo: str) -> pluggy.ContaPluggy:
    c = pluggy.conta(conta_id)
    if not c or c.tipo != tipo:
        raise ValidationError({"pluggy": "Escolha um cartão conectado." if tipo == "CREDIT" else "Escolha uma conta conectada."})
    return c


def _chamar(funcao, *args):
    try:
        return funcao(*args)
    except pluggy.ErroPluggy as exc:
        raise PluggyIndisponivel(str(exc)) from exc


class EstadoView(APIView):
    """Se o Open Finance está ligado para o usuário e quais contas a Pluggy enxerga."""

    def get(self, request):
        if not pluggy.liberado_para(request.user):
            return Response({"ativo": False, "contas": []})
        vinculos = {v.pluggy_conta: v for v in Vinculo.objects.filter(dono=request.user)}
        contas = _chamar(pluggy.contas)
        return Response(
            {
                "ativo": True,
                "contas": [
                    {
                        "id": c.id,
                        "tipo": c.tipo,
                        "nome": c.nome,
                        "numero": c.numero,
                        "saldo": c.saldo,
                        "conta": getattr(vinculos.get(c.id), "conta_id", None),
                        "cartao": getattr(vinculos.get(c.id), "cartao_id", None),
                    }
                    for c in contas
                ],
            }
        )


class FaturasView(APIView):
    """Faturas fechadas que a Pluggy tem para o cartão. A aberta é sempre oferecida à parte."""

    def get(self, request):
        _exigir_liberado(request)
        conta = request.query_params.get("pluggy", "")
        _chamar(_conta_pluggy, conta, "CREDIT")
        lista = _chamar(pluggy.faturas, conta)
        return Response(
            [{"id": b["id"], "vence": b["dueDate"][:10], "total": pluggy.centavos(b.get("totalAmount"))} for b in lista if b.get("dueDate")]
        )


class BuscarFaturaSerializer(serializers.Serializer):
    cartao = serializers.IntegerField()
    pluggy = serializers.CharField(max_length=64)
    fatura = serializers.CharField(max_length=64, default=ABERTA)


class PreviaFaturaView(APIView):
    def post(self, request):
        _exigir_liberado(request)
        s = BuscarFaturaSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        cartao = cartao_do_usuario(request, s.validated_data["cartao"])
        conta = _chamar(_conta_pluggy, s.validated_data["pluggy"], "CREDIT")
        escolhida = s.validated_data["fatura"]
        fechadas = _chamar(pluggy.faturas, conta.id)
        final = conta.numero[-4:] if conta.numero[-4:].isdigit() else ""

        if escolhida == ABERTA:
            ciclo = fatura_aberta(cartao, date.today())
            transacoes = _chamar(pluggy.transacoes, conta.id, ciclo.abre, ciclo.fecha)
            ids = {b["id"] for b in fechadas}
            lida = conversao.fatura_aberta(conta.nome, final, ids, ciclo.abre, ciclo.fecha, ciclo.vence, transacoes)
        else:
            fatura = next((b for b in fechadas if b["id"] == escolhida), None)
            if not fatura:
                raise ValidationError({"fatura": "Essa fatura não está mais na Pluggy."})
            fecha = date.fromisoformat((fatura.get("billClosingDate") or fatura["dueDate"])[:10])
            transacoes = _chamar(pluggy.transacoes, conta.id, fecha - timedelta(days=45), fecha + timedelta(days=2))
            lida = conversao.fatura_fechada(conta.nome, final, fechadas, fatura, transacoes)

        if not lida.itens:
            raise ValidationError({"fatura": "A Pluggy não trouxe lançamentos para esta fatura."})
        Vinculo.objects.update_or_create(cartao=cartao, defaults={"dono": request.user, "pluggy_conta": conta.id, "conta": None})
        return Response(previa(cartao, lida))


class BuscarExtratoSerializer(serializers.Serializer):
    conta = serializers.IntegerField()
    pluggy = serializers.CharField(max_length=64)
    desde = serializers.DateField()
    ate = serializers.DateField(required=False)

    def validate(self, dados):
        ate = dados.get("ate") or date.today()
        if dados["desde"] > ate:
            raise ValidationError({"desde": "A data inicial é depois da final."})
        if (ate - dados["desde"]).days > MAXIMO_DIAS:
            raise ValidationError({"desde": f"Busque no máximo {MAXIMO_DIAS} dias de cada vez."})
        dados["ate"] = ate
        return dados


class PreviaExtratoView(APIView):
    def post(self, request):
        _exigir_liberado(request)
        s = BuscarExtratoSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        local = conta_do_usuario(request, s.validated_data["conta"])
        conta = _chamar(_conta_pluggy, s.validated_data["pluggy"], "BANK")
        transacoes = _chamar(pluggy.transacoes, conta.id, s.validated_data["desde"], s.validated_data["ate"])
        lido = conversao.extrato(conta.nome, transacoes)
        if not lido.itens:
            raise ValidationError({"desde": "Nenhum movimento neste período."})
        Vinculo.objects.update_or_create(conta=local, defaults={"dono": request.user, "pluggy_conta": conta.id, "cartao": None})
        return Response(previa_extrato(local, lido))


def _dia(d: date | None, padrao: int) -> int:
    # O app guarda dias de 1 a 28 (fevereiro); dia 29 a 31 vira 28.
    return min(d.day, 28) if d else padrao


@transaction.atomic
def trazer_contas(dono) -> dict:
    """Cria no app as contas e cartões da Pluggy que ainda não têm par. Pode rodar quantas vezes quiser."""
    # Trava o usuário: duas chamadas juntas (a tela abre duas vezes) não criam conta em dobro.
    type(dono).objects.select_for_update().filter(pk=dono.pk).first()
    ligadas = set(Vinculo.objects.filter(dono=dono).values_list("pluggy_conta", flat=True))
    criadas = {"contas": [], "cartoes": []}
    for c in _chamar(pluggy.contas):
        if c.id in ligadas:
            continue
        if c.tipo == "BANK":
            tipo = Conta.Tipo.POUPANCA if c.subtipo == "SAVINGS_ACCOUNT" else Conta.Tipo.CORRENTE
            # Como no cadastro à mão: o saldo de hoje é o ponto de partida.
            conta = Conta.objects.create(dono=dono, nome=c.nome[:80] or "Conta", tipo=tipo, saldo_inicial=c.saldo)
            Vinculo.objects.create(dono=dono, conta=conta, pluggy_conta=c.id)
            criadas["contas"].append(conta.nome)
        elif c.tipo == "CREDIT":
            vence = _dia(c.vencimento, 10)
            # Sem a data do banco, fecha uma semana antes de vencer.
            fecha = _dia(c.fechamento, vence - 7 if vence > 7 else vence + 21)
            final = c.numero[-4:] if c.numero[-4:].isdigit() else ""
            cartao = Cartao.objects.create(
                dono=dono, nome=c.nome[:40] or "Cartão", final=final, limite=max(c.limite, 0), dia_fechamento=fecha, dia_vencimento=vence
            )
            Vinculo.objects.create(dono=dono, cartao=cartao, pluggy_conta=c.id)
            criadas["cartoes"].append(str(cartao))
    return criadas


class TrazerContasView(APIView):
    """Cadastra as contas e os cartões conectados na Pluggy, no lugar do cadastro à mão."""

    def post(self, request):
        _exigir_liberado(request)
        return Response(trazer_contas(request.user))
