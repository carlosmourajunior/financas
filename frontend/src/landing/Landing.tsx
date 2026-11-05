import { useEffect } from 'react'
import ReguaDoMes from '../components/ReguaDoMes'
import Icon, { type IconName } from '../components/Icon'
import type { ContaDoMes } from '../lib/tipos'

const recursos: { icon: IconName; titulo: string; texto: string }[] = [
  {
    icon: 'lista',
    titulo: 'Contas únicas, parceladas e recorrentes',
    texto: 'Lance o aluguel uma vez e ele aparece todo mês. Compre em 10x e veja cada parcela no mês certo.',
  },
  {
    icon: 'cartao',
    titulo: 'Fatura do cartão sem digitar nada',
    texto: 'Importe a fatura do Nubank, Itaú ou Sicredi. Parcelas que já estavam lá não se repetem.',
  },
  {
    icon: 'importar',
    titulo: 'Extrato do banco em um arquivo',
    texto: 'Envie o extrato e as entradas e saídas da conta entram de uma vez, prontas para conferir.',
  },
  {
    icon: 'emprestimo',
    titulo: 'Empréstimos dos dois lados',
    texto: 'O que você deve ao banco, com parcelas e saldo, e o que os amigos devem a você, com cada devolução.',
  },
  {
    icon: 'inicio',
    titulo: 'Um painel que se lê em segundos',
    texto: 'Para onde foi o dinheiro, o que vence esta semana e quanto sobra, sem gráfico que precise de legenda.',
  },
]

const passos = [
  { titulo: 'Crie sua conta', texto: 'Só nome, e-mail e senha. Seus dados ficam separados dos de qualquer outra pessoa.' },
  { titulo: 'Traga o que já existe', texto: 'Cadastre conta e cartões e importe a última fatura e o extrato do mês.' },
  { titulo: 'Abra quando bater a dúvida', texto: 'Antes de uma compra, a primeira tela já diz quanto ainda cabe no mês.' },
]

const contasExemplo: ContaDoMes[] = [
  { nome: 'Aluguel', valor: 180000, dia: 5, paga: true },
  { nome: 'Luz', valor: 21000, dia: 8, paga: true },
  { nome: 'Academia', valor: 11990, dia: 12, paga: true },
  { nome: 'Fatura Itaú', valor: 128490, dia: 20, paga: false },
  { nome: 'Internet', valor: 11990, dia: 25, paga: false },
]

const proximas = [
  { nome: 'Fatura Itaú', quando: 'vence dia 20', valor: '1.284,90', alerta: true },
  { nome: 'Internet', quando: 'vence dia 25', valor: '119,90', alerta: false },
  { nome: 'Salário', quando: 'entrou dia 5', valor: '+ 6.200,00', entrada: true },
]

function Botao({ href, children, variante = 'primario' }: { href: string; children: string; variante?: 'primario' | 'claro' | 'contorno' }) {
  const estilos = {
    primario: 'bg-tinta text-white hover:bg-tinta/90',
    claro: 'bg-white text-tinta hover:bg-nevoa',
    contorno: 'border border-borda bg-white text-tinta hover:bg-nevoa',
  }[variante]
  return (
    <a href={href} className={`inline-flex min-h-[54px] items-center justify-center gap-2 rounded-[14px] px-6 text-[17px] font-bold ${estilos}`}>
      {children}
      {variante !== 'contorno' && <Icon name="direita" size={20} strokeWidth={2.2} />}
    </a>
  )
}

