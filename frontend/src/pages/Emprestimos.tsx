import { useState } from 'react'
import BotaoPagar from '../components/BotaoPagar'
import { Erro } from '../components/Formularios'
import { Abas, Barra, Campo, Titulo, botaoPrimario, botaoSecundario, campo } from '../components/ui'
import { api, type Pagina } from '../lib/api'
import { diaMes, isoData, lerData, maiuscula } from '../lib/datas'
import { moeda, paraCentavos, pct } from '../lib/format'
import type { Emprestimo } from '../lib/tipos'
import { useApi } from '../lib/useApi'
import { useEnvio } from '../lib/useEnvio'

type Aba = 'devo' | 'devem'

const linkDiscreto = 'min-h-7 cursor-pointer text-[13px] font-semibold text-suave underline underline-offset-2'

/** Mesma regra da API: a 1ª parcela vence no primeiro dia de vencimento depois da contratação. */
function parcelasVencidas(data: string, dia: number | null, parcelas: number) {
  if (!data || !parcelas) return 0
  const inicio = lerData(data)
  const d = dia || inicio.getDate()
  const noMes = (ano: number, mes: number) => new Date(ano, mes, Math.min(d, new Date(ano, mes + 1, 0).getDate()))
  let primeira = noMes(inicio.getFullYear(), inicio.getMonth())
  if (primeira <= inicio) primeira = noMes(inicio.getFullYear(), inicio.getMonth() + 1)
  const hoje = lerData(isoData(new Date()))
  let vencidas = 0
  for (let k = 0; k < parcelas; k++) {
    if (noMes(primeira.getFullYear(), primeira.getMonth() + k) < hoje) vencidas++
  }
  return vencidas
}

function juros(valor: string | null) {
  if (!valor) return null
  return `juros de ${Number(valor).toLocaleString('pt-BR', { maximumFractionDigits: 3 })}% ao mês`
}

export default function Emprestimos() {
  const [aba, setAba] = useState<Aba>('devo')
  const [novo, setNovo] = useState(false)
  const devo = aba === 'devo'
  const resposta = useApi<Pagina<Emprestimo>>(`/emprestimos/?direcao=${aba}&limit=500`)
  const todos = resposta.dados?.results ?? []
  const itens = todos.filter((e) => e.saldo > 0)
  const quitados = todos.filter((e) => e.saldo <= 0)
  const total = itens.reduce((s, e) => s + e.saldo, 0)
  const porMes = itens.reduce((s, e) => s + (e.parcela_valor ?? 0), 0)
  const comPrazo = itens.filter((e) => e.prazo).length

  function trocarAba(a: Aba) {
    setAba(a)
    setNovo(false)
  }

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
        onChange={trocarAba}
      />

      <div className="flex flex-col gap-1.5 pt-1">
        <p className="text-[15px] text-suave">{devo ? 'Você ainda deve' : 'Ainda vão te devolver'}</p>
        <p className="font-display text-[44px] font-extrabold leading-none tracking-tight tabular-nums">{moeda(total)}</p>
        <p className="text-[15px] text-suave">
          {itens.length === 0
            ? devo
              ? 'Nenhum empréstimo em aberto'
              : 'Ninguém te deve agora'
            : devo
              ? `${moeda(porMes)} por mês em ${itens.length} ${itens.length === 1 ? 'empréstimo' : 'empréstimos'}`
              : `${itens.length} ${itens.length === 1 ? 'pessoa' : 'pessoas'}, ${comPrazo} com prazo combinado`}
        </p>
      </div>

      {resposta.erro && <p className="py-6 text-center text-suave">Não foi possível carregar. {resposta.erro}</p>}

      <div className="flex flex-col">
        {itens.map((e) => (
          <ItemEmprestimo key={e.id} e={e} aoMudar={resposta.recarregar} />
        ))}
      </div>

      {quitados.length > 0 && (
        <details className="text-suave">
          <summary className="cursor-pointer py-2 text-[15px] font-bold">
            {devo ? 'Quitados' : 'Já devolvidos'} ({quitados.length})
          </summary>
          {quitados.map((e) => (
            <ItemEmprestimo key={e.id} e={e} aoMudar={resposta.recarregar} />
          ))}
        </details>
      )}

      {novo ? (
        <FormEmprestimo
          direcao={aba}
          aoCancelar={() => setNovo(false)}
          aoSalvar={() => {
            setNovo(false)
            resposta.recarregar()
          }}
        />
      ) : (
        <button onClick={() => setNovo(true)} className={`${botaoPrimario} mt-2`}>
          {devo ? 'Registrar empréstimo' : 'Registrar que emprestei'}
        </button>
      )}
    </div>
  )
}

