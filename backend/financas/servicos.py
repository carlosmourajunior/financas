"""Regras de negócio: parcelas, recorrências, faturas e o resumo do Início."""

import calendar
from dataclasses import dataclass
from datetime import date, timedelta

from django.db import transaction
from django.db.models import Q, Sum

from .models import Cartao, Conta, Emprestimo, Frequencia, Lancamento, Natureza, PagamentoFatura, Recorrencia


def somar_meses(d: date, meses: int, dia: int | None = None) -> date:
    """Avança meses mantendo o dia, ou o último dia do mês quando ele não existe."""
    total = d.month - 1 + meses
    ano, mes = d.year + total // 12, total % 12 + 1
    dia = dia or d.day
    return date(ano, mes, min(dia, calendar.monthrange(ano, mes)[1]))


def fim_do_mes(d: date) -> date:
    return date(d.year, d.month, calendar.monthrange(d.year, d.month)[1])


def inicio_do_mes(d: date) -> date:
    return d.replace(day=1)


def proxima_data(d: date, frequencia: str, dia_base: int) -> date:
    if frequencia == Frequencia.SEMANAL:
        return d + timedelta(days=7)
    if frequencia == Frequencia.ANUAL:
        return somar_meses(d, 12, dia_base)
    return somar_meses(d, 1, dia_base)


# Parcelas -----------------------------------------------------------------


@transaction.atomic
def criar_parcelas(*, dono, valor_total: int, parcelas: int, primeira: date, **campos) -> list[Lancamento]:
    """Divide o total em parcelas mensais. Os centavos que sobram vão para a primeira."""
    base, resto = divmod(valor_total, parcelas)
    grupo = Lancamento.novo_grupo()
    hoje = date.today()
    criadas = []
    for i in range(parcelas):
        data = somar_meses(primeira, i)
        criadas.append(
            Lancamento(
                dono=dono,
                valor=base + (resto if i == 0 else 0),
                data=data,
                tipo=Lancamento.Tipo.PARCELADA,
                grupo=grupo,
                parcela_atual=i + 1,
                parcela_total=parcelas,
                pago=data <= hoje,
                **campos,
            )
        )
    return Lancamento.objects.bulk_create(criadas)


# Recorrências -------------------------------------------------------------


def gerar_ocorrencias(dono, ate: date) -> int:
    """Transforma as recorrências ativas em lançamentos até a data informada. Pode ser chamada várias vezes."""
    hoje = date.today()
    criadas = 0
    for rec in Recorrencia.objects.filter(dono=dono, ativa=True):
        limite = min(ate, rec.fim) if rec.fim else ate
        data = proxima_data(rec.gerada_ate, rec.frequencia, rec.inicio.day) if rec.gerada_ate else rec.inicio
        ultima = rec.gerada_ate
        while data <= limite:
            _, nova = Lancamento.objects.get_or_create(
                recorrencia=rec,
                data=data,
                defaults={
                    "dono": dono,
                    "descricao": rec.descricao,
                    "valor": rec.valor,
                    "natureza": rec.natureza,
                    "categoria": rec.categoria,
                    "conta": rec.conta,
                    "cartao": rec.cartao,
                    "tipo": Lancamento.Tipo.RECORRENTE,
                    "pago": data <= hoje,
                },
            )
            criadas += int(nova)
            ultima = data
            data = proxima_data(data, rec.frequencia, rec.inicio.day)
        if ultima != rec.gerada_ate:
            rec.gerada_ate = ultima
            rec.save(update_fields=["gerada_ate", "atualizado_em"])
    return criadas


def projetar_recorrencias(dono, inicio: date, fim: date) -> int:
    """Soma das despesas recorrentes que cairiam no período, sem gravar nada."""
    total = 0
    for rec in Recorrencia.objects.filter(dono=dono, ativa=True, natureza=Natureza.DESPESA):
        data = rec.inicio
        while data <= fim and (rec.fim is None or data <= rec.fim):
            if data >= inicio:
                total += rec.valor
            data = proxima_data(data, rec.frequencia, rec.inicio.day)
    return total


# Faturas ------------------------------------------------------------------


@dataclass
class Fatura:
    cartao: Cartao
    abre: date  # dia seguinte ao fechamento anterior
    fecha: date
    vence: date
    total: int

    @property
    def aberta(self) -> bool:
        return date.today() <= self.fecha


def _vencimento(cartao: Cartao, fechamento: date) -> date:
    # Se o vencimento é antes do fechamento no calendário, ele cai no mês seguinte.
    meses = 0 if cartao.dia_vencimento > cartao.dia_fechamento else 1
    return somar_meses(fechamento, meses, cartao.dia_vencimento)


