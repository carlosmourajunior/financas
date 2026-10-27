// Dados de exemplo usados enquanto a API não existe.
// Todos os valores estão em centavos.

export type Tipo = 'unica' | 'parcelada' | 'recorrente'
export type Natureza = 'despesa' | 'receita'

export interface Lancamento {
  id: number
  data: string // ISO
  descricao: string
  categoria: string
  meio: string
  valor: number
  natureza: Natureza
  tipo: Tipo
  parcela?: { atual: number; total: number }
}

export interface Conta {
  dia: number
  nome: string
  valor: number
  paga: boolean
}

export interface Cartao {
  id: string
  nome: string
  final: string
  fechaDia: number
  venceDia: number
  limite: number
  fatura: number
  parcelas: { nome: string; valor: number; pagas: number; total: number; fim: string }[]
  futuras: { mes: string; valor: number }[]
}

export interface Divida {
  nome: string
  origem: string
  juros: string
  parcela: number
  pagas: number
  total: number
  saldo: number
  proxima: string
}

export interface Credito {
  pessoa: string
  valor: number
  data: string
  devolvido: number
  prazo: string | null
}

export const hoje = new Date(2026, 9, 27)

export const usuario = { nome: 'Carlos', nomeCompleto: 'Carlos Moura', iniciais: 'CM' }

export const saldoEmConta = 273290

export const contasDoMes: Conta[] = [
  { dia: 5, nome: 'Aluguel', valor: 220000, paga: true },
  { dia: 10, nome: 'Fatura do cartão', valor: 184550, paga: true },
  { dia: 15, nome: 'Notebook', valor: 45000, paga: true },
  { dia: 20, nome: 'Academia', valor: 12900, paga: true },
  { dia: 28, nome: 'Condomínio', valor: 68000, paga: false },
  { dia: 30, nome: 'Seguro do carro', valor: 21000, paga: false },
]

export const resumoMes = { entrou: 1200000, saiu: 926710, compromissoProximoMes: 423970 }

export const categorias = [
  { nome: 'Moradia', valor: 352000 },
  { nome: 'Alimentação', valor: 172040 },
  { nome: 'Transporte', valor: 94020 },
  { nome: 'Lazer', valor: 78000 },
  { nome: 'Outros', valor: 230650 },
]

export const lancamentos: Lancamento[] = [
  { id: 1, data: '2026-10-27', descricao: 'Mercado', categoria: 'Alimentação', meio: 'Visa 4321', valor: 31245, natureza: 'despesa', tipo: 'unica' },
  { id: 2, data: '2026-10-27', descricao: 'Notebook', categoria: 'Eletrônicos', meio: 'Visa 4321', valor: 45000, natureza: 'despesa', tipo: 'parcelada', parcela: { atual: 3, total: 10 } },
  { id: 3, data: '2026-10-25', descricao: 'Streaming', categoria: 'Lazer', meio: 'Master 8890', valor: 3990, natureza: 'despesa', tipo: 'recorrente' },
  { id: 4, data: '2026-10-25', descricao: 'Uber', categoria: 'Transporte', meio: 'Pix', valor: 2780, natureza: 'despesa', tipo: 'unica' },
  { id: 5, data: '2026-10-24', descricao: 'Freelance', categoria: 'Receita', meio: 'Conta corrente', valor: 150000, natureza: 'receita', tipo: 'unica' },
  { id: 6, data: '2026-10-20', descricao: 'Academia', categoria: 'Saúde', meio: 'Débito automático', valor: 12900, natureza: 'despesa', tipo: 'recorrente' },
  { id: 7, data: '2026-10-20', descricao: 'Tênis', categoria: 'Vestuário', meio: 'Master 8890', valor: 8990, natureza: 'despesa', tipo: 'parcelada', parcela: { atual: 2, total: 4 } },
  { id: 8, data: '2026-10-05', descricao: 'Salário', categoria: 'Receita', meio: 'Conta corrente', valor: 1050000, natureza: 'receita', tipo: 'recorrente' },
]

