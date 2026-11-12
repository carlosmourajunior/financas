"""Cliente mínimo da API da Pluggy (https://docs.pluggy.ai), só leitura.

Uso pessoal com o MeuPluggy: as contas vêm dos itens listados em PLUGGY_ITEM_IDS, que pertencem
ao dono da instância. Por isso só os e-mails de PLUGGY_USUARIOS enxergam esses dados.
"""

import json
import logging
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
    return usuario.email.lower() in settings.PLUGGY_USUARIOS


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


@dataclass
class ContaPluggy:
    id: str
    tipo: str  # BANK ou CREDIT
    nome: str
    numero: str
    saldo: int
    vencimento: date | None = None  # cartão: vencimento da fatura atual
    fechamento: date | None = None


def contas() -> list[ContaPluggy]:
    """As contas e cartões de todos os itens configurados."""
    resultado = []
    for item in settings.PLUGGY_ITEM_IDS:
        for a in _get("/accounts", itemId=item).get("results", []):
            credito = a.get("creditData") or {}
            resultado.append(
                ContaPluggy(
                    id=a["id"],
                    tipo=a.get("type", ""),
                    nome=a.get("marketingName") or a.get("name") or "",
                    numero=a.get("number") or "",
                    saldo=centavos(a.get("balance")),
                    vencimento=_data(credito.get("balanceDueDate")),
                    fechamento=_data(credito.get("balanceCloseDate")),
                )
            )
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
