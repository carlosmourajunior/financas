"""Cliente mínimo da API da Pluggy (https://docs.pluggy.ai), só leitura.

Uso pessoal com o MeuPluggy: as contas vêm dos itens listados em PLUGGY_ITEM_IDS, que pertencem
ao dono da instância. Por isso só os e-mails de PLUGGY_USUARIOS enxergam esses dados.
"""

import json
import logging
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.conf import settings
from django.core.cache import cache

log = logging.getLogger("openfinance")

URL = "https://api.pluggy.ai"
CHAVE_CACHE = "pluggy:api-key"
# A chave da API vale 2 horas; renova antes.
VALIDADE_CHAVE = 90 * 60


class ErroPluggy(Exception):
    pass


def ativo() -> bool:
    return bool(settings.PLUGGY_CLIENT_ID and settings.PLUGGY_CLIENT_SECRET and settings.PLUGGY_ITEM_IDS)


def liberado_para(usuario) -> bool:
    """O módulo está ligado e este usuário é o dono das contas conectadas."""
    if not ativo() or not getattr(usuario, "is_authenticated", False):
        return False
    # Igualdade exata: o cadastro já grava o e-mail em minúsculas. Comparar com .lower() deixava
    # passar uma conta "DONO@..." diferente da do dono.
    return usuario.email in settings.PLUGGY_USUARIOS


def _requisicao(metodo: str, caminho: str, corpo: dict | None = None, chave: str | None = None) -> dict:
    cabecalhos = {"Content-Type": "application/json", "Accept": "application/json"}
    if chave:
        cabecalhos["X-API-KEY"] = chave
    dados = json.dumps(corpo).encode() if corpo is not None else None
    req = urllib.request.Request(f"{URL}{caminho}", data=dados, headers=cabecalhos, method=metodo)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as exc:
        detalhe = exc.read()[:300].decode(errors="replace")
        log.warning("Pluggy %s %s respondeu %s: %s", metodo, caminho.split("?")[0], exc.code, detalhe)
        if exc.code in (401, 403):
            cache.delete(CHAVE_CACHE)
            raise ErroPluggy("A Pluggy recusou as credenciais. Confira PLUGGY_CLIENT_ID e PLUGGY_CLIENT_SECRET.") from exc
        raise ErroPluggy("A Pluggy não respondeu como esperado. Tente de novo em alguns minutos.") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        log.warning("Pluggy fora do ar: %s", exc)
        raise ErroPluggy("Não conseguimos falar com a Pluggy agora. Tente de novo em alguns minutos.") from exc


def _chave() -> str:
    chave = cache.get(CHAVE_CACHE)
    if not chave:
        r = _requisicao("POST", "/auth", {"clientId": settings.PLUGGY_CLIENT_ID, "clientSecret": settings.PLUGGY_CLIENT_SECRET})
        chave = r["apiKey"]
        cache.set(CHAVE_CACHE, chave, VALIDADE_CHAVE)
    return chave


def _get(caminho: str, **params) -> dict:
    query = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
    return _requisicao("GET", f"{caminho}?{query}" if query else caminho, chave=_chave())


def centavos(valor) -> int:
    return int((Decimal(str(valor or 0)) * 100).quantize(Decimal(1)))


def _data(texto: str | None) -> date | None:
    return date.fromisoformat(texto[:10]) if texto else None


# Código do banco (COMPE), que abre o número de transferência da conta: "0260/0001/12345-6".
BANCOS = {
    "001": "Banco do Brasil",
    "033": "Santander",
    "041": "Banrisul",
    "070": "BRB",
    "077": "Inter",
    "104": "Caixa",
    "208": "BTG Pactual",
    "212": "Banco Original",
    "237": "Bradesco",
    "260": "Nubank",
    "290": "PagBank",
    "323": "Mercado Pago",
    "336": "C6 Bank",
    "341": "Itaú",
    "380": "PicPay",
    "422": "Safra",
    "655": "Neon",
    "748": "Sicredi",
    "756": "Sicoob",
}
# Conectores que não são o banco: com o MeuPluggy o banco vem do número da conta ou do nome.
_INTERMEDIARIOS = ("meupluggy", "meu pluggy", "pluggy")


