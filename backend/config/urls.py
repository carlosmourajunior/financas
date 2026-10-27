from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from financas import views as fin
from usuarios.views import CadastroView, EuView

router = DefaultRouter()
router.register("contas", fin.ContaViewSet, basename="conta")
router.register("cartoes", fin.CartaoViewSet, basename="cartao")
router.register("categorias", fin.CategoriaViewSet, basename="categoria")
router.register("lancamentos", fin.LancamentoViewSet, basename="lancamento")
router.register("recorrencias", fin.RecorrenciaViewSet, basename="recorrencia")
router.register("emprestimos", fin.EmprestimoViewSet, basename="emprestimo")
router.register("pagamentos-emprestimo", fin.PagamentoEmprestimoViewSet, basename="pagamento-emprestimo")

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/saude/", lambda r: JsonResponse({"ok": True})),
    path("api/auth/cadastro/", CadastroView.as_view()),
    path("api/auth/token/", TokenObtainPairView.as_view()),
    path("api/auth/token/renovar/", TokenRefreshView.as_view()),
    path("api/auth/eu/", EuView.as_view()),
    path("api/resumo/", fin.ResumoView.as_view()),
    path("api/", include(router.urls)),
]
