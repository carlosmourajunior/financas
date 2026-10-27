import { Navigate, Route, Routes } from 'react-router-dom'
import Layout from './components/Layout'
import Cartoes from './pages/Cartoes'
import Emprestimos from './pages/Emprestimos'
import Importar from './pages/Importar'
import Inicio from './pages/Inicio'
import Lancamentos from './pages/Lancamentos'
import Login from './pages/Login'
import NovoLancamento from './pages/NovoLancamento'

export default function App() {
  return (
    <Routes>
      <Route path="/entrar" element={<Login />} />
      <Route path="/lancamentos/novo" element={<NovoLancamento />} />
      <Route element={<Layout />}>
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