export const cartoes: Cartao[] = [
  {
    id: 'visa',
    nome: 'Visa',
    final: '4321',
    fechaDia: 3,
    venceDia: 10,
    limite: 600000,
    fatura: 184550,
    parcelas: [
      { nome: 'Notebook', valor: 45000, pagas: 3, total: 10, fim: 'agosto de 2027' },
      { nome: 'Geladeira', valor: 28000, pagas: 6, total: 12, fim: 'abril de 2027' },
    ],
    futuras: [
      { mes: 'Dezembro', valor: 76990 },
      { mes: 'Janeiro', valor: 76990 },
      { mes: 'Fevereiro', valor: 73000 },
    ],
  },
  {
    id: 'master',
    nome: 'Master',
    final: '8890',
    fechaDia: 15,
    venceDia: 22,
    limite: 400000,
    fatura: 46990,
    parcelas: [{ nome: 'Tênis', valor: 8990, pagas: 2, total: 4, fim: 'janeiro de 2027' }],
    futuras: [
      { mes: 'Dezembro', valor: 12980 },
      { mes: 'Janeiro', valor: 12980 },
      { mes: 'Fevereiro', valor: 3990 },
    ],
  },
]

export const dividas: Divida[] = [
  { nome: 'Empréstimo pessoal', origem: 'Banco do Brasil', juros: '2,1% ao mês', parcela: 61240, pagas: 8, total: 24, saldo: 980000, proxima: '12/11' },
  { nome: 'Financiamento do carro', origem: 'Banco Itaú', juros: '1,4% ao mês', parcela: 105000, pagas: 14, total: 48, saldo: 862000, proxima: '20/11' },
]

export const creditos: Credito[] = [
  { pessoa: 'João', valor: 80000, data: '10/09', devolvido: 20000, prazo: '15/11' },
  { pessoa: 'Ana', valor: 55000, data: '02/10', devolvido: 0, prazo: null },
]

export const importacaoExemplo = {
  fatura: {
    arquivo: 'fatura-outubro.pdf',
    destino: 'Visa final 4321',
    formatos: 'PDF, CSV ou OFX da fatura',
    linhas: [
      { id: 1, nome: 'Mercado', data: '27/10', cat: 'Alimentação', valor: 31245, duplicado: false, parcela: null as string | null },
      { id: 2, nome: 'Notebook 03/10', data: '27/10', cat: 'Eletrônicos', valor: 45000, duplicado: false, parcela: 'Notebook, parcela 3 de 10' },
      { id: 3, nome: 'Academia', data: '20/10', cat: 'Saúde', valor: 12900, duplicado: true, parcela: null },
      { id: 4, nome: 'Posto de gasolina', data: '18/10', cat: 'Transporte', valor: 21000, duplicado: false, parcela: null },
      { id: 5, nome: 'Farmácia', data: '16/10', cat: 'Saúde', valor: 6430, duplicado: false, parcela: null },
    ],
  },
  extrato: {
    arquivo: 'extrato-outubro.ofx',
    destino: 'Conta corrente',
    formatos: 'OFX, CSV ou PDF do extrato',
    linhas: [
      { id: 1, nome: 'Salário', data: '05/10', cat: 'Receita', valor: 1050000, duplicado: true, parcela: null as string | null },
      { id: 2, nome: 'Pix recebido', data: '24/10', cat: 'Receita', valor: 150000, duplicado: false, parcela: null },
      { id: 3, nome: 'Aluguel', data: '05/10', cat: 'Moradia', valor: 220000, duplicado: false, parcela: null },
      { id: 4, nome: 'Uber', data: '25/10', cat: 'Transporte', valor: 2780, duplicado: false, parcela: null },
      { id: 5, nome: 'Tarifa do banco', data: '01/10', cat: 'Taxas', valor: 1990, duplicado: false, parcela: null },
    ],
  },
}
