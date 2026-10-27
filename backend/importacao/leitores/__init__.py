"""Reconhece o banco pelo conteúdo do arquivo e chama o leitor certo."""

from . import itau, nubank, sicredi
from .base import FaturaLida, FormatoDesconhecido, Item, Tipo

__all__ = ["FaturaLida", "FormatoDesconhecido", "Item", "Tipo", "ler_fatura"]


def _texto(conteudo: bytes) -> str:
    for codificacao in ("utf-8-sig", "latin-1"):
        try:
            return conteudo.decode(codificacao)
        except UnicodeDecodeError:
            continue
    raise FormatoDesconhecido("Não conseguimos ler o texto do arquivo.")


def ler_fatura(conteudo: bytes, nome_arquivo: str = "") -> FaturaLida:
    if conteudo.startswith(b"%PDF"):
        return itau.ler_pdf(conteudo)
    texto = _texto(conteudo)
    if not texto.strip():
        raise FormatoDesconhecido("O arquivo está vazio.")
    if nubank.eh_nubank(texto):
        return nubank.ler(texto, nome_arquivo)
    if sicredi.eh_sicredi(texto):
        return sicredi.ler(texto, nome_arquivo)
    raise FormatoDesconhecido("Ainda não lemos faturas neste formato. Por enquanto: CSV do Nubank, PDF do Itaú e CSV do Sicredi.")
