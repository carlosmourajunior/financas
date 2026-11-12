"""Qual conta da Pluggy corresponde a cada conta ou cartão do app, para não escolher de novo toda vez."""

from django.db import models

from financas.models import Cartao, Conta, DoUsuario


class Vinculo(DoUsuario):
    conta = models.OneToOneField(Conta, null=True, blank=True, on_delete=models.CASCADE, related_name="vinculo_pluggy")
    cartao = models.OneToOneField(Cartao, null=True, blank=True, on_delete=models.CASCADE, related_name="vinculo_pluggy")
    pluggy_conta = models.CharField(max_length=64)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(conta__isnull=False, cartao__isnull=True) | models.Q(conta__isnull=True, cartao__isnull=False),
                name="vinculo_de_conta_ou_cartao",
            )
        ]

    def __str__(self):
        return f"{self.conta or self.cartao} -> {self.pluggy_conta}"
