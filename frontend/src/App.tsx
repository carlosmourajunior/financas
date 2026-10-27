import type { ReactNode } from 'react'
import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import Layout from './components/Layout'
import { useAuth } from './lib/auth'
import Cartoes from './pages/Cartoes'
import Emprestimos from './pages/Emprestimos'
import Importar from './pages/Importar'
import Inicio from './pages/Inicio'
import Lancamentos from './pages/Lancamentos'
import Login from './pages/Login'
import NovoLancamento from './pages/NovoLancamento'

function Protegida({ children }: { children: ReactNode }) {
  const { usuario, carregando } = useAuth()
  const local = useLocation()
  if (carregando) return <p className="p-8 text-suave">Carregando…</p>
  if (!usuario) return <Navigate to="/entrar" replace state={{ de: local.pathname }} />
  return children
}

export default function App() {
  return (
    <Routes>
      <Route path="/entrar" element={<Login />} />
      <Route
        path="/lancamentos/novo"
        element={
          <Protegida>
            <NovoLancamento />
          </Protegida>
        }
      />
      <Route
        element={
          <Protegida>
            <Layout />
          </Protegida>
        }
      >
        <Route index element={<Inicio />} />
        <Route path="/lancamentos" element={<Lancamentos />} />
        <Route path="/cartoes" element={<Cartoes />} />
        <Route path="/emprestimos" element={<Emprestimos />} />
        <Route path="/importar" element={<Importar />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
