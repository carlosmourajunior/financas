"""Do extrato da conta para lançamentos: prévia para classificar e gravação do que foi escolhido.

Cada linha vira uma de cinco classes:
- despesa ou receita: um lançamento na conta, único, parcelado ou recorrente;
- transferencia: dinheiro entre contas do próprio usuário, não grava nada;
- fatura: pagamento da fatura de um cartão, marca a fatura como paga;
- emprestimo: pagamento de um empréstimo, registra o pagamento nele.
"""

import uuid
from collections import Counter
from datetime import date, timedelta

from django.db import transaction
from django.db.models import Q

from financas.models import Cartao, Categoria, Conta, Emprestimo, Lancamento, Natureza, PagamentoEmprestimo, PagamentoFatura, Recorrencia
from financas.servicos import _vencimento, gerar_ocorrencias, somar_meses

from .leitores import ExtratoLido, Movimento
from .leitores.base import normalizar
from .servicos import _POR_PALAVRA


class Classe:
    DESPESA = "despesa"
    RECEITA = "receita"
    TRANSFERENCIA = "transferencia"
    FATURA = "fatura"
    EMPRESTIMO = "emprestimo"

    choices = [DESPESA, RECEITA, TRANSFERENCIA, FATURA, EMPRESTIMO]


_TAXAS = ("iof", "juros", "tarifa", "seguro", "anuidade", "multa", "encargo")
# Palavras que aparecem em boletos e Pix, além das da fatura do cartão.
_NO_EXTRATO = [
    (("educacao", "escola", "colegio", "faculdade", "idiomas", "curso"), "Educação"),
    (("habitacao", "aluguel", "condominio", "energia", "saneamento", "agua"), "Moradia"),
    (("peixaria", "acougue", "sacolao"), "Alimentação"),
]
# Um lançamento à mão com o mesmo valor, até estes dias antes ou depois, é o mesmo movimento.
FOLGA_DIAS = 5


def chave_do_movimento(m: Movimento, ordem: int = 1) -> str:
    """Identifica a linha em qualquer importação do mesmo extrato."""
    return f"extrato|{m.data.isoformat()}|{m.documento}|{m.valor}|{ordem}"


def fatura_paga_em(cartao: Cartao, data: date) -> date:
    """Fechamento da fatura cujo vencimento fica mais perto do dia do pagamento."""
    candidatas = [somar_meses(data, -m, cartao.dia_fechamento) for m in range(-1, 3)]
    return min(candidatas, key=lambda f: abs((_vencimento(cartao, f) - data).days))


def _eh_do_titular(nome: str, titular: str) -> bool:
    """'CARLOS ALBE' ou 'CARLOS ALBERTO PORTUGAL D' para o titular Carlos Alberto Portugal…: o banco corta o nome."""
    n, t = normalizar(nome), normalizar(titular)
    if not n or not t:
        return False
    partes = n.split()
    return len(partes) >= 2 and len(n) >= 8 and t.startswith(n.rstrip())


def _categoria_por_palavra(descricao: str, por_nome: dict[str, Categoria]) -> int | None:
    texto = normalizar(descricao).replace("mercado pago", "")
    nome = "Taxas" if any(p in texto for p in _TAXAS) else None
    if not nome:
        regras = _NO_EXTRATO + _POR_PALAVRA
        nome = next((n for palavras, n in regras if any(p.strip() in texto for p in palavras)), None)
    cat = por_nome.get(nome.lower()) if nome else None
    return cat.id if cat else None


