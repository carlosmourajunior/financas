import { useState, type ChangeEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Erro } from '../components/Formularios'
import Icon from '../components/Icon'
import { Abas, Campo, Secao, Titulo, botaoPrimario, campo } from '../components/ui'
import { api } from '../lib/api'
import { nomeCartao, useCadastros } from '../lib/cadastros'
import { diaMes, porExtenso } from '../lib/datas'
import { moeda } from '../lib/format'
import type { ItemImportado, PreviaFatura } from '../lib/tipos'

type Fonte = 'fatura' | 'extrato'

const MOSTRAR = 8

export default function Importar() {
  const navigate = useNavigate()
  const cad = useCadastros()
  const [fonte, setFonte] = useState<Fonte>('fatura')
  const [cartao, setCartao] = useState('')
  const [nomeArquivo, setNomeArquivo] = useState('')
  const [previa, setPrevia] = useState<PreviaFatura | null>(null)
  const [itens, setItens] = useState<ItemImportado[]>([])
  const [todos, setTodos] = useState(false)
  const [erro, setErro] = useState<string | null>(null)
  const [lendo, setLendo] = useState(false)
  const [gravando, setGravando] = useState(false)

  const cartaoEscolhido = cartao || (cad.cartoes[0] ? String(cad.cartoes[0].id) : '')
  const marcados = itens.filter((i) => i.importar)
  const somaMarcados = marcados.reduce((s, i) => s + (i.natureza === 'despesa' ? i.valor : -i.valor), 0)
  const despesas = cad.categorias.filter((c) => c.natureza === 'despesa')

  async function ler(e: ChangeEvent<HTMLInputElement>) {
    const arquivo = e.target.files?.[0]
    e.target.value = ''
    if (!arquivo || !cartaoEscolhido) return
    setErro(null)
    setPrevia(null)
    setNomeArquivo(arquivo.name)
    setLendo(true)
    const corpo = new FormData()
    corpo.append('arquivo', arquivo)
    corpo.append('cartao', cartaoEscolhido)
    try {
      const p = await api<PreviaFatura>('/importar/fatura/', { method: 'POST', body: corpo })
      setPrevia(p)
      setItens(p.itens)
      setTodos(false)
    } catch (err) {
      setErro((err as Error).message || 'Não foi possível ler o arquivo.')
    } finally {
      setLendo(false)
    }
  }

  function mudar(indice: number, mudanca: Partial<ItemImportado>) {
    setItens((lista) => lista.map((i, n) => (n === indice ? { ...i, ...mudanca } : i)))
  }

  async function importar() {
    setErro(null)
    setGravando(true)
    try {
      await api('/importar/fatura/confirmar/', { method: 'POST', body: { cartao: Number(cartaoEscolhido), fecha: previa!.ciclo.fecha, itens: marcados } })
      navigate('/cartoes')
    } catch (err) {
      setErro((err as Error).message || 'Não foi possível importar.')
      setGravando(false)
    }
  }

  const visiveis = todos ? itens : itens.slice(0, MOSTRAR)

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4 px-5 pb-8 pt-5 lg:px-8 lg:pt-7">
      <Titulo>Importar</Titulo>
      <Abas
        rotulo="O que importar"
        opcoes={[
          { id: 'fatura', label: 'Fatura do cartão' },
          { id: 'extrato', label: 'Extrato do banco' },
        ]}
        valor={fonte}
        onChange={setFonte}
      />

      {fonte === 'extrato' ? (
        <p className="rounded-xl bg-nevoa px-4 py-3 text-[15px] text-suave">A leitura de extratos do banco chega na próxima etapa.</p>
      ) : !cad.carregando && cad.cartoes.length === 0 ? (
        <p className="text-[17px] leading-snug text-suave">
          Para importar uma fatura, primeiro{' '}
          <Link to="/cartoes" className="font-bold text-tinta">
            cadastre o cartão
          </Link>
          .
        </p>
      ) : (
        <>
          <Campo label="Cartão">
            <select
              value={cartaoEscolhido}
              onChange={(e) => {
                setCartao(e.target.value)
                setPrevia(null)
              }}
              className={campo}
            >
              {cad.cartoes.map((c) => (
                <option key={c.id} value={c.id}>
                  {nomeCartao(c)}
                </option>
              ))}
            </select>
          </Campo>
          <label className="relative flex cursor-pointer items-center gap-3.5 rounded-[14px] border-2 border-dashed border-[#9aaaa7] bg-white px-4 py-5 focus-within:outline-2 focus-within:outline-tinta">
            <Icon name="arquivo" size={28} />
            <span className="flex flex-col gap-0.5">
              <span className="text-base font-bold">{lendo ? 'Lendo o arquivo…' : nomeArquivo || 'Escolher arquivo'}</span>
              <span className="text-sm text-suave">CSV do Nubank, PDF do Itaú ou CSV do Sicredi</span>
            </span>
            <input type="file" accept=".pdf,.csv" onChange={ler} disabled={lendo} className="sr-only" />
          </label>
        </>
      )}

      {erro && <Erro>{erro}</Erro>}

      {previa && fonte === 'fatura' && (
        <div className="flex flex-col gap-6 pt-3">
          <Secao titulo="Revise antes de importar">
            <Conferencia p={previa} />
            {visiveis.map((l, n) => (
              <div key={n} className="flex items-start gap-3 border-b border-linha py-3">
                <input
                  type="checkbox"
                  aria-label={`Importar ${l.descricao}`}
                  checked={l.importar}
                  onChange={(e) => mudar(n, { importar: e.target.checked })}
                  className="mt-0.5 size-5 shrink-0 cursor-pointer accent-tinta"
                />
                <span className="flex min-w-0 grow flex-col gap-0.5">
                  <span className="text-base font-bold">{l.descricao}</span>
                  <span className="flex flex-wrap items-center gap-x-1 text-sm text-suave">
                    {diaMes(l.data)}
                    {l.natureza === 'despesa' && (
                      <>
                        ,
                        <select
                          aria-label={`Categoria de ${l.descricao}`}
                          value={l.categoria ?? ''}
                          onChange={(e) => mudar(n, { categoria: e.target.value ? Number(e.target.value) : null })}
                          className="-my-1 min-h-8 cursor-pointer rounded-md bg-transparent py-1 text-sm text-suave hover:bg-nevoa"
                        >
                          <option value="">Sem categoria</option>
                          {despesas.map((c) => (
                            <option key={c.id} value={c.id}>
                              {c.nome}
                            </option>
                          ))}
                        </select>
                      </>
                    )}
                    {l.natureza === 'receita' && ', crédito na fatura'}
                  </span>
                  {l.repetido && <span className="text-sm font-semibold text-ambar-texto">Parece repetido: você já lançou igual à mão neste cartão</span>}
                  {l.parcela_total && (
                    <span className="text-sm font-semibold text-musgo">
                      Parcela {l.parcela_atual} de {l.parcela_total}
                      {l.parcela_atual! < l.parcela_total && `, cria as próximas ${l.parcela_total - l.parcela_atual!}`}
                    </span>
                  )}
                  {l.tipo === 'saldo_anterior' && (
                    <span className="text-sm text-suave">O banco cobrou nesta fatura o que ficou da anterior</span>
                  )}
                </span>
                <span className={`text-base font-bold tabular-nums ${l.natureza === 'receita' ? 'text-musgo' : ''}`}>
                  {l.natureza === 'receita' ? `- ${moeda(l.valor)}` : moeda(l.valor)}
                </span>
              </div>
            ))}
            {itens.length > MOSTRAR && (
              <button onClick={() => setTodos(!todos)} className="cursor-pointer py-3.5 text-left text-[15px] font-bold">
                {todos ? 'Mostrar menos' : `Ver os ${itens.length} lançamentos`}
              </button>
            )}
          </Secao>

          <div className="flex flex-col gap-2">
            <p className="text-[15px] text-suave">
              {marcados.length} marcados, somando <strong className="text-tinta">{moeda(somaMarcados)}</strong>
            </p>
            <button onClick={importar} disabled={gravando || marcados.length === 0} className={`${botaoPrimario} disabled:opacity-60`}>
              {gravando ? 'Importando…' : `Importar ${marcados.length} lançamentos`}
            </button>
          </div>
        </div>
      )}

      <div className="flex items-center gap-3 border-t border-linha py-3.5 text-suave">
        <Icon name="camera" />
        <span className="text-[15px]">Em breve: fotografar um comprovante de pagamento</span>
      </div>
    </div>
  )
}