def _banco_do_numero(transferencia: str) -> str:
    codigo = (transferencia or "").split("/")[0].strip().lstrip("0").zfill(3)
    return BANCOS.get(codigo, "")


_APELIDOS = {"nu pagamentos": "Nubank", "nu financeira": "Nubank", "itau unibanco": "Itaú", "caixa economica": "Caixa", "c6": "C6 Bank", "btg": "BTG Pactual"}


def _banco_no_texto(*textos: str) -> str:
    from importacao.leitores.base import normalizar

    texto = f" {normalizar(' '.join(textos))} "
    nomes = {normalizar(n): n for n in BANCOS.values()} | _APELIDOS
    return next((n for chave, n in sorted(nomes.items(), key=lambda x: -len(x[0])) if f" {chave} " in texto), "")


@dataclass
class ContaPluggy:
    id: str
    tipo: str  # BANK ou CREDIT
    nome: str
    numero: str
    saldo: int
    subtipo: str = ""
    item: str = ""
    banco: str = ""  # nome do banco, para quem tem cartão ou conta em mais de um
    limite: int = 0  # cartão: limite total
    vencimento: date | None = None  # cartão: vencimento da fatura atual
    fechamento: date | None = None


def contas() -> list[ContaPluggy]:
    """As contas e cartões de todos os itens configurados."""
    resultado = []
    for item in settings.PLUGGY_ITEM_IDS:
        brutas = _get("/accounts", itemId=item).get("results", [])
        conector = ((_get(f"/items/{item}").get("connector") or {}).get("name") or "").strip()
        if conector.lower() in _INTERMEDIARIOS:
            conector = ""
        # Um item é um banco: o número de uma conta corrente identifica o banco do cartão também.
        # Com o MeuPluggy o conector não diz o banco: vem do número de transferência ou do nome
        # da conta corrente ("Nu Pagamentos S.A. - Instituição de Pagamento"), que vale para o cartão.
        banco = (
            conector
            or next((b for a in brutas if (b := _banco_do_numero((a.get("bankData") or {}).get("transferNumber", "")))), "")
            or _banco_no_texto(*(f"{a.get('marketingName') or ''} {a.get('name') or ''}" for a in brutas))
        )
        for a in brutas:
            credito = a.get("creditData") or {}
            resultado.append(
                ContaPluggy(
                    id=a["id"],
                    tipo=a.get("type", ""),
                    nome=a.get("marketingName") or a.get("name") or "",
                    numero=a.get("number") or "",
                    saldo=centavos(a.get("balance")),
                    subtipo=a.get("subtype") or "",
                    item=item,
                    banco=banco or (credito.get("brand") or "").title(),
                    limite=centavos(credito.get("creditLimit")),
                    vencimento=_data(credito.get("balanceDueDate")),
                    fechamento=_data(credito.get("balanceCloseDate")),
                )
            )
    return resultado


_RAZAO_SOCIAL = re.compile(
    r"\b(s\s*/\s*a|s\.?\s?a\.?|ltda|instituic[aã]o de pagamento|banco m[uú]ltiplo|cooperativa|sociedade de cr[eé]dito)(?=\W|$)", re.I
)
_PEQUENAS = {"de", "do", "da", "dos", "das", "e"}
# Palavras do nome que já são o banco: "AZUL ITAU VISA INFINITE" do Itaú vira "Itaú Azul Visa Infinite".
_PALAVRAS_DO_BANCO = {"Nubank": {"nubank", "nu"}, "Itaú": {"itau", "unibanco"}, "C6 Bank": {"c6"}, "BTG Pactual": {"btg", "pactual"}}


def _normal(texto: str) -> str:
    from importacao.leitores.base import normalizar

    return normalizar(texto)


def titulo(texto: str) -> str:
    """'OUROCARD PLATINUM VISA' e 'platinum' em 'Ourocard Platinum Visa' e 'Platinum'. Misturado fica como veio."""
    if not (texto.isupper() or texto.islower()):
        return texto
    palavras = texto.lower().split()
    return " ".join(p if i and p in _PEQUENAS else p[:1].upper() + p[1:] for i, p in enumerate(palavras))


