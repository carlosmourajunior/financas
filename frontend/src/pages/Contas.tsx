import { useState, type ReactNode } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { RotuloCategoria } from '../components/Categorias'
import { Erro, FormConta } from '../components/Formularios'
import Icon from '../components/Icon'
import LinhaComData from '../components/LinhaComData'
import { TrazerDoBanco } from '../components/OpenFinance'
import { Abas, Barra, Campo, Secao, Titulo, botaoPrimario, botaoSecundario, campo } from '../components/ui'
import { api, type Pagina } from '../lib/api'
import { MESES, isoMes, lerData, porExtenso } from '../lib/datas'
import { moeda, paraCentavos, pct } from '../lib/format'
import type { Conta, DetalheConta, MovimentoEmConta, NumerosDoMes, VisaoGeralContas } from '../lib/tipos'
import { useApi } from '../lib/useApi'
import { useEnvio } from '../lib/useEnvio'

const TIPOS: Record<Conta['tipo'], string> = { corrente: 'Conta corrente', poupanca: 'Poupança', dinheiro: 'Dinheiro' }
const TODAS = 'todas'
const CHAVE_POUPANCA = 'financas.sem-poupanca'

function lerSemPoupanca() {
  try {
    return localStorage.getItem(CHAVE_POUPANCA) === '1'
  } catch {
    return false
  }
}

const pagina = 'mx-auto flex max-w-3xl flex-col gap-3.5 px-5 pt-5 lg:px-8 lg:pt-7'

function nomeDoMes(iso: string) {
  const d = lerData(iso)
  return `${MESES[d.getMonth()]} de ${d.getFullYear()}`
}

function mesVizinho(iso: string, passo: number) {
  const d = lerData(iso)
  return isoMes(new Date(d.getFullYear(), d.getMonth() + passo, 1))
}

export default function Contas() {
  const lista = useApi<Pagina<Conta>>('/contas/?limit=500')
  const contas = lista.dados?.results ?? []
  // ?conta= abre uma conta; sem ela, todas juntas. ?mes=AAAA-MM escolhe o mês.
  const [busca, setBusca] = useSearchParams()
  const sel = busca.get('conta') ?? TODAS
  const mes = busca.get('mes')
  const [novo, setNovo] = useState(false)
  // Esconder poupanças tira elas das abas, da lista e dos totais. Fica guardado neste aparelho.
  const [semPoupanca, setSemPoupancaEstado] = useState(lerSemPoupanca)
  const setSemPoupanca = (v: boolean) => {
    setSemPoupancaEstado(v)
    try {
      localStorage.setItem(CHAVE_POUPANCA, v ? '1' : '0')
    } catch {
      // sem armazenamento, vale só nesta visita
    }
  }
  const temPoupanca = contas.some((c) => c.tipo === 'poupanca')
  const visiveis = semPoupanca ? contas.filter((c) => c.tipo !== 'poupanca') : contas
  const conta = visiveis.find((c) => String(c.id) === sel)
  const aba = conta ? String(conta.id) : TODAS

  const ir = (id: string, m: string | null = mes) => {
    const p: Record<string, string> = {}
    if (id !== TODAS) p.conta = id
    if (m) p.mes = m
    setBusca(p, { replace: true })
  }

  const titulo = (
    <Titulo
      acoes={
        contas.length > 0 && (
          <button
            aria-label={novo ? 'Fechar cadastro de conta' : 'Adicionar conta'}
            aria-expanded={novo}
            onClick={() => setNovo(!novo)}
            className="flex size-11 cursor-pointer items-center justify-center rounded-xl border border-borda bg-white"
          >
            <Icon name={novo ? 'fechar' : 'mais'} size={20} strokeWidth={2} />
          </button>
        )
      }
    >
      Contas
    </Titulo>
  )

  if (lista.carregando && !lista.dados) {
    return (
      <div className={pagina}>
        {titulo}
        <p className="py-10 text-center text-suave">Carregando…</p>
      </div>
    )
  }

  if (contas.length === 0 || novo) {
    return (
      <div className={pagina}>
        {titulo}
        <p className="text-[17px] leading-snug text-suave">
          {contas.length ? 'Nova conta' : 'Cadastre a conta onde o seu dinheiro fica para ver o saldo e o que entrou e saiu de cada uma.'}
        </p>
        <div className="flex max-w-xl flex-col gap-4">
          <TrazerDoBanco
            aoTrazer={() => {
              setNovo(false)
              lista.recarregar()
            }}
          />
          <FormConta
            aoSalvar={(c) => {
              setNovo(false)
              lista.recarregar()
              ir(String(c.id))
            }}
          />
        </div>
      </div>
    )
  }

  return (
    <div className={pagina}>
      {titulo}
      <Abas
        rotulo="Conta"
        opcoes={[{ id: TODAS, label: 'Todas' }, ...visiveis.map((c) => ({ id: String(c.id), label: c.nome }))]}
        valor={aba}
        onChange={(id) => ir(id)}
      />
      {conta ? (
        <UmaConta key={conta.id} id={conta.id} mes={mes} irMes={(m) => ir(String(conta.id), m)} aoMudar={lista.recarregar} />
      ) : (
        <Todas
          mes={mes}
          irMes={(m) => ir(TODAS, m)}
          abrir={(id) => ir(String(id))}
          semPoupanca={semPoupanca && temPoupanca}
          filtro={
            temPoupanca && (
              <button
                aria-pressed={semPoupanca}
                onClick={() => setSemPoupanca(!semPoupanca)}
                className={`min-h-9 shrink-0 cursor-pointer whitespace-nowrap rounded-[10px] border px-3 text-sm font-bold ${
                  semPoupanca ? 'border-tinta bg-tinta text-white' : 'border-borda bg-white'
                }`}
              >
                Esconder poupanças
              </button>
            )
          }
        />
      )}
    </div>
  )
}

