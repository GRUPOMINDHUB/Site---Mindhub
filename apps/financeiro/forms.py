from django import forms
from .models import Contrato, Parcela

class ContratoForm(forms.ModelForm):
    class Meta:
        model = Contrato
        fields = ['aluno', 'valor_total_negociado', 'data_assinatura', 'observacoes_gerais', 'status']
        widgets = {
            'data_assinatura': forms.DateInput(attrs={'type': 'date'}),
            'observacoes_gerais': forms.Textarea(attrs={'rows': 3}),
        }

class ParcelaForm(forms.ModelForm):
    class Meta:
        model = Parcela
        fields = ['numero', 'valor', 'data_vencimento', 'data_pagamento', 'link_pagamento_ou_pix', 'comprovante', 'observacoes']
        widgets = {
            'data_vencimento': forms.DateInput(attrs={'type': 'date'}),
            'data_pagamento': forms.DateInput(attrs={'type': 'date'}),
            'observacoes': forms.Textarea(attrs={'rows': 2}),
        }
