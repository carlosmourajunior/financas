from rest_framework import generics, permissions

from .serializers import CadastroSerializer, UsuarioSerializer


class CadastroView(generics.CreateAPIView):
    serializer_class = CadastroSerializer
    permission_classes = [permissions.AllowAny]
    authentication_classes = []


class EuView(generics.RetrieveUpdateAPIView):
    serializer_class = UsuarioSerializer

    def get_object(self):
        return self.request.user