/** Setas para trocar de mês, com o nome dele no meio. */
function NavegarMes({ inicio, irMes }: { inicio: string; irMes: (m: string) => void }) {
  return (
    <div className="-mx-3 flex items-center gap-1">
      <button aria-label="Mês anterior" onClick={() => irMes(mesVizinho(inicio, -1))} className="flex size-11 cursor-pointer items-center justify-center">
        <Icon name="esquerda" size={20} strokeWidth={2} />
      </button>
      <span className="text-[15px] font-semibold text-suave" aria-live="polite">
        {nomeDoMes(inicio)}
      </span>
      <button aria-label="Próximo mês" onClick={() => irMes(mesVizinho(inicio, 1))} className="flex size-11 cursor-pointer items-center justify-center">
        <Icon name="direita" size={20} strokeWidth={2} />
      </button>
    </div>
  )
}

function NumerosMes({ m }: { m: NumerosDoMes }) {
  return (
    <div className="grid grid-cols-2 gap-x-4 border-y border-linha py-3 sm:grid-cols-4">
      <Numero rotulo="Entrou" valor={moeda(m.entrou)} classe="text-credito" />
      <Numero rotulo="Saiu" valor={moeda(m.saiu)} classe="text-debito" />
      <Numero rotulo="A receber" valor={moeda(m.a_receber)} classe={m.a_receber ? 'text-credito' : 'text-suave'} />
      <Numero rotulo="A pagar" valor={moeda(m.a_pagar)} classe={m.a_pagar ? 'text-ambar-texto' : 'text-suave'} />
    </div>
  )
}

function Numero({ rotulo, valor, classe = '' }: { rotulo: string; valor: string; classe?: string }) {
  return (
    <div className="flex flex-col gap-0.5 py-1.5">
      <span className="text-sm text-suave">{rotulo}</span>
      <span className={`text-[17px] font-bold tabular-nums ${classe}`}>{valor}</span>
    </div>
  )
}

