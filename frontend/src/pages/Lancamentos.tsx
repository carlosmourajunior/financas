import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import Icon from '../components/Icon'
import { Titulo } from '../components/ui'
import type { Pagina } from '../lib/api'
import { useCadastros } from '../lib/cadastros'
import { MESES, isoMes, lerData, maiuscula } from '../lib/datas'
import { moeda } from '../lib/format'
import type { Lancamento } from '../lib/tipos'
import { useApi } from '../lib/useApi'

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
  const d = lerData(iso)
  if (d.toDateString() === new Date().toDateString()) return 'Hoje'
  return `${DIAS[d.getDay()]}, ${d.getDate()}`
}

function combina(l: Lancamento, f: Filtro) {
  if (f === 'todos') return true
  if (f === 'despesa' || f === 'receita') return l.natureza === f
  return l.tipo === f
}

export default function Lancamentos() {
  const [filtro, setFiltro] = useState<Filtro>('todos')
  const [mes, setMes] = useState(() => {
    const d = new Date()
    return new Date(d.getFullYear(), d.getMonth(), 1)
  })
  const resposta = useApi<Pagina<Lancamento>>(`/lancamentos/?mes=${isoMes(mes)}&limit=1000`)
  const cad = useCadastros()
  const lancamentos = useMemo(() => resposta.dados?.results ?? [], [resposta.dados])
  const mudarMes = (delta: number) => setMes((m) => new Date(m.getFullYear(), m.getMonth() + delta, 1))

  const grupos = useMemo(() => {
    const out: { dia: string; itens: Lancamento[] }[] = []
    for (const l of lancamentos.filter((l) => combina(l, filtro))) {
      const dia = rotuloDia(l.data)
      if (out[out.length - 1]?.dia !== dia) out.push({ dia, itens: [] })
      out[out.length - 1].itens.push(l)
    }
    return out
  }, [filtro, lancamentos])

  const entrou = lancamentos.filter((l) => l.natureza === 'receita').reduce((s, l) => s + l.valor, 0)
  const saiu = lancamentos.filter((l) => l.natureza === 'despesa').reduce((s, l) => s + l.valor, 0)

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-3.5 px-5 pt-5 lg:px-8 lg:pt-7">
      <Titulo
        acoes={
          <Link
            to="/lancamentos/novo"
            className="hidden min-h-11 items-center gap-2 rounded-xl bg-tinta px-4 text-[15px] font-bold text-white lg:flex"
          >
            <Icon name="mais" size={18} strokeWidth={2} />
            Novo lançamento
          </Link>
        }
      >
        Lançamentos
      </Titulo>

      <div className="-ml-3 flex items-center gap-1">
        <button aria-label="Mês anterior" onClick={() => mudarMes(-1)} className="flex size-11 cursor-pointer items-center justify-center">
          <Icon name="esquerda" size={20} strokeWidth={2} />
        </button>
        <span className="text-[17px] font-bold" aria-live="polite">
          {maiuscula(MESES[mes.getMonth()])} de {mes.getFullYear()}
        </span>
        <button aria-label="Próximo mês" onClick={() => mudarMes(1)} className="flex size-11 cursor-pointer items-center justify-center">
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
        {resposta.erro && <p className="py-10 text-center text-suave">Não foi possível carregar. {resposta.erro}</p>}
        {resposta.carregando && !resposta.dados && <p className="py-10 text-center text-suave">Carregando…</p>}
        {resposta.dados && grupos.length === 0 && (
          <p className="py-10 text-center text-suave">
            {lancamentos.length === 0 ? 'Nenhum lançamento neste mês.' : 'Nenhum lançamento com esse filtro neste mês.'}
          </p>
        )}
        {grupos.map((g) => (
          <section key={g.dia}>
            <h2 className="pb-1 pt-5 text-[15px] font-bold text-suave">{g.dia}</h2>
            {g.itens.map((l) => (
              <div key={l.id} className="flex items-center gap-3 border-b border-linha py-3">
                <div className="flex min-w-0 grow flex-col gap-0.5">
                  <span className="text-base font-bold">{l.descricao}</span>
                  <span className="text-sm text-suave">
                    {l.natureza === 'receita' ? cad.meio(l) : `${cad.categoria(l)}, ${cad.meio(l)}`}
                    {!l.pago && ', a vencer'}
                  </span>
                </div>
                <div className="flex flex-col items-end gap-0.5">
                  <span className={`text-base font-bold tabular-nums ${l.natureza === 'receita' ? 'text-musgo' : ''}`}>
                    {l.natureza === 'receita' ? `+ ${moeda(l.valor)}` : moeda(l.valor)}
                  </span>
                  {l.parcela_total && (
                    <span className="text-sm text-suave">
                      parcela {l.parcela_atual} de {l.parcela_total}
                    </span>
                  )}
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
