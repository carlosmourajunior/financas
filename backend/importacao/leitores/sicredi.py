"""CSV da fatura do cartão Sicredi, separado por ponto e vírgula."""

import re
from datetime import date, datetime

from .base import FaturaLida, Item, Tipo, classificar, data_da_parcela, valor_br

_DATA = re.compile(r"^\d{2}/\d{2}/\d{4}$")
_PARCELA = re.compile(r"\((\d{1,2})/(\d{1,2})\)")
_CARTAO = re.compile(r"^\d{4}\.\d{2}XX\.XXXX\.(\d{4})$")


def eh_sicredi(texto: str) -> bool:
    inicio = texto[:600].lower()
    return "associado" in inicio and "cooperativa" in inicio


def _data(texto: str) -> date:
    return datetime.strptime(texto.strip(), "%d/%m/%Y").date()


def ler(texto: str, nome_arquivo: str = "") -> FaturaLida:
    fatura = FaturaLida(banco="Sicredi")
    resumo: dict[str, str] = {}

    for bruta in texto.lstrip("﻿").splitlines():
        partes = [p.strip().strip('"').strip() for p in bruta.split(";")]
        if not partes or not partes[0]:
            continue
        chave = partes[0]
        if m := _CARTAO.match(chave):
            fatura.final = m.group(1)
        elif _DATA.match(chave) and len(partes) >= 4 and partes[3]:
            descricao = re.sub(r"\s+", " ", partes[1]).strip()
            valor = valor_br(partes[3])
            atual = total = None
            if p := _PARCELA.search(partes[2]):
                atual, total = int(p.group(1)), int(p.group(2))
            fatura.itens.append(
                Item(
                    data=data_da_parcela(_data(chave), atual),
                    descricao=descricao,
                    valor=valor,
                    tipo=classificar(descricao, valor),
                    parcela_atual=atual,
                    parcela_total=total,
                )
            )
        elif len(partes) > 1:
            resumo[chave.lower()] = partes[1]

    if v := resumo.get("data de vencimento"):
        fatura.vencimento = _data(v)
    if v := resumo.get("valor total (r$)"):
        fatura.total = valor_br(v)

    # O resumo traz a fatura anterior e os encargos, que não aparecem como linhas.
    referencia = fatura.vencimento or (max(i.data for i in fatura.itens) if fatura.itens else date.today())
    if v := resumo.get("total da fatura anterior (r$)"):
        fatura.itens.append(Item(referencia, "Total da fatura anterior", valor_br(v), Tipo.SALDO_ANTERIOR))
    if (v := resumo.get("(+) encargos (r$)")) and valor_br(v):
        fatura.itens.append(Item(referencia, "Encargos da fatura", valor_br(v), Tipo.ENCARGO, categoria="encargos"))
    return fatura
