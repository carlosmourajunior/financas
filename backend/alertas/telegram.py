"""Alertas de segurança no Telegram.

Sem TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID no ambiente, só registra no log.
O envio roda numa thread para nunca atrasar a requisição.
"""
import json
import logging
import os
import socket
import threading
import urllib.request

from django.core.cache import cache

log = logging.getLogger('alertas')


def _origem():
    return os.environ.get('ALERTA_ORIGEM') or socket.gethostname()


def _enviar(token, chat, texto):
    try:
        req = urllib.request.Request(
            f'https://api.telegram.org/bot{token}/sendMessage',
            data=json.dumps({'chat_id': chat, 'text': texto,
                             'disable_web_page_preview': True}).encode(),
            headers={'Content-Type': 'application/json'},
        )
        urllib.request.urlopen(req, timeout=10).close()
    except Exception as exc:  # o alerta nunca pode derrubar a aplicação
        log.error('Falha ao enviar alerta ao Telegram: %s', exc)


def alertar(texto, chave=None, janela=3600):
    """Envia `texto`. Com `chave`, manda no máximo um alerta por `janela` segundos."""
    if chave and not cache.add(f'alerta:{chave}', 1, janela):
        return False
    log.warning('ALERTA: %s', texto)
    token = os.environ.get('TELEGRAM_BOT_TOKEN')
    chat = os.environ.get('TELEGRAM_CHAT_ID')
    if not (token and chat):
        return False
    threading.Thread(target=_enviar, args=(token, chat, f'🛡️ [{_origem()}] {texto}'),
                     daemon=True).start()
    return True


def contar(chave, janela):
    """Incrementa um contador que expira em `janela` segundos e devolve o total."""
    k = f'alerta-cont:{chave}'
    if cache.add(k, 1, janela):
        return 1
    try:
        return cache.incr(k)
    except ValueError:
        cache.set(k, 1, janela)
        return 1


def ip_cliente(request):
    """IP do visitante para o texto do alerta (não use para decidir acesso).

    O tráfego chega por Cloudflare Tunnel -> nginx -> Django: o IP real vem no
    CF-Connecting-IP; sem ele, o primeiro do X-Forwarded-For; por último REMOTE_ADDR.
    """
    if request is None:
        return '?'
    meta = request.META
    ip = meta.get('HTTP_CF_CONNECTING_IP')
    if not ip and meta.get('HTTP_X_FORWARDED_FOR'):
        ip = meta['HTTP_X_FORWARDED_FOR'].split(',')[0]
    return (ip or meta.get('REMOTE_ADDR') or '?').strip()
