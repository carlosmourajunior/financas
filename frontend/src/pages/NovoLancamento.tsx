import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import Icon from '../components/Icon'
import { Abas, Campo, botaoPrimario, campo } from '../components/ui'
import type { Natureza, Tipo } from '../data/mock'
import { moeda } from '../lib/format'

const tipos: { id: Tipo; label: string; desc: string }[] = [
  { id: 'unica', label: 'Única', desc: 'Acontece uma vez só' },
  { id: 'parcelada', label: 'Parcelada', desc: 'Dividida em parcelas mensais' },
  { id: 'recorrente', label: 'Recorrente', desc: 'Se repete, como aluguel ou salário' },
]

const MESES = ['janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho', 'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro']

/** Converte "4.500,00" ou "4500" em centavos. */
function paraCentavos(texto: string) {
  const limpo = texto.replace(/[^\d,]/g, '').replace(',', '.')
  const n = Number.parseFloat(limpo)
  return Number.isFinite(n) ? Math.round(n * 100) : 0
}

export default function NovoLancamento() {
  const navigate = useNavigate()
  const [natureza, setNatureza] = useState<Natureza>('despesa')
  const [tipo, setTipo] = useState<Tipo>('parcelada')
  const [valor, setValor] = useState('4.500,00')
  const [parcelas, setParcelas] = useState(10)
  const [primeira, setPrimeira] = useState('2026-11')

  const total = paraCentavos(valor)
  const porParcela = parcelas > 0 ? Math.round(total / parcelas) : 0
  const [ano, mes] = primeira.split('-').map(Number)
  const ultima = new Date(ano, mes - 1 + parcelas - 1, 1)

  function salvar(e: FormEvent) {
    e.preventDefault()
    // A gravação entra quando a API existir.
    navigate('/lancamentos')
  }

  return (
    <form onSubmit={salvar} className="mx-auto flex min-h-dvh max-w-xl flex-col bg-fundo">
      <div className="flex items-center justify-between px-2 pt-3">
        <Link to="/" aria-label="Fechar" className="flex size-11 items-center justify-center">
          <Icon name="fechar" strokeWidth={2} />
        </Link>
        <Abas
          rotulo="Natureza"
          opcoes={[
            { id: 'despesa', label: 'Despesa' },
            { id: 'receita', label: 'Receita' },
          ]}
          valor={natureza}
          onChange={setNatureza}
        />
        <span className="w-11" />
      </div>

      <div className="flex flex-col gap-5 px-5 py-5">
        <label className="flex flex-col gap-1 text-[15px] text-suave">
          {tipo === 'parcelada' ? 'Valor total da compra' : 'Valor'}
          <span className="flex items-baseline gap-2 font-display text-5xl font-extrabold tracking-tight text-tinta">
            R$
            <input
              inputMode="decimal"
              value={valor}
              onChange={(e) => setValor(e.target.value)}
              className="w-full min-w-0 bg-transparent tabular-nums outline-none"
            />
          </span>
        </label>

        <fieldset className="flex flex-col">
          <legend className="pb-1.5 text-[15px] font-bold">Tipo de lançamento</legend>
          {tipos.map((t) => (
            <label key={t.id} className="flex min-h-[60px] cursor-pointer items-center gap-3 border-b border-linha py-2">
              <input
                type="radio"
                name="tipo"
                checked={tipo === t.id}
                onChange={() => setTipo(t.id)}
                className="size-5 shrink-0 accent-tinta"
              />
              <span className="flex flex-col">
                <span className={`text-base ${tipo === t.id ? 'font-bold' : 'font-semibold'}`}>{t.label}</span>
                <span className="text-sm text-suave">{t.desc}</span>
              </span>
            </label>
          ))}
        </fieldset>

        {tipo === 'parcelada' && (
          <div className="flex flex-col gap-2.5 rounded-[14px] bg-nevoa p-4">
            <div className="grid grid-cols-2 gap-3">
              <Campo label="Parcelas">
                <input
                  type="number"
                  min={2}
                  max={72}
                  value={parcelas}
                  onChange={(e) => setParcelas(Number(e.target.value))}
                  className={`${campo} min-h-12 font-bold`}
                />
              </Campo>
              <Campo label="Primeira em">
                <input type="month" value={primeira} onChange={(e) => setPrimeira(e.target.value)} className={`${campo} min-h-12 font-bold`} />
              </Campo>
            </div>
            <p className="text-[15px]">
              {parcelas} parcelas de <strong>{moeda(porParcela)}</strong>, a última em {MESES[ultima.getMonth()]} de {ultima.getFullYear()}
            </p>
          </div>
        )}

        {tipo === 'recorrente' && (
          <div className="flex flex-col gap-2.5 rounded-[14px] bg-nevoa p-4">
            <div className="grid grid-cols-2 gap-3">
              <Campo label="Repete">
                <select className={`${campo} min-h-12`}>
                  <option>Todo mês</option>
                  <option>Toda semana</option>
                  <option>Todo ano</option>
                </select>
              </Campo>
              <Campo label="Até">
                <select className={`${campo} min-h-12`}>
                  <option>Sem fim</option>
                  <option>Uma data</option>
                  <option>N vezes</option>
                </select>
              </Campo>
            </div>
            <p className="text-[15px]">Entra nas contas todo mês, até você encerrar</p>
          </div>
        )}

        <Campo label="Descrição">
          <input defaultValue="Notebook" className={campo} />
        </Campo>
        <div className="grid grid-cols-2 gap-3">
          <Campo label="Categoria">
            <select className={campo}>
              <option>Eletrônicos</option>
              <option>Moradia</option>
              <option>Alimentação</option>
              <option>Transporte</option>
            </select>
          </Campo>
          <Campo label="Data">
            <input type="date" defaultValue="2026-10-27" className={campo} />
          </Campo>
        </div>
        <Campo label={natureza === 'despesa' ? 'Pago com' : 'Recebido em'}>
          <select className={campo}>
            {natureza === 'despesa' && <option>Visa final 4321</option>}
            {natureza === 'despesa' && <option>Master final 8890</option>}
            <option>Conta corrente</option>
            <option>Dinheiro</option>
          </select>
        </Campo>
      </div>

      <div className="sticky bottom-0 mt-auto border-t border-linha bg-white px-5 pb-7 pt-4">
        <button type="submit" className={botaoPrimario}>
          {natureza === 'despesa' ? 'Salvar despesa' : 'Salvar receita'}
        </button>
      </div>
    </form>
  )
}
