import { useEffect, useState, type ChangeEvent, type ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'
import { Erro, FormConta } from '../components/Formularios'
import { FormEmprestimo } from './Emprestimos'
import Icon from '../components/Icon'
import { Abas, Campo, Secao, botaoPrimario, campo } from '../components/ui'
import { api, type Pagina } from '../lib/api'
import { nomeCartao, useCadastros } from '../lib/cadastros'
import { diaMes, porExtenso } from '../lib/datas'
import { moeda } from '../lib/format'
import type { Categoria, ClasseMovimento, Emprestimo, ExtratoImportado, MovimentoImportado, PreviaExtrato, Tipo } from '../lib/tipos'
import { useApi } from '../lib/useApi'

const CLASSES: { id: ClasseMovimento; label: string }[] = [
  { id: 'despesa', label: 'Conta' },
  { id: 'receita', label: 'Recebimento' },
  { id: 'transferencia', label: 'Transferência' },
  { id: 'fatura', label: 'Fatura de cartão' },
  { id: 'emprestimo', label: 'Empréstimo' },
]

const TIPOS: { id: Tipo; label: string }[] = [
  { id: 'unica', label: 'Único' },
  { id: 'parcelada', label: 'Parcelado' },
  { id: 'recorrente', label: 'Recorrente' },
]

type Filtro = 'todas' | 'despesa' | 'receita' | 'outras'

const NOVA = 'nova'
const GUARDADA = 'importar-extrato'

interface Guardada {
  conta: string
  nomeArquivo: string
  previa: PreviaExtrato
  itens: MovimentoImportado[]
}

/** A revisão em andamento fica no navegador: recarregar a página não perde o que já foi classificado. */
function lerGuardada(): Guardada | null {
  try {
    const t = sessionStorage.getItem(GUARDADA)
    return t ? (JSON.parse(t) as Guardada) : null
  } catch {
    return null
  }
}

function guardar(g: Guardada | null) {
  try {
    if (g) sessionStorage.setItem(GUARDADA, JSON.stringify(g))
    else sessionStorage.removeItem(GUARDADA)
  } catch {
    // Sem armazenamento (aba anônima, cota cheia): segue sem guardar.
  }
}

const miniSelect = '-my-1 min-h-9 max-w-full cursor-pointer rounded-lg border border-linha bg-white px-2 py-1 text-sm text-tinta'

/** O mesmo favorecido escrito igual: o que for escolhido para um vale para os outros ainda não mexidos. */
function mesmo(a: string, b: string) {
  return a.trim().toLowerCase() === b.trim().toLowerCase()
}

export default function ImportarExtrato() {
  const navigate = useNavigate()
  const cad = useCadastros()
  const emprestimos = useApi<Pagina<Emprestimo>>('/emprestimos/?direcao=devo&limit=500')
  const [guardada] = useState(lerGuardada)
  const [conta, setConta] = useState(guardada?.conta ?? '')
  const [nomeArquivo, setNomeArquivo] = useState(guardada?.nomeArquivo ?? '')
  const [previa, setPrevia] = useState<PreviaExtrato | null>(guardada?.previa ?? null)
  const [itens, setItens] = useState<MovimentoImportado[]>(guardada?.itens ?? [])
  const [mexidos, setMexidos] = useState<Set<number>>(new Set())
  const [filtro, setFiltro] = useState<Filtro>('todas')
  const [erro, setErro] = useState<string | null>(null)
  const [lendo, setLendo] = useState(false)
  const [gravando, setGravando] = useState(false)
  const [novaConta, setNovaConta] = useState(false)
  const [novoEmprestimo, setNovoEmprestimo] = useState<number | null>(null)

  const contaEscolhida = conta || (cad.contas[0] ? String(cad.contas[0].id) : '')

  useEffect(() => {
    guardar(previa ? { conta: contaEscolhida, nomeArquivo, previa, itens } : null)
  }, [contaEscolhida, nomeArquivo, previa, itens])
  const marcados = itens.filter((i) => i.importar && i.classe !== 'transferencia')
  const saem = marcados.filter((i) => i.natureza === 'despesa').reduce((s, i) => s + i.valor, 0)
  const entram = marcados.filter((i) => i.natureza === 'receita').reduce((s, i) => s + i.valor, 0)

  async function ler(e: ChangeEvent<HTMLInputElement>) {
    const arquivo = e.target.files?.[0]
    e.target.value = ''
    if (!arquivo || !contaEscolhida) return
    setErro(null)
    setPrevia(null)
    setNomeArquivo(arquivo.name)
    setLendo(true)
    const corpo = new FormData()
    corpo.append('arquivo', arquivo)
    corpo.append('conta', contaEscolhida)
    try {
      const p = await api<PreviaExtrato>('/importar/extrato/', { method: 'POST', body: corpo })
      setConta(contaEscolhida)
      setPrevia(p)
      setItens(p.itens)
      setMexidos(new Set())
    } catch (err) {
      setErro((err as Error).message || 'Não foi possível ler o arquivo.')
    } finally {
      setLendo(false)
    }
  }

  /** Muda a linha e, para categoria e classe, as outras do mesmo favorecido que ainda não foram mexidas. */
  function mudar(indice: number, mudanca: Partial<MovimentoImportado>, espalhar = false) {
    setItens((lista) => {
      const alvo = lista[indice]
      return lista.map((i, n) => {
        if (n === indice) return { ...i, ...mudanca }
        if (espalhar && !mexidos.has(n) && i.natureza === alvo.natureza && mesmo(i.descricao, alvo.descricao) && !i.aviso.startsWith('Já')) {
          return { ...i, ...mudanca }
        }
        return i
      })
    })
    setMexidos((m) => new Set(m).add(indice))
  }

  async function importar() {
    setErro(null)
    setGravando(true)
    try {
      const r = await api<ExtratoImportado>('/importar/extrato/confirmar/', {
        method: 'POST',
        body: { conta: Number(contaEscolhida), itens: itens.filter((i) => i.importar) },
      })
      guardar(null)
      navigate('/lancamentos', { state: { importado: r } })
    } catch (err) {
      setErro((err as Error).message || 'Não foi possível importar.')
      setGravando(false)
    }
  }

  const visiveis = itens
    .map((item, indice) => ({ item, indice }))
    .filter(({ item }) =>
      filtro === 'todas' ? true : filtro === 'outras' ? !['despesa', 'receita'].includes(item.classe) : item.classe === filtro,
    )
  const quantos = (c: Filtro) =>
    itens.filter((i) => (c === 'outras' ? !['despesa', 'receita'].includes(i.classe) : i.classe === c)).length

  if (!cad.carregando && (cad.contas.length === 0 || novaConta)) {
    return (
      <div className="flex flex-col gap-3">
        <p className="text-[17px] leading-snug text-suave">Cadastre a conta do banco deste extrato.</p>
        <FormConta
          aoSalvar={(c) => {
            cad.recarregar()
            setConta(String(c.id))
            setNovaConta(false)
          }}
        />
        {novaConta && (
          <button onClick={() => setNovaConta(false)} className="cursor-pointer py-2 text-left text-[15px] font-bold text-suave">
            Cancelar
          </button>
        )}
      </div>
    )
  }

  return (
    <>
      <Campo label="Conta">
        <select
          value={contaEscolhida}
          onChange={(e) => {
            if (e.target.value === NOVA) return setNovaConta(true)
            setConta(e.target.value)
            setPrevia(null)
          }}
          className={campo}
        >
          {cad.contas.map((c) => (
            <option key={c.id} value={c.id}>
              {c.nome}
            </option>
          ))}
          <option value={NOVA}>+ Nova conta</option>
        </select>
      </Campo>
      <label className="relative flex cursor-pointer items-center gap-3.5 rounded-[14px] border-2 border-dashed border-[#9aaaa7] bg-white px-4 py-5 focus-within:outline-2 focus-within:outline-tinta">
        <Icon name="arquivo" size={28} />
        <span className="flex flex-col gap-0.5">
          <span className="text-base font-bold">{lendo ? 'Lendo o arquivo…' : nomeArquivo || 'Escolher arquivo'}</span>
          <span className="text-sm text-suave">CSV do extrato do Banco do Brasil</span>
        </span>
        <input type="file" accept=".csv" onChange={ler} disabled={lendo || !contaEscolhida} className="sr-only" />
      </label>

      {erro && <Erro>{erro}</Erro>}

      {novoEmprestimo !== null && itens[novoEmprestimo] && (
        <Janela titulo="Novo empréstimo" aoFechar={() => setNovoEmprestimo(null)}>
          <FormEmprestimo
            direcao="devo"
            inicial={inicialDoEmprestimo(itens[novoEmprestimo], previa?.banco ?? '')}
            aoCancelar={() => setNovoEmprestimo(null)}
            aoSalvar={(salvo) => {
              emprestimos.recarregar()
              mudar(novoEmprestimo, { classe: 'emprestimo', emprestimo: salvo.id, categoria: null, aviso: '' }, true)
              setNovoEmprestimo(null)
            }}
          />
        </Janela>
      )}

      {previa && (
        <div className="flex flex-col gap-6 pt-3">
          <Secao titulo="Classifique antes de importar">
            <Conferencia p={previa} />
            <Abas
              rotulo="Mostrar"
              opcoes={[
                { id: 'todas', label: `Todas (${itens.length})` },
                { id: 'despesa', label: `Contas (${quantos('despesa')})` },
                { id: 'receita', label: `Recebimentos (${quantos('receita')})` },
                { id: 'outras', label: `Outras (${quantos('outras')})` },
              ]}
              valor={filtro}
              onChange={setFiltro}
            />
            {visiveis.map(({ item, indice }) => (
              <Linha
                key={item.chave}
                l={item}
                categorias={cad.categorias}
                cartoes={cad.cartoes.map((c) => ({ id: c.id, nome: nomeCartao(c) }))}
                emprestimos={emprestimos.dados?.results ?? []}
                mudar={(m, espalhar) => mudar(indice, m, espalhar)}
                aoCriarCategoria={(c) => {
                  cad.recarregar()
                  mudar(indice, { categoria: c.id }, true)
                }}
                aoNovoEmprestimo={() => setNovoEmprestimo(indice)}
              />
            ))}
          </Secao>

          <div className="flex flex-col gap-2">
            <p className="text-[15px] text-suave">
              {marcados.length} para lançar: entram <strong className="text-musgo">{moeda(entram)}</strong> e saem{' '}
              <strong className="text-tinta">{moeda(saem)}</strong>
            </p>
            <button onClick={importar} disabled={gravando || marcados.length === 0} className={`${botaoPrimario} disabled:opacity-60`}>
              {gravando ? 'Importando…' : `Importar ${marcados.length} movimentos`}
            </button>
          </div>
        </div>
      )}
    </>
  )
}

function Linha({
  l,
  categorias,
  cartoes,
  emprestimos,
  mudar,
  aoCriarCategoria,
  aoNovoEmprestimo,
}: {
  l: MovimentoImportado
  categorias: Categoria[]
  cartoes: { id: number; nome: string }[]
  emprestimos: Emprestimo[]
  mudar: (m: Partial<MovimentoImportado>, espalhar?: boolean) => void
  aoCriarCategoria: (c: Categoria) => void
  aoNovoEmprestimo: () => void
}) {
  const [criando, setCriando] = useState(false)
  const lanca = l.classe === 'despesa' || l.classe === 'receita'
  const daNatureza = categorias.filter((c) => c.natureza === l.classe)
  // Uma saída não vira recebimento, nem uma entrada vira conta, fatura ou empréstimo.
  const classes = CLASSES.filter((c) => (l.natureza === 'receita' ? ['receita', 'transferencia'] : ['despesa', 'transferencia', 'fatura', 'emprestimo']).includes(c.id))

  return (
    <div className={`flex items-start gap-3 border-b border-linha py-3 ${l.importar ? '' : 'opacity-70'}`}>
      <input
        type="checkbox"
        aria-label={`Importar ${l.descricao}`}
        checked={l.importar}
        onChange={(e) => mudar({ importar: e.target.checked })}
        className="mt-0.5 size-5 shrink-0 cursor-pointer accent-tinta"
      />
      <span className="flex min-w-0 grow flex-col gap-1.5">
        <span className="flex items-baseline justify-between gap-3">
          <span className="min-w-0 text-base font-bold break-words">{l.descricao}</span>
          <span className={`shrink-0 text-base font-bold tabular-nums ${l.natureza === 'receita' ? 'text-musgo' : ''}`}>
            {l.natureza === 'receita' ? `+ ${moeda(l.valor)}` : moeda(l.valor)}
          </span>
        </span>
        <span className="text-sm text-suave">
          {diaMes(l.data)}, {l.origem}
        </span>
        {l.aviso && <span className="text-sm font-semibold text-ambar-texto">{l.aviso}</span>}
        {l.importar && (
          <span className="flex flex-wrap items-center gap-2 pt-0.5">
            <select
              aria-label={`Lançar ${l.descricao} como`}
              value={l.classe}
              onChange={(e) => {
                const classe = e.target.value as ClasseMovimento
                mudar(
                  {
                    classe,
                    categoria: null,
                    cartao: classe === 'fatura' ? (l.cartao ?? cartoes[0]?.id ?? null) : null,
                    emprestimo: classe === 'emprestimo' ? (l.emprestimo ?? emprestimos[0]?.id ?? null) : null,
                  },
                  true,
                )
              }}
              className={miniSelect}
            >
              {classes.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.label}
                </option>
              ))}
            </select>

            {lanca && (
              <select
                aria-label={`Tipo de ${l.descricao}`}
                value={l.tipo}
                onChange={(e) => {
                  const tipo = e.target.value as Tipo
                  mudar(tipo === 'parcelada' ? { tipo, parcela_atual: l.parcela_atual ?? 1, parcela_total: l.parcela_total ?? 2 } : { tipo })
                }}
                className={miniSelect}
              >
                {TIPOS.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.label}
                  </option>
                ))}
              </select>
            )}

            {lanca && l.tipo === 'parcelada' && (
              <span className="flex items-center gap-1 text-sm text-suave">
                parcela
                <input
                  type="number"
                  min={1}
                  max={99}
                  aria-label="Parcela atual"
                  value={l.parcela_atual ?? 1}
                  onChange={(e) => mudar({ parcela_atual: Number(e.target.value) || 1 })}
                  className="w-14 rounded-lg border border-linha px-2 py-1 text-sm text-tinta"
                />
                de
                <input
                  type="number"
                  min={1}
                  max={99}
                  aria-label="Total de parcelas"
                  value={l.parcela_total ?? 2}
                  onChange={(e) => mudar({ parcela_total: Number(e.target.value) || 1 })}
                  className="w-14 rounded-lg border border-linha px-2 py-1 text-sm text-tinta"
                />
              </span>
            )}

            {lanca && !criando && (
              <select
                aria-label={`Categoria de ${l.descricao}`}
                value={l.categoria ?? ''}
                onChange={(e) => {
                  if (e.target.value === NOVA) setCriando(true)
                  else mudar({ categoria: e.target.value ? Number(e.target.value) : null }, true)
                }}
                className={miniSelect}
              >
                <option value="">Sem categoria</option>
                {daNatureza.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.nome}
                  </option>
                ))}
                <option value={NOVA}>+ Nova categoria</option>
              </select>
            )}

            {lanca && criando && (
              <NovaCategoria
                natureza={l.classe as 'despesa' | 'receita'}
                aoCancelar={() => setCriando(false)}
                aoCriar={(c) => {
                  setCriando(false)
                  aoCriarCategoria(c)
                }}
              />
            )}

            {l.classe === 'fatura' &&
              (cartoes.length ? (
                <select
                  aria-label="Cartão da fatura"
                  value={l.cartao ?? ''}
                  onChange={(e) => mudar({ cartao: Number(e.target.value) })}
                  className={miniSelect}
                >
                  {cartoes.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.nome}
                    </option>
                  ))}
                </select>
              ) : (
                <span className="text-sm text-ambar-texto">Cadastre o cartão antes</span>
              ))}

            {l.classe === 'emprestimo' &&
              (emprestimos.length ? (
                <select
                  aria-label="Empréstimo"
                  value={l.emprestimo ?? ''}
                  onChange={(e) => {
                    if (e.target.value === NOVA) aoNovoEmprestimo()
                    else mudar({ emprestimo: Number(e.target.value) }, true)
                  }}
                  className={miniSelect}
                >
                  {emprestimos.map((e) => (
                    <option key={e.id} value={e.id}>
                      {e.nome}
                    </option>
                  ))}
                  <option value={NOVA}>+ Novo empréstimo</option>
                </select>
              ) : (
                <button type="button" onClick={aoNovoEmprestimo} className="cursor-pointer text-sm font-semibold text-ambar-texto underline">
                  Cadastrar o empréstimo
                </button>
              ))}
          </span>
        )}
        {l.importar && l.classe === 'transferencia' && (
          <span className="text-sm text-suave">Não entra como gasto nem como recebimento</span>
        )}
      </span>
    </div>
  )
}

