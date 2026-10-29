from rest_framework import serializers, status
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from financas.models import Cartao, Categoria, Natureza
from financas.servicos import somar_meses

from .leitores import FormatoDesconhecido, ler_fatura
from .servicos import confirmar, previa

TAMANHO_MAXIMO = 5 * 1024 * 1024


def cartao_do_usuario(request, cartao_id) -> Cartao:
    try:
        return Cartao.objects.get(dono=request.user, pk=int(cartao_id))
    except (Cartao.DoesNotExist, TypeError, ValueError) as exc:
        raise ValidationError({"cartao": "Escolha um dos seus cartões."}) from exc


class PreviaFaturaView(APIView):
    """Lê o arquivo e devolve as linhas para revisar. Não grava nada."""

    parser_classes = [MultiPartParser]

    def post(self, request):
        arquivo = request.FILES.get("arquivo")
        if not arquivo:
            raise ValidationError({"arquivo": "Envie o arquivo da fatura."})
        if arquivo.size > TAMANHO_MAXIMO:
            raise ValidationError({"arquivo": "O arquivo passa de 5 MB."})
        cartao = cartao_do_usuario(request, request.data.get("cartao"))
        try:
            lida = ler_fatura(arquivo.read(), arquivo.name)
        except FormatoDesconhecido as exc:
            raise ValidationError({"arquivo": str(exc)}) from exc
        except Exception as exc:  # PDF corrompido ou CSV fora do padrão
            raise ValidationError({"arquivo": "Não conseguimos ler este arquivo."}) from exc
        if not lida.itens:
            raise ValidationError({"arquivo": "Não encontramos lançamentos neste arquivo."})
        return Response(previa(cartao, lida))


class CategoriaDoUsuario(serializers.PrimaryKeyRelatedField):
    def get_queryset(self):
        return Categoria.objects.filter(dono=self.context["request"].user)


class ItemSerializer(serializers.Serializer):
    data = serializers.DateField()
    descricao = serializers.CharField(max_length=120)
    valor = serializers.IntegerField(min_value=1)
    natureza = serializers.ChoiceField(choices=Natureza.choices)
    categoria = CategoriaDoUsuario(allow_null=True, required=False)
    parcela_atual = serializers.IntegerField(min_value=1, max_value=99, allow_null=True, required=False)
    parcela_total = serializers.IntegerField(min_value=1, max_value=99, allow_null=True, required=False)


class ConfirmarSerializer(serializers.Serializer):
    cartao = serializers.IntegerField()
    fecha = serializers.DateField(help_text="Fechamento da fatura, como veio na prévia (ciclo.fecha).")
    itens = ItemSerializer(many=True, allow_empty=False)


class ConfirmarFaturaView(APIView):
    def post(self, request):
        s = ConfirmarSerializer(data=request.data, context={"request": request})
        s.is_valid(raise_exception=True)
        cartao = cartao_do_usuario(request, s.validated_data["cartao"])
        fecha = s.validated_data["fecha"]
        if fecha != somar_meses(fecha, 0, cartao.dia_fechamento):
            raise ValidationError({"fecha": "Não é um dia de fechamento deste cartão."})
        resultado = confirmar(cartao, s.validated_data["fecha"], s.validated_data["itens"])
        return Response(resultado, status=status.HTTP_201_CREATED)
