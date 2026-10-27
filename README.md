# Finanças

Controle financeiro pessoal em formato SaaS: API Django e front React, rodando com Docker.

## Estrutura

- `frontend/`: React + Vite + Tailwind, mobile first, com menu lateral no computador
- `backend/`: API Django + Django REST Framework, PostgreSQL, login com JWT
- `docker-compose.yml`: ambiente local

## Rodar localmente

```bash
docker compose up --build
```

Sobe o PostgreSQL, a API em http://localhost:8000/api e o front em http://localhost:5173. O front ainda usa dados de exemplo (`frontend/src/data/mock.ts`); a ligação com a API vem no próximo PR.

Para criar um usuário de demonstração com dados parecidos com os do protótipo:

```bash
docker compose exec backend python manage.py criar_demo
```

Ele entra com `demo@financas.local` e a senha `demo-financas-2026`. Para um usuário do admin (http://localhost:8000/admin): `docker compose exec backend python manage.py createsuperuser`.

## API

Todas as rotas, menos cadastro e login, exigem `Authorization: Bearer <token>`. Cada usuário só vê os próprios dados. Valores em centavos.

| Rota | O que faz |
| --- | --- |
| `POST /api/auth/cadastro/` | Cria a conta (`nome`, `email`, `senha`) e devolve os tokens |
| `POST /api/auth/token/` | Login (`email`, `password`) |
| `POST /api/auth/token/renovar/` | Novo token de acesso a partir do `refresh` |
| `GET /api/auth/eu/` | Dados do usuário logado |
| `GET /api/resumo/` | Números do Início: livre para gastar, contas do mês, faturas, empréstimos |
| `/api/lancamentos/` | Lançamentos. `?mes=AAAA-MM`, `?natureza=`, `?tipo=`. Na criação, `tipo=parcelada` com `parcelas` divide o `valor` total; `tipo=recorrente` com `frequencia` cria a regra |
| `/api/contas/`, `/api/cartoes/`, `/api/categorias/` | Cadastros básicos |
| `/api/recorrencias/` | Ver, pausar (`ativa=false`) ou encerrar contas recorrentes |
| `/api/emprestimos/`, `/api/pagamentos-emprestimo/` | Empréstimos (`direcao=devo` ou `devem`) e pagamentos ou devoluções |

Testes do backend: `docker compose exec backend python manage.py test`.

Sem Docker:

```bash
cd frontend
npm install
npm run dev
```

## Imagem de produção do front

```bash
docker build --target prod -t financas-frontend ./frontend
docker run -p 8080:80 financas-frontend
```

## Fluxo de trabalho

Toda mudança entra por pull request na `master`. O CI (GitHub Actions) roda lint e build do front, os testes da API com PostgreSQL e o build das imagens Docker em cada PR.