function Conferencia({ p }: { p: PreviaFatura }) {
  const vence = p.vencimento ? ` com vencimento em ${porExtenso(p.vencimento)}` : ''
  return (
    <div className="flex flex-col gap-2 pb-2 text-[15px] leading-relaxed">
      <p className="text-suave">
        Lemos a fatura do {p.banco}
        {vence} e encontramos {p.itens.length} lançamentos. Os iguais a lançamentos que você fez à mão ficaram desmarcados.
      </p>
      {p.conferida === true && (
        <p className="font-semibold text-musgo">Os lançamentos somam {moeda(p.total!)}, o mesmo total da fatura do banco.</p>
      )}
      {p.conferida === false && (
        <p className="font-semibold text-ambar-texto">
          A fatura diz {moeda(p.total!)}, mas as linhas lidas somam {moeda(p.total_lido)}. Confira antes de importar.
        </p>
      )}
      {p.conferida === null && (
        <p className="text-suave">
          Este arquivo não traz o total da fatura. As linhas somam <strong className="text-tinta">{moeda(p.total_lido)}</strong>.
        </p>
      )}
      {!p.final_confere && (
        <p className="font-semibold text-ambar-texto">O arquivo é do cartão final {p.final}, diferente do cartão escolhido.</p>
      )}
      <p className="text-suave">
        Entra na fatura que fecha em {porExtenso(p.ciclo.fecha)} e vence em {porExtenso(p.ciclo.vence)}.
      </p>
      {p.ja_importados > 0 && (
        <p className="font-semibold text-ambar-texto">
          Esta fatura já foi importada. Ao importar de novo, as {p.ja_importados} linhas da importação anterior são substituídas por estas.
        </p>
      )}
    </div>
  )
}
