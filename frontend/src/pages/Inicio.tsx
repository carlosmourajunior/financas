import { useState } from 'react'
import { Link } from 'react-router-dom'
import Icon from '../components/Icon'
import ReguaDoMes from '../components/ReguaDoMes'
import { Barra, LinhaLink, LinkAcao, Secao, botaoSecundario } from '../components/ui'
import {
  cartoes,
  categorias,
  contasDoMes,
  creditos,
  dividas,
  hoje,
  lancamentos,
  resumoMes,
  saldoEmConta,
  usuario,
} from '../data/mock'
import { moeda, moedaPartes, pct } from '../lib/format'

const OCULTO = 'R$ ••••'
const DIAS = ['domingo', 'segunda', 'terça', 'quarta', 'quinta', 'sexta', 'sábado']
const MESES = ['janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho', 'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro']

function quando(dia: number) {
  if (dia === hoje.getDate()) return 'hoje'
  if (dia === hoje.getDate() + 1) return 'amanhã'
  return `dia ${dia}`
}

export default function Inicio() {
  const [oculto, setOculto] = useState(false)
  const m = (centavos: number) => (oculto ? OCULTO : moeda(centavos))

  const aVencer = contasDoMes.filter((c) => !c.paga)
  const livre = saldoEmConta - aVencer.reduce((s, c) => s + c.valor, 0)
  const partes = moedaPartes(livre)
  const ultimoDia = new Date(hoje.getFullYear(), hoje.getMonth() + 1, 0).getDate()
  const maiorCategoria = Math.max(...categorias.map((c) => c.valor))
  const totalDevo = dividas.reduce((s, d) => s + d.saldo, 0)
  const parcelasDevo = dividas.reduce((s, d) => s + d.parcela, 0)
  const totalDevem = creditos.reduce((s, c) => s + c.valor - c.devolvido, 0)

  return (
    <div className="flex flex-col lg:gap-7 lg:px-8 lg:pt-7">
      <div className="hidden flex-wrap items-center justify-between gap-4 lg:flex">
        <div>
          <h1 className="font-display text-[30px] font-extrabold tracking-tight">Olá, {usuario.nome}</h1>
          <p className="text-base text-suave">
            {DIAS[hoje.getDay()].replace(/^./, (c) => c.toUpperCase())}, {hoje.getDate()} de {MESES[hoje.getMonth()]} de {hoje.getFullYear()}
          </p>
        </div>
        <div className="flex flex-wrap gap-2.5">
          <Link to="/importar" className={botaoSecundario}>
            <Icon name="importar" size={18} strokeWidth={2} />
            Importar arquivo
          </Link>
          <Link to="/lancamentos/novo" className="flex min-h-12 items-center gap-2 rounded-xl bg-tinta px-4 text-[15px] font-bold text-white">
            <Icon name="mais" size={18} strokeWidth={2} />
            Novo lançamento
          </Link>
        </div>
      </div>

      <section className="grid gap-x-12 gap-y-6 bg-tinta px-5 pb-7 pt-4 text-white lg:grid-cols-[repeat(auto-fit,minmax(300px,1fr))] lg:rounded-[20px] lg:px-8 lg:py-7">
        <div className="flex flex-col gap-5">
          <div className="flex items-center justify-between lg:hidden">
            <span className="text-base font-semibold">Olá, {usuario.nome}</span>
            <div className="flex gap-0.5">
              <BotaoOlho oculto={oculto} onClick={() => setOculto(!oculto)} />
              <button aria-label="Notificações" className="flex size-11 cursor-pointer items-center justify-center rounded-xl">
                <Icon name="sino" />
              </button>
            </div>
          </div>
          <div className="flex flex-col gap-1.5">
            <div className="flex items-center gap-2 text-base text-tinta-claro">
              Você ainda pode gastar
              <span className="hidden lg:inline">
                <BotaoOlho oculto={oculto} onClick={() => setOculto(!oculto)} />
              </span>
            </div>
            <div className="font-display text-[60px] font-extrabold leading-none tracking-[-2px] tabular-nums lg:text-[76px]">
              {oculto ? (
                OCULTO
              ) : (
                <>
                  {partes.inteiro}
                  <span className="text-[28px] tracking-tight lg:text-[34px]">{partes.centavos}</span>
                </>
              )}
            </div>
            <p className="text-[15px] text-tinta-claro">
              até {ultimoDia} de {MESES[hoje.getMonth()]}, já descontadas as contas que ainda vencem
            </p>
          </div>
          <ReguaDoMes hoje={hoje} contas={contasDoMes} />
        </div>

        <div className="flex flex-col justify-end">
          <div className="hidden pb-1.5 text-base font-bold lg:block">Ainda vence este mês</div>
          {aVencer.map((c) => (
            <div key={c.nome} className="flex items-center gap-3 border-t border-white/20 py-3">
              <span className="size-2.5 shrink-0 rounded-full bg-ambar" />
              <span className="grow text-[15px]">
                {c.nome}, {quando(c.dia)}
              </span>
              <span className="text-[15px] font-bold tabular-nums">{m(c.valor)}</span>
            </div>
          ))}
          <div className="hidden items-center gap-3 border-t border-white/20 py-3 lg:flex">
            <span className="grow text-[15px] text-tinta-claro">Em conta agora</span>
            <span className="text-[15px] font-bold tabular-nums">{m(saldoEmConta)}</span>
          </div>
        </div>
      </section>

      <div className="flex gap-2 px-5 pb-2 pt-5 lg:hidden">
        <Link to="/lancamentos/novo" className={`${botaoSecundario} flex-1`}>
          <Icon name="mais" size={18} strokeWidth={2} />
          Lançar
        </Link>
        <Link to="/importar" className={`${botaoSecundario} flex-1`}>
          <Icon name="importar" size={18} strokeWidth={2} />
          Importar
        </Link>
        <Link to="/cartoes" className={`${botaoSecundario} flex-1`}>
          <Icon name="cartao" size={18} strokeWidth={2} />
          Cartões
        </Link>
      </div>

      <div className="grid gap-8 px-5 pt-5 lg:grid-cols-[repeat(auto-fit,minmax(300px,1fr))] lg:gap-10 lg:px-0 lg:pt-0">
        <div className="flex flex-col gap-8">
          <Secao titulo={`${MESES[hoje.getMonth()].replace(/^./, (c) => c.toUpperCase())} até agora`}>
            <div className="grid grid-cols-2 gap-4">
              <Numero rotulo="Entrou" valor={m(resumoMes.entrou)} classe="text-musgo" />
              <Numero rotulo="Saiu" valor={m(resumoMes.saiu)} />
            </div>
            <p className="pt-3 text-[15px] text-suave lg:hidden">
              Em conta agora: <strong className="text-tinta">{m(saldoEmConta)}</strong>
            </p>
          </Secao>

          <Secao titulo="Para onde foi o dinheiro" acao={<LinkAcao to="/lancamentos">Detalhes</LinkAcao>}>
            {categorias.map((c) => (
              <div key={c.nome} className="flex flex-col gap-1.5 border-b border-linha py-2.5">
                <div className="flex justify-between text-[15px]">
                  <span className="font-semibold">{c.nome}</span>
                  <span className="font-bold tabular-nums">{m(c.valor)}</span>
                </div>
                <Barra largura={pct(c.valor, maiorCategoria)} altura="h-1.5" />
              </div>
            ))}
          </Secao>
        </div>

        <div className="flex flex-col gap-8">
          <Secao titulo="Faturas abertas">
            {cartoes.map((c) => (
              <LinhaLink
                key={c.id}
                to="/cartoes"
                titulo={`${c.nome} final ${c.final}`}
                sub={`fecha em ${c.fechaDia} de novembro`}
                valor={m(c.fatura)}
              />
            ))}
          </Secao>
          <Secao titulo="Novembro já tem compromisso">
            <p className="text-[15px] leading-relaxed text-suave">
              Parcelas e contas fixas somam <strong className="text-tinta">{m(resumoMes.compromissoProximoMes)}</strong>, cerca de{' '}
              {pct(resumoMes.compromissoProximoMes, resumoMes.entrou)} do que costuma entrar.
            </p>
          </Secao>
        </div>

        <div className="flex flex-col gap-8">
          <Secao titulo="Empréstimos">
            <LinhaLink
              to="/emprestimos"
              titulo="Você deve"
              sub={`${dividas.length} empréstimos, ${moeda(parcelasDevo)} por mês`}
              valor={m(totalDevo)}
            />
            <LinhaLink
              to="/emprestimos"
              titulo="Te devem"
              sub={creditos.map((c) => c.pessoa).join(' e ')}
              valor={m(totalDevem)}
              valorClasse="text-musgo"
            />
          </Secao>
        </div>
      </div>

      <div className="hidden lg:block">
        <Secao titulo="Últimos lançamentos" acao={<LinkAcao to="/lancamentos">Ver todos</LinkAcao>}>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[640px] border-collapse text-[15px]">
              <thead>
                <tr className="text-left text-suave">
                  <th className="border-b border-borda py-2.5 pr-3 font-semibold">Data</th>
                  <th className="border-b border-borda p-2.5 font-semibold">Descrição</th>
                  <th className="border-b border-borda p-2.5 font-semibold">Categoria</th>
                  <th className="border-b border-borda p-2.5 font-semibold">Pago com</th>
                  <th className="border-b border-borda py-2.5 pl-3 text-right font-semibold">Valor</th>
                </tr>
              </thead>
              <tbody>
                {lancamentos.slice(0, 6).map((l) => (
                  <tr key={l.id}>
                    <td className="border-b border-linha py-3 pr-3 text-suave">{l.data.slice(8, 10)}/{l.data.slice(5, 7)}</td>
                    <td className="border-b border-linha p-3 font-bold">
                      {l.descricao}{' '}
                      <span className="font-normal text-suave">
                        {l.parcela ? `parcela ${l.parcela.atual} de ${l.parcela.total}` : l.tipo === 'recorrente' ? 'todo mês' : ''}
                      </span>
                    </td>
                    <td className="border-b border-linha p-3">{l.categoria}</td>
                    <td className="border-b border-linha p-3">{l.meio}</td>
                    <td className={`border-b border-linha py-3 pl-3 text-right font-bold tabular-nums ${l.natureza === 'receita' ? 'text-musgo' : ''}`}>
                      {l.natureza === 'receita' ? `+ ${m(l.valor)}` : m(l.valor)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Secao>
      </div>
    </div>
  )
}

function BotaoOlho({ oculto, onClick }: { oculto: boolean; onClick: () => void }) {
  return (
    <button
      aria-label={oculto ? 'Mostrar valores' : 'Ocultar valores'}
      aria-pressed={oculto}
      onClick={onClick}
      className="flex size-11 cursor-pointer items-center justify-center rounded-xl text-white"
    >
      <Icon name="olho" />
    </button>
  )
}

function Numero({ rotulo, valor, classe = '' }: { rotulo: string; valor: string; classe?: string }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-sm text-suave">{rotulo}</span>
      <span className={`font-display text-2xl font-bold tabular-nums ${classe}`}>{valor}</span>
    </div>
  )
}
