from decimal import Decimal

from django import forms
from django.utils import timezone

from apps.financeiro.models import MetodoPagamentoContrato
from apps.usuarios.models import Usuario

from .services import escolhas_dificuldades, escolhas_nichos, monitores_ativos


class CadastroAlunoOnboardingForm(forms.Form):
    MODALIDADE_CHOICES = (
        ("AVISTA", "A vista"),
        ("PARCELADO", "Parcelado"),
    )

    nome = forms.CharField(max_length=200)
    email = forms.EmailField()
    telefone = forms.CharField(max_length=20, required=False)
    senha = forms.CharField(max_length=255, required=False, widget=forms.PasswordInput(render_value=True))
    monitor_responsavel = forms.ModelChoiceField(queryset=Usuario.objects.none())

    nome_empresa = forms.CharField(max_length=200)
    telefone_empresa = forms.CharField(max_length=20, required=False)
    cnpj = forms.CharField(max_length=18, required=False)
    endereco = forms.CharField(max_length=255, required=False)
    nicho = forms.ChoiceField(choices=escolhas_nichos())
    nome_representante = forms.CharField(max_length=200, required=False)
    cpf_representante = forms.CharField(max_length=14, required=False)
    dificuldades = forms.MultipleChoiceField(
        choices=escolhas_dificuldades(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )
    observacoes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 4}))

    valor_entrada = forms.DecimalField(
        label="Valor da Entrada (R$)",
        max_digits=10,
        decimal_places=2,
        min_value=Decimal("0.00"),
        required=False,
        initial=0,
        widget=forms.NumberInput(attrs={"step": "0.01", "placeholder": "0.00"}),
    )
    data_contrato = forms.DateField(
        label="Data do Contrato",
        initial=timezone.localdate,
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    modalidade_pagamento = forms.ChoiceField(choices=MODALIDADE_CHOICES, initial="PARCELADO")
    valor_total_avista = forms.DecimalField(
        label="Valor Total (R$)",
        max_digits=10,
        decimal_places=2,
        min_value=Decimal("0.01"),
        required=False,
        widget=forms.NumberInput(attrs={"step": "0.01", "placeholder": "0.00"}),
    )
    quantidade_parcelas = forms.IntegerField(label="Quantidade de Parcelas", min_value=1, required=False, initial=3)
    metodo_pagamento = forms.ChoiceField(label="Metodo de Pagamento", choices=MetodoPagamentoContrato.choices, initial=MetodoPagamentoContrato.PIX)
    link_pagamento_ou_pix = forms.CharField(
        label="Link de Pagamento ou Chave Pix",
        max_length=500,
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "https://... ou chave pix"}),
    )
    contrato_assinado = forms.FileField(label="Contrato Assinado", required=False)
    comprovante_entrada = forms.FileField(label="Comprovante da Entrada", required=False)

    def __init__(self, *args, allow_password_optional=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.allow_password_optional = allow_password_optional
        self.fields["monitor_responsavel"].queryset = monitores_ativos()

    def clean(self):
        cleaned_data = super().clean()
        modalidade = cleaned_data.get("modalidade_pagamento")
        valor_entrada = cleaned_data.get("valor_entrada") or Decimal("0.00")

        if valor_entrada < 0:
            self.add_error("valor_entrada", "Informe um valor de entrada valido.")

        if modalidade == "AVISTA":
            valor_total_avista = cleaned_data.get("valor_total_avista")
            if not valor_total_avista or valor_total_avista <= 0:
                self.add_error("valor_total_avista", "Informe o valor total para pagamento a vista.")
        elif modalidade == "PARCELADO":
            quantidade_parcelas = cleaned_data.get("quantidade_parcelas")
            if not quantidade_parcelas or quantidade_parcelas <= 0:
                self.add_error("quantidade_parcelas", "Informe a quantidade de parcelas.")

        return cleaned_data


class PropostaFinanceiraForm(forms.Form):
    motivo = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}))
    observacao_monitor = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}))
    quantidade_parcelas = forms.IntegerField(min_value=1, initial=3)
    valor_parcela = forms.DecimalField(max_digits=10, decimal_places=2)
    primeiro_vencimento = forms.DateField(initial=timezone.localdate, widget=forms.DateInput(attrs={"type": "date"}))


class ParecerPropostaFinanceiraForm(forms.Form):
    observacao_admin = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))
