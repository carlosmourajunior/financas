const brl = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' })

/** Valores ficam em centavos para evitar erro de arredondamento. */
export function moeda(centavos: number, opts: { sinal?: boolean } = {}) {
  const texto = brl.format(Math.abs(centavos) / 100)
  if (opts.sinal && centavos > 0) return `+ ${texto}`
  return centavos < 0 && opts.sinal ? `- ${texto}` : texto
}

/** Separa "R$ 1.842" e ",90" para o número de destaque. */
export function moedaPartes(centavos: number) {
  const texto = brl.format(centavos / 100)
  const i = texto.lastIndexOf(',')
  return { inteiro: texto.slice(0, i), centavos: texto.slice(i) }
}

export function pct(parte: number, total: number) {
  if (total <= 0) return '0%'
  return `${Math.min(100, Math.round((parte / total) * 100))}%`
}

/** Converte "4.500,00" ou "4500" em centavos. */
export function paraCentavos(texto: string) {
  const limpo = texto.replace(/[^\d,]/g, '').replace(',', '.')
  const n = Number.parseFloat(limpo)
  return Number.isFinite(n) ? Math.round(n * 100) : 0
}
