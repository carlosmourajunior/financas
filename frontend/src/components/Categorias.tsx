import { useState } from 'react'
import { api } from '../lib/api'
import type { Categoria, Natureza } from '../lib/tipos'

/** As mesmas cores que o backend usa para as categorias padrão; todas legíveis sobre branco. */
export const PALETA = [
  '#8C5A3C',
  '#E07A1F',
  '#C9A227',
  '#7A8C2E',
  '#3E9B5F',
  '#4C9F38',
  '#2A9D8F',
  '#2B7A9B',
  '#1E6FB8',
  '#5A67D8',
  '#B8578B',
  '#D14D72',
  '#B5651D',
  '#4A5568',
  '#8A9A97',
]

export const COR_SEM_CATEGORIA = '#8A9A97'

const NOVA = '__nova'

export function PontoCor({ cor, tamanho = 'size-2.5' }: { cor?: string | null; tamanho?: string }) {
  return <span aria-hidden="true" className={`inline-block shrink-0 rounded-full ${tamanho}`} style={{ backgroundColor: cor || COR_SEM_CATEGORIA }} />
}

/** Nome da categoria com a bolinha da cor dela na frente. */
export function RotuloCategoria({ nome, cor }: { nome: string; cor?: string | null }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <PontoCor cor={cor} />
      {nome}
    </span>
  )
}

export function EscolherCor({ valor, onChange }: { valor: string; onChange: (cor: string) => void }) {
  return (
    <span role="radiogroup" aria-label="Cor da categoria" className="flex flex-wrap gap-1.5">
      {PALETA.map((cor) => {
        const escolhida = cor.toUpperCase() === valor.toUpperCase()
        return (
          <button
            key={cor}
            type="button"
            role="radio"
            aria-checked={escolhida}
            aria-label={`Cor ${cor}`}
            onClick={() => onChange(cor)}
            className={`flex size-8 cursor-pointer items-center justify-center rounded-full ${escolhida ? 'ring-2 ring-tinta ring-offset-2' : ''}`}
          >
            <span className="size-6 rounded-full" style={{ backgroundColor: cor }} />
          </button>
        )
      })}
    </span>
  )
}

/** Cor ainda não usada pelo usuário, para a categoria nova não nascer igual às outras. */
export function corLivre(categorias: Categoria[]) {
  const usadas = new Set(categorias.map((c) => c.cor?.toUpperCase()))
  return PALETA.find((c) => !usadas.has(c.toUpperCase())) ?? PALETA[categorias.length % PALETA.length]
}

/** Criar uma categoria ali mesmo, sem sair do que estava fazendo. */
export function NovaCategoria({
  natureza,
  categorias = [],
  aoCriar,
  aoCancelar,
}: {
  natureza: Natureza
  categorias?: Categoria[]
  aoCriar: (c: Categoria) => void
  aoCancelar: () => void
}) {
  const [nome, setNome] = useState('')
  const [cor, setCor] = useState(() => corLivre(categorias))
  const [erro, setErro] = useState<string | null>(null)
  const [salvando, setSalvando] = useState(false)

  async function criar() {
    if (!nome.trim()) return setErro('Dê um nome à categoria.')
    setSalvando(true)
    setErro(null)
    try {
      aoCriar(await api<Categoria>('/categorias/', { method: 'POST', body: { nome: nome.trim(), natureza, cor } }))
    } catch (err) {
      setErro((err as Error).message || 'Não foi possível criar.')
      setSalvando(false)
    }
  }

  return (
    <span className="flex w-full flex-col gap-2 rounded-[10px] border border-linha bg-white p-3">
      <span className="text-sm font-semibold text-tinta">Nova categoria de {natureza === 'receita' ? 'recebimento' : 'gasto'}</span>
      <input
        autoFocus
        aria-label="Nome da nova categoria"
        placeholder={natureza === 'receita' ? 'Ex.: Aluguel recebido' : 'Ex.: Pets'}
        value={nome}
        onChange={(e) => setNome(e.target.value)}
        onKeyDown={(e) => {
          // Dentro de outro formulário, o Enter cria a categoria em vez de enviar o lançamento.
          if (e.key === 'Enter') {
            e.preventDefault()
            criar()
          }
          if (e.key === 'Escape') aoCancelar()
        }}
        className="min-h-10 w-full rounded-lg border border-borda px-2.5 text-[15px] text-tinta"
      />
      <EscolherCor valor={cor} onChange={setCor} />
      <span className="flex items-center gap-2">
        <button
          type="button"
          onClick={criar}
          disabled={salvando}
          className="min-h-10 cursor-pointer rounded-lg bg-tinta px-4 text-sm font-bold text-white disabled:opacity-60"
        >
          {salvando ? 'Criando…' : 'Criar'}
        </button>
        <button type="button" onClick={aoCancelar} className="min-h-10 cursor-pointer px-2 text-sm font-semibold text-suave">
          Cancelar
        </button>
      </span>
      {erro && (
        <span role="alert" className="text-sm font-semibold text-ambar-texto">
          {erro}
        </span>
      )}
    </span>
  )
}

/**
 * Lista de categorias com "+ Nova categoria" no fim. Ao criar, a nova já fica escolhida.
 * `aoCriar` serve para recarregar a lista de categorias da tela.
 */
export function SeletorCategoria({
  valor,
  natureza,
  categorias,
  aoEscolher,
  aoCriar,
  rotulo,
  className,
  envoltorio = 'inline-flex max-w-full items-center gap-1.5',
  disabled,
}: {
  valor: number | null | undefined
  natureza: Natureza
  categorias: Categoria[]
  aoEscolher: (id: number | null) => void
  aoCriar?: (c: Categoria) => void
  rotulo?: string
  className?: string
  envoltorio?: string
  disabled?: boolean
}) {
  const [criando, setCriando] = useState(false)
  const daNatureza = categorias.filter((c) => c.natureza === natureza)
  const escolhida = categorias.find((c) => c.id === valor)

  if (criando) {
    return (
      <NovaCategoria
        natureza={natureza}
        categorias={categorias}
        aoCancelar={() => setCriando(false)}
        aoCriar={(c) => {
          setCriando(false)
          aoCriar?.(c)
          aoEscolher(c.id)
        }}
      />
    )
  }

  return (
    <span className={envoltorio}>
      {escolhida && <PontoCor cor={escolhida.cor} />}
      <select
        aria-label={rotulo}
        value={valor ?? ''}
        disabled={disabled}
        onChange={(e) => {
          if (e.target.value === NOVA) setCriando(true)
          else aoEscolher(e.target.value ? Number(e.target.value) : null)
        }}
        className={className}
      >
        <option value="">Sem categoria</option>
        {daNatureza.map((c) => (
          <option key={c.id} value={c.id}>
            {c.nome}
          </option>
        ))}
        <option value={NOVA}>+ Nova categoria</option>
      </select>
    </span>
  )
}
