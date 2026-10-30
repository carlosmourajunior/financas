"""Fatura do Nubank: o CSV exportado pelo app (date,title,amount) e o PDF da fatura."""

import csv
import io
import re
from collections import Counter
from datetime import date

from .base import FaturaLida, FormatoDesconhecido, Item, Tipo, classificar, valor_br

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


# --- PDF da fatura -------------------------------------------------------------------------------

_MESES = {m: i for i, m in enumerate("JAN FEV MAR ABR MAI JUN JUL AGO SET OUT NOV DEZ".split(), start=1)}
_VALOR_PDF = r"[−-]?R\$ [\d.]+,\d{2}"
_LINHA = re.compile(rf"^(\d{{2}}) ([A-Z]{{3}}) (?:•+ (\d{{4}}) )?(.+?) ({_VALOR_PDF})$")
# Movimentos internos do rotativo e de renegociação: entram e saem da fatura e se anulam.
_INTERNO = re.compile(
    r"^(saldo em atraso|cr[ée]dito de atraso|saldo em rotativo|cr[ée]dito de rotativo|encerramento de d[íi]vida|juros de d[íi]vida encerrada)",
    re.I,
)
# O PDF do Nubank às vezes não fecha por alguns centavos de arredondamento dos encargos.
LIMITE_AJUSTE = 100

LIMITE_PAGINAS = 40


def eh_nubank_pdf(conteudo: bytes) -> bool:
    import pdfplumber

    with pdfplumber.open(io.BytesIO(conteudo)) as pdf:
        texto = " ".join((p.extract_text() or "") for p in pdf.pages[:4])
    return "Nu Pagamentos" in texto


def ler_pdf(conteudo: bytes) -> FaturaLida:
    import pdfplumber

    with pdfplumber.open(io.BytesIO(conteudo)) as pdf:
        if len(pdf.pages) > LIMITE_PAGINAS:
            raise FormatoDesconhecido("O PDF tem páginas demais para uma fatura.")
        paginas = [p.extract_text() or "" for p in pdf.pages]
    return ler_paginas(paginas)


def _valor_pdf(texto: str) -> int:
    return valor_br(texto.replace("−", "-"))


def _data_pdf(dia: str, mes: str, vencimento: date) -> date:
    m = _MESES[mes]
    ano = vencimento.year if m <= vencimento.month else vencimento.year - 1
    return date(ano, m, int(dia))


def ler_paginas(paginas: list[str]) -> FaturaLida:
    """Separado do PDF para poder testar com texto."""
    texto = "\n".join(paginas)
    fatura = FaturaLida(banco="Nubank")
    if m := re.search(r"Data de vencimento: (\d{2}) ([A-Z]{3}) (\d{4})", texto):
        fatura.vencimento = date(int(m.group(3)), _MESES[m.group(2)], int(m.group(1)))
    if m := re.search(rf"^Total a pagar ({_VALOR_PDF})$", texto, re.M):
        fatura.total = _valor_pdf(m.group(1))
    referencia = fatura.vencimento or date.today()
    if m := re.search(rf"^Fatura anterior ({_VALOR_PDF})$", texto, re.M):
        fatura.itens.append(Item(referencia, "Fatura anterior", _valor_pdf(m.group(1)), Tipo.SALDO_ANTERIOR))

    finais: Counter[str] = Counter()
    interno = 0
    for pagina in paginas:
        if "TRANSAÇÕES" not in pagina:
            continue
        for linha in pagina.split("TRANSAÇÕES", 1)[1].splitlines():
            m = _LINHA.match(linha.strip())
            if not m or m.group(2) not in _MESES:
                continue
            dia, mes, final, descricao, valor_txt = m.groups()
            valor = _valor_pdf(valor_txt)
            if _INTERNO.match(descricao):
                interno += valor
                continue
            if final:
                finais[final] += 1
            atual = total = None
            if p := _PARCELA.search(descricao):
                atual, total = int(p.group(1)), int(p.group(2))
                descricao = descricao[: p.start()].strip()
            fatura.itens.append(
                Item(
                    data=_data_pdf(dia, mes, referencia),
                    descricao=descricao,
                    valor=valor,
                    tipo=classificar(descricao, valor),
                    parcela_atual=atual,
                    parcela_total=total,
                )
            )

    if interno:
        fatura.itens.append(Item(referencia, "Rotativo e renegociação", interno, classificar("encargo", interno), categoria="encargos"))
    if fatura.total is not None and 0 < abs(diferenca := fatura.total - fatura.total_calculado) <= LIMITE_AJUSTE:
        fatura.itens.append(
            Item(referencia, "Ajuste de centavos do Nubank", diferenca, classificar("encargo", diferenca), categoria="encargos")
        )
    fatura.final = finais.most_common(1)[0][0] if finais else ""
    return fatura
