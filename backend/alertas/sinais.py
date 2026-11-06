"""Avisa no Telegram sobre tentativas de login suspeitas e logins de administradores."""
import os

from django.contrib.auth.signals import user_logged_in, user_login_failed
from django.dispatch import receiver

from .telegram import alertar, contar, ip_cliente

JANELA_FALHAS = 600  # 10 minutos


def _limite():
    try:
        return int(os.environ.get('ALERTA_FALHAS_LOGIN', '5'))
    except ValueError:
        return 5


@receiver(user_login_failed)
def login_falhou(sender, credentials=None, request=None, **kwargs):
    ip = ip_cliente(request)
    total = contar(f'falha:{ip}', JANELA_FALHAS)
    if total >= _limite():
        usuario = (credentials or {}).get('username') or (credentials or {}).get('email') or '?'
        alertar(f'{total} logins errados em 10 min do IP {ip} (último usuário: {usuario})',
                chave=f'falha:{ip}')


@receiver(user_logged_in)
def login_ok(sender, user=None, request=None, **kwargs):
    if user is not None and (user.is_superuser or user.is_staff):
        alertar(f'Login de administrador: {user.get_username()} do IP {ip_cliente(request)}')
