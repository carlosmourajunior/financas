"""Cria uma conta com as categorias padrão, para quando o cadastro pelo site está fechado.

    python manage.py criar_usuario --email voce@exemplo.com --nome "Seu Nome"

A senha é pedida no terminal (não fica no histórico do shell).
"""
import getpass

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from financas.models import criar_categorias_padrao


class Command(BaseCommand):
    help = "Cria uma conta de usuário com as categorias padrão."

    def add_arguments(self, parser):
        parser.add_argument("--email", required=True)
        parser.add_argument("--nome", required=True)

    def handle(self, *args, email, nome, **opcoes):
        Usuario = get_user_model()
        email = email.strip().lower()
        if Usuario.objects.filter(email__iexact=email).exists():
            raise CommandError(f"Já existe uma conta com {email}.")
        senha = getpass.getpass("Senha: ")
        if senha != getpass.getpass("Repita a senha: "):
            raise CommandError("As senhas não conferem.")
        try:
            validate_password(senha, Usuario(email=email, nome=nome))
        except ValidationError as exc:
            raise CommandError(" ".join(exc.messages)) from exc
        usuario = Usuario.objects.create_user(email=email, password=senha, nome=nome)
        criar_categorias_padrao(usuario)
        self.stdout.write(self.style.SUCCESS(f"Conta {email} criada."))
