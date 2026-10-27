export const MESES = ['janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho', 'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro']
export const DIAS = ['domingo', 'segunda', 'terça', 'quarta', 'quinta', 'sexta', 'sábado']

/** "2026-10-27" vira uma data local, sem o desvio de fuso do new Date(string). */
export function lerData(iso: string) {
  const [a, m, d] = iso.split('-').map(Number)
  return new Date(a, m - 1, d)
}

export function isoData(d: Date) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

export function isoMes(d: Date) {
  return isoData(d).slice(0, 7)
}

export function diaMes(iso: string) {
  const d = lerData(iso)
  return `${String(d.getDate()).padStart(2, '0')}/${String(d.getMonth() + 1).padStart(2, '0')}`
}

export function porExtenso(iso: string) {
  const d = lerData(iso)
  return `${d.getDate()} de ${MESES[d.getMonth()]}`
}

export function maiuscula(s: string) {
  return s.charAt(0).toUpperCase() + s.slice(1)
}
