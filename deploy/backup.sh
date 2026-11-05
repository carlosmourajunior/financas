#!/bin/sh
# Faz um pg_dump por dia, na hora BACKUP_HORA, e apaga os mais velhos que BACKUP_DIAS.
# Também roda um logo ao subir, para você ver que está funcionando.
set -eu

fazer_backup() {
	arquivo="/backups/financas-$(date +%Y-%m-%d_%H%M).sql.gz"
	if pg_dump --no-owner --clean --if-exists | gzip > "$arquivo.tmp"; then
		mv "$arquivo.tmp" "$arquivo"
		echo "$(date '+%F %T') backup ok: $arquivo ($(du -h "$arquivo" | cut -f1))"
	else
		rm -f "$arquivo.tmp"
		echo "$(date '+%F %T') ERRO no backup" >&2
	fi
	find /backups -name 'financas-*.sql.gz' -mtime +"$BACKUP_DIAS" -delete
}

fazer_backup
while true; do
	# Espera até a próxima BACKUP_HORA:00
	agora=$(date +%s)
	alvo=$(date -d "$(date +%F) ${BACKUP_HORA}:00" +%s 2>/dev/null || date -D '%Y-%m-%d %H:%M' -d "$(date +%F) ${BACKUP_HORA}:00" +%s)
	[ "$alvo" -le "$agora" ] && alvo=$((alvo + 86400))
	sleep $((alvo - agora))
	fazer_backup
done
