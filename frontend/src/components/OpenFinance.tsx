// Buscar fatura e extrato direto do banco (Open Finance pela Pluggy).
// Só aparece quando o backend tem o módulo ligado para o usuário; a prévia que volta é a mesma da importação de arquivo.
import { useState } from 'react'
import { Erro } from './Formularios'
import Icon from './Icon'
import { Campo, botaoPrimario, campo } from './ui'
import { api } from '../lib/api'
import { isoData, porExtenso } from '../lib/datas'
import { moeda } from '../lib/format'
import type { ContaPluggy, FaturaPluggy, Origem } from '../lib/openfinance'
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
