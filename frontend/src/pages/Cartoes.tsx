import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import BotaoPagar from '../components/BotaoPagar'
import { FormCartao } from '../components/Formularios'
import Icon from '../components/Icon'
import LinhaComData from '../components/LinhaComData'
import { Abas, Barra, Secao, Segmentos, Titulo, botaoSecundario } from '../components/ui'
import { api, type Pagina } from '../lib/api'
import { useCadastros } from '../lib/cadastros'
import { MESES, isoData, lerData, maiuscula, porExtenso } from '../lib/datas'
import { moeda, pct } from '../lib/format'
import { desfazerPagamentoFatura, pagarFatura } from '../lib/pagar'
import type { Cartao, Categoria, CompraNoCartao, DetalheCartao } from '../lib/tipos'
import { useApi } from '../lib/useApi'

function mesAno(iso: string) {
  const d = lerData(iso)
  return `${MESES[d.getMonth()]} de ${d.getFullYear()}`
}

export default function Cartoes() {
  const lista = useApi<Pagina<Cartao>>('/cartoes/?limit=500')
  const cartoes = lista.dados?.results ?? []
  // ?cartao=&fecha= abre uma fatura específica (vindo de Lançamentos, por exemplo).
  const [busca, setBusca] = useSearchParams()
  const sel = busca.get('cartao') ?? ''
  const fecha = busca.get('fecha')
  const [novo, setNovo] = useState(false)
  const [soSemCategoria, setSoSemCategoria] = useState(false)
  const categorias = useCadastros().categorias.filter((x) => x.natureza === 'despesa')
  const c = cartoes.find((x) => String(x.id) === sel) ?? cartoes[0]
  const detalhe = useApi<DetalheCartao>(c ? `/cartoes/${c.id}/detalhe/${fecha ? `?fecha=${fecha}` : ''}` : null)
  const setSel = (id: string) => setBusca({ cartao: id }, { replace: true })
  const irPara = (f: string) => setBusca({ cartao: String(c!.id), fecha: f }, { replace: true })

  const titulo = (
    <Titulo
      acoes={
        cartoes.length > 0 && (
          <button
            aria-label={novo ? 'Fechar cadastro de cartão' : 'Adicionar cartão'}
            aria-expanded={novo}
            onClick={() => setNovo(!novo)}
            className="flex size-11 cursor-pointer items-center justify-center rounded-xl border border-borda bg-white"
          >
            <Icon name={novo ? 'fechar' : 'mais'} size={20} strokeWidth={2} />
          </button>
        )
      }
    >
      Cartões
    </Titulo>
  )

  function salvo(cartao: Cartao) {
    setNovo(false)
    setSel(String(cartao.id))
    lista.recarregar()
  }

  if (lista.carregando && !lista.dados) {
    return (
      <div className="mx-auto flex max-w-3xl flex-col gap-3.5 px-5 pt-5 lg:px-8 lg:pt-7">
        {titulo}
        <p className="py-10 text-center text-suave">Carregando…</p>
      </div>
    )
  }

  if (!c || novo) {
    return (
      <div className="mx-auto flex max-w-3xl flex-col gap-3.5 px-5 pt-5 lg:px-8 lg:pt-7">
        {titulo}
        <p className="text-[17px] leading-snug text-suave">
          {c ? 'Novo cartão' : 'Cadastre seu cartão para acompanhar a fatura, o limite e as parcelas que ainda vêm.'}
        </p>
        <div className="max-w-xl">
          <FormCartao aoSalvar={salvo} />
        </div>
      </div>
    )
  }

  const d = detalhe.dados

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-3.5 px-5 pt-5 lg:px-8 lg:pt-7">
      {titulo}
      <Abas
        rotulo="Cartão"
        opcoes={cartoes.map((x) => ({ id: String(x.id), label: x.final ? `${x.nome} ${x.final}` : x.nome }))}
        valor={String(c.id)}
        onChange={setSel}
      />

      {detalhe.erro && <p className="py-10 text-center text-suave">Não foi possível carregar o cartão. {detalhe.erro}</p>}
      {!d && !detalhe.erro && <p className="py-10 text-center text-suave">Carregando…</p>}
      {d && (
        <div className="flex flex-col gap-7 pt-2">
          <section className="flex flex-col gap-3">
            <div className="-mx-3 flex items-center gap-1">
              <button aria-label="Fatura anterior" onClick={() => irPara(d.fatura.anterior)} className="flex size-11 cursor-pointer items-center justify-center">
                <Icon name="esquerda" size={20} strokeWidth={2} />
              </button>
              <span className="text-[15px] font-semibold text-suave" aria-live="polite">
                Fatura de {MESES[lerData(d.fatura.vence).getMonth()]} de {lerData(d.fatura.vence).getFullYear()}
                {d.fatura.aberta ? ', aberta' : lerData(d.fatura.fecha) < new Date() ? ', fechada' : ', futura'}
              </span>
              <button aria-label="Próxima fatura" onClick={() => irPara(d.fatura.seguinte)} className="flex size-11 cursor-pointer items-center justify-center">
                <Icon name="direita" size={20} strokeWidth={2} />
              </button>
            </div>
            <p className="font-display text-[44px] font-extrabold leading-none tracking-tight tabular-nums">{moeda(d.fatura.total)}</p>
            <p className="text-[15px] text-suave">
              {d.fatura.aberta ? 'Fecha' : 'Fechou'} em {porExtenso(d.fatura.fecha)} e vence em{' '}
              <strong className="text-tinta">{porExtenso(d.fatura.vence)}</strong>
            </p>
            {d.fatura.pagamento ? (
              <div className="flex flex-wrap items-center gap-x-3">
                <span className="text-[15px] font-semibold text-musgo">
                  Paga em {porExtenso(d.fatura.pagamento.data)}, {moeda(d.fatura.pagamento.valor)}
                </span>
                <BotaoPagar discreto rotulo="Desfazer" acao={() => desfazerPagamentoFatura(d.fatura.pagamento!.id)} aoMudar={detalhe.recarregar} />
              </div>
            ) : (
              !d.fatura.aberta &&
              d.fatura.total > 0 && (
                <div className="flex flex-wrap items-center gap-3">
                  <span className="text-[15px] font-semibold text-ambar-texto">
                    {d.fatura.vence < isoData(new Date()) ? 'Venceu e não foi paga' : 'Ainda não foi paga'}
                  </span>
                  <BotaoPagar rotulo="Marcar como paga" acao={() => pagarFatura(c.id, d.fatura.fecha)} aoMudar={detalhe.recarregar} />
                </div>
              )
            )}
            <div className="flex flex-col gap-1.5 pt-1">
              <Barra largura={pct(d.limite - d.disponivel, d.limite)} />
              <p className="text-[15px]">
                Disponível <strong>{moeda(d.disponivel)}</strong> de {moeda(d.limite)}
              </p>
            </div>
            <div className="flex gap-2.5 pt-1">
              <Link
                to="/importar"
                className="flex min-h-[50px] flex-1 items-center justify-center gap-2 rounded-[14px] bg-tinta text-base font-bold text-white"
              >
                <Icon name="importar" size={18} strokeWidth={2} />
                Importar fatura
              </Link>
              <a href="#compras" className={`${botaoSecundario} flex-1 rounded-[14px]`}>
                Ver compras
              </a>
            </div>
          </section>

          <div id="compras" className="scroll-mt-4">
            <Secao
              titulo={`Compras desta fatura (${d.compras.length})`}
              acao={
                semCategoria(d.compras) > 0 && (
                  <button
                    aria-pressed={soSemCategoria}
                    onClick={() => setSoSemCategoria(!soSemCategoria)}
                    className={`min-h-9 shrink-0 cursor-pointer whitespace-nowrap rounded-[10px] border px-3 text-sm font-bold ${
                      soSemCategoria ? 'border-tinta bg-tinta text-white' : 'border-borda bg-white'
                    }`}
                  >
                    Sem categoria ({semCategoria(d.compras)})
                  </button>
                )
              }
            >
              {d.compras.length === 0 && <p className="py-2.5 text-[15px] text-suave">Nenhuma compra nesta fatura.</p>}
              {d.compras
                .filter((l) => !soSemCategoria || (l.natureza === 'despesa' && !l.categoria_id))
                .map((l) => (
                  <LinhaComData
                    key={l.id}
                    data={l.data}
                    titulo={l.descricao}
                    detalhe={
                      l.natureza === 'receita' ? (
                        'Crédito na fatura'
                      ) : (
                        <EscolherCategoria compra={l} compras={d.compras} categorias={categorias} aoMudar={detalhe.recarregar} />
                      )
                    }
                    valor={l.natureza === 'receita' ? `- ${moeda(l.valor)}` : moeda(l.valor)}
                    valorClasse={l.natureza === 'receita' ? 'text-musgo' : ''}
                    extra={l.parcela_total && <span className="text-sm text-suave">parcela {l.parcela_atual} de {l.parcela_total}</span>}
                  />
                ))}
            </Secao>
          </div>

          <Secao titulo="Parcelas em andamento">
            {d.parcelas.length === 0 && <p className="py-2.5 text-[15px] text-suave">Nenhuma compra parcelada neste cartão.</p>}
            {d.parcelas.map((p, i) => (
              <div key={i} className="flex flex-col gap-1.5 border-b border-linha py-3">
                <div className="flex justify-between text-base font-bold">
                  <span>{p.descricao}</span>
                  <span className="tabular-nums">{moeda(p.valor)}</span>
                </div>
                <Segmentos pagas={p.atual} total={p.total} />
                <p className="text-sm text-suave">
                  Parcela {p.atual} de {p.total}, termina em {mesAno(p.termina)}
                </p>
              </div>
            ))}
          </Secao>

          <Secao titulo="Próximas faturas">
            <p className="pb-1.5 text-[15px] text-suave">O que já está garantido por parcelas e assinaturas</p>
            {d.proximas.map((f) => (
              <div key={f.fecha} className="flex justify-between border-b border-linha py-2.5 text-base">
                <span>{maiuscula(MESES[lerData(f.vence).getMonth()])}</span>
                <span className="font-bold tabular-nums">{moeda(f.total)}</span>
              </div>
            ))}
          </Secao>
        </div>
      )}
    </div>
  )
}