/** Recorte da tela Início com dados de exemplo, para mostrar o produto sem prometer nada que ele não faz. */
function PreviaInicio() {
  const hoje = new Date(2026, 10, 14)
  return (
    <div aria-label="Exemplo da tela inicial do Finanças" role="figure" className="w-full max-w-[400px] overflow-hidden rounded-[22px] border border-linha bg-white shadow-[0_24px_60px_-28px_rgba(18,52,59,0.45)]">
      <div className="flex flex-col gap-4 bg-tinta px-5 pb-5 pt-6 text-white">
        <p className="text-[15px] text-tinta-claro">Ainda pode gastar até 30 de novembro</p>
        <p className="font-display text-[44px] font-extrabold leading-none tracking-[-1.5px] tabular-nums">
          <span className="mr-1 align-top text-xl font-bold">R$</span>1.842<span className="text-2xl">,30</span>
        </p>
        <ReguaDoMes hoje={hoje} contas={contasExemplo} />
      </div>
      <ul className="divide-y divide-linha px-5">
        {proximas.map((p) => (
          <li key={p.nome} className="flex items-center justify-between gap-3 py-3.5">
            <div className="flex items-center gap-3">
              <span className={`size-2.5 shrink-0 rounded-full ${p.entrada ? 'bg-musgo' : p.alerta ? 'bg-ambar' : 'bg-marca-paga'}`} />
              <div>
                <p className="text-[16px] font-semibold leading-tight">{p.nome}</p>
                <p className={`text-[14px] ${p.alerta ? 'font-semibold text-ambar-texto' : 'text-suave'}`}>{p.quando}</p>
              </div>
            </div>
            <span className={`font-display text-[17px] font-bold tabular-nums ${p.entrada ? 'text-musgo' : ''}`}>{p.valor}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

export default function Landing({ linkApp }: { linkApp: string }) {
  useEffect(() => {
    document.title = 'Finanças: quanto ainda pode gastar este mês'
  }, [])

  const criar = `${linkApp}/entrar?modo=criar`

  return (
    <div className="min-h-dvh bg-fundo">
      <header className="mx-auto flex max-w-6xl items-center justify-between px-4 py-4 sm:px-6 lg:py-6">
        <a href="/" className="font-display text-[24px] font-extrabold tracking-tight">
          Finanças
        </a>
        <a href={linkApp} className="flex min-h-11 items-center rounded-xl px-3 text-[16px] font-bold hover:bg-nevoa">
          Entrar
        </a>
      </header>

      <main>
        <section className="mx-auto grid max-w-6xl items-center gap-12 px-4 pb-16 pt-6 sm:px-6 lg:grid-cols-[1.1fr_1fr] lg:gap-16 lg:pb-24 lg:pt-12">
          <div className="flex flex-col gap-6">
            <h1 className="font-display text-[42px] font-extrabold leading-[1.02] tracking-[-1.5px] sm:text-[56px] lg:text-[68px] lg:tracking-[-2.5px]">
              Quanto ainda dá para gastar até o fim do mês?
            </h1>
            <p className="max-w-[520px] text-[19px] leading-relaxed text-suave lg:text-[21px]">
              O Finanças junta conta, cartões, parcelas e empréstimos e responde essa pergunta todo dia. Sem planilha e sem
              somar fatura na mão.
            </p>
            <div className="flex flex-col gap-3 sm:flex-row">
              <Botao href={linkApp}>Entrar no sistema</Botao>
              <Botao href={criar} variante="contorno">
                Criar minha conta
              </Botao>
            </div>
          </div>
          <div className="flex justify-center lg:justify-end">
            <PreviaInicio />
          </div>
        </section>

        <section aria-labelledby="titulo-recursos" className="border-t border-linha bg-white">
          <div className="mx-auto grid max-w-6xl gap-8 px-4 py-16 sm:px-6 lg:grid-cols-[1fr_1.6fr] lg:gap-16 lg:py-24">
            <div className="flex flex-col gap-3 lg:sticky lg:top-10 lg:self-start">
              <h2 id="titulo-recursos" className="font-display text-[32px] font-extrabold leading-tight tracking-[-1px] lg:text-[40px]">
                Tudo o que mexe no seu mês, num lugar só
              </h2>
              <p className="text-[18px] leading-relaxed text-suave">
                Do boleto que se repete à compra parcelada no cartão, cada valor cai no mês em que sai da sua conta.
              </p>
            </div>
            <ul className="divide-y divide-linha border-y border-linha">
              {recursos.map((r) => (
                <li key={r.titulo} className="flex gap-4 py-6">
                  <span className="flex size-11 shrink-0 items-center justify-center rounded-xl bg-nevoa text-tinta">
                    <Icon name={r.icon} size={22} />
                  </span>
                  <div className="flex flex-col gap-1">
                    <h3 className="text-[19px] font-bold leading-snug">{r.titulo}</h3>
                    <p className="text-[17px] leading-relaxed text-suave">{r.texto}</p>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        </section>

        <section aria-labelledby="titulo-passos" className="mx-auto max-w-6xl px-4 py-16 sm:px-6 lg:py-24">
          <h2 id="titulo-passos" className="font-display text-[32px] font-extrabold leading-tight tracking-[-1px] lg:text-[40px]">
            Começa em três passos
          </h2>
          <ol className="mt-8 grid gap-8 md:grid-cols-3 md:gap-10">
            {passos.map((p, i) => (
              <li key={p.titulo} className="flex flex-col gap-2 border-t-2 border-tinta pt-5">
                <span className="font-display text-[40px] font-extrabold leading-none text-musgo tabular-nums">{i + 1}</span>
                <h3 className="text-[19px] font-bold">{p.titulo}</h3>
                <p className="text-[17px] leading-relaxed text-suave">{p.texto}</p>
              </li>
            ))}
          </ol>
        </section>

        <section className="px-4 pb-16 sm:px-6 lg:pb-24">
          <div className="mx-auto flex max-w-6xl flex-col items-start gap-6 rounded-[24px] bg-tinta px-6 py-10 text-white sm:px-10 lg:flex-row lg:items-center lg:justify-between lg:py-14">
            <div className="flex flex-col gap-2">
              <h2 className="font-display text-[30px] font-extrabold leading-tight tracking-[-1px] lg:text-[38px]">
                Abra e veja como está o seu mês
              </h2>
              <p className="text-[18px] text-tinta-claro">Já tem conta? Entre e continue de onde parou.</p>
            </div>
            <div className="flex w-full flex-col gap-3 sm:w-auto sm:flex-row">
              <Botao href={linkApp} variante="claro">
                Entrar no sistema
              </Botao>
              <a href={criar} className="inline-flex min-h-[54px] items-center justify-center rounded-[14px] border border-white/30 px-6 text-[17px] font-bold hover:bg-white/10">
                Criar conta
              </a>
            </div>
          </div>
        </section>
      </main>

      <footer className="border-t border-linha">
        <div className="mx-auto flex max-w-6xl flex-col gap-2 px-4 py-8 text-[15px] text-suave sm:flex-row sm:justify-between sm:px-6">
          <span className="font-display font-bold text-tinta">Finanças</span>
          <span>© {new Date().getFullYear()} RLC Soluções</span>
        </div>
      </footer>
    </div>
  )
}
