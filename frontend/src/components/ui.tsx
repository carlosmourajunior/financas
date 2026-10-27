import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import Icon from './Icon'

export function Titulo({ children, acoes }: { children: ReactNode; acoes?: ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-4">
      <h1 className="font-display text-[30px] font-extrabold tracking-tight">{children}</h1>
      {acoes}
    </div>
  )
}

export function Secao({ titulo, acao, children }: { titulo: string; acao?: ReactNode; children: ReactNode }) {
  return (
    <section className="flex flex-col">
      <div className="mb-1.5 flex items-baseline justify-between gap-4">
        <h2 className="font-display text-[21px] font-bold">{titulo}</h2>
        {acao}
      </div>
      {children}
    </section>
  )
}

export function LinkAcao({ to, children }: { to: string; children: ReactNode }) {
  return (
    <Link to={to} className="py-2.5 text-[15px] font-bold text-tinta hover:text-musgo">
      {children}
    </Link>
  )
}

export function Abas<T extends string>({
  rotulo,
  opcoes,
  valor,
  onChange,
}: {
  rotulo: string
  opcoes: { id: T; label: string }[]
  valor: T
  onChange: (v: T) => void
}) {
  return (
    <div role="tablist" aria-label={rotulo} className="flex gap-6 border-b border-linha">
      {opcoes.map((o) => {
        const ativa = o.id === valor
        return (
          <button
            key={o.id}
            role="tab"
            aria-selected={ativa}
            onClick={() => onChange(o.id)}
            className={`-mb-px min-h-11 cursor-pointer border-b-[3px] text-base ${
              ativa ? 'border-tinta font-bold text-tinta' : 'border-transparent font-semibold text-suave'
            }`}
          >
            {o.label}
          </button>
        )
      })}
    </div>
  )
}

export function Barra({ largura, cor = 'bg-tinta', altura = 'h-2' }: { largura: string; cor?: string; altura?: string }) {
  return (
    <div className={`${altura} rounded-full bg-linha`}>
      <div className={`${altura} rounded-full ${cor}`} style={{ width: largura }} />
    </div>
  )
}

/** Uma marca por parcela: pagas em tinta, restantes em cinza. */
export function Segmentos({ pagas, total }: { pagas: number; total: number }) {
  return (
    <div className="flex gap-[3px]" aria-hidden="true">
      {Array.from({ length: total }, (_, i) => (
        <span key={i} className={`h-1.5 flex-1 rounded-sm ${i < pagas ? 'bg-tinta' : 'bg-linha'}`} />
      ))}
    </div>
  )
}

export function LinhaLink({ to, titulo, sub, valor, valorClasse = '' }: { to: string; titulo: string; sub: string; valor: string; valorClasse?: string }) {
  return (
    <Link to={to} className="flex items-center gap-3 border-b border-linha py-3 text-tinta">
      <span className="flex grow flex-col gap-0.5">
        <span className="text-[15px] font-bold">{titulo}</span>
        <span className="text-sm text-suave">{sub}</span>
      </span>
      <span className={`text-base font-bold tabular-nums ${valorClasse}`}>{valor}</span>
      <span className="text-suave">
        <Icon name="direita" size={18} strokeWidth={2} />
      </span>
    </Link>
  )
}

export const botaoPrimario =
  'flex min-h-[54px] w-full cursor-pointer items-center justify-center gap-2 rounded-[14px] bg-tinta px-4 text-[17px] font-bold text-white hover:bg-tinta/90'

export const botaoSecundario =
  'flex min-h-12 cursor-pointer items-center justify-center gap-2 rounded-xl border border-borda bg-white px-4 text-[15px] font-bold text-tinta hover:bg-nevoa'

export const campo =
  'min-h-[50px] w-full rounded-xl border border-borda bg-white px-3.5 text-base text-tinta placeholder:text-suave/70'

export function Campo({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="flex flex-col gap-1.5 text-[15px] font-semibold">
      {label}
      {children}
    </label>
  )
}
