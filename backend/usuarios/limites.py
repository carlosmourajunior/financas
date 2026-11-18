"""Limite de tentativas no login e no cadastro, por IP do visitante.

O tráfego chega por Cloudflare Tunnel -> nginx -> Django, então o REMOTE_ADDR é sempre o
nginx. O IP real vem no CF-Connecting-IP (o nginx só escuta em 127.0.0.1, então só o túnel
chega a ele).
"""
from rest_framework.throttling import ScopedRateThrottle

from alertas.telegram import ip_cliente


class LimitePorIP(ScopedRateThrottle):
    def get_ident(self, request):
        return ip_cliente(request)
