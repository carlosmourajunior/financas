from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken

from financas.models import criar_categorias_padrao

Usuario = get_user_model()


class UsuarioSerializer(serializers.ModelSerializer):
    class Meta:
        model = Usuario
        fields = ["id", "nome", "email"]


class CadastroSerializer(serializers.Serializer):
    nome = serializers.CharField(max_length=120)
    email = serializers.EmailField()
    senha = serializers.CharField(write_only=True, min_length=8)

    def validate_email(self, valor):
        valor = valor.lower()
        if Usuario.objects.filter(email=valor).exists():
            raise serializers.ValidationError("Já existe uma conta com esse e-mail.")
        return valor

    def validate(self, dados):
        validate_password(dados["senha"], Usuario(email=dados["email"], nome=dados["nome"]))
        return dados

    def create(self, dados):
        usuario = Usuario.objects.create_user(email=dados["email"], password=dados["senha"], nome=dados["nome"])
        criar_categorias_padrao(usuario)
        return usuario

    def to_representation(self, usuario):
        refresh = RefreshToken.for_user(usuario)
        return {
            "usuario": UsuarioSerializer(usuario).data,
            "access": str(refresh.access_token),
            "refresh": str(refresh),
        }
