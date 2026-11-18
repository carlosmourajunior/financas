"""Buscar fatura e extrato direto do banco, pela Pluggy, e devolver a mesma prévia da importação de arquivo.

A gravação continua nas rotas de importação (/api/importar/.../confirmar/): o que vem do banco passa
pela mesma revisão e pela mesma regra de repetidos.
"""

import re
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


class CartaoDatasSerializer(serializers.ModelSerializer):
    class Meta:
        model = Cartao
        fields = ["id", "dia_fechamento", "dia_vencimento"]
        read_only_fields = ["id"]
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
        nomes = pluggy.nomes(contas)
        return Response(
            {
                "ativo": True,
                "contas": [
                    {
                        "id": c.id,
                        "tipo": c.tipo,
                        "nome": nomes[c.id],
                        "banco": c.banco,
                        "numero": c.numero,
                        "saldo": c.saldo,
                        "conta": getattr(vinculos.get(c.id), "conta_id", None),
                        "cartao": getattr(vinculos.get(c.id), "cartao_id", None),
                        "conferir_datas": getattr(vinculos.get(c.id), "conferir_datas", False),
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


def _dia(d: date | None) -> int | None:
    # O app guarda dias de 1 a 28 (fevereiro); dia 29 a 31 vira 28.
    return min(d.day, 28) if d else None


def _datas_do_cartao(c: pluggy.ContaPluggy) -> tuple[int | None, int | None]:
    """Fechamento e vencimento: do cartão ou, se o banco não informa ali, da última fatura."""
    fecha, vence = _dia(c.fechamento), _dia(c.vencimento)
    if fecha and vence:
        return fecha, vence
    try:
        ultima = next(iter(pluggy.faturas(c.id)), None)
    except pluggy.ErroPluggy:
        ultima = None
    if ultima:
        fecha = fecha or _dia(_data_iso(ultima.get("billClosingDate")))
        vence = vence or _dia(_data_iso(ultima.get("dueDate")))
    return fecha, vence


def _data_iso(texto: str | None) -> date | None:
    return date.fromisoformat(texto[:10]) if texto else None


def _nome_da_versao_anterior(c: pluggy.ContaPluggy) -> str:
    """Como a primeira versão nomeava, para reconhecer (e melhorar) o que ela criou sem guardar o nome."""
    nome = c.nome.strip()
    if c.banco and (not nome or re.search(r"\b(s\.?\s?a\.?|ltda|instituic[aã]o de pagamento|banco m[uú]ltiplo|cooperativa)\b", nome, re.I)):
        return f"{c.banco} Poupança" if c.subtipo == "SAVINGS_ACCOUNT" else c.banco
    nome = nome or ("Cartão" if c.tipo == "CREDIT" else "Conta")
    if nome.islower():
        nome = nome.title()
    if c.banco and c.banco.lower() not in nome.lower():
        nome = f"{c.banco} {nome}"
    return nome[: 40 if c.tipo == "CREDIT" else 80]


@transaction.atomic
def trazer_contas(dono) -> dict:
    """Cria no app as contas e cartões da Pluggy que ainda não têm par. Pode rodar quantas vezes quiser.

    O que já foi trazido e o usuário não renomeou ganha o nome atual (o jeito de nomear melhora).
    """
    # Trava o usuário: duas chamadas juntas (a tela abre duas vezes) não criam conta em dobro.
    type(dono).objects.select_for_update().filter(pk=dono.pk).first()
    ligadas = {v.pluggy_conta: v for v in Vinculo.objects.filter(dono=dono).select_related("conta", "cartao")}
    criadas = {"contas": [], "cartoes": [], "renomeadas": [], "conferir_datas": []}
    todas = _chamar(pluggy.contas)
    nomes = pluggy.nomes(todas)
    for c in todas:
        nome = nomes[c.id]
        if c.id in ligadas:
            v = ligadas[c.id]
            alvo = v.conta or v.cartao
            dados = {v.nome_dado} if v.nome_dado else {c.nome.strip(), _nome_da_versao_anterior(c)}
            if alvo.nome in dados and alvo.nome != nome:
                criadas["renomeadas"].append(f"{alvo.nome} → {nome}")
                alvo.nome = nome
                alvo.save(update_fields=["nome", "atualizado_em"])
            if v.cartao and not v.nome_dado:
                # Trazido por uma versão que inventava dia 3 e 10 quando o banco não informava.
                fecha, vence = _datas_do_cartao(c)
                if fecha and vence:
                    v.cartao.dia_fechamento, v.cartao.dia_vencimento = fecha, vence
                    v.cartao.save(update_fields=["dia_fechamento", "dia_vencimento", "atualizado_em"])
                else:
                    v.conferir_datas = True
                    v.save(update_fields=["conferir_datas", "atualizado_em"])
                    criadas["conferir_datas"].append(str(v.cartao))
            if v.cartao and not v.cartao.final and (final := pluggy.final_do_cartao(c.numero)):
                v.cartao.final = final
                v.cartao.save(update_fields=["final", "atualizado_em"])
            if v.nome_dado != alvo.nome:
                v.nome_dado = alvo.nome
                v.save(update_fields=["nome_dado", "atualizado_em"])
            continue
        if c.tipo == "BANK":
            tipo = Conta.Tipo.POUPANCA if c.subtipo == "SAVINGS_ACCOUNT" else Conta.Tipo.CORRENTE
            # Como no cadastro à mão: o saldo de hoje é o ponto de partida.
            conta = Conta.objects.create(dono=dono, nome=nome, tipo=tipo, saldo_inicial=c.saldo)
            Vinculo.objects.create(dono=dono, conta=conta, pluggy_conta=c.id, nome_dado=nome)
            criadas["contas"].append(nome)
        elif c.tipo == "CREDIT":
            fecha, vence = _datas_do_cartao(c)
            conferir = not (fecha and vence)
            # Sem a data, o cartão precisa de algum dia para existir; o aviso pede para conferir.
            vence = vence or 10
            fecha = fecha or (vence - 7 if vence > 7 else vence + 21)
            cartao = Cartao.objects.create(
                dono=dono, nome=nome, final=pluggy.final_do_cartao(c.numero), limite=max(c.limite, 0), dia_fechamento=fecha, dia_vencimento=vence
            )
            Vinculo.objects.create(dono=dono, cartao=cartao, pluggy_conta=c.id, nome_dado=nome, conferir_datas=conferir)
            criadas["cartoes"].append(str(cartao))
            if conferir:
                criadas["conferir_datas"].append(str(cartao))
    return criadas


class DatasConferidasView(APIView):
    """O usuário acertou o fechamento e o vencimento de um cartão trazido do banco."""

    def post(self, request):
        _exigir_liberado(request)
        cartao = cartao_do_usuario(request, request.data.get("cartao"))
        s = CartaoDatasSerializer(cartao, data=request.data)
        s.is_valid(raise_exception=True)
        s.save()
        Vinculo.objects.filter(cartao=cartao).update(conferir_datas=False)
        return Response(s.data)


class TrazerContasView(APIView):
    """Cadastra as contas e os cartões conectados na Pluggy, no lugar do cadastro à mão."""

    def post(self, request):
        _exigir_liberado(request)
        return Response(trazer_contas(request.user))
