import { NavLink, Outlet } from 'react-router-dom'
import { usuario } from '../data/mock'
import Icon, { type IconName } from './Icon'

const itens: { to: string; label: string; icon: IconName }[] = [
  { to: '/', label: 'Início', icon: 'inicio' },
  { to: '/lancamentos', label: 'Lançamentos', icon: 'lista' },
  { to: '/cartoes', label: 'Cartões', icon: 'cartao' },
  { to: '/emprestimos', label: 'Empréstimos', icon: 'emprestimo' },
  { to: '/importar', label: 'Importar', icon: 'importar' },
]

// No celular a barra inferior tem espaço para quatro itens e o botão de lançar.
const itensCelular = itens.filter((i) => i.to !== '/emprestimos')

export default function Layout() {
  return (
    <div className="min-h-dvh lg:flex">
      <aside className="hidden w-60 shrink-0 flex-col gap-7 border-r border-linha bg-white px-4 py-7 lg:sticky lg:top-0 lg:flex lg:h-dvh">
        <div className="px-3 font-display text-[26px] font-extrabold tracking-tight">Finanças</div>
        <nav aria-label="Navegação principal" className="flex flex-col gap-0.5">
          {itens.map((i) => (
            <NavLink
              key={i.to}
              to={i.to}
              end={i.to === '/'}
              className={({ isActive }) =>
                `flex min-h-11 items-center gap-3 rounded-[10px] px-3 text-base ${
                  isActive ? 'bg-nevoa font-bold text-tinta' : 'font-semibold text-suave hover:bg-nevoa/60'
                }`
              }
            >
              <Icon name={i.icon} size={20} />
              {i.label}
            </NavLink>
          ))}
        </nav>
        <div className="mt-auto flex items-center gap-2.5 px-3">
          <span className="flex size-9 items-center justify-center rounded-full bg-nevoa text-sm font-bold">{usuario.iniciais}</span>
          <span className="text-[15px] font-semibold">{usuario.nomeCompleto}</span>
        </div>
      </aside>

      <main className="min-w-0 flex-1 pb-24 lg:pb-12">
        <Outlet />
      </main>

      <nav
        aria-label="Navegação principal"
        className="fixed inset-x-0 bottom-0 z-10 flex h-[76px] items-start border-t border-linha bg-white px-2 lg:hidden"
      >
        {itensCelular.slice(0, 2).map((i) => (
          <ItemCelular key={i.to} {...i} />
        ))}
        <NavLink to="/lancamentos/novo" aria-label="Novo lançamento" className="flex flex-1 justify-center pt-2.5">
          <span className="flex size-[52px] items-center justify-center rounded-2xl bg-tinta text-white">
            <Icon name="mais" size={26} strokeWidth={2.2} />
          </span>
        </NavLink>
        {itensCelular.slice(2).map((i) => (
          <ItemCelular key={i.to} {...i} />
        ))}
      </nav>
    </div>
  )
}

function ItemCelular({ to, label, icon }: { to: string; label: string; icon: IconName }) {
  return (
    <NavLink
      to={to}
      end={to === '/'}
      className={({ isActive }) =>
        `flex min-h-11 flex-1 flex-col items-center gap-1 pt-3 text-xs ${isActive ? 'font-bold text-tinta' : 'font-semibold text-suave'}`
      }
    >
      <Icon name={icon} size={24} />
      {label}
    </NavLink>
  )
}
