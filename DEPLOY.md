# Publicar no servidor

Tudo roda com Docker num servidor só: PostgreSQL, API (gunicorn), front (nginx) e um serviço que faz backup do banco todo dia. O HTTPS fica no Cloudflare: um túnel leva `financas.rlcsolucoes.com.br` até o nginx do app, que escuta só em `127.0.0.1:PORTA` no servidor. Não precisa abrir porta nenhuma, e o app convive com os outros sistemas do servidor.

```
https://financas.rlcsolucoes.com.br/        landing page
https://financas.rlcsolucoes.com.br/app/    sistema (login em /app/entrar)
https://financas.rlcsolucoes.com.br/api/    API
https://financas.rlcsolucoes.com.br/admin/  admin do Django
```

## O que precisa

- Docker com o plugin `docker compose` no servidor.
- Uma porta livre no servidor para o app (padrão 8099, muda em `PORTA` no `.env`).
- O domínio `rlcsolucoes.com.br` no Cloudflare e um túnel (Zero Trust > Networks > Tunnels).

## Primeira vez

```bash
git clone https://github.com/carlosmourajunior/financas.git
cd financas
cp .env.example .env
# Gere os segredos e cole no .env:
openssl rand -hex 32   # DJANGO_SECRET_KEY
openssl rand -hex 24   # POSTGRES_PASSWORD
nano .env              # confira DOMINIO e PORTA, cole os dois segredos

docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml exec backend python manage.py createsuperuser
curl -s http://127.0.0.1:8099/api/saude/   # deve responder {"ok": true}
```

## Túnel do Cloudflare

Escolha um dos dois jeitos.

**A. O servidor já tem um cloudflared rodando** (o mesmo dos outros sistemas). No painel do túnel, em *Public hostnames*, adicione:

- Subdomain `financas`, domain `rlcsolucoes.com.br`
- Service `HTTP` → `localhost:8099` (ou a `PORTA` que você escolheu)

Se esse cloudflared roda em container sem `network_mode: host`, use o IP do host na rede do Docker (por exemplo `172.17.0.1:8099`) no lugar de `localhost`, e troque `127.0.0.1` por esse IP no `ports` do serviço `frontend`.

**B. Um túnel só para o app, dentro deste compose.** Crie o túnel no painel, copie o token para `CLOUDFLARE_TUNNEL_TOKEN` no `.env` e, em *Public hostnames*, aponte `financas.rlcsolucoes.com.br` para `HTTP` → `frontend:80`. Depois:

```bash
docker compose -f docker-compose.prod.yml --profile tunel up -d
```

No Cloudflare, ligue *SSL/TLS > Edge Certificates > Always Use HTTPS* para quem digitar http:// cair no HTTPS.

## Atualizar para a versão nova da master

```bash
cd financas
git pull
docker compose -f docker-compose.prod.yml up -d --build
```

Se usa o túnel do compose, acrescente `--profile tunel`. As migrações rodam sozinhas quando a API sobe.

## Backups

O serviço `backup` faz um `pg_dump` compactado ao subir e depois todo dia na `BACKUP_HORA` (horário de Brasília), em `BACKUP_PASTA` (padrão `./backups`). Guarda `BACKUP_DIAS` dias (padrão 14).

Os backups ficam no mesmo servidor. Para não perder tudo se o servidor sumir, copie a pasta para fora de vez em quando (por exemplo com `rclone` para o Google Drive, ou `scp` para o seu PC).

Ver se está funcionando:

```bash
docker compose -f docker-compose.prod.yml logs backup
ls -lh backups/
```

Fazer um backup agora:

```bash
docker compose -f docker-compose.prod.yml restart backup
```

Restaurar um backup (substitui o banco atual):

```bash
docker compose -f docker-compose.prod.yml stop backend
gunzip -c backups/financas-AAAA-MM-DD_HHMM.sql.gz | \
  docker compose -f docker-compose.prod.yml exec -T db psql -U financas -d financas
docker compose -f docker-compose.prod.yml start backend
```

## Comandos úteis

```bash
docker compose -f docker-compose.prod.yml ps            # o que está rodando
docker compose -f docker-compose.prod.yml logs -f frontend # acessos
docker compose -f docker-compose.prod.yml logs -f backend
```

## Segurança

- O `.env` tem os segredos. Ele não vai para o Git (`.gitignore`).
- Só o nginx do front escuta, e só em 127.0.0.1. O banco e a API ficam na rede interna do Docker.
- Qualquer pessoa que abrir o site pode criar uma conta. Cada conta só vê os próprios dados.
