from django.contrib import admin

from .models import Cartao, Categoria, Conta, Emprestimo, Lancamento, PagamentoEmprestimo, Recorrencia


@admin.register(Lancamento)
class LancamentoAdmin(admin.ModelAdmin):
    list_display = ["data", "descricao", "valor", "natureza", "tipo", "dono"]
    list_filter = ["natureza", "tipo"]
    search_fields = ["descricao", "dono__email"]


admin.site.register([Conta, Cartao, Categoria, Recorrencia, Emprestimo, PagamentoEmprestimo])