def no_cartao(qs) -> int:
    """Compras menos créditos (estornos) lançados no cartão."""
    r = qs.aggregate(
        despesas=Sum("valor", filter=Q(natureza=Natureza.DESPESA)),
        creditos=Sum("valor", filter=Q(natureza=Natureza.RECEITA)),
    )
    return (r["despesas"] or 0) - (r["creditos"] or 0)


def fatura_que_fecha_em(cartao: Cartao, fechamento: date) -> Fatura:
    anterior = somar_meses(fechamento, -1, cartao.dia_fechamento)
    abre = anterior + timedelta(days=1)
    total = no_cartao(Lancamento.objects.filter(dono=cartao.dono, cartao=cartao, data__gte=abre, data__lte=fechamento))
    return Fatura(cartao, abre, fechamento, _vencimento(cartao, fechamento), total)


def fechamento_de(cartao: Cartao, d: date) -> date:
    """Dia em que fecha a fatura onde cai a data `d`."""
    fecha = somar_meses(d, 0, cartao.dia_fechamento)
    return fecha if d <= fecha else somar_meses(fecha, 1, cartao.dia_fechamento)


def fatura_aberta(cartao: Cartao, hoje: date) -> Fatura:
    fecha_este_mes = date(hoje.year, hoje.month, cartao.dia_fechamento)
    fechamento = fecha_este_mes if hoje <= fecha_este_mes else somar_meses(fecha_este_mes, 1)
    return fatura_que_fecha_em(cartao, fechamento)


def faturas_vencendo(cartao: Cartao, inicio: date, fim: date) -> list[Fatura]:
    """Faturas (fechadas ou não) cujo vencimento cai no período."""
    aberta = fatura_aberta(cartao, inicio)
    candidatas = [fatura_que_fecha_em(cartao, somar_meses(aberta.fecha, -1, cartao.dia_fechamento)), aberta]
    return [f for f in candidatas if inicio <= f.vence <= fim]


def limite_usado(cartao: Cartao, hoje: date) -> int:
    """Tudo que ainda vai ser cobrado: a fatura aberta e as parcelas futuras."""
    abre = fatura_aberta(cartao, hoje).abre
    return no_cartao(Lancamento.objects.filter(dono=cartao.dono, cartao=cartao, data__gte=abre))


def detalhe_cartao(cartao: Cartao, hoje: date, meses: int = 3, fecha: date | None = None) -> dict:
    """Uma fatura do cartão (a aberta, ou a que fecha em `fecha`) com as compras, mais parcelas e próximas faturas."""
    aberta = fatura_aberta(cartao, hoje)
    escolhida = fatura_que_fecha_em(cartao, fecha) if fecha else aberta
    proximas = []
    f_proxima = aberta.fecha
    for _ in range(meses):
        f_proxima = somar_meses(f_proxima, 1, cartao.dia_fechamento)
        f = fatura_que_fecha_em(cartao, f_proxima)
        proximas.append({"fecha": f.fecha, "vence": f.vence, "total": f.total})

    grupos: dict = {}
    for l in Lancamento.objects.filter(dono=cartao.dono, cartao=cartao, tipo=Lancamento.Tipo.PARCELADA).order_by("data"):
        grupos.setdefault(l.grupo, []).append(l)
    parcelas = []
    for itens in grupos.values():
        ultima = itens[-1]
        if ultima.data < aberta.abre:
            continue  # compra já quitada
        # Vale o número da parcela gravado (07/10 da fatura importada), não quantas existem no app.
        atual = next(l for l in itens if l.data >= aberta.abre).parcela_atual
        parcelas.append(
            {
                "descricao": itens[0].descricao,
                "valor": ultima.valor,
                "atual": atual,
                "total": ultima.parcela_total,
                "termina": ultima.data,
            }
        )

    compras = Lancamento.objects.filter(cartao=cartao, data__gte=escolhida.abre, data__lte=escolhida.fecha).select_related("categoria")
    pagamento = PagamentoFatura.objects.filter(cartao=cartao, fecha=escolhida.fecha).first()
    return {
        "fatura": {
            "abre": escolhida.abre,
            "fecha": escolhida.fecha,
            "vence": escolhida.vence,
            "total": escolhida.total,
            "aberta": escolhida.fecha == aberta.fecha,
            "anterior": somar_meses(escolhida.fecha, -1, cartao.dia_fechamento),
            "seguinte": somar_meses(escolhida.fecha, 1, cartao.dia_fechamento),
            "pagamento": _pagamento(pagamento),
        },
        "compras": [
            {
                "id": l.id,
                "data": l.data,
                "descricao": l.descricao,
                "valor": l.valor,
                "natureza": l.natureza,
                "categoria": l.categoria.nome if l.categoria else None,
                "parcela_atual": l.parcela_atual,
                "parcela_total": l.parcela_total,
            }
            for l in compras.order_by("data", "id")
        ],
        "limite": cartao.limite,
        "disponivel": cartao.limite - limite_usado(cartao, hoje),
        "proximas": proximas,
        "parcelas": parcelas,
    }


