// Buscar fatura e extrato direto do banco (Open Finance pela Pluggy).
// Só aparece quando o backend tem o módulo ligado para o usuário; a prévia que volta é a mesma da importação de arquivo.
import { useEffect, useRef, useState } from 'react'
import { Erro } from './Formularios'
import Icon from './Icon'
import { Campo, botaoPrimario, botaoSecundario, campo } from './ui'
import { api } from '../lib/api'
import { isoData, porExtenso } from '../lib/datas'
import { moeda } from '../lib/format'
import { useOpenFinance, type ContaPluggy, type ContasTrazidas, type FaturaPluggy, type Origem } from '../lib/openfinance'
import type { PreviaExtrato, PreviaFatura } from '../lib/tipos'
import { useApi } from '../lib/useApi'

export function EscolherOrigem({ valor, onChange }: { valor: Origem; onChange: (o: Origem) => void }) {
  const opcoes: { id: Origem; label: string }[] = [
    { id: 'arquivo', label: 'De um arquivo' },
    { id: 'banco', label: 'Direto do banco' },
  ]
  return (
    <div role="radiogroup" aria-label="De onde importar" className="grid grid-cols-2 gap-1 rounded-xl bg-nevoa p-1">
      {opcoes.map((o) => (
        <button
          key={o.id}
          role="radio"
          aria-checked={valor === o.id}
          onClick={() => onChange(o.id)}
          className={`min-h-11 cursor-pointer rounded-[10px] text-[15px] font-bold ${
            valor === o.id ? 'bg-white text-tinta shadow-sm' : 'text-suave hover:text-tinta'
          }`}
        >
          {o.label}
        </button>
      ))}
    </div>
  )
}

function rotulo(c: ContaPluggy) {
  return c.numero ? `${c.nome} (${c.numero})` : c.nome
}

function SemContas({ tipo }: { tipo: string }) {
  return (
    <p className="text-[15px] leading-snug text-suave">
      Nenhum {tipo} conectado no MeuPluggy. Conecte em meu.pluggy.ai e autorize na Pluggy para ele aparecer aqui.
    </p>
  )
}

