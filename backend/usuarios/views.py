from django.conf import settings
from rest_framework import generics, permissions
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView

from .limites import LimitePorIP
from .serializers import CadastroSerializer, UsuarioSerializer


class CadastroView(generics.CreateAPIView):
    serializer_class = CadastroSerializer
    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    throttle_classes = [LimitePorIP]
    throttle_scope = "cadastro"

    def get(self, request):
        """O front pergunta se mostra a aba "Criar conta"."""
        return Response({"aberto": settings.CADASTRO_ABERTO})

    def create(self, request, *args, **kwargs):
        if not settings.CADASTRO_ABERTO:
            raise PermissionDenied("O cadastro está fechado. Peça a quem administra o sistema para criar sua conta.")
        return super().create(request, *args, **kwargs)

    def get_throttles(self):
        # Consultar se o cadastro está aberto não gasta o limite.
        return super().get_throttles() if self.request.method == "POST" else []


class LoginView(TokenObtainPairView):
    """Login por e-mail e senha, com limite de tentativas por IP contra força bruta."""

    throttle_classes = [LimitePorIP]
    throttle_scope = "login"


class EuView(generics.RetrieveUpdateAPIView):
    serializer_class = UsuarioSerializer

    def get_object(self):
        return self.request.user
