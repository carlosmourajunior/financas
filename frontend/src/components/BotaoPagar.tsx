import { useState } from 'react'

/** Botão pequeno que chama a API e avisa quando terminou; mostra o erro sem sair da linha. */
export default function BotaoPagar({
  rotulo,
  acao,
  aoMudar,
  discreto = false,
}: {
  rotulo: string
  acao: () => Promise<unknown>
  aoMudar: () => void
  discreto?: boolean
}) {
  const [enviando, setEnviando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)

  async function clicar() {
    setErro(null)
    setEnviando(true)
    try {
      await acao()
      aoMudar()
    } catch (err) {
      setErro((err as Error).message || 'Não foi possível salvar.')
    } finally {
      setEnviando(false)
    }
  }

  return (
    <span className="flex flex-wrap items-center gap-2">
      <button
        type="button"
        onClick={clicar}
        disabled={enviando}
        className={
          discreto
            ? 'min-h-7 cursor-pointer text-[13px] font-semibold text-suave underline underline-offset-2 disabled:opacity-60'
            : 'min-h-10 cursor-pointer rounded-[10px] border border-borda bg-white px-3 text-sm font-bold text-tinta disabled:opacity-60'
        }
      >
        {enviando ? 'Salvando…' : rotulo}
      </button>
      {erro && <span className="text-sm font-semibold text-ambar-texto">{erro}</span>}
    </span>
  )
}
