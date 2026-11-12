"""Transações da Pluggy no mesmo formato que os leitores de arquivo devolvem.

Assim a prévia, a detecção de repetidos e a gravação são as mesmas da importação de arquivo:
nada que vem do banco entra sem passar pela revisão.
"""

import re
from datetime import date, timedelta

from importacao.leitores import ExtratoLido, FaturaLida, Item, Movimento, Tipo
from importacao.leitores.base import classificar, normalizar

from .pluggy import centavos

# Categoria da Pluggy (em inglês) -> ramo que a importação já sabe traduzir para uma categoria.
_RAMOS = [
    (("supermarket", "groceries", "food", "restaurant", "eating", "delivery", "bakery"), "supermercado"),
    (("health", "pharmacy", "drugstore", "hospital", "dentist", "clinic", "wellness"), "saude"),
    (("clothing", "apparel", "shoes"), "vestuario"),
    (("leisure", "entertainment", "streaming", "games", "cinema", "music", "sports", "gym"), "lazer"),
    (("travel", "airline", "hotel", "accommodation", "tourism"), "viagem"),
    (("education", "school", "university", "course", "books"), "educacao"),
    (("transport", "gas station", "fuel", "parking", "taxi", "ride", "toll", "vehicle", "automotive"), "transporte"),
    (("housing", "rent", "electricity", "water", "utilities", "home", "condominium"), "casa"),
    (("electronics",), "eletronicos"),
    (("interest", "fee", "tax", "iof", "late payment"), "encargos"),
]
# "LOJA X 03/10" ou "LOJA X PARC 03/10": a parcela já vem nos metadados.
_PARCELA_NO_FIM = re.compile(r"\s*(-\s*)?(parc(ela)?\.?\s*)?\d{1,2}\s*/\s*\d{1,2}\s*$", re.I)


def _ramo(categoria: str | None) -> str | None:
    texto = (categoria or "").lower()
    return next((ramo for palavras, ramo in _RAMOS if any(p in texto for p in palavras)), None)


def _data(t: dict) -> date:
    return date.fromisoformat(t["date"][:10])


def item_da_fatura(t: dict) -> Item | None:
    meta = t.get("creditCardMetadata") or {}
    atual, total = meta.get("installmentNumber"), meta.get("totalInstallments")
    if not (atual and total and 1 <= atual <= total and total > 1):
        atual = total = None
    descricao = (t.get("description") or t.get("descriptionRaw") or "Sem descrição").strip()
    if atual:
        descricao = _PARCELA_NO_FIM.sub("", descricao) or descricao
    # No cartão a compra vem positiva e o pagamento/estorno negativo, como nos arquivos.
    valor = centavos(t.get("amount"))
    tipo = classificar(descricao, valor)
    if tipo in (Tipo.PAGAMENTO, Tipo.SALDO_ANTERIOR) or valor == 0:
        # O pagamento da fatura anterior aparece no extrato da conta; aqui não vira lançamento.
        return None
    return Item(
        data=_data(t),
        descricao=descricao[:120],
        valor=valor,
        tipo=tipo,
        parcela_atual=atual,
        parcela_total=total,
        categoria=_ramo(t.get("category")),
    )


def fatura_fechada(nome: str, final: str, conta_faturas: list[dict], fatura: dict, transacoes: list[dict]) -> FaturaLida:
    """Os lançamentos de uma fatura já fechada. Pelo Open Finance cada transação traz o id da fatura."""
    com_fatura = [t for t in transacoes if (t.get("creditCardMetadata") or {}).get("billId")]
    if com_fatura:
        escolhidas = [t for t in com_fatura if t["creditCardMetadata"]["billId"] == fatura["id"]]
    else:
        # Sem o id (conectores diretos): pelo período entre o fechamento anterior e este.
        fecha = date.fromisoformat((fatura.get("billClosingDate") or fatura["dueDate"])[:10])
        anteriores = [b for b in conta_faturas if (b.get("dueDate") or "") < fatura["dueDate"]]
        abre = (
            date.fromisoformat((anteriores[0].get("billClosingDate") or anteriores[0]["dueDate"])[:10]) + timedelta(days=1)
            if anteriores
            else fecha - timedelta(days=31)
        )
        escolhidas = [t for t in transacoes if abre <= _data(t) <= fecha]
    itens = [i for i in map(item_da_fatura, escolhidas) if i]
    total = fatura.get("totalAmount")
    return FaturaLida(
        banco=nome,
        itens=sorted(itens, key=lambda i: i.data),
        total=centavos(total) if total is not None else None,
        vencimento=date.fromisoformat(fatura["dueDate"][:10]),
        final=final,
    )


def fatura_aberta(nome: str, final: str, ids_fechadas: set[str], abre: date, fecha: date, vence: date, transacoes: list[dict]) -> FaturaLida:
    """O que já entrou na fatura que ainda não fechou: sem fatura ou de fatura que a Pluggy ainda não listou."""
    escolhidas = [
        t
        for t in transacoes
        if (t.get("creditCardMetadata") or {}).get("billId") not in ids_fechadas and abre <= _data(t) <= fecha
    ]
    itens = [i for i in map(item_da_fatura, escolhidas) if i]
    return FaturaLida(banco=nome, itens=sorted(itens, key=lambda i: i.data), total=None, vencimento=vence, final=final)


_APLICACAO = ("aplicacao automatica", "resgate automatico", "rende facil", "aplic aut", "resg aut")


def movimento(t: dict) -> Movimento:
    valor = abs(centavos(t.get("amount")))
    if t.get("type") == "DEBIT":
        valor = -valor
    origem = (t.get("description") or t.get("descriptionRaw") or "").strip()
    pagamento = t.get("paymentData") or {}
    # Pix e TED trazem quem pagou ou recebeu; é o nome que interessa na lista.
    outro = (pagamento.get("receiver") if valor < 0 else pagamento.get("payer")) or {}
    nome = (outro.get("name") or "").strip()
    texto = normalizar(origem)
    return Movimento(
        data=_data(t),
        descricao=(nome or origem or "Sem descrição")[:120],
        origem=origem[:120] if nome else (pagamento.get("paymentMethod") or ""),
        valor=valor,
        detalhes=t.get("category") or "",
        # O id da transação não muda de pendente para efetivada: importar de novo não duplica.
        documento=t.get("providerId") or t.get("id") or "",
        aplicacao=any(p in texto for p in _APLICACAO),
    )


def extrato(nome: str, transacoes: list[dict]) -> ExtratoLido:
    # Pendentes (agendamentos, bloqueios) só entram depois de efetivadas.
    efetivadas = [t for t in transacoes if t.get("status", "POSTED") == "POSTED" and centavos(t.get("amount"))]
    return ExtratoLido(banco=nome, itens=sorted((movimento(t) for t in efetivadas), key=lambda m: m.data))
