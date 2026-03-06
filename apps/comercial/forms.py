from django import forms
from django.utils import timezone

from apps.usuarios.models import Usuario

from .services import escolhas_dificuldades, escolhas_nichos, monitores_ativos


class CadastroAlunoOnboardingForm(forms.Form):
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

    valor_total_negociado = forms.DecimalField(max_digits=10, decimal_places=2)
    data_assinatura = forms.DateField(initial=timezone.localdate, widget=forms.DateInput(attrs={"type": "date"}))
    quantidade_entrada = forms.IntegerField(min_value=0, initial=1)
    valor_entrada = forms.DecimalField(max_digits=10, decimal_places=2, initial=0)
    quantidade_recorrente = forms.IntegerField(min_value=0, initial=6)
    valor_recorrente = forms.DecimalField(max_digits=10, decimal_places=2, initial=0)
    primeiro_vencimento = forms.DateField(initial=timezone.localdate, widget=forms.DateInput(attrs={"type": "date"}))
    contrato_assinado = forms.FileField(required=False)
    comprovante_entrada = forms.FileField(required=False)

    def __init__(self, *args, allow_password_optional=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.allow_password_optional = allow_password_optional
        self.fields["monitor_responsavel"].queryset = monitores_ativos()

    def clean(self):
        cleaned_data = super().clean()
        quantidade_total = (cleaned_data.get("quantidade_entrada") or 0) + (cleaned_data.get("quantidade_recorrente") or 0)
        if quantidade_total <= 0:
            raise forms.ValidationError("Defina ao menos uma parcela de entrada ou recorrente.")

        return cleaned_data


class PropostaFinanceiraForm(forms.Form):
    motivo = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}))
    observacao_monitor = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}))
    quantidade_parcelas = forms.IntegerField(min_value=1, initial=3)
    valor_parcela = forms.DecimalField(max_digits=10, decimal_places=2)
    primeiro_vencimento = forms.DateField(initial=timezone.localdate, widget=forms.DateInput(attrs={"type": "date"}))


class ParecerPropostaFinanceiraForm(forms.Form):
    observacao_admin = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))