def _pagamento(p: PagamentoFatura | None) -> dict | None:
    return {"id": p.id, "valor": p.valor, "data": p.data} if p else None


def pagamentos_por_fecha(cartao: Cartao) -> dict[date, PagamentoFatura]:
    return {p.fecha: p for p in PagamentoFatura.objects.filter(cartao=cartao)}


def faturas_do_mes(dono, mes: date, hoje: date) -> list[dict]:
    """Uma linha por fatura que vence no mês, para a lista de lançamentos."""
    inicio, fim = inicio_do_mes(mes), fim_do_mes(mes)
    linhas = []
    for c in Cartao.objects.filter(dono=dono):
        pagos = pagamentos_por_fecha(c)
        for f in faturas_vencendo(c, inicio, fim):
            if f.total:
                pagamento = pagos.get(f.fecha)
                linhas.append(
                    {
                        "cartao": c.id,
                        "nome": f"Fatura {c.nome}",
                        "final": c.final,
                        "abre": f.abre,
                        "fecha": f.fecha,
                        "vence": f.vence,
                        "total": f.total,
                        "paga": pagamento is not None,
                        "pagamento": _pagamento(pagamento),
                        "compras": Lancamento.objects.filter(cartao=c, data__gte=f.abre, data__lte=f.fecha).count(),
                    }
                )
    return sorted(linhas, key=lambda l: l["vence"])


def faturas_em_aberto(cartao: Cartao, ate: date, meses: int = 6) -> list[Fatura]:
    """Faturas que vencem até `ate`, dos últimos meses, ainda sem pagamento registrado."""
    pagos = pagamentos_por_fecha(cartao)
    fecha = fatura_aberta(cartao, ate).fecha
    abertas = []
    for _ in range(meses + 1):
        f = fatura_que_fecha_em(cartao, fecha)
        if f.vence <= ate and f.total > 0 and f.fecha not in pagos:
            abertas.append(f)
        fecha = somar_meses(fecha, -1, cartao.dia_fechamento)
    return sorted(abertas, key=lambda f: f.vence)


def quitar_faturas_vencidas(cartao: Cartao, hoje: date) -> int:
    """Registra como pagas no vencimento todas as faturas que venceram antes de hoje.

    Usado para dados antigos (de quando a fatura contava como paga sozinha) e para o demo.
    """
    primeira = Lancamento.objects.filter(cartao=cartao).order_by("data").values_list("data", flat=True).first()
    if not primeira:
        return 0
    pagos = pagamentos_por_fecha(cartao)
    fecha = somar_meses(primeira, 0, cartao.dia_fechamento)
    if fecha < primeira:
        fecha = somar_meses(fecha, 1, cartao.dia_fechamento)
    criados = 0
    while True:
        f = fatura_que_fecha_em(cartao, fecha)
        if f.vence >= hoje:
            return criados
        if f.total > 0 and f.fecha not in pagos:
            PagamentoFatura.objects.create(dono=cartao.dono, cartao=cartao, fecha=f.fecha, valor=f.total, data=f.vence)
            criados += 1
        fecha = somar_meses(fecha, 1, cartao.dia_fechamento)


def pendencias(dono, hoje: date, cartoes: list[Cartao], dias: int = 180) -> list[dict]:
    """Contas (despesas em conta e faturas) que vencem até hoje e não foram pagas."""
    itens = [
        {"tipo": "lancamento", "id": l.id, "nome": l.descricao, "valor": l.valor, "data": l.data}
        for l in Lancamento.objects.filter(
            dono=dono,
            conta__isnull=False,
            natureza=Natureza.DESPESA,
            pago=False,
            data__lte=hoje,
            data__gte=hoje - timedelta(days=dias),
        )
    ]
    for c in cartoes:
        for f in faturas_em_aberto(c, hoje):
            itens.append({"tipo": "fatura", "cartao": c.id, "fecha": f.fecha, "nome": f"Fatura {c}", "valor": f.total, "data": f.vence})
    return sorted(itens, key=lambda i: (i["data"], i["nome"]))


# Resumo do Início ---------------------------------------------------------


def _soma(qs) -> int:
    return qs.aggregate(s=Sum("valor"))["s"] or 0


