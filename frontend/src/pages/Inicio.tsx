import { useState } from 'react'
import { Link } from 'react-router-dom'
import BotaoPagar from '../components/BotaoPagar'
import { FormConta } from '../components/Formularios'
import Icon from '../components/Icon'
import ReguaDoMes from '../components/ReguaDoMes'
import { Barra, LinhaLink, LinkAcao, Secao, botaoSecundario } from '../components/ui'
import type { Pagina } from '../lib/api'
import { useAuth } from '../lib/auth'
import { nomeCartao, useCadastros } from '../lib/cadastros'
import { DIAS, MESES, diaMes, isoMes, lerData, maiuscula, porExtenso } from '../lib/datas'
import { moeda, moedaPartes, pct } from '../lib/format'
import { marcarLancamento, pagarFatura } from '../lib/pagar'
import type { Lancamento, Pendencia, Resumo } from '../lib/tipos'
import { useApi } from '../lib/useApi'

const OCULTO = 'R$ ••••'

function quando(dia: number, hoje: Date) {
  if (dia === hoje.getDate()) return 'hoje'
  if (dia === hoje.getDate() + 1) return 'amanhã'
  return `dia ${dia}`
}

function primeiroNome(nome: string) {
  return nome.split(' ')[0] || nome
}

export default function Inicio() {
  const { usuario, sair } = useAuth()
  const [oculto, setOculto] = useState(false)
  const m = (centavos: number) => (oculto ? OCULTO : moeda(centavos))

  const resumo = useApi<Resumo>('/resumo/')
  const cad = useCadastros()
  const mesAtual = isoMes(new Date())
  const ultimos = useApi<Pagina<Lancamento>>(`/lancamentos/?mes=${mesAtual}&sem_cartao=1&limit=6`)

  if (resumo.erro) return <p className="px-5 py-10 text-center text-suave">Não foi possível carregar o resumo. {resumo.erro}</p>
  if (!resumo.dados || cad.carregando) return <p className="px-5 py-10 text-center text-suave">Carregando…</p>

  const nome = primeiroNome(usuario?.nome ?? '')

  if (cad.contas.length === 0) {
    return (
      <div className="mx-auto flex max-w-xl flex-col gap-6 px-5 pt-8 lg:pt-12">
        <div className="flex flex-col gap-2">
          <h1 className="font-display text-[30px] font-extrabold tracking-tight">Olá, {nome}</h1>
          <p className="text-[17px] leading-snug text-suave">
            Para saber quanto ainda pode gastar, comece pela conta onde o seu dinheiro fica. Depois é só lançar ou importar.
          </p>
        </div>
        <FormConta botao="Criar minha primeira conta" aoSalvar={() => cad.recarregar()} />
        <button onClick={sair} className="min-h-11 cursor-pointer self-start text-[15px] font-semibold text-suave lg:hidden">
          Sair
        </button>
      </div>
    )
  }

  const r = resumo.dados
  const hoje = lerData(r.hoje)
  const aVencer = r.contas_do_mes.filter((c) => !c.paga)
  const partes = moedaPartes(r.livre_para_gastar)
  const ultimoDia = new Date(hoje.getFullYear(), hoje.getMonth() + 1, 0).getDate()
  const maiorCategoria = Math.max(0, ...r.categorias.map((c) => c.valor))
  const proximoMes = MESES[(hoje.getMonth() + 1) % 12]
  const emp = r.emprestimos

  return (
    <div className="flex flex-col lg:gap-7 lg:px-8 lg:pt-7">
      <div className="hidden flex-wrap items-center justify-between gap-4 lg:flex">
        <div>
          <h1 className="font-display text-[30px] font-extrabold tracking-tight">Olá, {nome}</h1>
          <p className="text-base text-suave">
            {maiuscula(DIAS[hoje.getDay()])}, {porExtenso(r.hoje)} de {hoje.getFullYear()}
          </p>
        </div>
        <div className="flex flex-wrap gap-2.5">
          <Link to="/importar" className={botaoSecundario}>
            <Icon name="importar" size={18} strokeWidth={2} />
            Importar arquivo
          </Link>
          <Link to="/lancamentos/novo" className="flex min-h-12 items-center gap-2 rounded-xl bg-tinta px-4 text-[15px] font-bold text-white">
            <Icon name="mais" size={18} strokeWidth={2} />
            Novo pagamento
          </Link>
          <Link to="/lancamentos/novo?natureza=receita" className="flex min-h-12 items-center gap-2 rounded-xl bg-musgo px-4 text-[15px] font-bold text-white">
            <Icon name="mais" size={18} strokeWidth={2} />
            Novo recebimento
          </Link>
        </div>
      </div>

      <section className="grid gap-x-12 gap-y-6 bg-tinta px-5 pb-7 pt-4 text-white lg:grid-cols-[repeat(auto-fit,minmax(300px,1fr))] lg:rounded-[20px] lg:px-8 lg:py-7">
        <div className="flex flex-col gap-5">
          <div className="flex items-center justify-between lg:hidden">
            <span className="text-base font-semibold">Olá, {nome}</span>
            <div className="flex items-center gap-0.5">
              <BotaoOlho oculto={oculto} onClick={() => setOculto(!oculto)} />
              <button onClick={sair} className="min-h-11 cursor-pointer rounded-xl px-3 text-[15px] font-semibold text-tinta-claro">
                Sair
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
          <ReguaDoMes hoje={hoje} contas={r.contas_do_mes} />
        </div>

        <div className="flex flex-col justify-end">
          <div className="hidden pb-1.5 text-base font-bold lg:block">Ainda vence este mês</div>
          {aVencer.length === 0 && (
            <p className="border-t border-white/20 py-3 text-[15px] text-tinta-claro">Nenhuma conta a vencer até o fim do mês.</p>
          )}
          {aVencer.map((c, i) => (
            <div key={i} className="flex items-center gap-3 border-t border-white/20 py-3">
              <span className="size-2.5 shrink-0 rounded-full bg-ambar" />
              <span className="grow text-[15px]">
                {c.nome}, {quando(c.dia, hoje)}
              </span>
              <span className="text-[15px] font-bold tabular-nums">{m(c.valor)}</span>
            </div>
          ))}
          <div className="hidden items-center gap-3 border-t border-white/20 py-3 lg:flex">
            <span className="grow text-[15px] text-tinta-claro">Em conta agora</span>
            <span className="text-[15px] font-bold tabular-nums">{m(r.saldo_em_conta)}</span>
          </div>
        </div>
      </section>

      <div className="flex gap-2 px-5 pb-2 pt-5 lg:hidden">
        <Link to="/lancamentos/novo" className={`${botaoSecundario} flex-1 px-2`}>
          <Icon name="mais" size={18} strokeWidth={2} />
          Pagamento
        </Link>
        <Link to="/lancamentos/novo?natureza=receita" className={`${botaoSecundario} flex-1 px-2 text-musgo`}>
          <Icon name="mais" size={18} strokeWidth={2} />
          Recebimento
        </Link>
        <Link to="/importar" className={`${botaoSecundario} flex-1 px-2`}>
          <Icon name="importar" size={18} strokeWidth={2} />
          Importar
        </Link>
      </div>

      <div className="px-5 pt-5 lg:px-0 lg:pt-0">
        <Pendencias vencidas={r.vencidas} hoje={r.vencem_hoje} m={m} aoMudar={resumo.recarregar} />
      </div>

      <div className="grid gap-8 px-5 pt-5 lg:grid-cols-[repeat(auto-fit,minmax(300px,1fr))] lg:gap-10 lg:px-0 lg:pt-0">
        <div className="flex flex-col gap-8">
          <Secao titulo={`${maiuscula(MESES[hoje.getMonth()])} até agora`}>
            <div className="grid grid-cols-2 gap-4">
              <Numero rotulo="Entrou" valor={m(r.entrou)} classe="text-musgo" />
              <Numero rotulo="Saiu" valor={m(r.saiu)} />
            </div>
            <p className="pt-3 text-[15px] text-suave lg:hidden">
              Em conta agora: <strong className="text-tinta">{m(r.saldo_em_conta)}</strong>
            </p>
          </Secao>

          <Secao titulo="Para onde foi o dinheiro" acao={<LinkAcao to="/lancamentos">Detalhes</LinkAcao>}>
            {r.categorias.length === 0 && <p className="py-2.5 text-[15px] text-suave">Nenhuma despesa lançada este mês.</p>}
            {r.categorias.map((c) => (
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
          <Secao titulo="Faturas do cartão">
            {r.faturas.length === 0 && (
              <LinhaLink to="/cartoes" titulo="Nenhum cartão cadastrado" sub="Cadastre para acompanhar as faturas" valor="" />
            )}
            {r.faturas.map((f) => {
              const c = cad.cartoes.find((x) => x.id === f.cartao)
              return (
                <LinhaLink
                  key={f.cartao}
                  to={`/cartoes?cartao=${f.cartao}`}
                  titulo={c ? nomeCartao(c) : f.nome}
                  sub={f.aberta ? `aberta, fecha em ${porExtenso(f.fecha)}` : `fechada, vence em ${porExtenso(f.vence)}`}
                  valor={m(f.total)}
                />
              )
            })}
          </Secao>
          <Secao
            titulo={`${maiuscula(proximoMes)} já tem compromisso`}
            acao={<LinkAcao to={`/lancamentos?mes=${isoMes(new Date(hoje.getFullYear(), hoje.getMonth() + 1, 1))}`}>Ver</LinkAcao>}
          >
            <p className="text-[15px] leading-relaxed text-suave">
              Parcelas e contas fixas somam <strong className="text-tinta">{m(r.compromisso_proximo_mes)}</strong>
              {r.entradas_proximo_mes > 0 ? (
                <>
                  , e estão previstos <strong className="text-musgo">{m(r.entradas_proximo_mes)}</strong> de recebimentos.
                </>
              ) : r.entrou > 0 ? (
                `, cerca de ${pct(r.compromisso_proximo_mes, r.entrou)} do que entrou este mês.`
              ) : (
                '.'
              )}
            </p>
          </Secao>
        </div>

        <div className="flex flex-col gap-8">
          <Secao titulo="Empréstimos">
            <LinhaLink
              to="/emprestimos"
              titulo="Você deve"
              sub={emp.devo_quantidade ? `${emp.devo_quantidade} ${emp.devo_quantidade === 1 ? 'empréstimo' : 'empréstimos'}, ${m(emp.devo_por_mes)} por mês` : 'Nada em aberto'}
              valor={m(emp.devo_total)}
            />
            <LinhaLink
              to="/emprestimos"
              titulo="Te devem"
              sub={emp.devem_pessoas.length ? emp.devem_pessoas.join(', ') : 'Ninguém te deve'}
              valor={m(emp.devem_total)}
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
                {(ultimos.dados?.results ?? []).map((l) => (
                  <tr key={l.id}>
                    <td className="border-b border-linha py-3 pr-3 text-suave">{diaMes(l.data)}</td>
                    <td className="border-b border-linha p-3 font-bold">
                      {l.descricao}{' '}
                      <span className="font-normal text-suave">
                        {l.parcela_total ? `parcela ${l.parcela_atual} de ${l.parcela_total}` : l.tipo === 'recorrente' ? 'todo mês' : ''}
                      </span>
                    </td>
                    <td className="border-b border-linha p-3">{cad.categoria(l)}</td>
                    <td className="border-b border-linha p-3">{cad.meio(l)}</td>
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

/** Contas que já venceram sem pagamento e as que vencem hoje, com o botão de pagar ao lado. */
function Pendencias({ vencidas, hoje, m, aoMudar }: { vencidas: Pendencia[]; hoje: Pendencia[]; m: (c: number) => string; aoMudar: () => void }) {
  if (vencidas.length === 0 && hoje.length === 0) {
    return <p className="rounded-[14px] bg-nevoa px-4 py-3 text-[15px] text-suave">Nenhuma conta vencida nem vencendo hoje.</p>
  }
  const soma = (l: Pendencia[]) => l.reduce((s, p) => s + p.valor, 0)
  return (
    <div className="grid gap-x-10 gap-y-6 lg:grid-cols-2">
      {vencidas.length > 0 && (
        <Secao titulo={`Vencidas, ${m(soma(vencidas))}`}>
          {vencidas.map((p) => (
            <LinhaPendencia key={chave(p)} p={p} quando={`Venceu em ${porExtenso(p.data)}`} m={m} aoMudar={aoMudar} />
          ))}
        </Secao>
      )}
      {hoje.length > 0 && (
        <Secao titulo={`Vencem hoje, ${m(soma(hoje))}`}>
          {hoje.map((p) => (
            <LinhaPendencia key={chave(p)} p={p} quando="Vence hoje" m={m} aoMudar={aoMudar} />
          ))}
        </Secao>
      )}
    </div>
  )
}

function chave(p: Pendencia) {
  return p.tipo === 'fatura' ? `f${p.cartao}-${p.fecha}` : `l${p.id}`
}

function LinhaPendencia({ p, quando, m, aoMudar }: { p: Pendencia; quando: string; m: (c: number) => string; aoMudar: () => void }) {
  const fatura = p.tipo === 'fatura'
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-2 border-b border-linha py-3">
      <span className="size-2.5 shrink-0 rounded-full bg-ambar" />
      <span className="flex min-w-0 grow flex-col">
        {fatura ? (
          <Link to={`/cartoes?cartao=${p.cartao}&fecha=${p.fecha}`} className="text-base font-bold underline-offset-2 hover:underline">
            {p.nome}
          </Link>
        ) : (
          <span className="text-base font-bold">{p.nome}</span>
        )}
        <span className="text-sm font-semibold text-ambar-texto">{quando}</span>
      </span>
      <span className="text-base font-bold tabular-nums">{m(p.valor)}</span>
      <BotaoPagar
        rotulo={fatura ? 'Marcar como paga' : 'Marcar como pago'}
        acao={() => (p.tipo === 'fatura' ? pagarFatura(p.cartao, p.fecha) : marcarLancamento(p.id, true))}
        aoMudar={aoMudar}
      />
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
