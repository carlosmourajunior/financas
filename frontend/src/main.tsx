import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'

// A raiz do site é a landing page; o sistema mora em /app.
const BASE_APP = '/app'
const { pathname, search, hash } = window.location
const noApp = pathname === BASE_APP || pathname.startsWith(`${BASE_APP}/`)

async function iniciar() {
  const raiz = createRoot(document.getElementById('root')!)

  if (noApp) {
    const { default: Aplicativo } = await import('./Aplicativo')
    raiz.render(
      <StrictMode>
        <Aplicativo base={BASE_APP} />
      </StrictMode>,
    )
    return
  }

  if (pathname !== '/') {
    // Endereços antigos do sistema (/lancamentos, /entrar…) continuam funcionando.
    window.location.replace(`${BASE_APP}${pathname}${search}${hash}`)
    return
  }

  const { default: Landing } = await import('./landing/Landing')
  raiz.render(
    <StrictMode>
      <Landing linkApp={BASE_APP} />
    </StrictMode>,
  )
}

void iniciar()
