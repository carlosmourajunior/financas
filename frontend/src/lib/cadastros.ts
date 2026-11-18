import { COR_SEM_CATEGORIA } from '../components/Categorias'
import type { Pagina } from './api'
import type { Cartao, Categoria, Conta, Lancamento } from './tipos'
import { useApi } from './useApi'

/** Contas, cartões e categorias do usuário, com os nomes que as listas mostram. */
export function useCadastros() {
  const contas = useApi<Pagina<Conta>>('/contas/?limit=500')
  const cartoes = useApi<Pagina<Cartao>>('/cartoes/?limit=500')
  const categorias = useApi<Pagina<Categoria>>('/categorias/?limit=500')

  const listaContas = contas.dados?.results ?? []
  const listaCartoes = cartoes.dados?.results ?? []
  const listaCategorias = categorias.dados?.results ?? []

  function meio(l: Lancamento) {
    if (l.cartao) {
      const c = listaCartoes.find((x) => x.id === l.cartao)
      return c ? nomeCartao(c) : 'Cartão'
    }
    return listaContas.find((x) => x.id === l.conta)?.nome ?? 'Sem conta'
  }

  function categoria(l: Pick<Lancamento, 'categoria'>) {
    return listaCategorias.find((x) => x.id === l.categoria)?.nome ?? 'Sem categoria'
  }

  /** Cor da categoria; sem categoria, um cinza neutro. */
  function cor(id: number | null | undefined) {
    return listaCategorias.find((x) => x.id === id)?.cor ?? COR_SEM_CATEGORIA
  }

  return {
    contas: listaContas,
    // Desativados ficam de fora das escolhas; o nome deles ainda aparece nos lançamentos antigos.
    cartoes: listaCartoes.filter((c) => c.ativo !== false),
    categorias: listaCategorias,
    carregando: contas.carregando || cartoes.carregando || categorias.carregando,
    recarregar() {
      contas.recarregar()
      cartoes.recarregar()
      categorias.recarregar()
    },
    meio,
    categoria,
    cor,
    recarregarCategorias: categorias.recarregar,
  }
}

export function nomeCartao(c: Cartao) {
  return c.final ? `${c.nome} final ${c.final}` : c.nome
}
