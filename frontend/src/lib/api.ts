// Cliente da API: guarda os tokens, renova o acesso quando expira e trata erros.

const BASE = (import.meta.env.VITE_API_URL as string | undefined) ?? 'http://localhost:8000/api'
const CHAVE = 'financas.tokens'

interface Tokens {
  access: string
  refresh: string
}

export class ErroApi extends Error {
  status: number
  dados: unknown

  constructor(status: number, dados: unknown) {
    super(mensagemDeErro(dados) ?? `Erro ${status}`)
    this.status = status
    this.dados = dados
  }
}

/** Junta as mensagens que o DRF devolve ({campo: [msg]} ou {detail: msg}) numa frase. */
function mensagemDeErro(dados: unknown): string | null {
  if (!dados || typeof dados !== 'object') return null
  const partes: string[] = []
  for (const valor of Object.values(dados as Record<string, unknown>)) {
    if (typeof valor === 'string') partes.push(valor)
    else if (Array.isArray(valor)) partes.push(...valor.filter((v): v is string => typeof v === 'string'))
  }
  return partes.length ? partes.join(' ') : null
}

let ouvinteSaida: (() => void) | null = null
export function aoSair(fn: () => void) {
  ouvinteSaida = fn
}

export function lerTokens(): Tokens | null {
  try {
    const bruto = localStorage.getItem(CHAVE)
    return bruto ? (JSON.parse(bruto) as Tokens) : null
  } catch {
    return null
  }
}

export function salvarTokens(t: Tokens | null) {
  try {
    if (t) localStorage.setItem(CHAVE, JSON.stringify(t))
    else localStorage.removeItem(CHAVE)
  } catch {
    // Sem armazenamento (aba anônima bloqueada): a sessão dura até recarregar.
  }
  tokensEmMemoria = t
}

let tokensEmMemoria: Tokens | null = lerTokens()
let renovando: Promise<boolean> | null = null

async function renovar(): Promise<boolean> {
  const refresh = tokensEmMemoria?.refresh
  if (!refresh) return false
  renovando ??= fetch(`${BASE}/auth/token/renovar/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh }),
  })
    .then(async (r) => {
      if (!r.ok) return false
      const { access } = (await r.json()) as { access: string }
      salvarTokens({ access, refresh })
      return true
    })
    .catch(() => false)
    .finally(() => {
      renovando = null
    })
  return renovando
}

export async function api<T>(caminho: string, opcoes: { method?: string; body?: unknown; auth?: boolean } = {}): Promise<T> {
  const { method = 'GET', body, auth = true } = opcoes

  // Arquivos vão como FormData; o navegador monta o Content-Type com o boundary.
  const arquivo = body instanceof FormData
  const chamar = () =>
    fetch(`${BASE}${caminho}`, {
      method,
      headers: {
        ...(body !== undefined && !arquivo ? { 'Content-Type': 'application/json' } : {}),
        ...(auth && tokensEmMemoria ? { Authorization: `Bearer ${tokensEmMemoria.access}` } : {}),
      },
      body: arquivo ? body : body !== undefined ? JSON.stringify(body) : undefined,
    })

  let resposta = await chamar()
  if (resposta.status === 401 && auth) {
    if (await renovar()) {
      resposta = await chamar()
    } else {
      salvarTokens(null)
      ouvinteSaida?.()
    }
  }

  if (resposta.status === 204) return undefined as T
  const dados = await resposta.json().catch(() => null)
  if (!resposta.ok) throw new ErroApi(resposta.status, dados)
  return dados as T
}

export interface Pagina<T> {
  count: number
  results: T[]
}
