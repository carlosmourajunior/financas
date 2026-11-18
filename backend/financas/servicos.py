"""Regras de negócio: parcelas, recorrências, faturas e o resumo do Início."""

import calendar
from dataclasses import dataclass
from datetime import date, timedelta

from django.db import transaction
from django.db.models import Q, Sum

from .models import COR_SEM_CATEGORIA, Cartao, Conta, Emprestimo, Frequencia, Lancamento, Natureza, PagamentoFatura, Recorrencia


def somar_meses(d: date, meses: int, dia: int | None = None) -> date:
    """Avança meses mantendo o dia, ou o último dia do mês quando ele não existe."""
    total = d.month - 1 + meses
    ano, mes = d.year + total // 12, total % 12 + 1
    dia = dia or d.day
    return date(ano, mes, min(dia, calendar.monthrange(ano, mes)[1]))


def fecha_do_mes(cartao, d: date, meses: int = 0) -> date:
    """Dia em que fecha a fatura do cartão no mês de `d` (mais `meses`): o registrado pelo banco ou o de costume."""
    alvo = somar_meses(d, meses, 1)
    # Lido do __dict__: em migrações antigas o campo fica de fora da consulta (a coluna ainda não existe).
    fechamentos = cartao.__dict__.get("fechamentos") or {}
    dia = fechamentos.get(f"{alvo.year}-{alvo.month:02d}") or cartao.dia_fechamento
    return somar_meses(alvo, 0, dia)


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


def vencimentos_das_parcelas(emprestimo) -> list[date]:
    """Vencimento de cada parcela: a 1ª no primeiro dia de vencimento depois da contratação, as outras mês a mês."""
    if not emprestimo.parcela_valor or not emprestimo.parcelas_total:
        return []
    dia = emprestimo.dia_vencimento or emprestimo.data.day
    primeira = somar_meses(emprestimo.data, 0, dia)
    if primeira <= emprestimo.data:
        primeira = somar_meses(emprestimo.data, 1, dia)
    return [somar_meses(primeira, k, dia) for k in range(emprestimo.parcelas_total)]


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


def projetar_recorrencias(dono, inicio: date, fim: date, natureza: str = Natureza.DESPESA) -> int:
    """Soma das recorrências fora do cartão (despesas, ou receitas) que cairiam no período, sem gravar nada."""
    total = 0
    for rec in Recorrencia.objects.filter(dono=dono, ativa=True, natureza=natureza, cartao__isnull=True):
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
    anterior = fecha_do_mes(cartao, fechamento, -1)
    abre = anterior + timedelta(days=1)
    total = no_cartao(Lancamento.objects.filter(dono=cartao.dono, cartao=cartao, data__gte=abre, data__lte=fechamento))
    return Fatura(cartao, abre, fechamento, _vencimento(cartao, fechamento), total)


def fechamento_de(cartao: Cartao, d: date) -> date:
    """Dia em que fecha a fatura onde cai a data `d`."""
    fecha = fecha_do_mes(cartao, d, 0)
    return fecha if d <= fecha else fecha_do_mes(cartao, fecha, 1)


def fatura_aberta(cartao: Cartao, hoje: date) -> Fatura:
    fecha_este_mes = fecha_do_mes(cartao, hoje)
    fechamento = fecha_este_mes if hoje <= fecha_este_mes else fecha_do_mes(cartao, hoje, 1)
    return fatura_que_fecha_em(cartao, fechamento)


def fatura_atual(cartao: Cartao, hoje: date) -> Fatura:
    """A fatura para olhar agora: a que já fechou e ainda não foi paga; paga (ou vazia), a aberta."""
    aberta = fatura_aberta(cartao, hoje)
    fechada = fatura_que_fecha_em(cartao, fecha_do_mes(cartao, aberta.fecha, -1))
    if fechada.total > 0 and not PagamentoFatura.objects.filter(cartao=cartao, fecha=fechada.fecha).exists():
        return fechada
    return aberta