function ItemEmprestimo({ e, aoMudar }: { e: Emprestimo; aoMudar: () => void }) {
  const [pagando, setPagando] = useState(false)
  const [editando, setEditando] = useState(false)
  const [apagando, setApagando] = useState(false)
  const [vendoPagamentos, setVendoPagamentos] = useState(false)

  if (editando) {
    return (
      <FormEmprestimo
        direcao={e.direcao}
        e={e}
        aoCancelar={() => setEditando(false)}
        aoSalvar={() => {
          setEditando(false)
          aoMudar()
        }}
      />
    )
  }

  const devo = e.direcao === 'devo'
  const detalhes = [e.instituicao, juros(e.juros_mensal)].filter(Boolean).join(', ')

  return (
    <div className="flex flex-col gap-2 border-b border-linha py-4">
      <div className="flex items-baseline justify-between gap-3">
        <span className="text-[17px] font-bold">{e.nome}</span>
        <span className={`text-base font-bold tabular-nums ${devo ? '' : 'text-musgo'}`}>
          {devo && e.parcela_valor ? `${moeda(e.parcela_valor)}/mês` : moeda(e.saldo)}
        </span>
      </div>
      {devo ? (
        detalhes && <p className="text-sm text-suave">{maiuscula(detalhes)}</p>
      ) : (
        <p className="text-sm text-suave">
          Emprestou {moeda(e.valor_total)} em {diaMes(e.data)}, já devolveu {e.pago ? moeda(e.pago) : 'nada'}
        </p>
      )}
      <Barra
        largura={e.parcelas_total && e.parcelas_pagas !== null ? pct(e.parcelas_pagas, e.parcelas_total) : pct(e.pago, e.valor_total)}
        cor={devo ? 'bg-tinta' : 'bg-musgo'}
      />
      <div className="flex justify-between gap-3 text-sm">
        <span>
          {e.parcelas_total ? `Paga ${e.parcelas_pagas ?? 0} de ${e.parcelas_total}` : `Pago ${moeda(e.pago)} de ${moeda(e.valor_total)}`}
        </span>
        {devo && (
          <span>
            Ainda deve <strong>{moeda(e.saldo)}</strong>
          </span>
        )}
      </div>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <span className="text-sm font-semibold text-ambar-texto">
          {devo
            ? e.dia_vencimento
              ? `Próxima parcela dia ${e.dia_vencimento}`
              : ''
            : e.prazo
              ? `Combinado para ${diaMes(e.prazo)}`
              : 'Sem data combinada'}
        </span>
        {!pagando && (
          <button onClick={() => setPagando(true)} className="min-h-10 cursor-pointer rounded-[10px] border border-borda bg-white px-3 text-sm font-bold">
            {devo ? 'Registrar pagamento' : 'Registrar devolução'}
          </button>
        )}
      </div>
      <span className="flex flex-wrap items-center gap-x-4 gap-y-1">
        <button type="button" onClick={() => setEditando(true)} className={linkDiscreto}>
          Editar
        </button>
        {e.pagamentos.length > 0 && (
          <button type="button" onClick={() => setVendoPagamentos(!vendoPagamentos)} className={linkDiscreto}>
            {vendoPagamentos ? 'Esconder pagamentos' : `Ver pagamentos (${e.pagamentos.length})`}
          </button>
        )}
        {!apagando && (
          <button type="button" onClick={() => setApagando(true)} className={linkDiscreto}>
            Apagar
          </button>
        )}
      </span>
      {apagando && (
        <span className="flex flex-wrap items-center gap-2 rounded-[10px] bg-nevoa px-3 py-2">
          <span className="text-sm font-semibold">Apagar {e.nome} e os {e.pagamentos.length} pagamentos registrados?</span>
          <BotaoPagar rotulo="Apagar" acao={() => api(`/emprestimos/${e.id}/`, { method: 'DELETE' })} aoMudar={aoMudar} />
          <button type="button" onClick={() => setApagando(false)} className="min-h-10 cursor-pointer px-2 text-sm font-semibold text-suave">
            Cancelar
          </button>
        </span>
      )}
      {vendoPagamentos && (
        <ul className="flex flex-col rounded-[10px] bg-nevoa px-3 py-1">
          {[...e.pagamentos].reverse().map((p) => (
            <li key={p.id} className="flex items-center justify-between gap-3 border-b border-linha py-1.5 text-sm last:border-0">
              <span>
                {diaMes(p.data)}/{p.data.slice(0, 4)}
              </span>
              <span className="flex items-center gap-3">
                <span className="font-semibold tabular-nums">{moeda(p.valor)}</span>
                <BotaoPagar rotulo="Apagar" discreto acao={() => api(`/pagamentos-emprestimo/${p.id}/`, { method: 'DELETE' })} aoMudar={aoMudar} />
              </span>
            </li>
          ))}
        </ul>
      )}
      {pagando && (
        <Pagamento
          e={e}
          aoCancelar={() => setPagando(false)}
          aoSalvar={() => {
            setPagando(false)
            aoMudar()
          }}
        />
      )}
    </div>
  )
}

