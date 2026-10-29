import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { DIAS, lerData } from '../lib/datas'

/** Linha de lista com o dia em destaque à esquerda, para ver de relance quando cada coisa vence. */
export default function LinhaComData({
  data,
  titulo,
  detalhe,
  situacao,
  alerta = false,
  valor,
  valorClasse = '',
  extra,
  para,
  acao,
}: {
  data: string
  titulo: string
  detalhe?: string
  situacao?: string
  alerta?: boolean
  valor: string
  valorClasse?: string
  extra?: ReactNode
  para?: string
  /** Botão abaixo do texto, como "Marcar como pago". Fica fora do link. */
  acao?: ReactNode
}) {
  const d = lerData(data)
  const conteudo = (
    <>
      <span className="flex w-11 shrink-0 flex-col items-center pt-0.5" aria-label={`dia ${d.getDate()}`}>
        <span className="font-display text-[22px] font-bold leading-none tabular-nums">{d.getDate()}</span>
        <span className="pt-1 text-xs text-suave">{DIAS[d.getDay()].slice(0, 3)}</span>
      </span>
      <span className="flex min-w-0 grow flex-col gap-0.5">
        <span className="text-base font-bold">{titulo}</span>
        {detalhe && <span className="text-sm text-suave">{detalhe}</span>}
        {situacao && <span className={`text-sm font-semibold ${alerta ? 'text-ambar-texto' : 'text-suave'}`}>{situacao}</span>}
      </span>
      <span className="flex flex-col items-end gap-0.5">
        <span className={`text-base font-bold tabular-nums ${valorClasse}`}>{valor}</span>
        {extra}
      </span>
    </>
  )
  const classe = 'flex items-start gap-3 py-3 text-tinta'
  return (
    <div className="border-b border-linha">
      {para ? (
        <Link to={para} className={`${classe} hover:bg-nevoa/50`}>
          {conteudo}
        </Link>
      ) : (
        <div className={classe}>{conteudo}</div>
      )}
      {acao && <div className="-mt-2 pb-2.5 pl-14">{acao}</div>}
    </div>
  )
}
