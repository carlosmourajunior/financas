import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { aoSair, api, lerTokens, salvarTokens } from './api'
import type { Usuario } from './tipos'

interface Auth {
  usuario: Usuario | null
  carregando: boolean
  entrar: (email: string, senha: string) => Promise<void>
  cadastrar: (nome: string, email: string, senha: string) => Promise<void>
  sair: () => void
}

const Contexto = createContext<Auth | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [usuario, setUsuario] = useState<Usuario | null>(null)
  const [carregando, setCarregando] = useState(() => lerTokens() !== null)

  const sair = useCallback(() => {
    salvarTokens(null)
    setUsuario(null)
  }, [])

  useEffect(() => {
    aoSair(() => setUsuario(null))
    if (!lerTokens()) return
    api<Usuario>('/auth/eu/')
      .then(setUsuario)
      .catch(() => salvarTokens(null))
      .finally(() => setCarregando(false))
  }, [])

  const entrar = useCallback(async (email: string, senha: string) => {
    const tokens = await api<{ access: string; refresh: string }>('/auth/token/', {
      method: 'POST',
      body: { email: email.trim().toLowerCase(), password: senha },
      auth: false,
    })
    salvarTokens(tokens)
    setUsuario(await api<Usuario>('/auth/eu/'))
  }, [])

  const cadastrar = useCallback(async (nome: string, email: string, senha: string) => {
    const r = await api<{ usuario: Usuario; access: string; refresh: string }>('/auth/cadastro/', {
      method: 'POST',
      body: { nome, email, senha },
      auth: false,
    })
    salvarTokens({ access: r.access, refresh: r.refresh })
    setUsuario(r.usuario)
  }, [])

  const valor = useMemo(() => ({ usuario, carregando, entrar, cadastrar, sair }), [usuario, carregando, entrar, cadastrar, sair])
  return <Contexto.Provider value={valor}>{children}</Contexto.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth() {
  const ctx = useContext(Contexto)
  if (!ctx) throw new Error('useAuth precisa estar dentro do AuthProvider')
  return ctx
}
