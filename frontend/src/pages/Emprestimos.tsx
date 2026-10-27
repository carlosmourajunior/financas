import { useState } from 'react'
import { Erro } from '../components/Formularios'
import { Abas, Barra, Campo, Titulo, botaoPrimario, botaoSecundario, campo } from '../components/ui'
import { api, type Pagina } from '../lib/api'
import { diaMes, isoData, maiuscula } from '../lib/datas'
import { moeda, paraCentavos, pct } from '../lib/format'
import type { Emprestimo } from '../lib/tipos'
import { useApi } from '../lib/useApi'
import { useEnvio } from '../lib/useEnvio'

type Aba = 'devo' | 'devem'

function juros(valor: string | null) {
  if (!valor) return null
  return `juros de ${Number(valor).toLocaleString('pt-BR', { maximumFractionDigits: 3 })}% ao mês`
}

export default function Emprestimos() {
  const [aba, setAba] = useState<Aba>('devo')
  const [novo, setNovo] = useState(false)
  const devo = aba === 'devo'
  const resposta = useApi<Pagina<Emprestimo>>(`/emprestimos/?direcao=${aba}&limit=500`)
  const itens = (resposta.dados?.results ?? []).filter((e) => e.saldo > 0)
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

      {novo ? (
        <NovoEmprestimo
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

function NovoEmprestimo({ direcao, aoSalvar, aoCancelar }: { direcao: Aba; aoSalvar: () => void; aoCancelar: () => void }) {
  const devo = direcao === 'devo'
  const [nome, setNome] = useState('')
  const [instituicao, setInstituicao] = useState('')
  const [valor, setValor] = useState('')
  const [parcela, setParcela] = useState('')
  const [parcelas, setParcelas] = useState('')
  const [jurosMes, setJurosMes] = useState('')
  const [dia, setDia] = useState('')
  const [data, setData] = useState(() => isoData(new Date()))
  const [prazo, setPrazo] = useState('')

  const { erro, enviando, enviar } = useEnvio(async () => {
    const total = paraCentavos(valor)
    if (total <= 0) throw new Error('Informe um valor maior que zero.')
    await api('/emprestimos/', {
      method: 'POST',
      body: {
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
      },
    })
    aoSalvar()
  })

  return (
    <form onSubmit={enviar} className="mt-2 flex flex-col gap-4 border-t border-linha pt-5">
      <h2 className="font-display text-[21px] font-bold">{devo ? 'Novo empréstimo' : 'Quem te deve'}</h2>
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
