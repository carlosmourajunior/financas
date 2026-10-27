"""CSV exportado pelo app do Nubank: date,title,amount."""

import csv
import io
import re
from datetime import date

from .base import FaturaLida, Item, classificar, valor_br

_PARCELA = re.compile(r"\s*-\s*(?:Parcela\s+)?(\d{1,2})/(\d{1,2})\s*$", re.I)
_DATA_NO_NOME = re.compile(r"(\d{4})-(\d{2})-(\d{2})")


def eh_nubank(texto: str) -> bool:
    return texto.lstrip("﻿").splitlines()[0].strip().lower() == "date,title,amount"


def ler(texto: str, nome_arquivo: str = "") -> FaturaLida:
    # O Nubank nomeia o arquivo com a data de vencimento (Nubank_2026-08-22.csv).
    m = _DATA_NO_NOME.search(nome_arquivo)
    fatura = FaturaLida(banco="Nubank", vencimento=date(*map(int, m.groups())) if m else None)

    for linha in csv.DictReader(io.StringIO(texto.lstrip("﻿"))):
        descricao = linha["title"].strip()
        valor = valor_br(linha["amount"])
        atual = total = None
        if p := _PARCELA.search(descricao):
            atual, total = int(p.group(1)), int(p.group(2))
            descricao = descricao[: p.start()].strip()
        fatura.itens.append(
            Item(
                data=date.fromisoformat(linha["date"]),
                descricao=descricao,
                valor=valor,
                tipo=classificar(descricao, valor),
                parcela_atual=atual,
                parcela_total=total,
            )
        )
    return fatura