def resumo(dono, hoje: date) -> dict:
    inicio, fim = inicio_do_mes(hoje), fim_do_mes(hoje)
    gerar_ocorrencias(dono, fim)
    lanc = Lancamento.objects.filter(dono=dono)

    # Saldo em conta: o que já aconteceu nas contas até hoje.
    # Saldo em conta: o que já foi pago ou recebido nas contas, mais as faturas pagas.
    em_conta = lanc.filter(conta__isnull=False, pago=True)
    cartoes = list(Cartao.objects.filter(dono=dono))
    saldo = (
        (Conta.objects.filter(dono=dono).aggregate(s=Sum("saldo_inicial"))["s"] or 0)
        + _soma(em_conta.filter(natureza=Natureza.RECEITA))
        - _soma(em_conta.filter(natureza=Natureza.DESPESA))
        - _soma(PagamentoFatura.objects.filter(dono=dono))
    )

    # Contas do mês para a régua: despesas em conta e faturas que vencem no mês.
    contas_mes = [
        {"dia": l.data.day, "nome": l.descricao, "valor": l.valor, "paga": l.pago}
        for l in lanc.filter(conta__isnull=False, natureza=Natureza.DESPESA, data__gte=inicio, data__lte=fim).order_by("data")
    ]
    for c in cartoes:
        pagos = pagamentos_por_fecha(c)
        for f in faturas_vencendo(c, inicio, fim):
            if f.total:
                contas_mes.append({"dia": f.vence.day, "nome": f"Fatura {c}", "valor": f.total, "paga": f.fecha in pagos})
    contas_mes.sort(key=lambda c: c["dia"])

    pendentes = pendencias(dono, hoje, cartoes)
    vencidas = [p for p in pendentes if p["data"] < hoje]
    # Inclui o que já venceu e não foi pago, deste mês e dos anteriores: ainda vai sair da conta.
    a_vencer = sum(c["valor"] for c in contas_mes if not c["paga"]) + sum(p["valor"] for p in vencidas if p["data"] < inicio)

    do_mes = lanc.filter(data__gte=inicio, data__lte=fim)
    categorias = (
        do_mes.filter(natureza=Natureza.DESPESA)
        .values("categoria__nome")
        .annotate(valor=Sum("valor"))
        .order_by("-valor")
    )

    prox_inicio = fim + timedelta(days=1)
    prox_fim = fim_do_mes(prox_inicio)
    compromisso = _soma(lanc.filter(natureza=Natureza.DESPESA, recorrencia__isnull=True, data__gte=prox_inicio, data__lte=prox_fim))
    compromisso += projetar_recorrencias(dono, prox_inicio, prox_fim)

    faturas = []
    for c in cartoes:
        f = fatura_aberta(c, hoje)
        faturas.append(
            {
                "cartao": c.id,
                "nome": str(c),
                "total": f.total,
                "fecha": f.fecha,
                "vence": f.vence,
                "limite": c.limite,
                "disponivel": c.limite - limite_usado(c, hoje),
            }
        )

    emprestimos = Emprestimo.objects.filter(dono=dono).prefetch_related("pagamentos")
    devo = [e for e in emprestimos if e.direcao == Emprestimo.Direcao.DEVO]
    devem = [e for e in emprestimos if e.direcao == Emprestimo.Direcao.DEVEM]

    def saldo_emp(e):
        return max(0, e.valor_total - sum(p.valor for p in e.pagamentos.all()))

    return {
        "hoje": hoje,
        "saldo_em_conta": saldo,
        "a_vencer": a_vencer,
        "livre_para_gastar": saldo - a_vencer,
        "contas_do_mes": contas_mes,
        "vencidas": vencidas,
        "vencem_hoje": [p for p in pendentes if p["data"] == hoje],
        # Estorno no cartão abate a fatura, não é dinheiro que entrou.
        "entrou": _soma(do_mes.filter(natureza=Natureza.RECEITA, cartao__isnull=True)),
        "saiu": _soma(do_mes.filter(natureza=Natureza.DESPESA)),
        "categorias": [{"nome": c["categoria__nome"] or "Sem categoria", "valor": c["valor"]} for c in categorias],
        "faturas": faturas,
        "compromisso_proximo_mes": compromisso,
        "emprestimos": {
            "devo_total": sum(saldo_emp(e) for e in devo),
            "devo_por_mes": sum(e.parcela_valor or 0 for e in devo if saldo_emp(e) > 0),
            "devo_quantidade": sum(1 for e in devo if saldo_emp(e) > 0),
            "devem_total": sum(saldo_emp(e) for e in devem),
            "devem_pessoas": [e.nome for e in devem if saldo_emp(e) > 0],
        },
    }
