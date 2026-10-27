"""PDF da fatura do cartão Itaú.

As páginas de lançamentos têm duas colunas; cada coluna é lida separada e na ordem
(esquerda, direita), e as linhas passam por uma máquina de estados por seção.
"""

import io
import re
from datetime import date, datetime

from .base import FaturaLida, FormatoDesconhecido, Item, Tipo, classificar, data_da_parcela, data_sem_ano, valor_br

VALOR = r"-?[\d.]+,\d{2}"
# A letra no fim é a marca do resumo da coluna vizinha (P, S, E, L) que às vezes cai nesta coluna.
_ITEM = re.compile(rf"^(\d{{2}}/\d{{2}}) (.+?) ({VALOR})(?: [A-Z=])?$")
_PARCELA = re.compile(r"\s(\d{2})/(\d{2})$")
_DATA_DD_MM = re.compile(r"^\d{2}/\d{2}$")

# Primeira palavra da linha abaixo de cada compra: o ramo do estabelecimento.
_RAMOS = {
    "supermercado",
    "supermarket",
    "restaurante",
    "saúde",
    "health",
    "vestuário",
    "lazer",
    "educação",
    "transporte",
    "viagem",
    "hotel",
    "casa",
    "eletronicos",
    "serviços",
    "outros",
}

LIMITE_PAGINAS = 40


def eh_itau(texto_primeira_pagina: str) -> bool:
    t = texto_primeira_pagina.lower()
    return "itaú" in t or "itau" in t


def _buscar(padrao: str, texto: str) -> str | None:
    m = re.search(padrao, texto)
    return m.group(1) if m else None


def colunas(pagina) -> list[str]:
    """Texto de cada coluna da página, da esquerda para a direita."""
    largura = pagina.width
    datas_direita = [
        w["x0"] for w in pagina.extract_words() if _DATA_DD_MM.match(w["text"]) and w["x0"] > largura / 2
    ]
    if not datas_direita:
        return [pagina.extract_text(x_tolerance=1.5) or ""]
    corte = min(datas_direita) - 5
    return [
        pagina.crop((0, 0, corte, pagina.height)).extract_text(x_tolerance=1.5) or "",
        pagina.crop((corte, 0, largura, pagina.height)).extract_text(x_tolerance=1.5) or "",
    ]


def ler_pdf(conteudo: bytes) -> FaturaLida:
    import pdfplumber

    with pdfplumber.open(io.BytesIO(conteudo)) as pdf:
        if len(pdf.pages) > LIMITE_PAGINAS:
            raise FormatoDesconhecido("O PDF tem páginas demais para uma fatura.")
        capa = pdf.pages[0].extract_text() or ""
        if not eh_itau(capa):
            raise FormatoDesconhecido("Não reconhecemos este PDF como fatura do Itaú.")
        textos = [t for p in pdf.pages[1:] for t in colunas(p)]
    return ler_texto(capa, textos)


def ler_texto(capa: str, colunas_texto: list[str]) -> FaturaLida:
    """Separado do PDF para poder testar com texto."""
    fatura = FaturaLida(banco="Itaú")
    if v := _buscar(r"Vencimento:\s*(\d{2}/\d{2}/\d{4})", capa):
        fatura.vencimento = datetime.strptime(v, "%d/%m/%Y").date()
    if v := _buscar(rf"Total desta fatura\s+({VALOR})", capa):
        fatura.total = valor_br(v)
    fatura.final = _buscar(r"Cart[ãa]o\s+\d{4}\.XXXX\.XXXX\.(\d{4})", capa) or ""
    referencia = fatura.vencimento or date.today()

    if v := _buscar(rf"Total da fatura anterior\s+({VALOR})", capa):
        fatura.itens.append(Item(referencia, "Total da fatura anterior", valor_br(v), Tipo.SALDO_ANTERIOR))
    if (v := _buscar(rf"Encargos \(Financiamento \+ morat[óo]rio\)\s+({VALOR})", capa)) and valor_br(v):
        fatura.itens.append(Item(referencia, "Encargos (juros e IOF do financiamento)", valor_br(v), Tipo.ENCARGO, categoria="encargos"))

    secao = None
    anterior: Item | None = None
    for linha in (l.strip() for t in colunas_texto for l in t.splitlines()):
        if linha.startswith("Pagamentos efetuados"):
            secao = "pagamentos"
        elif linha.startswith("Lançamentos: compras e saques"):
            secao = "compras"
        elif linha.startswith("Lançamentos internacionais"):
            secao = "internacionais"
        elif linha.startswith("Lançamentos: produtos e serviços"):
            secao = "servicos"
        elif linha.startswith("Compras parceladas - próximas faturas"):
            break  # daqui em diante é projeção, não cobrança desta fatura
        elif secao == "internacionais" and (v := _buscar(rf"^Repasse de IOF em R\$ ({VALOR})$", linha)):
            fatura.itens.append(Item(referencia, "IOF de compras internacionais", valor_br(v), Tipo.ENCARGO, categoria="encargos"))
        elif secao and (m := _ITEM.match(linha)):
            dia_mes, descricao, valor_txt = m.groups()
            valor = valor_br(valor_txt)
            atual = total = None
            if p := _PARCELA.search(descricao):
                atual, total = int(p.group(1)), int(p.group(2))
                descricao = descricao[: p.start()].strip()
            tipo = Tipo.PAGAMENTO if secao == "pagamentos" else classificar(descricao, valor)
            anterior = Item(
                data=data_da_parcela(data_sem_ano(dia_mes, referencia), atual),
                descricao=descricao,
                valor=valor,
                tipo=tipo,
                parcela_atual=atual,
                parcela_total=total,
            )
            fatura.itens.append(anterior)
            continue
        elif anterior and secao == "compras" and anterior.categoria is None:
            ramo = linha.split(" ", 1)[0].lower()
            if ramo in _RAMOS:
                anterior.categoria = ramo
        anterior = None
    return fatura
