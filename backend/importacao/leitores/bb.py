"""CSV do extrato de conta corrente do Banco do Brasil.

Colunas: Data, Lançamento, Detalhes, Nº documento, Valor, Tipo Lançamento. As linhas de saldo
(Saldo Anterior, Saldo do dia, S A L D O) só servem para conferir.
"""

import csv
import io
import re
from datetime import datetime

from .base import ExtratoLido, Movimento, normalizar, valor_br

_SALDO = re.compile(r"^(saldo anterior|saldo do dia|s a l d o)$", re.IGNORECASE)
# "01/10 18:59 00007358439619 NOME" ou "06/10 NOME 009/010": tira data, hora e CPF/CNPJ.
_PREFIXO = re.compile(r"^\d{2}/\d{2}(?: \d{2}:\d{2})?\s+(?:\d{11,14}\s+)?")
_PARCELA = re.compile(r"\s+(\d{3})/(\d{3})$")
# Nestes o Detalhes traz quem recebeu ou pagou; nos outros, o nome do lançamento já diz tudo.
_COM_FAVORECIDO = ("pix", "pagamento de boleto", "ted", "doc", "transferencia", "transferido")
# Aplicação e resgate automáticos da conta: dinheiro do próprio titular.
_APLICACAO = ("bb rende facil", "aplicacao", "resgate")


def eh_bb(texto: str) -> bool:
    cabecalho = normalizar(texto.lstrip("﻿").splitlines()[0]) if texto.strip() else ""
    return cabecalho.startswith("data lancamento detalhes")


def ler(texto: str) -> ExtratoLido:
    extrato = ExtratoLido(banco="Banco do Brasil")
    linhas = list(csv.reader(io.StringIO(texto.lstrip("﻿"))))
    for linha in linhas[1:]:
        if len(linha) < 5 or not linha[0].strip():
            continue
        data = datetime.strptime(linha[0].strip(), "%d/%m/%Y").date()  # noqa: DTZ007
        lancamento, detalhes, documento, valor = (c.strip() for c in linha[1:5])
        if _SALDO.match(lancamento):
            if normalizar(lancamento) == "saldo anterior":
                extrato.saldo_anterior = valor_br(valor)
            else:
                extrato.saldo_final, extrato.data_final = valor_br(valor), data
            continue
        favorecido = _PREFIXO.sub("", detalhes)
        atual = total = None
        if p := _PARCELA.search(favorecido):
            atual, total = int(p.group(1)), int(p.group(2))
            favorecido = favorecido[: p.start()].strip()
        tipo = normalizar(lancamento)
        if tipo.startswith("pgto cdc") and detalhes:
            descricao = f"{lancamento} {detalhes.split('-')[0].strip()}"  # o número do contrato separa os empréstimos
        else:
            descricao = favorecido if favorecido and tipo.startswith(_COM_FAVORECIDO) else lancamento
        descricao = " ".join(descricao.split())
        extrato.itens.append(
            Movimento(
                data=data,
                descricao=descricao[:120],
                origem=lancamento,
                detalhes=detalhes,
                documento=documento,
                valor=valor_br(valor),
                parcela_atual=atual,
                parcela_total=total,
                aplicacao=tipo.startswith(_APLICACAO),
            )
        )
    return extrato