function Pagamento({ e, aoSalvar, aoCancelar }: { e: Emprestimo; aoSalvar: () => void; aoCancelar: () => void }) {
  const sugestao = e.parcela_valor && e.parcela_valor <= e.saldo ? e.parcela_valor : e.saldo
  const [valor, setValor] = useState((sugestao / 100).toLocaleString('pt-BR', { minimumFractionDigits: 2 }))
  const [data, setData] = useState(() => isoData(new Date()))
  const { erro, enviando, enviar } = useEnvio(async () => {
    const centavos = paraCentavos(valor)
    if (centavos <= 0) throw new Error('Informe um valor maior que zero.')
    await api('/pagamentos-emprestimo/', { method: 'POST', body: { emprestimo: e.id, valor: centavos, data } })
    aoSalvar()
  })

  return (
    <form onSubmit={enviar} className="flex flex-col gap-3 rounded-[14px] bg-nevoa p-4">
      <div className="grid grid-cols-2 gap-3">
        <Campo label="Valor">
          <input required inputMode="decimal" value={valor} onChange={(ev) => setValor(ev.target.value)} className={`${campo} tabular-nums`} />
        </Campo>
        <Campo label="Data">
          <input type="date" required value={data} onChange={(ev) => setData(ev.target.value)} className={campo} />
        </Campo>
      </div>
      {erro && <Erro>{erro}</Erro>}
      <div className="flex gap-2.5">
        <button type="button" onClick={aoCancelar} className={`${botaoSecundario} flex-1`}>
          Cancelar
        </button>
        <button type="submit" disabled={enviando} className="flex min-h-12 flex-1 cursor-pointer items-center justify-center rounded-xl bg-tinta px-4 text-[15px] font-bold text-white disabled:opacity-60">
          {enviando ? 'Salvando…' : 'Salvar'}
        </button>
      </div>
    </form>
  )
}

function texto(centavos: number | null) {
  return centavos ? (centavos / 100).toLocaleString('pt-BR', { minimumFractionDigits: 2 }) : ''
}

