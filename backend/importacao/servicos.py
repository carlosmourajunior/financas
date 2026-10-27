"""Da fatura lida para lançamentos: prévia para revisar e gravação do que foi escolhido."""

from datetime import date, timedelta

from django.db import transaction

from financas.models import Cartao, Categoria, Lancamento, Natureza
from financas.servicos import Fatura, _vencimento, fatura_que_fecha_em, somar_meses

from .leitores import FaturaLida, Item, Tipo
from .leitores.base import normalizar, sem_acento

# Ramo informado pelo banco ou palavra da descrição -> categoria padrão.
_POR_RAMO = {
    "supermercado": "Alimentação",
    "supermarket": "Alimentação",
    "restaurante": "Alimentação",
    "saude": "Saúde",
    "health": "Saúde",
    "vestuario": "Vestuário",
    "lazer": "Lazer",
    "viagem": "Lazer",
    "hotel": "Lazer",
    "educacao": "Educação",
    "transporte": "Transporte",
    "casa": "Moradia",
    "eletronicos": "Eletrônicos",
    "encargos": "Taxas",
}
_POR_PALAVRA = [
    (("juros", "iof", "multa", "anuidade", "encargo", "tarifa", "mensalidade - plano"), "Taxas"),
    (("posto", "uber", "99app", "estacionamento", "pedagio", "tagitau", "sem parar"), "Transporte"),
    (("mercado", "sup ", "hortifruti", "horti", "panificadora", "padaria", "acougue", "acai", "lanchonete", "restaurante"), "Alimentação"),
    (("burger", "mcdonald", "sushi", "pizza", "delivery", "ifood", "temakeria", "grill"), "Alimentação"),
    (("drogaria", "drogasil", "farmacia", "medical", "clinica"), "Saúde"),
    (("spotify", "netflix", "youtube", "playstation", "amazonprime", "apple.com", "google one", "cine"), "Lazer"),
    (("shoes", "store", "moda", "confeccoe", "centauro"), "Vestuário"),
    (("papelaria",), "Educação"),
    (("ipva",), "Transporte"),
]

IMPORTAVEIS = (Tipo.COMPRA, Tipo.ENCARGO, Tipo.CREDITO)


def ciclo_da_fatura(cartao: Cartao, lida: FaturaLida) -> Fatura:
    """A fatura do app que corresponde à do arquivo, pelo vencimento ou pelas compras."""
    if lida.vencimento:
        candidatas = [somar_meses(lida.vencimento, -m, cartao.dia_fechamento) for m in range(0, 3)]
        fecha = min(candidatas, key=lambda f: abs((_vencimento(cartao, f) - lida.vencimento).days))
    else:
        # Sem vencimento no arquivo: o ciclo que contém a compra mais recente sem parcela.
        datas = [i.data for i in lida.itens if i.tipo == Tipo.COMPRA and not i.parcela_total] or [i.data for i in lida.itens]
        ultima = max(datas)
        fecha = date(ultima.year, ultima.month, cartao.dia_fechamento)
        if ultima > fecha:
            fecha = somar_meses(fecha, 1, cartao.dia_fechamento)
    return fatura_que_fecha_em(cartao, fecha)


def _dentro(d: date, ciclo: Fatura) -> date:
    """O app separa as faturas pela data; prende cada linha no ciclo desta fatura."""
    return min(max(d, ciclo.abre), ciclo.fecha)


def _sugerir_categoria(item: Item, por_nome: dict[str, Categoria], historico: dict[str, int]) -> int | None:
    chave = normalizar(item.descricao)
    if chave in historico:
        return historico[chave]
    nome = _POR_RAMO.get(sem_acento(item.categoria or "").lower())
    if not nome:
        texto = item.descricao.lower()
        nome = next((n for palavras, n in _POR_PALAVRA if any(p in texto for p in palavras)), None)
    if item.tipo == Tipo.ENCARGO:
        nome = "Taxas"
    cat = por_nome.get(nome.lower()) if nome else None
    return cat.id if cat else None


