// Exemplo da tela de importação, até a leitura de faturas e extratos existir.
// Valores em centavos.

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
