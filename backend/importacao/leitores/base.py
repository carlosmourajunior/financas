"""Formato comum que todo leitor de fatura devolve."""

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date

from financas.servicos import somar_meses


class FormatoDesconhecido(ValueError):
    pass


class Tipo:
    COMPRA = "compra"
    ENCARGO = "encargo"  # juros, IOF, multa, anuidade
    CREDITO = "credito"  # estorno ou crédito na fatura
    PAGAMENTO = "pagamento"  # pagamento da fatura anterior: não vira lançamento
    SALDO_ANTERIOR = "saldo_anterior"  # total da fatura anterior: não vira lançamento


@dataclass
class Item:
    data: date
    descricao: str
    valor: int  # centavos; positivo é cobrança, negativo é crédito
    tipo: str = Tipo.COMPRA
    parcela_atual: int | None = None
    parcela_total: int | None = None
    categoria: str | None = None  # categoria sugerida pelo banco, em texto livre


@dataclass
class FaturaLida:
    banco: str
    itens: list[Item] = field(default_factory=list)
    total: int | None = None  # total declarado no arquivo
    vencimento: date | None = None
    final: str = ""

    @property
    def total_calculado(self) -> int:
        return sum(i.valor for i in self.itens)

    @property
    def conferida(self) -> bool | None:
        """True quando os itens lidos somam o total da fatura; None quando o arquivo não traz o total."""
        return None if self.total is None else self.total_calculado == self.total


def valor_br(texto: str) -> int:
    """'R$ -1.234,56', '- 957,49' ou '1.011,04' em centavos."""
    limpo = texto.replace("R$", "").replace(" ", "").replace("\xa0", "").replace(".", "")
    negativo = limpo.startswith("-")
    limpo = limpo.lstrip("-+")
    inteiro, _, centavos = limpo.partition(",")
    total = int(inteiro or 0) * 100 + int((centavos + "00")[:2])
    return -total if negativo else total


def sem_acento(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c))


def normalizar(texto: str) -> str:
    """Chave para comparar descrições: minúsculas, sem acento, só letras e números."""
    return re.sub(r"[^a-z0-9]+", " ", sem_acento(texto).lower()).strip()


_PAGAMENTO = re.compile(r"^(pagamento|pag fat|pgto fat)", re.I)
_SALDO = re.compile(r"(valor pendente|saldo anterior|fatura anterior)", re.I)
_ENCARGO = re.compile(r"(juros|iof|multa|anuidade|mensalidade|encargo|tarifa)", re.I)


def classificar(descricao: str, valor: int) -> str:
    if _PAGAMENTO.search(descricao) and valor < 0:
        return Tipo.PAGAMENTO
    if _SALDO.search(descricao):
        return Tipo.SALDO_ANTERIOR
    if valor < 0:
        return Tipo.CREDITO
    if _ENCARGO.search(descricao):
        return Tipo.ENCARGO
    return Tipo.COMPRA


def data_sem_ano(dia_mes: str, referencia: date) -> date:
    """'02/11' na fatura que vence em referência: o ano mais recente que não passa dela."""
    dia, mes = map(int, dia_mes.split("/"))
    ano = referencia.year if (mes, dia) <= (referencia.month, referencia.day) else referencia.year - 1
    try:
        return date(ano, mes, dia)
    except ValueError:  # 29/02 fora de ano bissexto
        return date(ano, mes, 28)


def data_da_parcela(compra: date, parcela_atual: int | None) -> date:
    """Bancos mostram a data da compra; a parcela k cai k-1 meses depois."""
    return somar_meses(compra, (parcela_atual or 1) - 1) if parcela_atual else compra


@dataclass
class Movimento:
    """Uma linha do extrato da conta."""

    data: date
    descricao: str  # quem recebeu ou pagou, ou o nome do lançamento
    origem: str  # o lançamento como o banco escreve (Pix - Enviado, Pagamento de Boleto…)
    valor: int  # centavos; positivo entra, negativo sai
    detalhes: str = ""
    documento: str = ""
    parcela_atual: int | None = None
    parcela_total: int | None = None
    aplicacao: bool = False  # aplicação ou resgate automático da própria conta


@dataclass
class ExtratoLido:
    banco: str
    itens: list[Movimento] = field(default_factory=list)
    saldo_anterior: int | None = None
    saldo_final: int | None = None
    data_final: date | None = None

    @property
    def conferido(self) -> bool | None:
        """True quando saldo anterior + movimentos dá o saldo final do arquivo."""
        if self.saldo_anterior is None or self.saldo_final is None:
            return None
        return self.saldo_anterior + sum(i.valor for i in self.itens) == self.saldo_final