export function BuscarFatura({
  cartao,
  contas,
  aoLer,
}: {
  cartao: string
  contas: ContaPluggy[]
  aoLer: (p: PreviaFatura, nome: string) => void
}) {
  const cartoes = contas.filter((c) => c.tipo === 'CREDIT')
  const vinculada = cartoes.find((c) => String(c.cartao) === cartao)
  const [escolhida, setEscolhida] = useState('')
  const pluggy = escolhida || vinculada?.id || cartoes[0]?.id || ''
  const faturas = useApi<FaturaPluggy[]>(pluggy ? `/openfinance/faturas/?pluggy=${pluggy}` : null)
  const [fatura, setFatura] = useState('aberta')
  const [buscando, setBuscando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)

  if (cartoes.length === 0) return <SemContas tipo="cartão" />

  async function buscar() {
    setErro(null)
    setBuscando(true)
    try {
      const p = await api<PreviaFatura>('/openfinance/fatura/', { method: 'POST', body: { cartao: Number(cartao), pluggy, fatura } })
      aoLer(p, cartoes.find((c) => c.id === pluggy)?.nome ?? 'banco')
    } catch (err) {
      setErro((err as Error).message || 'Não foi possível buscar a fatura.')
    } finally {
      setBuscando(false)
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <Campo label="Cartão no banco">
        <select
          value={pluggy}
          onChange={(e) => {
            setEscolhida(e.target.value)
            setFatura('aberta')
          }}
          className={campo}
        >
          {cartoes.map((c) => (
            <option key={c.id} value={c.id}>
              {rotulo(c)}
            </option>
          ))}
        </select>
      </Campo>
      <Campo label="Fatura">
        <select value={fatura} onChange={(e) => setFatura(e.target.value)} className={campo} disabled={faturas.carregando}>
          <option value="aberta">Fatura aberta (ainda não fechou)</option>
          {(faturas.dados ?? []).map((f) => (
            <option key={f.id} value={f.id}>
              Venceu em {porExtenso(f.vence)}, {moeda(f.total)}
            </option>
          ))}
        </select>
      </Campo>
      {faturas.erro && <Erro>{faturas.erro}</Erro>}
      {erro && <Erro>{erro}</Erro>}
      <BotaoBuscar buscando={buscando} onClick={buscar} disabled={!pluggy || !cartao} texto="Buscar fatura no banco" />
    </div>
  )
}

function diasAtras(n: number) {
  const d = new Date()
  d.setDate(d.getDate() - n)
  return isoData(d)
}

export function BuscarExtrato({
  conta,
  contas,
  aoLer,
}: {
  conta: string
  contas: ContaPluggy[]
  aoLer: (p: PreviaExtrato, nome: string) => void
}) {
  const bancos = contas.filter((c) => c.tipo === 'BANK')
  const vinculada = bancos.find((c) => String(c.conta) === conta)
  const [escolhida, setEscolhida] = useState('')
  const pluggy = escolhida || vinculada?.id || bancos[0]?.id || ''
  const [desde, setDesde] = useState(() => diasAtras(30))
  const [ate, setAte] = useState(() => isoData(new Date()))
  const [buscando, setBuscando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)

  if (bancos.length === 0) return <SemContas tipo="banco" />
  const atual = bancos.find((c) => c.id === pluggy)

  async function buscar() {
    setErro(null)
    setBuscando(true)
    try {
      const p = await api<PreviaExtrato>('/openfinance/extrato/', { method: 'POST', body: { conta: Number(conta), pluggy, desde, ate } })
      aoLer(p, atual?.nome ?? 'banco')
    } catch (err) {
      setErro((err as Error).message || 'Não foi possível buscar o extrato.')
    } finally {
      setBuscando(false)
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <Campo label="Conta no banco">
        <select value={pluggy} onChange={(e) => setEscolhida(e.target.value)} className={campo}>
          {bancos.map((c) => (
            <option key={c.id} value={c.id}>
              {rotulo(c)}
            </option>
          ))}
        </select>
      </Campo>
      {atual && <p className="-mt-2 text-sm text-suave">Saldo no banco agora: {moeda(atual.saldo)}</p>}
      <div className="grid grid-cols-2 gap-3">
        <Campo label="De">
          <input type="date" value={desde} max={ate} onChange={(e) => setDesde(e.target.value)} className={campo} />
        </Campo>
        <Campo label="Até">
          <input type="date" value={ate} min={desde} onChange={(e) => setAte(e.target.value)} className={campo} />
        </Campo>
      </div>
      {erro && <Erro>{erro}</Erro>}
      <BotaoBuscar buscando={buscando} onClick={buscar} disabled={!pluggy || !conta || !desde} texto="Buscar extrato no banco" />
      <p className="text-sm text-suave">O banco atualiza uma vez por dia. O que já foi importado vem desmarcado.</p>
    </div>
  )
}

function BotaoBuscar({ buscando, onClick, disabled, texto }: { buscando: boolean; onClick: () => void; disabled: boolean; texto: string }) {
  return (
    <button onClick={onClick} disabled={buscando || disabled} className={`${botaoPrimario} disabled:opacity-60`}>
      <Icon name="buscar" size={20} />
      {buscando ? 'Buscando no banco…' : texto}
    </button>
  )
}

/**
 * Cadastra as contas e os cartões conectados na Pluggy. Some quando o Open Finance está desligado.
 * Com `automatico`, roda sozinho ao abrir (primeiro acesso); o cadastro à mão continua disponível.
 */
export function TrazerDoBanco({ automatico = false, aoTrazer }: { automatico?: boolean; aoTrazer: (r: ContasTrazidas) => void }) {
  const of = useOpenFinance()
  const [trazendo, setTrazendo] = useState(false)
  const [erro, setErro] = useState<string | null>(null)
  const [aviso, setAviso] = useState<string | null>(null)
  const jaRodou = useRef(false)

  async function trazer() {
    setErro(null)
    setAviso(null)
    setTrazendo(true)
    try {
      const r = await api<ContasTrazidas>('/openfinance/trazer-contas/', { method: 'POST' })
      // Primeiro acesso: já traz os últimos meses, para o app não abrir vazio.
      if (automatico && (r.contas.length || r.cartoes.length)) await api('/openfinance/importar-recentes/', { method: 'POST', body: { dias: 60 } })
      const nomes = [...r.contas, ...r.cartoes]
      const partes = [nomes.length ? `Trouxemos do banco: ${nomes.join(', ')}.` : 'Tudo o que está conectado no banco já está aqui.']
      if (r.renomeadas.length) partes.push(`Nomes acertados: ${r.renomeadas.join(', ')}.`)
      if (r.conferir_datas.length) partes.push(`Confira o fechamento e o vencimento de: ${r.conferir_datas.join(', ')}. O banco não informou.`)
      setAviso(partes.join(' '))
      aoTrazer(r)
    } catch (err) {
      setErro((err as Error).message || 'Não foi possível trazer as contas do banco.')
    } finally {
      setTrazendo(false)
    }
  }

  useEffect(() => {
    if (automatico && of.ativo && !jaRodou.current) {
      jaRodou.current = true
      void trazer()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [automatico, of.ativo])

  if (!of.ativo) return null
  return (
    <div className="flex flex-col gap-2">
      <button onClick={trazer} disabled={trazendo} className={`${botaoSecundario} w-full disabled:opacity-60`}>
        <Icon name="buscar" size={20} />
        {trazendo ? 'Buscando no banco…' : 'Trazer contas e cartões do banco'}
      </button>
      {aviso && <p className="text-[15px] font-semibold text-musgo">{aviso}</p>}
      {erro && <Erro>{erro}</Erro>}
    </div>
  )
}

const DIAS_DO_MES = Array.from({ length: 28 }, (_, i) => i + 1)

/** O banco não informou fechamento e vencimento: pede os dias no lugar de inventar. */
export function ConferirDatas({ cartao, aoSalvar }: { cartao: { id: number; dia_fechamento: number; dia_vencimento: number }; aoSalvar: () => void }) {
  const [fecha, setFecha] = useState(cartao.dia_fechamento)
  const [vence, setVence] = useState(cartao.dia_vencimento)
  const [salvando, setSalvando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)

  async function salvar() {
    setErro(null)
    setSalvando(true)
    try {
      await api('/openfinance/datas-conferidas/', { method: 'POST', body: { cartao: cartao.id, dia_fechamento: fecha, dia_vencimento: vence } })
      aoSalvar()
    } catch (err) {
      setErro((err as Error).message || 'Não foi possível salvar.')
    } finally {
      setSalvando(false)
    }
  }

  return (
    <div className="flex flex-col gap-3 border-l-4 border-ambar bg-white py-3 pl-4 pr-3">
      <p className="text-[15px] font-semibold leading-snug text-ambar-texto">
        O banco não informou o fechamento e o vencimento deste cartão. Confira na fatura e acerte os dias.
      </p>
      <div className="grid grid-cols-2 gap-3">
        <Campo label="Fecha no dia">
          <select value={fecha} onChange={(e) => setFecha(Number(e.target.value))} className={campo}>
            {DIAS_DO_MES.map((d) => (
              <option key={d} value={d}>
                {d}
              </option>
            ))}
          </select>
        </Campo>
        <Campo label="Vence no dia">
          <select value={vence} onChange={(e) => setVence(Number(e.target.value))} className={campo}>
            {DIAS_DO_MES.map((d) => (
              <option key={d} value={d}>
                {d}
              </option>
            ))}
          </select>
        </Campo>
      </div>
      {erro && <Erro>{erro}</Erro>}
      <button onClick={salvar} disabled={salvando} className={`${botaoSecundario} disabled:opacity-60`}>
        {salvando ? 'Salvando…' : 'Salvar os dias'}
      </button>
    </div>
  )
}

interface Importados {
  lancamentos_cartao: number
  faturas: number
  movimentos: number
  pulados: string[]
}

/** Traz de uma vez os últimos dias de todas as contas e cartões ligados, sem revisar linha a linha. */
export function ImportarRecentes() {
  const of = useOpenFinance()
  const [dias, setDias] = useState(60)
  const [poupancas, setPoupancas] = useState(false)
  const [rodando, setRodando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)
  const [r, setR] = useState<Importados | null>(null)

  if (!of.ativo || !of.contas.some((c) => c.conta || c.cartao)) return null

  async function importar() {
    setErro(null)
    setR(null)
    setRodando(true)
    try {
      setR(await api<Importados>('/openfinance/importar-recentes/', { method: 'POST', body: { dias, poupancas } }))
    } catch (err) {
      setErro((err as Error).message || 'Não foi possível importar.')
    } finally {
      setRodando(false)
    }
  }

  return (
    <section className="flex flex-col gap-3 border-b border-linha pb-5">
      <h2 className="text-lg font-bold">Tudo do banco de uma vez</h2>
      <p className="text-[15px] leading-snug text-suave">
        Contas viram lançamentos, que você categoriza depois. Compras do cartão ficam no cartão, e em Lançamentos aparece só a fatura. O que já
        foi importado não se repete.
      </p>
      <div className="flex flex-wrap items-end gap-3">
        <Campo label="Período">
          <select value={dias} onChange={(e) => setDias(Number(e.target.value))} className={campo}>
            <option value={30}>Últimos 30 dias</option>
            <option value={60}>Últimos 60 dias</option>
            <option value={90}>Últimos 90 dias</option>
            <option value={180}>Últimos 6 meses</option>
          </select>
        </Campo>
        <label className="flex min-h-[50px] cursor-pointer items-center gap-2 text-[15px] font-semibold">
          <input type="checkbox" checked={poupancas} onChange={(e) => setPoupancas(e.target.checked)} className="size-5 accent-tinta" />
          Incluir poupanças
        </label>
      </div>
      <button onClick={importar} disabled={rodando} className={`${botaoPrimario} disabled:opacity-60`}>
        <Icon name="buscar" size={20} />
        {rodando ? 'Importando do banco…' : 'Importar do banco'}
      </button>
      {erro && <Erro>{erro}</Erro>}
      {r && (
        <div className="flex flex-col gap-1 text-[15px]">
          <p className="font-semibold text-musgo">
            {r.movimentos} movimentos das contas e {r.lancamentos_cartao} lançamentos em {r.faturas} faturas de cartão.
          </p>
          {r.pulados.map((p) => (
            <p key={p} className="text-ambar-texto">
              {p}
            </p>
          ))}
        </div>
      )}
    </section>
  )
}