/** Cria ou, com `e`, edita um empréstimo. `inicial` preenche um novo (vindo do extrato, por exemplo). */
export function FormEmprestimo({
  direcao,
  e,
  inicial,
  aoSalvar,
  aoCancelar,
}: {
  direcao: Aba
  e?: Emprestimo
  inicial?: Partial<Emprestimo>
  aoSalvar: (salvo: Emprestimo) => void
  aoCancelar: () => void
}) {
  const devo = direcao === 'devo'
  const base = e ?? inicial
  const [nome, setNome] = useState(base?.nome ?? '')
  const [instituicao, setInstituicao] = useState(base?.instituicao ?? '')
  const [valor, setValor] = useState(texto(base?.valor_total ?? null))
  const [parcela, setParcela] = useState(texto(base?.parcela_valor ?? null))
  const [parcelas, setParcelas] = useState(e?.parcelas_total ? String(e.parcelas_total) : '')
  const [jurosMes, setJurosMes] = useState(e?.juros_mensal ? e.juros_mensal.replace('.', ',') : '')
  const [dia, setDia] = useState(base?.dia_vencimento ? String(base.dia_vencimento) : '')
  const [data, setData] = useState(() => e?.data ?? isoData(new Date()))
  const [prazo, setPrazo] = useState(e?.prazo ?? '')
  // Vazio segue a conta das parcelas vencidas; um número digitado vale no lugar dela.
  const [jaPagas, setJaPagas] = useState('')

  const vencidas = parcelasVencidas(data, dia ? Number(dia) : null, Number(parcelas) || 0)
  const pagasNaCriacao = jaPagas === '' ? vencidas : Math.min(Number(jaPagas) || 0, Number(parcelas) || 0)
  const mostraJaPagas = devo && !e && Boolean(parcela) && Number(parcelas) > 0

  const { erro, enviando, enviar } = useEnvio(async () => {
    const total = paraCentavos(valor)
    if (total <= 0) throw new Error('Informe um valor maior que zero.')
    const corpo = {
      direcao,
      nome,
      data,
      valor_total: total,
      ...(devo
        ? {
            instituicao,
            parcela_valor: parcela ? paraCentavos(parcela) : null,
            parcelas_total: parcelas ? Number(parcelas) : null,
            juros_mensal: jurosMes ? jurosMes.replace(',', '.') : null,
            dia_vencimento: dia ? Number(dia) : null,
          }
        : { prazo: prazo || null }),
    }
    const salvo = e
      ? await api<Emprestimo>(`/emprestimos/${e.id}/`, { method: 'PATCH', body: corpo })
      : await api<Emprestimo>('/emprestimos/', { method: 'POST', body: { ...corpo, ...(mostraJaPagas ? { parcelas_ja_pagas: pagasNaCriacao } : {}) } })
    aoSalvar(salvo)
  })

  return (
    <form onSubmit={enviar} className={`flex flex-col gap-4 ${inicial ? '' : 'mt-2 border-t border-linha pt-5'}`}>
      <h2 className="font-display text-[21px] font-bold">{e ? `Editar ${e.nome}` : devo ? 'Novo empréstimo' : 'Quem te deve'}</h2>
      <Campo label={devo ? 'Nome do empréstimo' : 'Pessoa'}>
        <input
          required
          value={nome}
          onChange={(ev) => setNome(ev.target.value)}
          placeholder={devo ? 'Ex.: Financiamento do carro' : 'Ex.: João'}
          className={campo}
        />
      </Campo>
      {devo && (
        <Campo label="Banco ou instituição">
          <input value={instituicao} onChange={(ev) => setInstituicao(ev.target.value)} className={campo} />
        </Campo>
      )}
      <div className="grid grid-cols-2 gap-3">
        <Campo label={devo ? 'Total a pagar' : 'Valor emprestado'}>
          <input required inputMode="decimal" value={valor} onChange={(ev) => setValor(ev.target.value)} placeholder="0,00" className={`${campo} tabular-nums`} />
        </Campo>
        <Campo label={devo ? 'Contratado em' : 'Emprestou em'}>
          <input type="date" required value={data} onChange={(ev) => setData(ev.target.value)} className={campo} />
        </Campo>
      </div>
      {devo ? (
        <>
          <div className="grid grid-cols-2 gap-3">
            <Campo label="Valor da parcela">
              <input inputMode="decimal" value={parcela} onChange={(ev) => setParcela(ev.target.value)} placeholder="0,00" className={`${campo} tabular-nums`} />
            </Campo>
            <Campo label="Número de parcelas">
              <input type="number" min={1} value={parcelas} onChange={(ev) => setParcelas(ev.target.value)} className={campo} />
            </Campo>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Campo label="Juros ao mês (%)">
              <input inputMode="decimal" value={jurosMes} onChange={(ev) => setJurosMes(ev.target.value)} placeholder="2,1" className={campo} />
            </Campo>
            <Campo label="Vence no dia">
              <input type="number" min={1} max={28} value={dia} onChange={(ev) => setDia(ev.target.value)} className={campo} />
            </Campo>
          </div>
          {mostraJaPagas && (
            <div className="flex flex-col gap-1.5">
              <Campo label="Parcelas já pagas">
                <input
                  type="number"
                  min={0}
                  max={Number(parcelas)}
                  value={jaPagas === '' ? String(vencidas) : jaPagas}
                  onChange={(ev) => setJaPagas(ev.target.value)}
                  className={campo}
                />
              </Campo>
              <p className="text-sm text-suave">
                {vencidas === 0
                  ? 'Nenhuma parcela venceu até hoje.'
                  : `${vencidas} ${vencidas === 1 ? 'parcela venceu' : 'parcelas venceram'} até hoje e entram como pagas. Se alguma está atrasada, diminua o número.`}
              </p>
            </div>
          )}
          {e && <p className="text-sm text-suave">Os pagamentos já registrados não mudam. Para corrigir um, use Ver pagamentos.</p>}
        </>
      ) : (
        <Campo label="Combinado para devolver em">
          <input type="date" value={prazo} min={data} onChange={(ev) => setPrazo(ev.target.value)} className={campo} />
        </Campo>
      )}
      {erro && <Erro>{erro}</Erro>}
      <div className="flex gap-2.5">
        <button type="button" onClick={aoCancelar} className={`${botaoSecundario} flex-1`}>
          Cancelar
        </button>
        <button type="submit" disabled={enviando} className={`${botaoPrimario} flex-1 disabled:opacity-60`}>
          {enviando ? 'Salvando…' : 'Salvar'}
        </button>
      </div>
    </form>
  )
}