function Movimentos({ itens, mostrarConta = false }: { itens: MovimentoEmConta[]; mostrarConta?: boolean }) {
  if (itens.length === 0) return <p className="py-2.5 text-[15px] text-suave">Nenhum lançamento neste mês.</p>
  return (
    <>
      {itens.map((l) => {
        const receita = l.natureza === 'receita'
        const nomeCategoria = l.categoria ?? (receita ? null : 'Sem categoria')
        const detalhe =
          mostrarConta || nomeCategoria ? (
            <>
              {mostrarConta && l.conta_nome}
              {mostrarConta && l.conta_nome && nomeCategoria && ', '}
              {nomeCategoria && <RotuloCategoria nome={nomeCategoria} cor={l.categoria_cor} />}
            </>
          ) : undefined
        return (
          <LinhaComData
            key={l.id}
            data={l.data}
            titulo={l.descricao}
            detalhe={detalhe}
            situacao={l.pago ? undefined : receita ? 'A receber' : 'A pagar'}
            alerta={!l.pago && !receita}
            valor={`${receita ? '+' : '-'} ${moeda(l.valor)}`}
            valorClasse={receita ? 'text-credito' : 'text-debito'}
            extra={l.parcela_total && <span className="text-sm text-suave">parcela {l.parcela_atual} de {l.parcela_total}</span>}
          />
        )
      })}
    </>
  )
}

function Destaque({ rotulo, valor, children }: { rotulo: string; valor: number; children?: ReactNode }) {
  return (
    <div className="flex flex-col gap-2">
      <span className="text-[15px] font-semibold text-suave">{rotulo}</span>
      <p className={`font-display text-[44px] font-extrabold leading-none tracking-tight tabular-nums ${valor < 0 ? 'text-debito' : ''}`}>
        {valor < 0 ? `- ${moeda(valor)}` : moeda(valor)}
      </p>
      {children}
    </div>
  )
}

