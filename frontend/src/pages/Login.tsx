import { useState, type FormEvent } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import { Abas, Campo, botaoPrimario, campo } from '../components/ui'
import { useAuth } from '../lib/auth'

type Modo = 'entrar' | 'criar'

export default function Login() {
  const navigate = useNavigate()
  const local = useLocation()
  const auth = useAuth()
  const [modo, setModo] = useState<Modo>('entrar')
  const [nome, setNome] = useState('')
  const [email, setEmail] = useState('')
  const [senha, setSenha] = useState('')
  const [erro, setErro] = useState<string | null>(null)
  const [enviando, setEnviando] = useState(false)
  const entrar = modo === 'entrar'
  const destino = (local.state as { de?: string } | null)?.de ?? '/'

  if (auth.usuario) return <Navigate to={destino} replace />

  async function enviar(e: FormEvent) {
    e.preventDefault()
    setErro(null)
    setEnviando(true)
    try {
      if (entrar) await auth.entrar(email, senha)
      else await auth.cadastrar(nome, email, senha)
      navigate(destino, { replace: true })
    } catch (err) {
      const status = (err as { status?: number }).status
      setErro(entrar && status === 401 ? 'E-mail ou senha incorretos.' : (err as Error).message || 'Não foi possível conectar. Tente de novo.')
    } finally {
      setEnviando(false)
    }
  }

  return (
    <div className="mx-auto flex min-h-dvh max-w-md flex-col gap-7 px-6 pb-8 pt-14">
      <div className="flex flex-col gap-3.5">
        <h1 className="font-display text-[44px] font-extrabold leading-none tracking-[-1.5px]">Finanças</h1>
        <p className="max-w-[300px] text-lg leading-snug text-suave">
          Saiba quanto ainda pode gastar este mês, com cartões, contas e extratos juntos.
        </p>
        <div aria-hidden="true" className="relative mt-1.5 h-4">
          <div className="absolute inset-x-0 top-[7px] h-0.5 bg-linha" />
          <div className="absolute left-0 top-1.5 h-1 w-[62%] rounded-full bg-tinta" />
          <div className="absolute left-[78%] top-0.5 size-3 rounded-full bg-ambar" />
          <div className="absolute left-[92%] top-0.5 size-3 rounded-full bg-ambar" />
        </div>
      </div>

      <Abas
        rotulo="Acesso"
        opcoes={[
          { id: 'entrar', label: 'Entrar' },
          { id: 'criar', label: 'Criar conta' },
        ]}
        valor={modo}
        onChange={setModo}
      />

      <form onSubmit={enviar} className="flex grow flex-col gap-4">
        {!entrar && (
          <Campo label="Nome">
            <input
              required
              autoComplete="name"
              value={nome}
              onChange={(e) => setNome(e.target.value)}
              placeholder="Como quer ser chamado"
              className={`${campo} min-h-[52px]`}
            />
          </Campo>
        )}
        <Campo label="E-mail">
          <input
            required
            type="email"
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="voce@email.com"
            className={`${campo} min-h-[52px]`}
          />
        </Campo>
        <Campo label="Senha">
          <input
            required
            type="password"
            minLength={8}
            autoComplete={entrar ? 'current-password' : 'new-password'}
            value={senha}
            onChange={(e) => setSenha(e.target.value)}
            placeholder="Pelo menos 8 caracteres"
            className={`${campo} min-h-[52px]`}
          />
        </Campo>
        {entrar ? (
          <a href="#esqueci" className="self-start py-2.5 text-[15px] font-bold">
            Esqueci minha senha
          </a>
        ) : (
          <label className="flex items-start gap-2.5 text-[15px] leading-snug text-suave">
            <input required type="checkbox" className="size-5 shrink-0 accent-tinta" />
            Aceito os termos de uso e a política de privacidade
          </label>
        )}

        {erro && (
          <p role="alert" className="rounded-xl bg-[#fbeceb] px-4 py-3 text-[15px] font-semibold text-[#9c2b20]">
            {erro}
          </p>
        )}

        <div className="mt-auto flex flex-col gap-2.5 pt-6">
          <button type="submit" disabled={enviando} className={`${botaoPrimario} disabled:opacity-60`}>
            {enviando ? 'Aguarde…' : entrar ? 'Entrar' : 'Criar minha conta'}
          </button>
        </div>
      </form>
    </div>
  )
}
