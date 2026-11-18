import { useState } from 'react'
import { EscolherCor, NovaCategoria, PontoCor } from '../components/Categorias'
import { Abas, Titulo, botaoSecundario } from '../components/ui'
import { api } from '../lib/api'
import { useCadastros } from '../lib/cadastros'
import type { Categoria, Natureza } from '../lib/tipos'

export default function Categorias() {
  const cad = useCadastros()
  const [natureza, setNatureza] = useState<Natureza>('despesa')
  const [criando, setCriando] = useState(false)
  const lista = cad.categorias.filter((c) => c.natureza === natureza)

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-4 px-5 pt-5 lg:px-8 lg:pt-7">
      <Titulo>Categorias</Titulo>
      <p className="text-[15px] text-suave">A cor de cada categoria aparece nos lançamentos, nas faturas e no gráfico do Início.</p>

      <Abas
        rotulo="Tipo de categoria"
        opcoes={[
          { id: 'despesa', label: 'Gastos' },
          { id: 'receita', label: 'Recebimentos' },
        ]}
        valor={natureza}
        onChange={(n) => {
          setNatureza(n)
          setCriando(false)
        }}
      />

      {criando ? (
        <NovaCategoria
          key={natureza}
          natureza={natureza}
          categorias={cad.categorias}
          aoCancelar={() => setCriando(false)}
          aoCriar={() => {
            setCriando(false)
            cad.recarregarCategorias()
          }}
        />
      ) : (
        <button type="button" onClick={() => setCriando(true)} className={`${botaoSecundario} self-start`}>
          + Nova categoria
        </button>
      )}

      <div className="flex flex-col">
        {cad.carregando && !cad.categorias.length && <p className="py-8 text-center text-suave">Carregando…</p>}
        {!cad.carregando && lista.length === 0 && <p className="py-8 text-center text-suave">Nenhuma categoria ainda.</p>}
        {lista.map((c) => (
          <LinhaCategoria key={c.id} c={c} aoMudar={cad.recarregarCategorias} />
        ))}
      </div>
    </div>
  )
}

function LinhaCategoria({ c, aoMudar }: { c: Categoria; aoMudar: () => void }) {
  const [editando, setEditando] = useState(false)
  const [excluindo, setExcluindo] = useState(false)
  const [nome, setNome] = useState(c.nome)
  const [cor, setCor] = useState(c.cor)
  const [erro, setErro] = useState<string | null>(null)
  const [salvando, setSalvando] = useState(false)

  async function fazer(acao: () => Promise<unknown>) {
    setErro(null)
    setSalvando(true)
    try {
      await acao()
      setEditando(false)
      setExcluindo(false)
      aoMudar()
    } catch (err) {
      setErro((err as Error).message || 'Não foi possível salvar.')
    } finally {
      setSalvando(false)
    }
  }

  if (editando) {
    return (
      <form
        onSubmit={(e) => {
          e.preventDefault()
          fazer(() => api(`/categorias/${c.id}/`, { method: 'PATCH', body: { nome: nome.trim(), cor } }))
        }}
        className="flex flex-col gap-2.5 border-b border-linha py-3"
      >
        <input
          autoFocus
          aria-label="Nome da categoria"
          value={nome}
          onChange={(e) => setNome(e.target.value)}
          className="min-h-11 w-full rounded-lg border border-borda px-3 text-base text-tinta"
        />
        <EscolherCor valor={cor} onChange={setCor} />
        <span className="flex items-center gap-2">
          <button type="submit" disabled={salvando} className="min-h-10 cursor-pointer rounded-lg bg-tinta px-4 text-sm font-bold text-white disabled:opacity-60">
            {salvando ? 'Salvando…' : 'Salvar'}
          </button>
          <button
            type="button"
            onClick={() => {
              setEditando(false)
              setNome(c.nome)
              setCor(c.cor)
              setErro(null)
            }}
            className="min-h-10 cursor-pointer px-2 text-sm font-semibold text-suave"
          >
            Cancelar
          </button>
        </span>
        {erro && <span role="alert" className="text-sm font-semibold text-ambar-texto">{erro}</span>}
      </form>
    )
  }

  return (
    <div className="flex flex-col border-b border-linha py-3">
      <div className="flex items-center gap-3">
        <PontoCor cor={c.cor} tamanho="size-4" />
        <span className="grow text-base font-bold">{c.nome}</span>
        {!excluindo && (
          <>
            <button type="button" onClick={() => setEditando(true)} className="min-h-10 cursor-pointer px-2 text-sm font-semibold text-tinta underline underline-offset-2">
              Editar
            </button>
            <button type="button" onClick={() => setExcluindo(true)} className="min-h-10 cursor-pointer px-2 text-sm font-semibold text-suave underline underline-offset-2">
              Excluir
            </button>
          </>
        )}
      </div>
      {excluindo && (
        <div className="flex flex-wrap items-center gap-2 pl-7 pt-1.5 text-sm">
          <span className="text-suave">Os lançamentos dela ficam sem categoria.</span>
          <button
            type="button"
            disabled={salvando}
            onClick={() => fazer(() => api(`/categorias/${c.id}/`, { method: 'DELETE' }))}
            className="min-h-9 cursor-pointer rounded-lg bg-debito px-3 font-bold text-white disabled:opacity-60"
          >
            Excluir
          </button>
          <button type="button" onClick={() => setExcluindo(false)} className="min-h-9 cursor-pointer px-2 font-semibold text-suave">
            Manter
          </button>
        </div>
      )}
      {erro && !editando && <span role="alert" className="pl-7 text-sm font-semibold text-ambar-texto">{erro}</span>}
    </div>
  )
}