function Todas({
  mes,
  irMes,
  abrir,
  semPoupanca,
  filtro,
}: {
  mes: string | null
  irMes: (m: string) => void
  abrir: (id: number) => void
  semPoupanca: boolean
  filtro: ReactNode
}) {
  const params = new URLSearchParams()
  if (mes) params.set('mes', mes)
  if (semPoupanca) params.set('sem_poupanca', '1')
  const r = useApi<VisaoGeralContas>(`/contas/visao-geral/${params.size ? `?${params}` : ''}`)
  const d = r.dados
  if (r.erro) return <p className="py-10 text-center text-suave">Não foi possível carregar as contas. {r.erro}</p>
  if (!d) return <p className="py-10 text-center text-suave">Carregando…</p>

  return (
    <div className="flex flex-col gap-7 pt-2">
      <section className="flex flex-col gap-3">
        <Destaque rotulo={semPoupanca ? 'Nas contas, sem as poupanças' : 'Em todas as contas agora'} valor={d.em_contas}>
          {d.cartoes.length > 0 && (
            <p className="text-[15px] text-suave">
              Depois das faturas a pagar ({moeda(d.faturas_a_pagar)}) ficam{' '}
              <strong className={d.depois_das_faturas < 0 ? 'text-debito' : 'text-tinta'}>
                {d.depois_das_faturas < 0 ? `- ${moeda(d.depois_das_faturas)}` : moeda(d.depois_das_faturas)}
              </strong>
            </p>
          )}
        </Destaque>
      </section>

      <Secao titulo="Contas" acao={filtro}>
        {d.contas.map((c) => (
          <button
            key={c.id}
            onClick={() => abrir(c.id)}
            className="flex cursor-pointer items-center gap-3 border-b border-linha py-3 text-left text-tinta hover:bg-nevoa/50"
          >
            <span className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-nevoa">
              <Icon name="banco" size={20} />
            </span>
            <span className="flex min-w-0 grow flex-col gap-0.5">
              <span className="text-base font-bold">{c.nome}</span>
              <span className="text-sm text-suave">
                {TIPOS[c.tipo]}
                {c.pluggy && ', conectada ao banco'}
              </span>
            </span>
            <span className={`whitespace-nowrap text-base font-bold tabular-nums ${c.saldo < 0 ? 'text-debito' : ''}`}>
              {c.saldo < 0 ? `- ${moeda(c.saldo)}` : moeda(c.saldo)}
            </span>
            <span className="text-suave">
              <Icon name="direita" size={18} strokeWidth={2} />
            </span>
          </button>
        ))}
        {d.sem_poupanca && d.poupancas > 0 && (
          <p className="border-b border-linha py-3 text-sm text-suave">
            {d.poupancas === 1 ? '1 poupança escondida' : `${d.poupancas} poupanças escondidas`}, fora do total e dos lançamentos
          </p>
        )}
        {d.faturas_pagas > 0 && (
          <div className="flex items-start gap-3 border-b border-linha py-3">
            <span className="flex grow flex-col gap-0.5">
              <span className="text-base font-bold">Faturas pagas</span>
              <span className="text-sm text-suave">Saem do total porque ainda não dizem de qual conta saíram</span>
            </span>
            <span className="whitespace-nowrap text-base font-bold tabular-nums">- {moeda(d.faturas_pagas)}</span>
          </div>
        )}
        <div className="flex justify-between py-3 text-base">
          <span className="font-bold">Total</span>
          <span className="font-bold tabular-nums">{d.em_contas < 0 ? `- ${moeda(d.em_contas)}` : moeda(d.em_contas)}</span>
        </div>
      </Secao>

      {d.cartoes.length > 0 && (
        <Secao titulo="Cartões" acao={<Link to="/cartoes" className="py-2.5 text-[15px] font-bold text-tinta hover:text-musgo">Ver cartões</Link>}>
          {d.cartoes.map((c) => (
            <Link key={c.id} to={`/cartoes?cartao=${c.id}`} className="flex flex-col gap-2 border-b border-linha py-3 text-tinta hover:bg-nevoa/50">
              <span className="flex items-center gap-3">
                <span className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-nevoa">
                  <Icon name="cartao" size={20} />
                </span>
                <span className="flex min-w-0 grow flex-col gap-0.5">
                  <span className="text-base font-bold">{c.final ? `${c.nome} ${c.final}` : c.nome}</span>
                  <span className={`text-sm ${c.paga ? 'text-musgo' : !c.aberta && c.fatura > 0 ? 'font-semibold text-ambar-texto' : 'text-suave'}`}>
                    {c.paga
                      ? 'Fatura paga'
                      : c.aberta
                        ? `Fatura aberta, vence em ${porExtenso(c.vence)}`
                        : `Fatura fechada, vence em ${porExtenso(c.vence)}`}
                  </span>
                </span>
                <span className="whitespace-nowrap text-base font-bold tabular-nums">{moeda(c.fatura)}</span>
                <span className="text-suave">
                  <Icon name="direita" size={18} strokeWidth={2} />
                </span>
              </span>
              <span className="flex flex-col gap-1 pl-[52px]">
                <Barra largura={pct(c.limite - c.disponivel, c.limite)} altura="h-1.5" />
                <span className="text-sm text-suave">
                  Disponível {moeda(c.disponivel)} de {moeda(c.limite)}
                </span>
              </span>
            </Link>
          ))}
        </Secao>
      )}

      <section className="flex flex-col gap-2">
        <NavegarMes inicio={d.mes.inicio} irMes={irMes} />
        <NumerosMes m={d.mes} />
      </section>

      <Secao titulo={`Lançamentos em conta (${d.movimentos.length})`}>
        <p className="pb-1.5 text-[15px] text-suave">De todas as contas. As compras no cartão aparecem na fatura.</p>
        <Movimentos itens={d.movimentos} mostrarConta />
      </Secao>
    </div>
  )
}