def faturas_vencendo(cartao: Cartao, inicio: date, fim: date) -> list[Fatura]:
    """Faturas (fechadas ou não) cujo vencimento cai no período."""
    aberta = fatura_aberta(cartao, inicio)
    candidatas = [fatura_que_fecha_em(cartao, fecha_do_mes(cartao, aberta.fecha, -1)), aberta]
    return [f for f in candidatas if inicio <= f.vence <= fim]


def limite_usado(cartao: Cartao, hoje: date) -> int:
    """Tudo que ainda vai ser cobrado: a fatura aberta e as parcelas futuras."""
    abre = fatura_aberta(cartao, hoje).abre
    return no_cartao(Lancamento.objects.filter(dono=cartao.dono, cartao=cartao, data__gte=abre))


def detalhe_cartao(cartao: Cartao, hoje: date, meses: int = 3, fecha: date | None = None) -> dict:
    """Uma fatura do cartão (a atual, ou a que fecha em `fecha`) com as compras, mais parcelas e próximas faturas."""
    quitar_passados(cartao.dono, hoje)
    aberta = fatura_aberta(cartao, hoje)
    # Assinaturas no cartão entram também nas próximas faturas e na que foi pedida.
    ate = fecha_do_mes(cartao, aberta.fecha, meses)
    gerar_ocorrencias(cartao.dono, max(ate, fecha) if fecha else ate)
    escolhida = fatura_que_fecha_em(cartao, fecha) if fecha else fatura_atual(cartao, hoje)
    proximas = []
    f_proxima = aberta.fecha
    for _ in range(meses):
        f_proxima = fecha_do_mes(cartao, f_proxima, 1)
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
            "anterior": fecha_do_mes(cartao, escolhida.fecha, -1),
            "seguinte": fecha_do_mes(cartao, escolhida.fecha, 1),
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
                "categoria_id": l.categoria_id,
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
    quitar_passados(dono, hoje)
    inicio, fim = inicio_do_mes(mes), fim_do_mes(mes)
    linhas = []
    for c in Cartao.objects.filter(dono=dono, ativo=True):
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
        fecha = fecha_do_mes(cartao, fecha, -1)
    return sorted(abertas, key=lambda f: f.vence)


def quitar_faturas_vencidas(cartao: Cartao, hoje: date) -> int:
    """Registra como pagas no vencimento todas as faturas que venceram antes de hoje.

    Usado para dados antigos (de quando a fatura contava como paga sozinha) e para o demo.
    """
    primeira = Lancamento.objects.filter(cartao=cartao).order_by("data").values_list("data", flat=True).first()
    if not primeira:
        return 0
    pagos = pagamentos_por_fecha(cartao)
    fecha = fecha_do_mes(cartao, primeira, 0)
    if fecha < primeira:
        fecha = fecha_do_mes(cartao, fecha, 1)
    criados = 0
    while True:
        f = fatura_que_fecha_em(cartao, fecha)
        if f.vence >= hoje:
            return criados
        if f.total > 0 and f.fecha not in pagos:
            PagamentoFatura.objects.create(dono=cartao.dono, cartao=cartao, fecha=f.fecha, valor=f.total, data=f.vence)
            criados += 1
        fecha = fecha_do_mes(cartao, fecha, 1)


def acertar_pagamentos_fora_do_fechamento(cartao: Cartao) -> int:
    """Pagamento gravado num dia que não é mais o fechamento do mês (o dia mudou depois) vai para o fechamento certo.

    Se o fechamento certo já tem pagamento, o antigo é repetido e sai. Devolve quantos mudou.
    """
    mudou = 0
    pagos = list(PagamentoFatura.objects.filter(cartao=cartao))
    certos = {p.fecha for p in pagos if p.fecha == fecha_do_mes(cartao, p.fecha)}
    for p in pagos:
        certo = fecha_do_mes(cartao, p.fecha)
        if p.fecha == certo:
            continue
        if certo in certos:
            p.delete()
        else:
            p.fecha = certo
            p.save(update_fields=["fecha", "atualizado_em"])
            certos.add(certo)
        mudou += 1
    return mudou


