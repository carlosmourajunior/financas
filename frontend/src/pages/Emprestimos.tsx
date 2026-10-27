import { useState } from 'react'
import { Abas, Barra, Titulo, botaoPrimario } from '../components/ui'
import { creditos, dividas } from '../data/mock'
import { moeda, pct } from '../lib/format'

type Aba = 'devo' | 'devem'

export default function Emprestimos() {
  const [aba, setAba] = useState<Aba>('devo')
  const devo = aba === 'devo'
  const totalDevo = dividas.reduce((s, d) => s + d.saldo, 0)
  const porMes = dividas.reduce((s, d) => s + d.parcela, 0)
  const totalDevem = creditos.reduce((s, c) => s + c.valor - c.devolvido, 0)
  const comPrazo = creditos.filter((c) => c.prazo).length

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4 px-5 pt-5 lg:px-8 lg:pt-7">
      <Titulo>Empréstimos</Titulo>
      <Abas
        rotulo="Tipo de empréstimo"
        opcoes={[
          { id: 'devo', label: 'Eu devo' },
          { id: 'devem', label: 'Me devem' },
        ]}
        valor={aba}
        onChange={setAba}
      />

      <div className="flex flex-col gap-1.5 pt-1">
        <p className="text-[15px] text-suave">{devo ? 'Você ainda deve' : 'Ainda vão te devolver'}</p>
        <p className="font-display text-[44px] font-extrabold leading-none tracking-tight tabular-nums">{moeda(devo ? totalDevo : totalDevem)}</p>
        <p className="text-[15px] text-suave">
          {devo
            ? `${moeda(porMes)} por mês em ${dividas.length} empréstimos`
            : `${creditos.length} pessoas, ${comPrazo} com prazo combinado`}
        </p>
      </div>

      <div className="flex flex-col">
        {devo
          ? dividas.map((d) => (
              <div key={d.nome} className="flex flex-col gap-2 border-b border-linha py-4">
                <div className="flex items-baseline justify-between gap-3">
                  <span className="text-[17px] font-bold">{d.nome}</span>
                  <span className="text-base font-bold tabular-nums">{moeda(d.parcela)}/mês</span>
                </div>
                <p className="text-sm text-suave">
                  {d.origem}, juros de {d.juros}
                </p>
                <Barra largura={pct(d.pagas, d.total)} />
                <div className="flex justify-between text-sm">
                  <span>
                    Paga {d.pagas} de {d.total}
                  </span>
                  <span>
                    Ainda deve <strong>{moeda(d.saldo)}</strong>
                  </span>
                </div>
                <p className="text-sm font-semibold text-ambar-texto">Próxima parcela dia {d.proxima}</p>
              </div>
            ))
          : creditos.map((c) => (
              <div key={c.pessoa} className="flex flex-col gap-2 border-b border-linha py-4">
                <div className="flex items-baseline justify-between gap-3">
                  <span className="text-[17px] font-bold">{c.pessoa}</span>
                  <span className="text-base font-bold text-musgo tabular-nums">{moeda(c.valor - c.devolvido)}</span>
                </div>
                <p className="text-sm text-suave">
                  Emprestou {moeda(c.valor)} em {c.data}, já devolveu {c.devolvido ? moeda(c.devolvido) : 'nada'}
                </p>
                <Barra largura={pct(c.devolvido, c.valor)} cor="bg-musgo" />
                <div className="flex items-center justify-between gap-3">
                  <span className="text-sm font-semibold text-ambar-texto">{c.prazo ? `Combinado para ${c.prazo}` : 'Sem data combinada'}</span>
                  <button className="min-h-10 cursor-pointer rounded-[10px] border border-borda bg-white px-3 text-sm font-bold">Registrar devolução</button>
                </div>
              </div>
            ))}
      </div>

      <button className={`${botaoPrimario} mt-2`}>{devo ? 'Registrar empréstimo' : 'Registrar que emprestei'}</button>
    </div>
  )
}