function UmaConta({ id, mes, irMes, aoMudar }: { id: number; mes: string | null; irMes: (m: string) => void; aoMudar: () => void }) {
  const r = useApi<DetalheConta>(`/contas/${id}/detalhe/${mes ? `?mes=${mes}` : ''}`)
  const [editando, setEditando] = useState(false)
  const d = r.dados
  if (r.erro) return <p className="py-10 text-center text-suave">Não foi possível carregar a conta. {r.erro}</p>
  if (!d) return <p className="py-10 text-center text-suave">Carregando…</p>
  const fimDoMes = porExtenso(d.mes.fim)

  return (
    <div className="flex flex-col gap-7 pt-2">
      <section className="flex flex-col gap-3">
        <Destaque rotulo={`${TIPOS[d.conta.tipo]}${d.conta.pluggy ? ', conectada ao banco' : ''}`} valor={d.saldo}>
          <p className="text-[15px] text-suave">
            Previsto para {fimDoMes}:{' '}
            <strong className={d.previsto < 0 ? 'text-debito' : 'text-tinta'}>{d.previsto < 0 ? `- ${moeda(d.previsto)}` : moeda(d.previsto)}</strong>
          </p>
        </Destaque>
        <div className="flex gap-2.5 pt-1">
          <Link
            to="/importar?fonte=extrato"
            className="flex min-h-[50px] flex-1 items-center justify-center gap-2 rounded-[14px] bg-tinta text-base font-bold text-white"
          >
            <Icon name="importar" size={18} strokeWidth={2} />
            Importar extrato
          </Link>
          <button onClick={() => setEditando(!editando)} aria-expanded={editando} className={`${botaoSecundario} flex-1 rounded-[14px]`}>
            {editando ? 'Fechar' : 'Editar conta'}
          </button>
        </div>
        {editando && (
          <EditarConta
            conta={d.conta}
            aoSalvar={() => {
              setEditando(false)
              r.recarregar()
              aoMudar()
            }}
          />
        )}
      </section>

      <section className="flex flex-col gap-2">
        <NavegarMes inicio={d.mes.inicio} irMes={irMes} />
        <NumerosMes m={d.mes} />
      </section>

      <Secao titulo={`Lançamentos (${d.movimentos.length})`}>
        <Movimentos itens={d.movimentos} />
      </Secao>
    </div>
  )
}

function EditarConta({ conta, aoSalvar }: { conta: Conta; aoSalvar: () => void }) {
  const [nome, setNome] = useState(conta.nome)
  const [tipo, setTipo] = useState<Conta['tipo']>(conta.tipo)
  const [saldo, setSaldo] = useState((conta.saldo_inicial / 100).toFixed(2).replace('.', ','))
  const { erro, enviando, enviar } = useEnvio(async () => {
    await api(`/contas/${conta.id}/`, { method: 'PATCH', body: { nome, tipo, saldo_inicial: paraCentavos(saldo) * (saldo.trim().startsWith('-') ? -1 : 1) } })
    aoSalvar()
  })

  return (
    <form onSubmit={enviar} className="flex flex-col gap-4 rounded-[14px] border border-linha bg-white p-4">
      <Campo label="Nome da conta">
        <input required value={nome} onChange={(e) => setNome(e.target.value)} className={campo} />
      </Campo>
      <div className="grid grid-cols-2 gap-3">
        <Campo label="Tipo">
          <select value={tipo} onChange={(e) => setTipo(e.target.value as Conta['tipo'])} className={campo}>
            <option value="corrente">Conta corrente</option>
            <option value="poupanca">Poupança</option>
            <option value="dinheiro">Dinheiro</option>
          </select>
        </Campo>
        <Campo label="Saldo de partida">
          <input inputMode="decimal" value={saldo} onChange={(e) => setSaldo(e.target.value)} className={`${campo} tabular-nums`} />
        </Campo>
      </div>
      <p className="text-sm text-suave">O saldo de partida é o que havia na conta antes dos lançamentos registrados aqui. O saldo atual soma a ele o que entrou e saiu.</p>
      {erro && <Erro>{erro}</Erro>}
      <button type="submit" disabled={enviando} className={`${botaoPrimario} disabled:opacity-60`}>
        {enviando ? 'Salvando…' : 'Salvar'}
      </button>
    </form>
  )
}