def quitar_passados(dono, hoje: date) -> None:
    """O que tem data antes de hoje conta como pago ou recebido: lançamentos e faturas que já venceram.

    De hoje em diante fica pendente até ser marcado.
    """
    Lancamento.objects.filter(dono=dono, pago=False, data__lt=hoje).update(pago=True)
    for c in Cartao.objects.filter(dono=dono, ativo=True):
        acertar_pagamentos_fora_do_fechamento(c)
        quitar_faturas_vencidas(c, hoje)


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
    quitar_passados(dono, hoje)
    lanc = Lancamento.objects.filter(dono=dono)

    # Saldo em conta: o que já aconteceu nas contas até hoje.
    # Saldo em conta: o que já foi pago ou recebido nas contas, mais as faturas pagas.
    em_conta = lanc.filter(conta__isnull=False, pago=True)
    cartoes = list(Cartao.objects.filter(dono=dono, ativo=True))
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
    faturas_que_vencem = 0
    for c in cartoes:
        pagos = pagamentos_por_fecha(c)
        for f in faturas_vencendo(c, inicio, fim):
            if f.total:
                faturas_que_vencem += f.total
                contas_mes.append({"dia": f.vence.day, "nome": f"Fatura {c}", "valor": f.total, "paga": f.fecha in pagos})
    contas_mes.sort(key=lambda c: c["dia"])

    pendentes = pendencias(dono, hoje, cartoes)
    vencidas = [p for p in pendentes if p["data"] < hoje]
    # Inclui o que já venceu e não foi pago, deste mês e dos anteriores: ainda vai sair da conta.
    a_vencer = sum(c["valor"] for c in contas_mes if not c["paga"]) + sum(p["valor"] for p in vencidas if p["data"] < inicio)
    # Fatura que já fechou e só vence no mês que vem: o valor já está definido, então também sai do que dá para gastar.
    fechadas_depois = []
    for c in cartoes:
        f = fatura_atual(c, hoje)
        if f.fecha < hoje and f.vence > fim and f.total > 0:
            fechadas_depois.append({"cartao": c.id, "nome": f"Fatura {c}", "valor": f.total, "vence": f.vence})
    a_vencer += sum(f["valor"] for f in fechadas_depois)

    do_mes = lanc.filter(data__gte=inicio, data__lte=fim)
    # Gasto do mês: o que é pago fora do cartão com data no mês, mais cada fatura inteira no mês em que fecha.
    no_mes = Q(cartao__isnull=True, data__gte=inicio, data__lte=fim)
    faturas_que_fecham = 0
    por_cartao = []
    for c in cartoes:
        f = fatura_que_fecha_em(c, fecha_do_mes(c, inicio, 0))
        no_mes |= Q(cartao=c, data__gte=f.abre, data__lte=f.fecha)
        faturas_que_fecham += f.total
        if f.total:
            por_cartao.append({"cartao": c.id, "nome": str(c), "valor": f.total, "fecha": f.fecha, "vence": f.vence})
    gastos = lanc.filter(no_mes, natureza=Natureza.DESPESA)
    creditos = _soma(lanc.filter(no_mes, natureza=Natureza.RECEITA, cartao__isnull=False))
    categorias = (
        gastos
        .values("categoria", "categoria__nome", "categoria__cor")
        .annotate(valor=Sum("valor"))
        .order_by("-valor")
    )

    prox_inicio = fim + timedelta(days=1)
    prox_fim = fim_do_mes(prox_inicio)
    # O que sai da conta no mês que vem: contas fora do cartão e as faturas que vencem nele.
    compromisso = _soma(
        lanc.filter(natureza=Natureza.DESPESA, cartao__isnull=True, recorrencia__isnull=True, data__gte=prox_inicio, data__lte=prox_fim)
    )
    compromisso += projetar_recorrencias(dono, prox_inicio, prox_fim)
    compromisso += sum(f.total for c in cartoes for f in faturas_vencendo(c, prox_inicio, prox_fim))
    entradas_previstas = _soma(
        lanc.filter(natureza=Natureza.RECEITA, cartao__isnull=True, recorrencia__isnull=True, data__gte=prox_inicio, data__lte=prox_fim)
    ) + projetar_recorrencias(dono, prox_inicio, prox_fim, Natureza.RECEITA)

    # Por cartão, a fatura fechada que falta pagar; sem ela, a aberta.
    faturas = []
    for c in cartoes:
        f = fatura_atual(c, hoje)
        faturas.append(
            {
                "cartao": c.id,
                "nome": str(c),
                "total": f.total,
                "fecha": f.fecha,
                "vence": f.vence,
                "aberta": f.fecha >= hoje,
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
        "fechadas_a_pagar": fechadas_depois,
        "vencem_hoje": [p for p in pendentes if p["data"] == hoje],
        # Estorno no cartão abate a fatura, não é dinheiro que entrou.
        "entrou": _soma(do_mes.filter(natureza=Natureza.RECEITA, cartao__isnull=True)),
        # Gasto do mês: a fatura entra no mês em que fecha.
        "saiu": _soma(gastos.filter(cartao__isnull=True)) + faturas_que_fecham,
        # O mesmo gasto dividido: cada cartão pela fatura e os lançamentos fora do cartão.
        "gastou_detalhe": {
            "cartoes": por_cartao,
            "recorrentes": _soma(gastos.filter(cartao__isnull=True, tipo=Lancamento.Tipo.RECORRENTE)),
            "parceladas": _soma(gastos.filter(cartao__isnull=True, tipo=Lancamento.Tipo.PARCELADA)),
            "avulsas": _soma(gastos.filter(cartao__isnull=True, tipo=Lancamento.Tipo.UNICA)),
        },
        # Dinheiro que sai da conta: a fatura entra no mês em que vence.
        "sai_da_conta": _soma(gastos.filter(cartao__isnull=True)) + faturas_que_vencem,
        # Parcelas de compras de meses anteriores: entram no gasto, mas não são compra nova.
        "parcelas_anteriores": _soma(gastos.filter(parcela_atual__gt=1)),
        # Estornos e créditos nas faturas do mês: abatem o gasto, fora das categorias.
        "creditos_cartao": creditos,
        "categorias": [
            {"id": c["categoria"], "nome": c["categoria__nome"] or "Sem categoria", "cor": c["categoria__cor"] or COR_SEM_CATEGORIA, "valor": c["valor"]}
            for c in categorias
        ],
        "faturas": faturas,
        "compromisso_proximo_mes": compromisso,
        "entradas_proximo_mes": entradas_previstas,
        "emprestimos": {
            "devo_total": sum(saldo_emp(e) for e in devo),
            "devo_por_mes": sum(e.parcela_valor or 0 for e in devo if saldo_emp(e) > 0),
            "devo_quantidade": sum(1 for e in devo if saldo_emp(e) > 0),
            "devem_total": sum(saldo_emp(e) for e in devem),
            "devem_pessoas": [e.nome for e in devem if saldo_emp(e) > 0],
        },
    }


# Contas -------------------------------------------------------------------


def _movimento(l: Lancamento) -> dict:
    return {
        "id": l.id,
        "data": l.data,
        "descricao": l.descricao,
        "valor": l.valor,
        "natureza": l.natureza,
        "pago": l.pago,
        "tipo": l.tipo,
        "categoria": l.categoria.nome if l.categoria else None,
        "categoria_cor": l.categoria.cor if l.categoria else None,
        "conta": l.conta_id,
        "conta_nome": l.conta.nome if l.conta else None,
        "parcela_atual": l.parcela_atual,
        "parcela_total": l.parcela_total,
    }


def _no_mes(qs, inicio: date, fim: date) -> dict:
    """Entrou e saiu (já pagos) e o que ainda falta pagar ou receber no período."""
    do_mes = qs.filter(data__gte=inicio, data__lte=fim)
    return {
        "inicio": inicio,
        "fim": fim,
        "entrou": _soma(do_mes.filter(natureza=Natureza.RECEITA, pago=True)),
        "saiu": _soma(do_mes.filter(natureza=Natureza.DESPESA, pago=True)),
        "a_receber": _soma(do_mes.filter(natureza=Natureza.RECEITA, pago=False)),
        "a_pagar": _soma(do_mes.filter(natureza=Natureza.DESPESA, pago=False)),
    }


def saldos_das_contas(dono) -> dict[int, int]:
    """Saldo de cada conta: o de partida mais o que já foi recebido, menos o que já foi pago nela."""
    movimentos = (
        Lancamento.objects.filter(dono=dono, conta__isnull=False, pago=True)
        .values("conta")
        .annotate(
            receitas=Sum("valor", filter=Q(natureza=Natureza.RECEITA)),
            despesas=Sum("valor", filter=Q(natureza=Natureza.DESPESA)),
        )
    )
    por_conta = {m["conta"]: (m["receitas"] or 0) - (m["despesas"] or 0) for m in movimentos}
    return {c.id: c.saldo_inicial + por_conta.get(c.id, 0) for c in Conta.objects.filter(dono=dono)}


def _tem_pluggy(objeto) -> bool:
    # O vínculo fica no app openfinance; sem ele, a relação reversa não existe.
    return hasattr(objeto, "vinculo_pluggy")


def detalhe_conta(conta: Conta, hoje: date, mes: date | None = None) -> dict:
    """Saldo da conta, os números do mês (o atual ou `mes`) e os lançamentos dele."""
    quitar_passados(conta.dono, hoje)
    mes = inicio_do_mes(mes or hoje)
    fim = fim_do_mes(mes)
    gerar_ocorrencias(conta.dono, fim)
    qs = Lancamento.objects.filter(dono=conta.dono, conta=conta)
    saldo = saldos_das_contas(conta.dono)[conta.id]
    return {
        "conta": {"id": conta.id, "nome": conta.nome, "tipo": conta.tipo, "saldo_inicial": conta.saldo_inicial, "pluggy": _tem_pluggy(conta)},
        "saldo": saldo,
        # O saldo quando o mês terminar, se tudo que falta pagar e receber nele acontecer.
        "previsto": saldo + _soma(qs.filter(data__lte=fim, pago=False, natureza=Natureza.RECEITA)) - _soma(qs.filter(data__lte=fim, pago=False, natureza=Natureza.DESPESA)),
        "mes": _no_mes(qs, mes, fim),
        "movimentos": [_movimento(l) for l in qs.filter(data__gte=mes, data__lte=fim).select_related("categoria", "conta").order_by("-data", "-id")],
    }


def visao_geral(dono, hoje: date, mes: date | None = None, sem_poupanca: bool = False) -> dict:
    """Todas as contas e cartões juntos: saldo de cada um, o total e o que as faturas ainda vão levar.

    `sem_poupanca` deixa as poupanças de fora da lista, dos totais e dos lançamentos.
    """
    quitar_passados(dono, hoje)
    mes = inicio_do_mes(mes or hoje)
    fim = fim_do_mes(mes)
    gerar_ocorrencias(dono, fim)
    todas = Conta.objects.filter(dono=dono).select_related("vinculo_pluggy")
    escolhidas = todas.exclude(tipo=Conta.Tipo.POUPANCA) if sem_poupanca else todas
    saldos = {i: s for i, s in saldos_das_contas(dono).items() if i in {c.id for c in escolhidas}}
    contas = [{"id": c.id, "nome": c.nome, "tipo": c.tipo, "saldo": saldos[c.id], "pluggy": _tem_pluggy(c)} for c in escolhidas]
    # A fatura paga ainda não diz de qual conta saiu, então entra no total e não no saldo de uma conta.
    faturas_pagas = _soma(PagamentoFatura.objects.filter(dono=dono))

    cartoes = []
    for c in Cartao.objects.filter(dono=dono, ativo=True).select_related("vinculo_pluggy"):
        f = fatura_atual(c, hoje)
        paga = PagamentoFatura.objects.filter(cartao=c, fecha=f.fecha).exists()
        cartoes.append(
            {
                "id": c.id,
                "nome": c.nome,
                "final": c.final,
                "fatura": f.total,
                "fecha": f.fecha,
                "vence": f.vence,
                "aberta": f.fecha >= hoje,
                "paga": paga,
                "limite": c.limite,
                "disponivel": c.limite - limite_usado(c, hoje),
                "pluggy": _tem_pluggy(c),
            }
        )

    em_contas = sum(saldos.values()) - faturas_pagas
    a_pagar_cartoes = sum(c["fatura"] for c in cartoes if not c["paga"] and c["fatura"] > 0)
    qs = Lancamento.objects.filter(dono=dono, conta__in=list(saldos))
    return {
        "poupancas": todas.filter(tipo=Conta.Tipo.POUPANCA).count(),
        "sem_poupanca": sem_poupanca,
        "saldo_contas": sum(saldos.values()),
        "faturas_pagas": faturas_pagas,
        "em_contas": em_contas,
        "faturas_a_pagar": a_pagar_cartoes,
        "depois_das_faturas": em_contas - a_pagar_cartoes,
        "contas": contas,
        "cartoes": cartoes,
        "mes": _no_mes(qs, mes, fim),
        "movimentos": [_movimento(l) for l in qs.filter(data__gte=mes, data__lte=fim).select_related("categoria", "conta").order_by("-data", "-id")],
    }


@transaction.atomic
def repetir_lancamento(lanc: Lancamento, tipo: str, *, frequencia: str = Frequencia.MENSAL, parcela_atual: int = 1, parcela_total: int = 1) -> int:
    """Um lançamento único (vindo do banco, por exemplo) passa a recorrente ou a parcela k de n.

    Recorrente: vira a primeira ocorrência e as próximas aparecem nos meses seguintes.
    Parcelada: as parcelas que faltam são criadas mês a mês, como previsão. Devolve quantas criou.
    """
    hoje = date.today()
    if tipo == Lancamento.Tipo.RECORRENTE:
        rec = Recorrencia.objects.create(
            dono=lanc.dono,
            descricao=lanc.descricao,
            valor=lanc.valor,
            natureza=lanc.natureza,
            categoria=lanc.categoria,
            conta=lanc.conta,
            cartao=lanc.cartao,
            frequencia=frequencia,
            inicio=lanc.data,
            gerada_ate=lanc.data,
        )
        lanc.tipo, lanc.recorrencia = Lancamento.Tipo.RECORRENTE, rec
        lanc.save(update_fields=["tipo", "recorrencia", "atualizado_em"])
        return gerar_ocorrencias(lanc.dono, fim_do_mes(somar_meses(hoje, 1)))

    grupo = Lancamento.novo_grupo()
    lanc.tipo, lanc.grupo, lanc.parcela_atual, lanc.parcela_total = Lancamento.Tipo.PARCELADA, grupo, parcela_atual, parcela_total
    lanc.save(update_fields=["tipo", "grupo", "parcela_atual", "parcela_total", "atualizado_em"])
    seguintes = []
    for k in range(parcela_atual + 1, parcela_total + 1):
        data = somar_meses(lanc.data, k - parcela_atual)
        seguintes.append(
            Lancamento(
                dono=lanc.dono,
                descricao=lanc.descricao,
                valor=lanc.valor,
                natureza=lanc.natureza,
                data=data,
                categoria=lanc.categoria,
                conta=lanc.conta,
                cartao=lanc.cartao,
                tipo=Lancamento.Tipo.PARCELADA,
                grupo=grupo,
                parcela_atual=k,
                parcela_total=parcela_total,
                pago=data <= hoje,
            )
        )
    Lancamento.objects.bulk_create(seguintes)
    return len(seguintes)