function semCategoria(compras: CompraNoCartao[]) {
  return compras.filter((l) => l.natureza === 'despesa' && !l.categoria_id).length
}

/** Categoria da compra, editável na hora. Sem categoria, as outras da mesma loja nesta fatura recebem a mesma. */
function EscolherCategoria({
  compra,
  compras,
  categorias,
  aoMudar,
}: {
  compra: CompraNoCartao
  compras: CompraNoCartao[]
  categorias: Categoria[]
  aoMudar: () => void
}) {
  const [salvando, setSalvando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)

  async function mudar(valor: string) {
    const categoria = valor ? Number(valor) : null
    const iguais = compra.categoria_id
      ? [compra]
      : compras.filter((l) => l.natureza === 'despesa' && !l.categoria_id && l.descricao === compra.descricao)
    setErro(null)
    setSalvando(true)
    try {
      await Promise.all(iguais.map((l) => api(`/lancamentos/${l.id}/`, { method: 'PATCH', body: { categoria } })))
      aoMudar()
    } catch (err) {
      setErro((err as Error).message || 'Não foi possível salvar.')
    } finally {
      setSalvando(false)
    }
  }

  return (
    <span className="flex flex-wrap items-center gap-2">
      <select
        aria-label={`Categoria de ${compra.descricao}`}
        value={compra.categoria_id ?? ''}
        disabled={salvando}
        onChange={(e) => mudar(e.target.value)}
        className={`-mx-1 -my-1 min-h-8 cursor-pointer rounded-md bg-transparent px-1 py-1 text-sm hover:bg-nevoa disabled:opacity-60 ${
          compra.categoria_id ? 'text-suave' : 'font-semibold text-ambar-texto'
        }`}
      >
        <option value="">Sem categoria</option>
        {categorias.map((c) => (
          <option key={c.id} value={c.id}>
            {c.nome}
          </option>
        ))}
      </select>
      {erro && <span className="text-sm font-semibold text-ambar-texto">{erro}</span>}
    </span>
  )
}