def previa_extrato(conta: Conta, lida: ExtratoLido) -> dict:
    dono = conta.dono
    titular = getattr(dono, "nome", "") or ""
    categorias = list(Categoria.objects.filter(dono=dono))
    por_nome = {n: {c.nome.lower(): c for c in categorias if c.natureza == n} for n in (Natureza.DESPESA, Natureza.RECEITA)}
    # A última categoria e o último jeito de lançar (único, parcelado, recorrente) para cada descrição.
    historico: dict[tuple[str, str], int] = {}
    for desc, natureza, cat in (
        Lancamento.objects.filter(dono=dono, categoria__isnull=False, cartao__isnull=True)
        .order_by("data")
        .values_list("descricao", "natureza", "categoria")
    ):
        historico[(normalizar(desc), natureza)] = cat
    recorrentes = {(normalizar(r.descricao), r.natureza) for r in Recorrencia.objects.filter(dono=dono, ativa=True, cartao__isnull=True)}

    cartoes = list(Cartao.objects.filter(dono=dono))
    emprestimos = list(Emprestimo.objects.filter(dono=dono))
    ja_importadas = set(Lancamento.objects.filter(dono=dono, chave__startswith="extrato|").values_list("chave", flat=True))

    datas = [m.data for m in lida.itens] or [date.today()]
    candidatos = list(
        Lancamento.objects.filter(
            dono=dono,
            cartao__isnull=True,
            data__gte=min(datas) - timedelta(days=FOLGA_DIAS),
            data__lte=max(datas) + timedelta(days=FOLGA_DIAS),
        )
        .exclude(chave__startswith="extrato|")
        .filter(Q(conta=conta) | Q(conta__isnull=True))
    )
    usados: set[int] = set()

    ordens: Counter[tuple] = Counter()
    itens = []
    for m in lida.itens:
        base = (m.data, m.documento, m.valor)
        ordens[base] += 1
        chave = chave_do_movimento(m, ordens[base])
        natureza = Natureza.RECEITA if m.valor > 0 else Natureza.DESPESA
        valor = abs(m.valor)
        texto = normalizar(f"{m.origem} {m.descricao}")
        item = {
            "data": m.data,
            "descricao": m.descricao,
            "origem": m.origem,
            "valor": valor,
            "natureza": natureza,
            "classe": natureza,
            "tipo": Lancamento.Tipo.UNICA,
            "parcela_atual": None,
            "parcela_total": None,
            "categoria": None,
            "cartao": None,
            "emprestimo": None,
            "lancamento": None,
            "chave": chave,
            "importar": True,
            "aviso": "",
        }

        if m.aplicacao or _eh_do_titular(m.descricao, titular):
            item.update(classe=Classe.TRANSFERENCIA, importar=False)
            item["aviso"] = "Aplicação ou resgate automático da conta" if m.aplicacao else "Parece transferência entre contas suas"
        elif natureza == Natureza.DESPESA and (cartao := _cartao_no_texto(texto, cartoes)):
            item.update(classe=Classe.FATURA, cartao=cartao.id)
            fecha = fatura_paga_em(cartao, m.data)
            if PagamentoFatura.objects.filter(cartao=cartao, fecha=fecha).exists():
                item.update(importar=False, aviso="Esta fatura já está marcada como paga")
        elif natureza == Natureza.DESPESA and (emp := _emprestimo_do_valor(valor, emprestimos)):
            item.update(classe=Classe.EMPRESTIMO, emprestimo=emp.id)
            if PagamentoEmprestimo.objects.filter(emprestimo=emp, valor=valor, data=m.data).exists():
                item.update(importar=False, aviso="Este pagamento já está no empréstimo")
        else:
            if m.parcela_total and m.parcela_atual and m.parcela_atual <= m.parcela_total:
                item.update(tipo=Lancamento.Tipo.PARCELADA, parcela_atual=m.parcela_atual, parcela_total=m.parcela_total)
            elif (normalizar(m.descricao), natureza) in recorrentes:
                item["tipo"] = Lancamento.Tipo.RECORRENTE
            item["categoria"] = historico.get((normalizar(m.descricao), natureza)) or _categoria_por_palavra(
                f"{m.origem} {m.descricao} {m.detalhes}", por_nome[natureza]
            )
            if "pgto cdc" in texto:
                item["aviso"] = "Parece parcela de empréstimo: escolha Empréstimo para ligar a ele"

        if chave in ja_importadas:
            item.update(importar=False, aviso="Já importado de um extrato anterior")
        elif item["classe"] in (Classe.DESPESA, Classe.RECEITA):
            igual = _igual_lancado(candidatos, usados, m.data, valor, natureza)
            if igual:
                usados.add(igual.id)
                item["lancamento"] = igual.id
                if igual.pago:
                    item.update(importar=False, aviso=f"Já lançado como {igual.descricao} em {igual.data:%d/%m}")
                else:
                    item["aviso"] = f"Igual a {igual.descricao} de {igual.data:%d/%m}: ao importar, ele fica pago"
                    item["categoria"] = item["categoria"] or igual.categoria_id
        itens.append(item)

    entradas = sum(m.valor for m in lida.itens if m.valor > 0)
    saidas = -sum(m.valor for m in lida.itens if m.valor < 0)
    return {
        "banco": lida.banco,
        "saldo_anterior": lida.saldo_anterior,
        "saldo_final": lida.saldo_final,
        "data_final": lida.data_final,
        "conferido": lida.conferido,
        "entradas": entradas,
        "saidas": saidas,
        "itens": itens,
    }


def _cartao_no_texto(texto: str, cartoes: list[Cartao]) -> Cartao | None:
    """'Pagamento de Boleto BANCO C6' com um cartão chamado C6: é a fatura dele."""
    if "boleto" not in texto and "fatura" not in texto and "cartao" not in texto:
        return None
    palavras = set(texto.split())
    for c in cartoes:
        nome = normalizar(c.nome)
        if nome and (nome in palavras or f" {nome} " in f" {texto} "):
            return c
    return None


