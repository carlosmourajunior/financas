import { useMemo, useState } from 'react'
import Icon from '../components/Icon'
import { Titulo } from '../components/ui'
import { hoje, lancamentos, type Lancamento } from '../data/mock'
import { moeda } from '../lib/format'

type Filtro = 'todos' | 'despesa' | 'receita' | 'parcelada' | 'recorrente'

const filtros: { id: Filtro; label: string }[] = [
  { id: 'todos', label: 'Todos' },
  { id: 'despesa', label: 'Despesas' },
  { id: 'receita', label: 'Receitas' },
  { id: 'parcelada', label: 'Parceladas' },
  { id: 'recorrente', label: 'Recorrentes' },
]

const DIAS = ['Domingo', 'Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado']

function rotuloDia(iso: string) {
  const d = new Date(`${iso}T12:00:00`)
  if (d.toDateString() === hoje.toDateString()) return 'Hoje'
  return `${DIAS[d.getDay()]}, ${d.getDate()}`
}

function combina(l: Lancamento, f: Filtro) {
  if (f === 'todos') return true
  if (f === 'despesa' || f === 'receita') return l.natureza === f
  return l.tipo === f
}

export default function Lancamentos() {
  const [filtro, setFiltro] = useState<Filtro>('todos')

  const grupos = useMemo(() => {
    const out: { dia: string; itens: Lancamento[] }[] = []
    for (const l of lancamentos.filter((l) => combina(l, filtro))) {
      const dia = rotuloDia(l.data)
      if (out[out.length - 1]?.dia !== dia) out.push({ dia, itens: [] })
      out[out.length - 1].itens.push(l)
    }
    return out
  }, [filtro])

  const entrou = lancamentos.filter((l) => l.natureza === 'receita').reduce((s, l) => s + l.valor, 0)
  const saiu = lancamentos.filter((l) => l.natureza === 'despesa').reduce((s, l) => s + l.valor, 0)

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-3.5 px-5 pt-5 lg:px-8 lg:pt-7">
      <Titulo
        acoes={
          <button aria-label="Buscar" className="flex size-11 cursor-pointer items-center justify-center rounded-xl border border-borda bg-white">
            <Icon name="buscar" size={20} />
          </button>
        }
      >
        Lançamentos
      </Titulo>

      <div className="-ml-3 flex items-center gap-1">
        <button aria-label="Mês anterior" className="flex size-11 cursor-pointer items-center justify-center">
          <Icon name="esquerda" size={20} strokeWidth={2} />
        </button>
        <span className="text-[17px] font-bold">Outubro de 2026</span>
        <button aria-label="Próximo mês" className="flex size-11 cursor-pointer items-center justify-center">
          <Icon name="direita" size={20} strokeWidth={2} />
        </button>
      </div>

      <p className="flex gap-7">
        <span className="flex flex-col">
          <span className="text-sm text-suave">Entrou</span>
          <span className="font-display text-[22px] font-bold text-musgo tabular-nums">{moeda(entrou)}</span>
        </span>
        <span className="flex flex-col">
          <span className="text-sm text-suave">Saiu</span>
          <span className="font-display text-[22px] font-bold tabular-nums">{moeda(saiu)}</span>
        </span>
      </p>

      <div className="flex flex-wrap gap-2">
        {filtros.map((f) => (
          <button
            key={f.id}
            aria-pressed={filtro === f.id}
            onClick={() => setFiltro(f.id)}
            className={`min-h-[38px] cursor-pointer rounded-[10px] border px-3.5 text-[15px] ${
              filtro === f.id ? 'border-tinta bg-tinta font-bold text-white' : 'border-borda bg-white font-semibold'
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      <div className="flex flex-col">
        {grupos.length === 0 && <p className="py-10 text-center text-suave">Nenhum lançamento com esse filtro neste mês.</p>}
        {grupos.map((g) => (
          <section key={g.dia}>
            <h2 className="pb-1 pt-5 text-[15px] font-bold text-suave">{g.dia}</h2>
            {g.itens.map((l) => (
              <div key={l.id} className="flex items-center gap-3 border-b border-linha py-3">
                <div className="flex min-w-0 grow flex-col gap-0.5">
                  <span className="text-base font-bold">{l.descricao}</span>
                  <span className="text-sm text-suave">
                    {l.natureza === 'receita' ? l.meio : `${l.categoria}, ${l.meio}`}
                  </span>
                </div>
                <div className="flex flex-col items-end gap-0.5">
                  <span className={`text-base font-bold tabular-nums ${l.natureza === 'receita' ? 'text-musgo' : ''}`}>
                    {l.natureza === 'receita' ? `+ ${moeda(l.valor)}` : moeda(l.valor)}
                  </span>
                  {l.parcela && <span className="text-sm text-suave">parcela {l.parcela.atual} de {l.parcela.total}</span>}
                  {l.tipo === 'recorrente' && <span className="text-sm text-suave">todo mês</span>}
                </div>
              </div>
            ))}
          </section>
        ))}
      </div>
    </div>
  )
}
