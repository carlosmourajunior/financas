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
  vencidas: Pendencia[]
  vencem_hoje: Pendencia[]
  entrou: number
  saiu: number
  categorias: { nome: string; valor: number }[]
  parcelas_anteriores: number
  creditos_cartao: number
  sai_da_conta: number
  gastou_detalhe: {
    cartoes: { cartao: number; nome: string; valor: number; fecha: string; vence: string }[]
    recorrentes: number
    parceladas: number
    avulsas: number
  }
  fechadas_a_pagar: { cartao: number; nome: string; valor: number; vence: string }[]
  faturas: { cartao: number; nome: string; total: number; fecha: string; vence: string; aberta: boolean; limite: number; disponivel: number }[]
  compromisso_proximo_mes: number
  entradas_proximo_mes: number
  emprestimos: {
    devo_total: number
    devo_por_mes: number
    devo_quantidade: number
    devem_total: number
    devem_pessoas: string[]
  }
}

export interface CompraNoCartao {
  id: number
  data: string
  descricao: string
  valor: number
  natureza: Natureza
  categoria: string | null
  categoria_id: number | null
  parcela_atual: number | null
  parcela_total: number | null
}

export interface PagamentoFatura {
  id: number
  valor: number
  data: string
}

/** Conta que vence até hoje e não foi paga: um lançamento em conta ou uma fatura. */
export type Pendencia = { nome: string; valor: number; data: string } & (
  | { tipo: 'lancamento'; id: number }
  | { tipo: 'fatura'; cartao: number; fecha: string }
)

export interface FaturaDoMes {
  cartao: number
  nome: string
  final: string
  abre: string
  fecha: string
  vence: string
  total: number
  paga: boolean
  pagamento: PagamentoFatura | null
  compras: number
}

export interface DetalheCartao {
  fatura: { abre: string; fecha: string; vence: string; total: number; aberta: boolean; anterior: string; seguinte: string; pagamento: PagamentoFatura | null }
  compras: CompraNoCartao[]
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

export interface ItemImportado {
  data: string
  descricao: string
  valor: number
  natureza: Natureza
  tipo: 'compra' | 'encargo' | 'credito' | 'saldo_anterior'
  parcela_atual: number | null
  parcela_total: number | null
  categoria: number | null
  repetido: boolean
  importar: boolean
}

export interface PreviaFatura {
  banco: string
  final: string
  final_confere: boolean
  vencimento: string | null
  total: number | null
  total_lido: number
  conferida: boolean | null
  ciclo: { abre: string; fecha: string; vence: string }
  ja_importados: number
  itens: ItemImportado[]
}

export type ClasseMovimento = 'despesa' | 'receita' | 'transferencia' | 'fatura' | 'emprestimo'

export interface MovimentoImportado {
  data: string
  descricao: string
  origem: string
  valor: number
  natureza: Natureza
  classe: ClasseMovimento
  tipo: Tipo
  parcela_atual: number | null
  parcela_total: number | null
  categoria: number | null
  cartao: number | null
  emprestimo: number | null
  lancamento: number | null
  chave: string
  importar: boolean
  aviso: string
}

export interface PreviaExtrato {
  banco: string
  saldo_anterior: number | null
  saldo_final: number | null
  data_final: string | null
  conferido: boolean | null
  entradas: number
  saidas: number
  itens: MovimentoImportado[]
}

export interface ExtratoImportado {
  criados?: number
  pagos?: number
  faturas?: number
  emprestimos?: number
  transferencias?: number
  repetidos?: number
}