/** O empréstimo novo já vem com o que a linha do extrato diz: parcela, dia do débito e banco. */
function inicialDoEmprestimo(l: MovimentoImportado, banco: string): Partial<Emprestimo> {
  const dia = Number(l.data.slice(8, 10))
  return {
    nome: l.descricao,
    instituicao: banco,
    parcela_valor: l.valor,
    dia_vencimento: Math.min(dia, 28),
  }
}

/** Janela sobre a tela: cadastrar algo sem sair da importação. */
function Janela({ titulo, aoFechar, children }: { titulo: string; aoFechar: () => void; children: ReactNode }) {
  useEffect(() => {
    const fechar = (e: KeyboardEvent) => e.key === 'Escape' && aoFechar()
    window.addEventListener('keydown', fechar)
    return () => window.removeEventListener('keydown', fechar)
  }, [aoFechar])
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-tinta/40 sm:items-center" onClick={aoFechar}>
      <div
        role="dialog"
        aria-modal="true"
        aria-label={titulo}
        onClick={(e) => e.stopPropagation()}
        className="max-h-[92vh] w-full max-w-lg overflow-y-auto rounded-t-[20px] bg-fundo px-5 py-5 sm:rounded-[20px]"
      >
        {children}
      </div>
    </div>
  )
}

