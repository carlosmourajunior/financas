from rest_framework import generics, permissions
from rest_framework_simplejwt.views import TokenObtainPairView

from .limites import LimitePorIP
from .serializers import CadastroSerializer, UsuarioSerializer


class CadastroView(generics.CreateAPIView):
    serializer_class = CadastroSerializer
    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    throttle_classes = [LimitePorIP]
    throttle_scope = "cadastro"


class LoginView(TokenObtainPairView):
    """Login por e-mail e senha, com limite de tentativas por IP contra força bruta."""

    throttle_classes = [LimitePorIP]
    throttle_scope = "login"


class EuView(generics.RetrieveUpdateAPIView):
    serializer_class = UsuarioSerializer

    def get_object(self):
        return self.request.user