def _emprestimo_do_valor(valor: int, emprestimos: list[Emprestimo]) -> Emprestimo | None:
    """Parcela de empréstimo que eu devo com o mesmo valor; no BB aparece como Pgto CDC."""
    devo = [e for e in emprestimos if e.direcao == Emprestimo.Direcao.DEVO and e.parcela_valor == valor]
    if len(devo) == 1:
        return devo[0]
    return None


def _igual_lancado(candidatos: list[Lancamento], usados: set[int], data: date, valor: int, natureza: str) -> Lancamento | None:
    iguais = [
        c
        for c in candidatos
        if c.id not in usados and c.valor == valor and c.natureza == natureza and abs((c.data - data).days) <= FOLGA_DIAS
    ]
    # Prefere o que ainda não foi pago e o de data mais próxima.
    iguais.sort(key=lambda c: (c.pago, abs((c.data - data).days)))
    return iguais[0] if iguais else None


@transaction.atomic
def confirmar_extrato(conta: Conta, itens: list[dict]) -> dict:
    """Grava as linhas escolhidas. Importar o mesmo extrato de novo não duplica: cada linha tem sua chave."""
    dono = conta.dono
    hoje = date.today()
    ja_importadas = set(Lancamento.objects.filter(dono=dono, chave__startswith="extrato|").values_list("chave", flat=True))
    feito = Counter()

    for i in itens:
        classe, chave, data, valor = i["classe"], i.get("chave", ""), i["data"], i["valor"]
        if classe == Classe.TRANSFERENCIA:
            feito["transferencias"] += 1
            continue
        if classe == Classe.FATURA:
            cartao = i["cartao"]
            fecha = fatura_paga_em(cartao, data)
            _, novo = PagamentoFatura.objects.get_or_create(cartao=cartao, fecha=fecha, defaults={"dono": dono, "valor": valor, "data": data})
            feito["faturas" if novo else "repetidos"] += 1
            continue
        if classe == Classe.EMPRESTIMO:
            _, novo = PagamentoEmprestimo.objects.get_or_create(emprestimo=i["emprestimo"], valor=valor, data=data, defaults={"dono": dono})
            feito["emprestimos" if novo else "repetidos"] += 1
            continue

        if chave and chave in ja_importadas:
            feito["repetidos"] += 1
            continue
        ja_importadas.add(chave)
        natureza = Natureza.RECEITA if classe == Classe.RECEITA else Natureza.DESPESA
        categoria = i.get("categoria")

        existente = i.get("lancamento")
        if existente and not existente.pago:
            # O que já estava lançado (uma conta a pagar, uma ocorrência da recorrência) passa a estar pago.
            existente.pago = True
            existente.conta = existente.conta or conta
            existente.categoria = existente.categoria or categoria
            existente.chave = chave
            existente.save(update_fields=["pago", "conta", "categoria", "chave", "atualizado_em"])
            feito["pagos"] += 1
            continue

        campos = {
            "dono": dono,
            "descricao": i["descricao"],
            "natureza": natureza,
            "categoria": categoria,
            "conta": conta,
            "importado": True,
        }
        tipo = i.get("tipo") or Lancamento.Tipo.UNICA
        if tipo == Lancamento.Tipo.PARCELADA and i.get("parcela_total"):
            atual, total = i.get("parcela_atual") or 1, i["parcela_total"]
            grupo = uuid.uuid4()
            for k in range(atual, total + 1):
                d = somar_meses(data, k - atual)
                Lancamento.objects.create(
                    **campos,
                    valor=valor,
                    data=d,
                    tipo=tipo,
                    grupo=grupo,
                    parcela_atual=k,
                    parcela_total=total,
                    pago=k == atual or d <= hoje,
                    chave=chave if k == atual else "",
                )
            feito["criados"] += 1
        elif tipo == Lancamento.Tipo.RECORRENTE:
            rec = Recorrencia.objects.create(
                dono=dono, descricao=i["descricao"], valor=valor, natureza=natureza, categoria=categoria, conta=conta, inicio=data
            )
            Lancamento.objects.create(**campos, valor=valor, data=data, tipo=tipo, recorrencia=rec, pago=True, chave=chave)
            gerar_ocorrencias(dono, max(data, hoje))
            feito["criados"] += 1
        else:
            Lancamento.objects.create(**campos, valor=valor, data=data, tipo=Lancamento.Tipo.UNICA, pago=True, chave=chave)
            feito["criados"] += 1
    return dict(feito)
