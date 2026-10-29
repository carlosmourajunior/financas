import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import Icon from '../components/Icon'
import LinhaComData from '../components/LinhaComData'
import { Titulo } from '../components/ui'
import type { Pagina } from '../lib/api'
import { useCadastros } from '../lib/cadastros'
import { MESES, isoData, isoMes, lerData, maiuscula, porExtenso } from '../lib/datas'
import { moeda } from '../lib/format'
import type { FaturaDoMes, Lancamento } from '../lib/tipos'
import { useApi } from '../lib/useApi'

type Filtro = 'todos' | 'despesa' | 'receita' | 'fatura' | 'recorrente' | 'parcelada'

const filtros: { id: Filtro; label: string }[] = [
  { id: 'todos', label: 'Todos' },
  { id: 'despesa', label: 'Despesas' },
  { id: 'receita', label: 'Receitas' },
  { id: 'fatura', label: 'Faturas' },
  { id: 'recorrente', label: 'Recorrentes' },
  { id: 'parcelada', label: 'Parceladas' },
]

/** Uma linha da lista: lançamento feito à mão ou o total de uma fatura de cartão. */
interface Linha {
  chave: string
  data: string
  titulo: string
  detalhe: string
  valor: number
  natureza: 'despesa' | 'receita'
  pago: boolean
  tipo: Lancamento['tipo'] | 'fatura'
  parcela?: string
  para?: string
}

function situacao(l: Linha, hoje: string) {
  if (l.natureza === 'receita') return l.pago ? 'Recebido' : `A receber em ${porExtenso(l.data)}`
  if (l.pago) return l.tipo === 'fatura' ? 'Paga no vencimento' : 'Pago'
  if (l.data === hoje) return 'Vence hoje'
  if (l.data < hoje) return 'Venceu e não foi pago'
  const dias = Math.round((lerData(l.data).getTime() - lerData(hoje).getTime()) / 86_400_000)
  return dias === 1 ? 'Vence amanhã' : `Vence em ${dias} dias`
}

function combina(l: Linha, f: Filtro) {
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
  // Compras no cartão ficam em Cartões; aqui entra só o total de cada fatura.
  const resposta = useApi<Pagina<Lancamento>>(`/lancamentos/?mes=${isoMes(mes)}&sem_cartao=1&limit=1000`)
  const faturas = useApi<FaturaDoMes[]>(`/faturas/?mes=${isoMes(mes)}`)
  const cad = useCadastros()
  const mudarMes = (delta: number) => setMes((m) => new Date(m.getFullYear(), m.getMonth() + delta, 1))
  const hoje = isoData(new Date())

  const linhas = useMemo(() => {
    const out: Linha[] = (resposta.dados?.results ?? []).map((l) => ({
      chave: `l${l.id}`,
      data: l.data,
      titulo: l.descricao,
      detalhe: l.natureza === 'receita' ? cad.meio(l) : `${cad.categoria(l)}, ${cad.meio(l)}`,
      valor: l.valor,
      natureza: l.natureza,
      pago: l.pago,
      tipo: l.tipo,
      parcela: l.parcela_total ? `parcela ${l.parcela_atual} de ${l.parcela_total}` : l.tipo === 'recorrente' ? 'todo mês' : undefined,
    }))
    for (const f of faturas.dados ?? []) {
      out.push({
        chave: `f${f.cartao}-${f.fecha}`,
        data: f.vence,
        titulo: f.final ? `${f.nome} final ${f.final}` : f.nome,
        detalhe: `${f.compras} ${f.compras === 1 ? 'compra' : 'compras'}, fechou em ${porExtenso(f.fecha)}`,
        valor: f.total,
        natureza: f.total < 0 ? 'receita' : 'despesa',
        pago: f.paga,
        tipo: 'fatura',
        para: `/cartoes?cartao=${f.cartao}&fecha=${f.fecha}`,
      })
    }
    return out.sort((a, b) => a.data.localeCompare(b.data) || a.titulo.localeCompare(b.titulo))
  }, [resposta.dados, faturas.dados, cad])

  const visiveis = linhas.filter((l) => combina(l, filtro))
  const entrou = linhas.filter((l) => l.natureza === 'receita').reduce((s, l) => s + Math.abs(l.valor), 0)
  const saiu = linhas.filter((l) => l.natureza === 'despesa').reduce((s, l) => s + l.valor, 0)
  const falta = linhas.filter((l) => l.natureza === 'despesa' && !l.pago).reduce((s, l) => s + l.valor, 0)
  const carregando = (resposta.carregando && !resposta.dados) || (faturas.carregando && !faturas.dados)
  const erro = resposta.erro || faturas.erro

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

      <p className="flex flex-wrap gap-x-7 gap-y-2">
        <span className="flex flex-col">
          <span className="text-sm text-suave">Entrou</span>
          <span className="font-display text-[22px] font-bold text-musgo tabular-nums">{moeda(entrou)}</span>
        </span>
        <span className="flex flex-col">
          <span className="text-sm text-suave">Saiu</span>
          <span className="font-display text-[22px] font-bold tabular-nums">{moeda(saiu)}</span>
        </span>
        <span className="flex flex-col">
          <span className="text-sm text-suave">Falta pagar</span>
          <span className={`font-display text-[22px] font-bold tabular-nums ${falta ? 'text-ambar-texto' : ''}`}>{moeda(falta)}</span>
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

      <div className="flex flex-col pt-2">
        {erro && <p className="py-10 text-center text-suave">Não foi possível carregar. {erro}</p>}
        {carregando && <p className="py-10 text-center text-suave">Carregando…</p>}
        {!carregando && !erro && visiveis.length === 0 && (
          <p className="py-10 text-center text-suave">
            {linhas.length === 0 ? 'Nenhum lançamento neste mês.' : 'Nenhum lançamento com esse filtro neste mês.'}
          </p>
        )}
        {visiveis.map((l) => (
          <LinhaComData
            key={l.chave}
            data={l.data}
            titulo={l.titulo}
            detalhe={l.detalhe}
            situacao={situacao(l, hoje)}
            alerta={!l.pago && l.natureza === 'despesa'}
            valor={l.natureza === 'receita' ? `+ ${moeda(Math.abs(l.valor))}` : moeda(l.valor)}
            valorClasse={l.natureza === 'receita' ? 'text-musgo' : ''}
            extra={l.parcela && <span className="text-sm text-suave">{l.parcela}</span>}
            para={l.para}
          />
        ))}
      </div>
    </div>
  )
}
