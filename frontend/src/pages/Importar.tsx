import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import Icon from '../components/Icon'
import { Abas, Campo, Secao, Titulo, botaoPrimario, campo } from '../components/ui'
import { importacaoExemplo } from '../data/mock'
import { moeda } from '../lib/format'

type Fonte = keyof typeof importacaoExemplo

export default function Importar() {
  const navigate = useNavigate()
  const [fonte, setFonte] = useState<Fonte>('fatura')
  const dados = importacaoExemplo[fonte]
  const [desmarcados, setDesmarcados] = useState<Record<Fonte, Set<number>>>({
    fatura: new Set(importacaoExemplo.fatura.linhas.filter((l) => l.duplicado).map((l) => l.id)),
    extrato: new Set(importacaoExemplo.extrato.linhas.filter((l) => l.duplicado).map((l) => l.id)),
  })
  const fora = desmarcados[fonte]
  const totalEncontrado = 23
  const aImportar = totalEncontrado - fora.size

  function alternar(id: number) {
    const novo = new Set(fora)
    if (novo.has(id)) novo.delete(id)
    else novo.add(id)
    setDesmarcados({ ...desmarcados, [fonte]: novo })
  }

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4 px-5 pt-5 lg:px-8 lg:pt-7">
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
      <Campo label={fonte === 'fatura' ? 'Cartão' : 'Conta'}>
        <select className={campo}>
          <option>{dados.destino}</option>
        </select>
      </Campo>
      <label className="relative flex cursor-pointer items-center gap-3.5 rounded-[14px] border-2 border-dashed border-[#9aaaa7] bg-white px-4 py-5 focus-within:outline-2 focus-within:outline-tinta">
        <Icon name="arquivo" size={28} />
        <span className="flex flex-col gap-0.5">
          <span className="text-base font-bold">Escolher arquivo</span>
          <span className="text-sm text-suave">{dados.formatos}</span>
        </span>
        <input type="file" accept=".pdf,.csv,.ofx" className="sr-only" />
      </label>

      <div className="flex flex-col gap-6 pt-3">
        <Secao titulo="Revise antes de importar">
          <p className="pb-2 text-[15px] leading-relaxed text-suave">
            Lemos {dados.arquivo} e encontramos {totalEncontrado} lançamentos. Os que parecem repetidos ficaram desmarcados.
          </p>
          {dados.linhas.map((l) => (
            <label key={l.id} className="flex cursor-pointer items-start gap-3 border-b border-linha py-3">
              <input type="checkbox" checked={!fora.has(l.id)} onChange={() => alternar(l.id)} className="mt-0.5 size-5 shrink-0 accent-tinta" />
              <span className="flex min-w-0 grow flex-col gap-0.5">
                <span className="text-base font-bold">{l.nome}</span>
                <span className="text-sm text-suave">
                  {l.data}, {l.cat}
                </span>
                {l.duplicado && <span className="text-sm font-semibold text-ambar-texto">Parece repetido: já existe igual em {l.data}</span>}
                {l.parcela && <span className="text-sm font-semibold text-musgo">Ligado a {l.parcela}</span>}
              </span>
              <span className="text-base font-bold tabular-nums">{l.cat === 'Receita' ? `+ ${moeda(l.valor)}` : moeda(l.valor)}</span>
            </label>
          ))}
          <button className="cursor-pointer py-3.5 text-left text-[15px] font-bold">Ver os {totalEncontrado} lançamentos</button>
        </Secao>

        <button className={botaoPrimario} onClick={() => navigate('/lancamentos')}>
          Importar {aImportar} lançamentos
        </button>

        <div className="flex items-center gap-3 border-t border-linha py-3.5 text-suave">
          <Icon name="camera" />
          <span className="text-[15px]">Em breve: fotografar um comprovante de pagamento</span>
        </div>
      </div>
    </div>
  )
}
