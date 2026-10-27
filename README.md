# Finanças

Controle financeiro pessoal em formato SaaS: API Django e front React, rodando com Docker.

## Estrutura

- `frontend/`: React + Vite + Tailwind, mobile first, com menu lateral no computador
- `backend/`: API Django + Django REST Framework (próximo PR)
- `docker-compose.yml`: ambiente local

## Rodar localmente

```bash
docker compose up --build
```

Abra http://localhost:5173. Por enquanto o front usa dados de exemplo (`frontend/src/data/mock.ts`).

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

Toda mudança entra por pull request na `master`. O CI (GitHub Actions) roda lint, build e o build da imagem Docker em cada PR.
