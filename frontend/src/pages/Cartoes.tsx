import { useState } from 'react'
import { Link } from 'react-router-dom'
import { FormCartao } from '../components/Formularios'
import Icon from '../components/Icon'
import { Abas, Barra, Secao, Segmentos, Titulo, botaoSecundario } from '../components/ui'
import type { Pagina } from '../lib/api'
import { MESES, lerData, maiuscula, porExtenso } from '../lib/datas'
import { moeda, pct } from '../lib/format'
import type { Cartao, DetalheCartao } from '../lib/tipos'
import { useApi } from '../lib/useApi'

function mesAno(iso: string) {
  const d = lerData(iso)
  return `${MESES[d.getMonth()]} de ${d.getFullYear()}`
}

export default function Cartoes() {
  const lista = useApi<Pagina<Cartao>>('/cartoes/?limit=500')
  const cartoes = lista.dados?.results ?? []
  const [sel, setSel] = useState<string>('')
  const [novo, setNovo] = useState(false)
  const c = cartoes.find((x) => String(x.id) === sel) ?? cartoes[0]
  const detalhe = useApi<DetalheCartao>(c ? `/cartoes/${c.id}/detalhe/` : null)

  const titulo = (
    <Titulo
      acoes={
        cartoes.length > 0 && (
          <button
            aria-label={novo ? 'Fechar cadastro de cartão' : 'Adicionar cartão'}
            aria-expanded={novo}
            onClick={() => setNovo(!novo)}
            className="flex size-11 cursor-pointer items-center justify-center rounded-xl border border-borda bg-white"
          >
            <Icon name={novo ? 'fechar' : 'mais'} size={20} strokeWidth={2} />
          </button>
        )
      }
    >
      Cartões
    </Titulo>
  )

  function salvo(cartao: Cartao) {
    setNovo(false)
    setSel(String(cartao.id))
    lista.recarregar()
  }

  if (lista.carregando && !lista.dados) {
    return (
      <div className="mx-auto flex max-w-3xl flex-col gap-3.5 px-5 pt-5 lg:px-8 lg:pt-7">
        {titulo}
        <p className="py-10 text-center text-suave">Carregando…</p>
      </div>
    )
  }

  if (!c || novo) {
    return (
      <div className="mx-auto flex max-w-3xl flex-col gap-3.5 px-5 pt-5 lg:px-8 lg:pt-7">
        {titulo}
        <p className="text-[17px] leading-snug text-suave">
          {c ? 'Novo cartão' : 'Cadastre seu cartão para acompanhar a fatura, o limite e as parcelas que ainda vêm.'}
        </p>
        <div className="max-w-xl">
          <FormCartao aoSalvar={salvo} />
        </div>
      </div>
    )
  }

  const d = detalhe.dados

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-3.5 px-5 pt-5 lg:px-8 lg:pt-7">
      {titulo}
      <Abas
        rotulo="Cartão"
        opcoes={cartoes.map((x) => ({ id: String(x.id), label: x.final ? `${x.nome} ${x.final}` : x.nome }))}
        valor={String(c.id)}
        onChange={setSel}
      />

      {detalhe.erro && <p className="py-10 text-center text-suave">Não foi possível carregar o cartão. {detalhe.erro}</p>}
      {!d && !detalhe.erro && <p className="py-10 text-center text-suave">Carregando…</p>}
      {d && (
        <div className="flex flex-col gap-7 pt-2">
          <section className="flex flex-col gap-3">
            <p className="text-[15px] text-suave">Fatura de {MESES[lerData(d.fatura.vence).getMonth()]}, aberta</p>
            <p className="font-display text-[44px] font-extrabold leading-none tracking-tight tabular-nums">{moeda(d.fatura.total)}</p>
            <p className="text-[15px] text-suave">
              Fecha em {porExtenso(d.fatura.fecha)} e vence em {porExtenso(d.fatura.vence)}
            </p>
            <div className="flex flex-col gap-1.5 pt-1">
              <Barra largura={pct(d.limite - d.disponivel, d.limite)} />
              <p className="text-[15px]">
                Disponível <strong>{moeda(d.disponivel)}</strong> de {moeda(d.limite)}
              </p>
            </div>
            <div className="flex gap-2.5 pt-1">
              <Link
                to="/importar"
                className="flex min-h-[50px] flex-1 items-center justify-center gap-2 rounded-[14px] bg-tinta text-base font-bold text-white"
              >
                <Icon name="importar" size={18} strokeWidth={2} />
                Importar fatura
              </Link>
              <Link to="/lancamentos" className={`${botaoSecundario} flex-1 rounded-[14px]`}>
                Ver compras
              </Link>
            </div>
          </section>

          <Secao titulo="Parcelas em andamento">
            {d.parcelas.length === 0 && <p className="py-2.5 text-[15px] text-suave">Nenhuma compra parcelada neste cartão.</p>}
            {d.parcelas.map((p, i) => (
              <div key={i} className="flex flex-col gap-1.5 border-b border-linha py-3">
                <div className="flex justify-between text-base font-bold">
                  <span>{p.descricao}</span>
                  <span className="tabular-nums">{moeda(p.valor)}</span>
                </div>
                <Segmentos pagas={p.atual} total={p.total} />
                <p className="text-sm text-suave">
                  Parcela {p.atual} de {p.total}, termina em {mesAno(p.termina)}
                </p>
              </div>
            ))}
          </Secao>

          <Secao titulo="Próximas faturas">
            <p className="pb-1.5 text-[15px] text-suave">O que já está garantido por parcelas e assinaturas</p>
            {d.proximas.map((f) => (
              <div key={f.fecha} className="flex justify-between border-b border-linha py-2.5 text-base">
                <span>{maiuscula(MESES[lerData(f.vence).getMonth()])}</span>
                <span className="font-bold tabular-nums">{moeda(f.total)}</span>
              </div>
            ))}
          </Secao>
        </div>
      )}
    </div>
  )
}
