import { useState } from 'react'
import { Link } from 'react-router-dom'
import Icon from '../components/Icon'
import { Abas, Barra, Secao, Segmentos, Titulo, botaoSecundario } from '../components/ui'
import { cartoes } from '../data/mock'
import { moeda, pct } from '../lib/format'

export default function Cartoes() {
  const [sel, setSel] = useState(cartoes[0].id)
  const c = cartoes.find((x) => x.id === sel)!

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-3.5 px-5 pt-5 lg:px-8 lg:pt-7">
      <Titulo
        acoes={
          <button aria-label="Adicionar cartão" className="flex size-11 cursor-pointer items-center justify-center rounded-xl border border-borda bg-white">
            <Icon name="mais" size={20} strokeWidth={2} />
          </button>
        }
      >
        Cartões
      </Titulo>
      <Abas rotulo="Cartão" opcoes={cartoes.map((x) => ({ id: x.id, label: `${x.nome} ${x.final}` }))} valor={sel} onChange={setSel} />

      <div className="flex flex-col gap-7 pt-2">
        <section className="flex flex-col gap-3">
          <p className="text-[15px] text-suave">Fatura de novembro, aberta</p>
          <p className="font-display text-[44px] font-extrabold leading-none tracking-tight tabular-nums">{moeda(c.fatura)}</p>
          <p className="text-[15px] text-suave">
            Fecha dia {c.fechaDia} e vence dia {c.venceDia}
          </p>
          <div className="flex flex-col gap-1.5 pt-1">
            <Barra largura={pct(c.fatura, c.limite)} />
            <p className="text-[15px]">
              Disponível <strong>{moeda(c.limite - c.fatura)}</strong> de {moeda(c.limite)}
            </p>
          </div>
          <div className="flex gap-2.5 pt-1">
            <Link to="/importar" className="flex min-h-[50px] flex-1 items-center justify-center gap-2 rounded-[14px] bg-tinta text-base font-bold text-white">
              <Icon name="importar" size={18} strokeWidth={2} />
              Importar fatura
            </Link>
            <Link to="/lancamentos" className={`${botaoSecundario} flex-1 rounded-[14px]`}>
              Ver compras
            </Link>
          </div>
        </section>

        <Secao titulo="Parcelas em andamento">
          {c.parcelas.map((p) => (
            <div key={p.nome} className="flex flex-col gap-1.5 border-b border-linha py-3">
              <div className="flex justify-between text-base font-bold">
                <span>{p.nome}</span>
                <span className="tabular-nums">{moeda(p.valor)}</span>
              </div>
              <Segmentos pagas={p.pagas} total={p.total} />
              <p className="text-sm text-suave">
                Parcela {p.pagas} de {p.total}, termina em {p.fim}
              </p>
            </div>
          ))}
        </Secao>

        <Secao titulo="Próximas faturas">
          <p className="pb-1.5 text-[15px] text-suave">O que já está garantido por parcelas e assinaturas</p>
          {c.futuras.map((f) => (
            <div key={f.mes} className="flex justify-between border-b border-linha py-2.5 text-base">
              <span>{f.mes}</span>
              <span className="font-bold tabular-nums">{moeda(f.valor)}</span>
            </div>
          ))}
        </Secao>
      </div>
    </div>
  )
}
