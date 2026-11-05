import { BrowserRouter } from 'react-router-dom'
import App from './App'
import { AuthProvider } from './lib/auth'

export default function Aplicativo({ base }: { base: string }) {
  return (
    <BrowserRouter basename={base}>
      <AuthProvider>
        <App />
      </AuthProvider>
    </BrowserRouter>
  )
}
