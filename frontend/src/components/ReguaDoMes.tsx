import type { Conta } from '../data/mock'

const MESES = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez']

/**
 * Linha do mês com o dia de hoje e as contas: pagas em cinza, a vencer em âmbar.
 * Fica sobre o fundo tinta do destaque do Início.
 */
export default function ReguaDoMes({ hoje, contas }: { hoje: Date; contas: Conta[] }) {
  const diasNoMes = new Date(hoje.getFullYear(), hoje.getMonth() + 1, 0).getDate()
  const pos = (dia: number) => `${((dia - 1) / (diasNoMes - 1)) * 100}%`
  const aVencer = contas.filter((c) => !c.paga)
  const descricao = `Régua de ${MESES[hoje.getMonth()]}: hoje é dia ${hoje.getDate()}, ${contas.length - aVencer.length} contas pagas e ${aVencer.length} a vencer`

  return (
    <div className="flex flex-col gap-2">
      <div role="img" aria-label={descricao} className="relative h-7">
        <div className="absolute inset-x-0 top-[13px] h-0.5 bg-white/25" />
        <div className="absolute left-0 top-3 h-1 rounded-full bg-white" style={{ width: pos(hoje.getDate()) }} />
        {contas.map((c) =>
          c.paga ? (
            <span key={c.nome} className="absolute top-[9px] -ml-[5px] size-2.5 rounded-full bg-marca-paga" style={{ left: pos(c.dia) }} />
          ) : (
            <span
              key={c.nome}
              className="absolute top-[7px] -ml-[7px] size-3.5 rounded-full border-2 border-tinta bg-ambar"
              style={{ left: pos(c.dia) }}
            />
          ),
        )}
        <span className="absolute top-0.5 -ml-0.5 h-6 w-1 rounded-full bg-white" style={{ left: pos(hoje.getDate()) }} />
      </div>
      <div className="flex justify-between text-[13px] text-tinta-claro/80 tabular-nums">
        <span>1 {MESES[hoje.getMonth()]}</span>
        <span>hoje, {hoje.getDate()}</span>
        <span>{diasNoMes}</span>
      </div>
    </div>
  )
}
