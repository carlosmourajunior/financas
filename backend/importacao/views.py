from rest_framework import serializers, status
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from financas.models import Cartao, Categoria, Conta, Emprestimo, Lancamento, Natureza
from financas.servicos import somar_meses

from .extrato import Classe, confirmar_extrato, previa_extrato
from .leitores import FormatoDesconhecido, ler_extrato, ler_fatura
from .servicos import confirmar, previa

TAMANHO_MAXIMO = 5 * 1024 * 1024


def cartao_do_usuario(request, cartao_id) -> Cartao:
    try:
        return Cartao.objects.get(dono=request.user, pk=int(cartao_id))
    except (Cartao.DoesNotExist, TypeError, ValueError) as exc:
        raise ValidationError({"cartao": "Escolha um dos seus cartões."}) from exc


def conta_do_usuario(request, conta_id) -> Conta:
    try:
        return Conta.objects.get(dono=request.user, pk=int(conta_id))
    except (Conta.DoesNotExist, TypeError, ValueError) as exc:
        raise ValidationError({"conta": "Escolha uma das suas contas."}) from exc


def ler_arquivo(request, leitor, nome: str):
    arquivo = request.FILES.get("arquivo")
    if not arquivo:
        raise ValidationError({"arquivo": f"Envie o arquivo {nome}."})
    if arquivo.size > TAMANHO_MAXIMO:
        raise ValidationError({"arquivo": "O arquivo passa de 5 MB."})
    try:
        return leitor(arquivo.read(), arquivo.name)
    except FormatoDesconhecido as exc:
        raise ValidationError({"arquivo": str(exc)}) from exc
    except Exception as exc:  # PDF corrompido ou CSV fora do padrão
        raise ValidationError({"arquivo": "Não conseguimos ler este arquivo."}) from exc


class PreviaFaturaView(APIView):
    """Lê o arquivo e devolve as linhas para revisar. Não grava nada."""

    parser_classes = [MultiPartParser]

    def post(self, request):
        cartao = cartao_do_usuario(request, request.data.get("cartao"))
        lida = ler_arquivo(request, ler_fatura, "da fatura")
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


class PreviaExtratoView(APIView):
    """Lê o extrato e devolve as linhas para classificar. Não grava nada."""

    parser_classes = [MultiPartParser]

    def post(self, request):
        conta = conta_do_usuario(request, request.data.get("conta"))
        lido = ler_arquivo(request, ler_extrato, "do extrato")
        if not lido.itens:
            raise ValidationError({"arquivo": "Não encontramos movimentos neste extrato."})
        return Response(previa_extrato(conta, lido))


class DoUsuarioRelacionado(serializers.PrimaryKeyRelatedField):
    def __init__(self, modelo, **kwargs):
        self.modelo = modelo
        super().__init__(allow_null=True, required=False, **kwargs)

    def get_queryset(self):
        return self.modelo.objects.filter(dono=self.context["request"].user)


class MovimentoSerializer(serializers.Serializer):
    data = serializers.DateField()
    descricao = serializers.CharField(max_length=120)
    valor = serializers.IntegerField(min_value=1)
    classe = serializers.ChoiceField(choices=Classe.choices)
    tipo = serializers.ChoiceField(choices=Lancamento.Tipo.choices, default=Lancamento.Tipo.UNICA)
    parcela_atual = serializers.IntegerField(min_value=1, max_value=99, allow_null=True, required=False)
    parcela_total = serializers.IntegerField(min_value=1, max_value=99, allow_null=True, required=False)
    categoria = DoUsuarioRelacionado(Categoria)
    cartao = DoUsuarioRelacionado(Cartao)
    emprestimo = DoUsuarioRelacionado(Emprestimo)
    lancamento = DoUsuarioRelacionado(Lancamento)
    chave = serializers.CharField(max_length=200, required=False, allow_blank=True)

    def validate(self, dados):
        classe = dados["classe"]
        if classe == Classe.FATURA and not dados.get("cartao"):
            raise ValidationError({"cartao": "Escolha o cartão desta fatura."})
        if classe == Classe.EMPRESTIMO and not dados.get("emprestimo"):
            raise ValidationError({"emprestimo": "Escolha o empréstimo deste pagamento."})
        cat = dados.get("categoria")
        if cat and classe in (Classe.DESPESA, Classe.RECEITA) and cat.natureza != classe:
            raise ValidationError({"categoria": f"A categoria {cat.nome} não é de {'recebimento' if classe == Classe.RECEITA else 'conta'}."})
        if dados["tipo"] == Lancamento.Tipo.PARCELADA:
            atual, total = dados.get("parcela_atual") or 1, dados.get("parcela_total")
            if not total or atual > total:
                raise ValidationError({"parcela_total": "Informe a parcela e o total de parcelas."})
        lanc = dados.get("lancamento")
        if lanc and lanc.cartao_id:
            raise ValidationError({"lancamento": "Esse lançamento é de cartão."})
        return dados


class ConfirmarExtratoSerializer(serializers.Serializer):
    conta = serializers.IntegerField()
    itens = MovimentoSerializer(many=True, allow_empty=False)


class ConfirmarExtratoView(APIView):
    def post(self, request):
        s = ConfirmarExtratoSerializer(data=request.data, context={"request": request})
        s.is_valid(raise_exception=True)
        conta = conta_do_usuario(request, s.validated_data["conta"])
        return Response(confirmar_extrato(conta, s.validated_data["itens"]), status=status.HTTP_201_CREATED)
