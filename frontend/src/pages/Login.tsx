import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { Abas, Campo, botaoPrimario, campo } from '../components/ui'

type Modo = 'entrar' | 'criar'

export default function Login() {
  const navigate = useNavigate()
  const [modo, setModo] = useState<Modo>('entrar')
  const entrar = modo === 'entrar'

  function enviar(e: FormEvent) {
    e.preventDefault()
    // Autenticação com JWT entra junto com a API.
    navigate('/')
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
            <input required autoComplete="name" placeholder="Como quer ser chamado" className={`${campo} min-h-[52px]`} />
          </Campo>
        )}
        <Campo label="E-mail">
          <input required type="email" autoComplete="email" placeholder="voce@email.com" className={`${campo} min-h-[52px]`} />
        </Campo>
        <Campo label="Senha">
          <input
            required
            type="password"
            minLength={8}
            autoComplete={entrar ? 'current-password' : 'new-password'}
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

        <div className="mt-auto flex flex-col gap-2.5 pt-6">
          <button type="submit" className={botaoPrimario}>
            {entrar ? 'Entrar' : 'Criar minha conta'}
          </button>
          <button type="button" className="min-h-[52px] cursor-pointer rounded-[14px] border border-borda bg-white text-base font-semibold">
            Continuar com Google
          </button>
        </div>
      </form>
    </div>
  )
}
