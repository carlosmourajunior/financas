# Publicar no servidor

Tudo roda com Docker num servidor só: PostgreSQL, API (gunicorn), front (nginx), o Caddy na frente com HTTPS automático (Let's Encrypt) e um serviço que faz backup do banco todo dia.

```
https://seu-dominio/        front
https://seu-dominio/api/    API
https://seu-dominio/admin/  admin do Django
```

## O que precisa

- Um servidor Linux com Docker e o plugin `docker compose` (1 GB de RAM basta; 2 GB dá folga para o build).
- Um domínio ou subdomínio com registro **A** apontando para o IP do servidor.
- Portas 80 e 443 abertas no firewall (o Caddy usa a 80 para pedir o certificado).

## Primeira vez

```bash
git clone https://github.com/carlosmourajunior/financas.git
cd financas
cp .env.example .env
# Gere os segredos e cole no .env:
openssl rand -hex 32   # DJANGO_SECRET_KEY
openssl rand -hex 24   # POSTGRES_PASSWORD
nano .env              # preencha DOMINIO, EMAIL_ACME e os dois segredos

docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml exec backend python manage.py createsuperuser
```

Depois abra `https://DOMINIO` e crie sua conta pela tela de cadastro. O superusuário serve para o `/admin`.

## Atualizar para a versão nova da master

```bash
cd financas
git pull
docker compose -f docker-compose.prod.yml up -d --build
```

As migrações rodam sozinhas quando a API sobe.

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
docker compose -f docker-compose.prod.yml logs -f caddy # certificado, acessos
docker compose -f docker-compose.prod.yml logs -f backend
```

## Segurança

- O `.env` tem os segredos. Ele não vai para o Git (`.gitignore`).
- Só o Caddy expõe portas (80 e 443). O banco e a API ficam na rede interna do Docker.
- Qualquer pessoa que abrir o site pode criar uma conta. Cada conta só vê os próprios dados.
