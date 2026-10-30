"""Reconhece o banco pelo conteúdo do arquivo e chama o leitor certo."""

from . import bb, itau, nubank, sicredi
from .base import ExtratoLido, FaturaLida, FormatoDesconhecido, Item, Movimento, Tipo

__all__ = ["ExtratoLido", "FaturaLida", "FormatoDesconhecido", "Item", "Movimento", "Tipo", "ler_extrato", "ler_fatura"]


def _texto(conteudo: bytes) -> str:
    for codificacao in ("utf-8-sig", "latin-1"):
        try:
            return conteudo.decode(codificacao)
        except UnicodeDecodeError:
            continue
    raise FormatoDesconhecido("Não conseguimos ler o texto do arquivo.")


def ler_fatura(conteudo: bytes, nome_arquivo: str = "") -> FaturaLida:
    if conteudo.startswith(b"%PDF"):
        if nubank.eh_nubank_pdf(conteudo):
            return nubank.ler_pdf(conteudo)
        return itau.ler_pdf(conteudo)
    texto = _texto(conteudo)
    if not texto.strip():
        raise FormatoDesconhecido("O arquivo está vazio.")
    if nubank.eh_nubank(texto):
        return nubank.ler(texto, nome_arquivo)
    if sicredi.eh_sicredi(texto):
        return sicredi.ler(texto, nome_arquivo)
    raise FormatoDesconhecido("Ainda não lemos faturas neste formato. Por enquanto: CSV ou PDF do Nubank, PDF do Itaú e CSV do Sicredi.")


def ler_extrato(conteudo: bytes, nome_arquivo: str = "") -> ExtratoLido:
    if conteudo.startswith(b"%PDF"):
        raise FormatoDesconhecido("Por enquanto lemos o extrato em CSV. No app do banco, exporte o extrato como CSV.")
    texto = _texto(conteudo)
    if not texto.strip():
        raise FormatoDesconhecido("O arquivo está vazio.")
    if bb.eh_bb(texto):
        return bb.ler(texto)
    raise FormatoDesconhecido("Ainda não lemos extratos neste formato. Por enquanto: CSV do Banco do Brasil.")