function NovaCategoria({
  natureza,
  aoCriar,
  aoCancelar,
}: {
  natureza: 'despesa' | 'receita'
  aoCriar: (c: Categoria) => void
  aoCancelar: () => void
}) {
  const [nome, setNome] = useState('')
  const [erro, setErro] = useState<string | null>(null)
  const [salvando, setSalvando] = useState(false)

  async function criar() {
    if (!nome.trim()) return
    setSalvando(true)
    setErro(null)
    try {
      aoCriar(await api<Categoria>('/categorias/', { method: 'POST', body: { nome: nome.trim(), natureza } }))
    } catch (err) {
      setErro((err as Error).message || 'Não foi possível criar.')
      setSalvando(false)
    }
  }

  return (
    <span className="flex flex-wrap items-center gap-2">
      <input
        autoFocus
        aria-label="Nome da nova categoria"
        placeholder={natureza === 'receita' ? 'Ex.: Aluguel recebido' : 'Ex.: Escola'}
        value={nome}
        onChange={(e) => setNome(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter') criar()
          if (e.key === 'Escape') aoCancelar()
        }}
        className="min-h-9 w-40 rounded-lg border border-linha px-2 text-sm text-tinta"
      />
      <button onClick={criar} disabled={salvando} className="min-h-9 cursor-pointer rounded-lg bg-tinta px-3 text-sm font-bold text-white">
        Criar
      </button>
      <button onClick={aoCancelar} className="min-h-9 cursor-pointer px-1 text-sm font-semibold text-suave">
        Cancelar
      </button>
      {erro && <span className="w-full text-sm text-ambar-texto">{erro}</span>}
    </span>
  )
}

function Conferencia({ p }: { p: PreviaExtrato }) {
  return (
    <div className="flex flex-col gap-2 pb-2 text-[15px] leading-relaxed">
      <p className="text-suave">
        Lemos o extrato do {p.banco} e encontramos {p.itens.length} movimentos: entraram {moeda(p.entradas)} e saíram {moeda(p.saidas)}.
        Aplicações automáticas e transferências entre contas suas vêm desmarcadas.
      </p>
      {p.conferido === true && p.saldo_final !== null && (
        <p className="font-semibold text-musgo">
          Os movimentos fecham com o saldo do banco: {moeda(p.saldo_final)}
          {p.data_final && ` em ${porExtenso(p.data_final)}`}.
        </p>
      )}
      {p.conferido === false && (
        <p className="font-semibold text-ambar-texto">Os movimentos lidos não fecham com o saldo do extrato. Confira antes de importar.</p>
      )}
    </div>
  )
}
