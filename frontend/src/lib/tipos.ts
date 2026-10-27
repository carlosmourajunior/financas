// Formatos que a API devolve. Valores em centavos e datas em AAAA-MM-DD.

export type Natureza = 'despesa' | 'receita'
export type Tipo = 'unica' | 'parcelada' | 'recorrente'

export interface Usuario {
  id: number
  nome: string
  email: string
}

export interface Conta {
  id: number
  nome: string
  tipo: 'corrente' | 'poupanca' | 'dinheiro'
  saldo_inicial: number
}

export interface Cartao {
  id: number
  nome: string
  final: string
  limite: number
  dia_fechamento: number
  dia_vencimento: number
}

export interface Categoria {
  id: number
  nome: string
  natureza: Natureza
}

export interface Lancamento {
  id: number
  descricao: string
  valor: number
  natureza: Natureza
  data: string
  categoria: number | null
  conta: number | null
  cartao: number | null
  tipo: Tipo
  pago: boolean
  parcela_atual: number | null
  parcela_total: number | null
}

export interface ContaDoMes {
  dia: number
  nome: string
  valor: number
  paga: boolean
}

export interface Resumo {
  hoje: string
  saldo_em_conta: number
  a_vencer: number
  livre_para_gastar: number
  contas_do_mes: ContaDoMes[]
  entrou: number
  saiu: number
  categorias: { nome: string; valor: number }[]
  faturas: { cartao: number; nome: string; total: number; fecha: string; vence: string; limite: number; disponivel: number }[]
  compromisso_proximo_mes: number
  emprestimos: {
    devo_total: number
    devo_por_mes: number
    devo_quantidade: number
    devem_total: number
    devem_pessoas: string[]
  }
}

export interface DetalheCartao {
  fatura: { abre: string; fecha: string; vence: string; total: number }
  limite: number
  disponivel: number
  proximas: { fecha: string; vence: string; total: number }[]
  parcelas: { descricao: string; valor: number; atual: number; total: number; termina: string }[]
}

export interface Emprestimo {
  id: number
  direcao: 'devo' | 'devem'
  nome: string
  instituicao: string
  valor_total: number
  juros_mensal: string | null
  parcela_valor: number | null
  parcelas_total: number | null
  data: string
  prazo: string | null
  dia_vencimento: number | null
  pago: number
  saldo: number
  parcelas_pagas: number | null
}