def _sem_o_banco(nome: str, banco: str) -> str:
    chaves = _PALAVRAS_DO_BANCO.get(banco) or {w for w in _normal(banco).split() if w not in _PEQUENAS and w != "banco"}
    frase = _normal(banco)
    resto = [p for p in nome.split() if _normal(p) not in chaves and _normal(p) not in _PEQUENAS | {"banco"}]
    # Só tira as palavras quando o banco aparece no nome; "Conta Azul" de outro banco fica inteira.
    if not (frase in _normal(nome) or any(_normal(p) in chaves for p in nome.split())):
        return nome
    return " ".join(resto)


def nome_com_banco(c: "ContaPluggy", padrao: str) -> str:
    """O banco na frente, sem razão social nem banco repetido.

    'platinum' do Nubank vira 'Nubank Platinum'; 'Nu Pagamentos S.A. - ...' e 'BANCO DO BRASIL S/A'
    viram 'Nubank' e 'Banco do Brasil'; 'Mercado Pago (Conta Pré-paga)' vira 'Mercado Pago'.
    """
    nome = re.sub(r"\s*\([^)]*\)\s*$", "", c.nome.strip()) if c.tipo == "BANK" else c.nome.strip()
    if c.banco and _RAZAO_SOCIAL.search(nome):
        nome = ""
    nome = titulo(nome)
    if c.banco:
        nome = f"{c.banco} {_sem_o_banco(nome, c.banco)}".strip()
    nome = nome or padrao
    if c.tipo == "BANK" and c.subtipo == "SAVINGS_ACCOUNT" and "poupan" not in nome.lower():
        nome = f"{nome} Poupança"
    return nome


def final_do_cartao(numero: str) -> str:
    digitos = re.sub(r"\D", "", numero or "")
    return digitos[-4:] if len(digitos) >= 4 else ""


def nomes(contas_: list["ContaPluggy"]) -> dict[str, str]:
    """Nome de cada conta no app. Iguais ganham o número no fim (cartões se separam pelo final)."""
    base = {c.id: nome_com_banco(c, "Cartão" if c.tipo == "CREDIT" else "Conta") for c in contas_}
    contagem: dict[tuple, int] = {}
    for c in contas_:
        contagem[(c.tipo, base[c.id])] = contagem.get((c.tipo, base[c.id]), 0) + 1
    resultado = {}
    for c in contas_:
        nome, limite = base[c.id], 40 if c.tipo == "CREDIT" else 80
        if contagem[(c.tipo, nome)] > 1 and c.tipo == "BANK" and c.numero:
            sufixo = f" {c.numero.strip()[-12:]}"
            nome = nome[: limite - len(sufixo)] + sufixo
        resultado[c.id] = nome[:limite]
    return resultado


def conta(conta_id: str) -> ContaPluggy | None:
    return next((c for c in contas() if c.id == conta_id), None)


def transacoes(conta_id: str, desde: date, ate: date) -> list[dict]:
    """Todas as transações do período, seguindo o cursor da API."""
    resultado = []
    params = {"accountId": conta_id, "dateFrom": desde.isoformat(), "dateTo": ate.isoformat()}
    while True:
        r = _get("/v2/transactions", **params)
        resultado.extend(r.get("results", []))
        proximo = r.get("next")
        if not proximo:
            return resultado
        depois = urllib.parse.parse_qs(urllib.parse.urlparse(proximo).query).get("after")
        if not depois:
            return resultado
        params["after"] = depois[0]


def faturas(conta_id: str) -> list[dict]:
    """Faturas fechadas do cartão, da mais recente para a mais antiga."""
    resultado, pagina = [], 1
    while True:
        r = _get("/bills", accountId=conta_id, page=pagina, pageSize=500)
        resultado.extend(r.get("results", []))
        if pagina >= (r.get("totalPages") or 1):
            break
        pagina += 1
    return sorted(resultado, key=lambda b: b.get("dueDate") or "", reverse=True)
