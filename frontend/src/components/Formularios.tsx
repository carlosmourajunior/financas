import { useState, type ReactNode } from 'react'
import { api } from '../lib/api'
import { paraCentavos } from '../lib/format'
import type { Cartao, Conta } from '../lib/tipos'
import { useEnvio } from '../lib/useEnvio'
import { Campo, botaoPrimario, campo } from './ui'

export function Erro({ children }: { children: ReactNode }) {
  return (
    <p role="alert" className="rounded-xl bg-[#fbeceb] px-4 py-3 text-[15px] font-semibold text-[#9c2b20]">
      {children}
    </p>
  )
}

export function FormConta({ aoSalvar, botao = 'Salvar conta' }: { aoSalvar: (c: Conta) => void; botao?: string }) {
  const [nome, setNome] = useState('')
  const [tipo, setTipo] = useState<Conta['tipo']>('corrente')
  const [saldo, setSaldo] = useState('')
  const { erro, enviando, enviar } = useEnvio(async () => {
    const c = await api<Conta>('/contas/', { method: 'POST', body: { nome, tipo, saldo_inicial: paraCentavos(saldo) } })
    setNome('')
    setSaldo('')
    aoSalvar(c)
  })

  return (
    <form onSubmit={enviar} className="flex flex-col gap-4">
      <Campo label="Nome da conta">
        <input required value={nome} onChange={(e) => setNome(e.target.value)} placeholder="Ex.: Conta do banco" className={campo} />
      </Campo>
      <div className="grid grid-cols-2 gap-3">
        <Campo label="Tipo">
          <select value={tipo} onChange={(e) => setTipo(e.target.value as Conta['tipo'])} className={campo}>
            <option value="corrente">Conta corrente</option>
            <option value="poupanca">Poupança</option>
            <option value="dinheiro">Dinheiro</option>
          </select>
        </Campo>
        <Campo label="Saldo hoje">
          <input inputMode="decimal" value={saldo} onChange={(e) => setSaldo(e.target.value)} placeholder="0,00" className={`${campo} tabular-nums`} />
        </Campo>
      </div>
      {erro && <Erro>{erro}</Erro>}
      <button type="submit" disabled={enviando} className={`${botaoPrimario} disabled:opacity-60`}>
        {enviando ? 'Salvando…' : botao}
      </button>
    </form>
  )
}

export function FormCartao({ aoSalvar }: { aoSalvar: (c: Cartao) => void }) {
  const [nome, setNome] = useState('')
  const [final, setFinal] = useState('')
  const [limite, setLimite] = useState('')
  const [fecha, setFecha] = useState(3)
  const [vence, setVence] = useState(10)
  const { erro, enviando, enviar } = useEnvio(async () => {
    const c = await api<Cartao>('/cartoes/', {
      method: 'POST',
      body: { nome, final, limite: paraCentavos(limite), dia_fechamento: fecha, dia_vencimento: vence },
    })
    aoSalvar(c)
  })

  return (
    <form onSubmit={enviar} className="flex flex-col gap-4">
      <div className="grid grid-cols-[1fr_120px] gap-3">
        <Campo label="Nome do cartão">
          <input required value={nome} onChange={(e) => setNome(e.target.value)} placeholder="Ex.: Visa" className={campo} />
        </Campo>
        <Campo label="Final">
          <input
            inputMode="numeric"
            maxLength={4}
            value={final}
            onChange={(e) => setFinal(e.target.value.replace(/\D/g, ''))}
            placeholder="4321"
            className={`${campo} tabular-nums`}
          />
        </Campo>
      </div>
      <Campo label="Limite">
        <input required inputMode="decimal" value={limite} onChange={(e) => setLimite(e.target.value)} placeholder="0,00" className={`${campo} tabular-nums`} />
      </Campo>
      <div className="grid grid-cols-2 gap-3">
        <Campo label="Fecha no dia">
          <input type="number" min={1} max={28} required value={fecha} onChange={(e) => setFecha(Number(e.target.value))} className={campo} />
        </Campo>
        <Campo label="Vence no dia">
          <input type="number" min={1} max={28} required value={vence} onChange={(e) => setVence(Number(e.target.value))} className={campo} />
        </Campo>
      </div>
      {erro && <Erro>{erro}</Erro>}
      <button type="submit" disabled={enviando} className={`${botaoPrimario} disabled:opacity-60`}>
        {enviando ? 'Salvando…' : 'Salvar cartão'}
      </button>
    </form>
  )
}
