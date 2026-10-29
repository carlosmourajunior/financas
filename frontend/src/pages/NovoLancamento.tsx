import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { Erro } from '../components/Formularios'
import Icon from '../components/Icon'
import { Abas, Campo, botaoPrimario, campo } from '../components/ui'
import { api } from '../lib/api'
import { nomeCartao, useCadastros } from '../lib/cadastros'
import { MESES, isoData, lerData } from '../lib/datas'
import { moeda, paraCentavos } from '../lib/format'
import type { Natureza, Tipo } from '../lib/tipos'
import { useEnvio } from '../lib/useEnvio'

const tipos: { id: Tipo; label: string; desc: string }[] = [
  { id: 'unica', label: 'Única', desc: 'Acontece uma vez só' },
  { id: 'parcelada', label: 'Parcelada', desc: 'Dividida em parcelas mensais' },
  { id: 'recorrente', label: 'Recorrente', desc: 'Se repete, como aluguel ou salário' },
]

type Frequencia = 'mensal' | 'semanal' | 'anual'

export default function NovoLancamento() {
  const navigate = useNavigate()
  const cad = useCadastros()
  const [busca] = useSearchParams()
  const [natureza, setNatureza] = useState<Natureza>(busca.get('natureza') === 'receita' ? 'receita' : 'despesa')
  const [tipo, setTipo] = useState<Tipo>('unica')
  const [valor, setValor] = useState('')
  const [parcelas, setParcelas] = useState(2)
  const [frequencia, setFrequencia] = useState<Frequencia>('mensal')
  const [fim, setFim] = useState('')
  const [temFim, setTemFim] = useState(false)
  const [descricao, setDescricao] = useState('')
  const [categoria, setCategoria] = useState('')
  const [data, setData] = useState(() => isoData(new Date()))
  // "conta:3" ou "cartao:5"; vazio usa a primeira conta.
  const [meio, setMeio] = useState('')
  // Sem escolha, o que tem data até hoje já foi pago; o que é para depois fica em aberto.
  const [jaPago, setJaPago] = useState<boolean | null>(null)

  const total = paraCentavos(valor)
  const porParcela = parcelas > 0 ? Math.round(total / parcelas) : 0
  const d = lerData(data)
  const ultima = new Date(d.getFullYear(), d.getMonth() + parcelas - 1, 1)
  const categorias = cad.categorias.filter((c) => c.natureza === natureza)
  const meioEscolhido = meio || (cad.contas[0] ? `conta:${cad.contas[0].id}` : '')
  const pago = jaPago ?? data <= isoData(new Date())
  // Compra no cartão é paga na fatura. Parcelas e recorrentes seguem a data: as que já passaram contam como pagas.
  const perguntaPago = tipo === 'unica' && meioEscolhido.startsWith('conta')

  // Diz em palavras até quando a recorrência vai, para não terminar sem querer.
  const vezes = temFim && fim && frequencia === 'mensal' ? contarMeses(data, fim) : null
  const resumoRecorrencia = !temFim || !fim
    ? 'Sem data final: entra em todos os meses até você excluir'
    : vezes !== null
      ? `Entra ${vezes === 1 ? 'só uma vez' : `${vezes} vezes`}, de ${mesDe(data)} a ${mesDe(fim)}`
      : `Entra até ${mesDe(fim)}`

  const { erro, enviando, enviar } = useEnvio(async () => {
    if (total <= 0) throw new Error('Informe um valor maior que zero.')
    const [qual, id] = meioEscolhido.split(':')
    await api('/lancamentos/', {
      method: 'POST',
      body: {
        descricao,
        valor: total,
        natureza,
        data,
        tipo,
        categoria: categoria ? Number(categoria) : null,
        conta: qual === 'conta' ? Number(id) : null,
        cartao: qual === 'cartao' ? Number(id) : null,
        ...(perguntaPago ? { pago } : {}),
        ...(tipo === 'parcelada' ? { parcelas } : {}),
        ...(tipo === 'recorrente' ? { frequencia, fim: temFim && fim ? fim : null } : {}),
      },
    })
    navigate('/lancamentos')
  })

  function mudarNatureza(n: Natureza) {
    setNatureza(n)
    setCategoria('')
    // Receita não entra em cartão.
    if (n === 'receita' && meio.startsWith('cartao')) setMeio('')
  }

  return (
    <form onSubmit={enviar} className="mx-auto flex min-h-dvh max-w-xl flex-col bg-fundo">
      <div className="flex items-center justify-between px-2 pt-3">
        <Link to="/" aria-label="Fechar" className="flex size-11 items-center justify-center">
          <Icon name="fechar" strokeWidth={2} />
        </Link>
        <Abas
          rotulo="Natureza"
          opcoes={[
            { id: 'despesa', label: 'Despesa' },
            { id: 'receita', label: 'Receita' },
          ]}
          valor={natureza}
          onChange={mudarNatureza}
        />
        <span className="w-11" />
      </div>

      <div className="flex flex-col gap-5 px-5 py-5">
        <label className="flex flex-col gap-1 text-[15px] text-suave">
          {tipo === 'parcelada' ? 'Valor total da compra' : 'Valor'}
          <span className="flex items-baseline gap-2 font-display text-5xl font-extrabold tracking-tight text-tinta">
            R$
            <input
              required
              inputMode="decimal"
              placeholder="0,00"
              value={valor}
              onChange={(e) => setValor(e.target.value)}
              className="w-full min-w-0 bg-transparent tabular-nums outline-none"
            />
          </span>
        </label>

        <fieldset className="flex flex-col">
          <legend className="pb-1.5 text-[15px] font-bold">Tipo de lançamento</legend>
          {tipos.map((t) => (
            <label key={t.id} className="flex min-h-[60px] cursor-pointer items-center gap-3 border-b border-linha py-2">
              <input
                type="radio"
                name="tipo"
                checked={tipo === t.id}
                onChange={() => setTipo(t.id)}
                className="size-5 shrink-0 accent-tinta"
              />
              <span className="flex flex-col">
                <span className={`text-base ${tipo === t.id ? 'font-bold' : 'font-semibold'}`}>{t.label}</span>
                <span className="text-sm text-suave">{t.desc}</span>
              </span>
            </label>
          ))}
        </fieldset>

        {tipo === 'parcelada' && (
          <div className="flex flex-col gap-2.5 rounded-[14px] bg-nevoa p-4">
            <div className="grid grid-cols-2 gap-3">
              <Campo label="Parcelas">
                <input
                  type="number"
                  min={2}
                  max={72}
                  value={parcelas}
                  onChange={(e) => setParcelas(Number(e.target.value))}
                  className={`${campo} min-h-12 font-bold`}
                />
              </Campo>
            </div>
            <p className="text-[15px]">
              {parcelas} parcelas de <strong>{moeda(porParcela)}</strong>, a última em {MESES[ultima.getMonth()]} de {ultima.getFullYear()}
            </p>
          </div>
        )}

        {tipo === 'recorrente' && (
          <div className="flex flex-col gap-2.5 rounded-[14px] bg-nevoa p-4">
            <Campo label="Repete">
              <select value={frequencia} onChange={(e) => setFrequencia(e.target.value as Frequencia)} className={`${campo} min-h-12`}>
                <option value="mensal">Todo mês</option>
                <option value="semanal">Toda semana</option>
                <option value="anual">Todo ano</option>
              </select>
            </Campo>
            <label className="flex min-h-11 cursor-pointer items-center gap-3 text-base font-semibold">
              <input
                type="checkbox"
                checked={temFim}
                onChange={(e) => {
                  setTemFim(e.target.checked)
                  if (!e.target.checked) setFim('')
                }}
                className="size-5 shrink-0 cursor-pointer accent-tinta"
              />
              Tem data para terminar
            </label>
            {temFim && (
              <Campo label="Última vez em">
                <input type="date" required value={fim} min={data} onChange={(e) => setFim(e.target.value)} className={`${campo} min-h-12`} />
              </Campo>
            )}
            <p className="text-[15px]">{resumoRecorrencia}</p>
          </div>
        )}

        <Campo label="Descrição">
          <input
            required
            value={descricao}
            onChange={(e) => setDescricao(e.target.value)}
            placeholder={natureza === 'despesa' ? 'Ex.: Mercado' : 'Ex.: Salário'}
            className={campo}
          />
        </Campo>
        <div className="grid grid-cols-2 gap-3">
          <Campo label="Categoria">
            <select value={categoria} onChange={(e) => setCategoria(e.target.value)} className={campo}>
              <option value="">Sem categoria</option>
              {categorias.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.nome}
                </option>
              ))}
            </select>
          </Campo>
          <Campo label={tipo === 'parcelada' ? 'Primeira parcela' : tipo === 'recorrente' ? 'Começa em' : 'Data'}>
            <input type="date" required value={data} onChange={(e) => setData(e.target.value)} className={campo} />
          </Campo>
        </div>
        <Campo label={natureza === 'despesa' ? 'Pago com' : 'Recebido em'}>
          <select value={meioEscolhido} onChange={(e) => setMeio(e.target.value)} className={campo}>
            {natureza === 'despesa' &&
              cad.cartoes.map((c) => (
                <option key={`cartao:${c.id}`} value={`cartao:${c.id}`}>
                  {nomeCartao(c)}
                </option>
              ))}
            {cad.contas.map((c) => (
              <option key={`conta:${c.id}`} value={`conta:${c.id}`}>
                {c.nome}
              </option>
            ))}
          </select>
        </Campo>
        {perguntaPago && (
          <label className="flex min-h-11 cursor-pointer items-center gap-3 text-base font-semibold">
            <input type="checkbox" checked={pago} onChange={(e) => setJaPago(e.target.checked)} className="size-5 shrink-0 cursor-pointer accent-tinta" />
            {natureza === 'despesa' ? 'Já paguei' : 'Já recebi'}
          </label>
        )}
        {!cad.carregando && cad.contas.length === 0 && cad.cartoes.length === 0 && (
          <p className="text-[15px] text-suave">
            Você ainda não tem conta nem cartão. <Link to="/" className="font-bold text-tinta">Cadastre uma conta no Início</Link>.
          </p>
        )}
        {erro && <Erro>{erro}</Erro>}
      </div>

      <div className="sticky bottom-0 mt-auto border-t border-linha bg-white px-5 pb-7 pt-4">
        <button type="submit" disabled={enviando} className={`${botaoPrimario} disabled:opacity-60`}>
          {enviando ? 'Salvando…' : natureza === 'despesa' ? 'Salvar despesa' : 'Salvar receita'}
        </button>
      </div>
    </form>
  )
}

function mesDe(iso: string) {
  const d = lerData(iso)
  return `${MESES[d.getMonth()]} de ${d.getFullYear()}`
}

/** Quantas vezes uma recorrência mensal cai entre o início e a data final. */
function contarMeses(inicio: string, fim: string) {
  const a = lerData(inicio)
  const b = lerData(fim)
  const meses = (b.getFullYear() - a.getFullYear()) * 12 + b.getMonth() - a.getMonth()
  return Math.max(0, meses + (b.getDate() >= a.getDate() ? 1 : 0))
}
