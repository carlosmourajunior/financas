// Open Finance pela Pluggy: estado do módulo e formatos da API.
import { useApi } from './useApi'

export interface ContaPluggy {
  id: string
  tipo: 'BANK' | 'CREDIT'
  nome: string
  numero: string
  saldo: number
  conta: number | null
  cartao: number | null
}

export interface EstadoOpenFinance {
  ativo: boolean
  contas: ContaPluggy[]
}

export interface FaturaPluggy {
  id: string
  vence: string
  total: number
}

export type Origem = 'arquivo' | 'banco'

/** Se o Open Finance está ligado. Falha na consulta conta como desligado: a importação por arquivo continua. */
export function useOpenFinance() {
  const r = useApi<EstadoOpenFinance>('/openfinance/')
  return { ativo: Boolean(r.dados?.ativo), contas: r.dados?.contas ?? [], erro: r.erro }
}