def previa(cartao: Cartao, lida: FaturaLida) -> dict:
    dono = cartao.dono
    ciclo = ciclo_da_fatura(cartao, lida)
    categorias = Categoria.objects.filter(dono=dono, natureza=Natureza.DESPESA)
    por_nome = {c.nome.lower(): c for c in categorias}
    # A última categoria usada para cada descrição vale mais que o palpite.
    historico = {}
    for desc, cat in (
        Lancamento.objects.filter(dono=dono, categoria__isnull=False).order_by("data").values_list("descricao", "categoria")
    ):
        historico[normalizar(desc)] = cat

    # Lançamentos que já existem no cartão perto deste ciclo, para marcar repetidos.
    existentes = list(
        Lancamento.objects.filter(dono=dono, cartao=cartao, data__gte=ciclo.abre - timedelta(days=7), data__lte=ciclo.fecha + timedelta(days=7))
    )

    def repetido(data: date, valor: int, descricao: str, atual, total) -> bool:
        chave = normalizar(descricao)
        for e in existentes:
            mesma_parcela = (e.parcela_atual, e.parcela_total) == (atual, total)
            if e.valor == valor and mesma_parcela and (normalizar(e.descricao) == chave or abs((e.data - data).days) <= 1):
                existentes.remove(e)  # cada existente só cobre uma linha
                return True
        return False

    itens = []
    for i in lida.itens:
        if i.tipo not in IMPORTAVEIS or i.valor == 0:
            continue
        data = _dentro(i.data, ciclo)
        valor = abs(i.valor)
        dup = repetido(data, valor, i.descricao, i.parcela_atual, i.parcela_total)
        itens.append(
            {
                "data": data,
                "descricao": i.descricao,
                "valor": valor,
                "natureza": Natureza.RECEITA if i.valor < 0 else Natureza.DESPESA,
                "tipo": i.tipo,
                "parcela_atual": i.parcela_atual,
                "parcela_total": i.parcela_total,
                "categoria": None if i.valor < 0 else _sugerir_categoria(i, por_nome, historico),
                "repetido": dup,
                "importar": not dup,
            }
        )

    # O que sobrou da fatura anterior sem pagar (rotativo) também é cobrado nesta;
    # se pagou a mais, a diferença vira crédito.
    carregado = sum(i.valor for i in lida.itens if i.tipo in (Tipo.SALDO_ANTERIOR, Tipo.PAGAMENTO))
    if carregado:
        descricao = "Saldo não pago da fatura anterior" if carregado > 0 else "Crédito da fatura anterior"
        dup = repetido(ciclo.abre, abs(carregado), descricao, None, None)
        taxas = por_nome.get("taxas")
        itens.insert(
            0,
            {
                "data": ciclo.abre,
                "descricao": descricao,
                "valor": abs(carregado),
                "natureza": Natureza.DESPESA if carregado > 0 else Natureza.RECEITA,
                "tipo": Tipo.SALDO_ANTERIOR,
                "parcela_atual": None,
                "parcela_total": None,
                "categoria": taxas.id if taxas and carregado > 0 else None,
                "repetido": dup,
                "importar": not dup,
            },
        )

    return {
        "banco": lida.banco,
        "final": lida.final,
        "final_confere": not lida.final or not cartao.final or lida.final == cartao.final,
        "vencimento": lida.vencimento,
        "total": lida.total,
        "total_lido": lida.total_calculado,
        "conferida": lida.conferida,
        "ciclo": {"abre": ciclo.abre, "fecha": ciclo.fecha, "vence": ciclo.vence},
        "itens": itens,
    }


@transaction.atomic
def confirmar(cartao: Cartao, itens: list[dict]) -> int:
    """Grava as linhas escolhidas. Uma parcela k de n cria também as parcelas seguintes."""
    hoje = date.today()
    criados = 0
    for i in itens:
        base = {
            "dono": cartao.dono,
            "cartao": cartao,
            "descricao": i["descricao"],
            "natureza": i["natureza"],
            # Da prévia vem o id; da API, a categoria já validada.
            "categoria_id": getattr(i.get("categoria"), "id", i.get("categoria")),
        }
        atual, total = i.get("parcela_atual"), i.get("parcela_total")
        if atual and total and total >= atual:
            grupo = Lancamento.novo_grupo()
            for k in range(atual, total + 1):
                data = somar_meses(i["data"], k - atual)
                Lancamento.objects.create(
                    **base,
                    valor=i["valor"],
                    data=data,
                    tipo=Lancamento.Tipo.PARCELADA,
                    pago=data <= hoje,
                    grupo=grupo,
                    parcela_atual=k,
                    parcela_total=total,
                )
                criados += 1
        else:
            Lancamento.objects.create(**base, valor=i["valor"], data=i["data"], tipo=Lancamento.Tipo.UNICA, pago=i["data"] <= hoje)
            criados += 1
    return criados
