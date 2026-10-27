import { useCallback, useEffect, useState } from 'react'
import { api } from './api'

/** Busca um caminho da API e expõe dados, erro e um recarregar. */
export function useApi<T>(caminho: string | null) {
  const [dados, setDados] = useState<T | null>(null)
  const [erro, setErro] = useState<string | null>(null)
  const [carregando, setCarregando] = useState(Boolean(caminho))
  const [versao, setVersao] = useState(0)

  useEffect(() => {
    if (!caminho) return
    let ativo = true
    setCarregando(true)
    api<T>(caminho)
      .then((d) => {
        if (ativo) {
          setDados(d)
          setErro(null)
        }
      })
      .catch((e: Error) => ativo && setErro(e.message))
      .finally(() => ativo && setCarregando(false))
    return () => {
      ativo = false
    }
  }, [caminho, versao])

  const recarregar = useCallback(() => setVersao((v) => v + 1), [])
  return { dados, erro, carregando, recarregar }
}
