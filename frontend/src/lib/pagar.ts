import { api } from './api'

/** Marca (ou desmarca) um lançamento como pago ou recebido. */
export function marcarLancamento(id: number, pago: boolean) {
  return api(`/lancamentos/${id}/`, { method: 'PATCH', body: { pago } })
}

/** Registra o pagamento da fatura que fecha em `fecha`, pelo total e com a data de hoje. */
export function pagarFatura(cartao: number, fecha: string) {
  return api('/pagamentos-fatura/', { method: 'POST', body: { cartao, fecha } })
}

export function desfazerPagamentoFatura(id: number) {
  return api(`/pagamentos-fatura/${id}/`, { method: 'DELETE' })
}

/** Apaga o lançamento; com `seguintes`, também as próximas parcelas ou ocorrências da recorrência. */
export function excluirLancamento(id: number, seguintes: boolean) {
  return api(`/lancamentos/${id}/${seguintes ? '?seguintes=1' : ''}`, { method: 'DELETE' })
}
