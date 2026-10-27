import { useState, type FormEvent } from 'react'

/** Envia o formulário e mostra o erro da API, sem perder o que foi digitado. */
export function useEnvio(acao: () => Promise<void>) {
  const [erro, setErro] = useState<string | null>(null)
  const [enviando, setEnviando] = useState(false)
  async function enviar(e: FormEvent) {
    e.preventDefault()
    setErro(null)
    setEnviando(true)
    try {
      await acao()
    } catch (err) {
      setErro((err as Error).message || 'Não foi possível salvar. Tente de novo.')
    } finally {
      setEnviando(false)
    }
  }
  return { erro, enviando, enviar }
}
