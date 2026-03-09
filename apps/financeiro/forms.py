from django import forms

from .models import Contrato, Parcela


class ContratoForm(forms.ModelForm):
    class Meta:
        model = Contrato
        fields = [
            "aluno",
            "valor_total_negociado",
            "data_assinatura",
            "observacoes_gerais",
            "status",
        ]
        widgets = {
            "data_assinatura": forms.DateInput(attrs={"type": "date"}),
            "observacoes_gerais": forms.Textarea(attrs={"rows": 3}),
        }


class ParcelaForm(forms.ModelForm):
    class Meta:
        model = Parcela
        fields = [
            "numero",
            "valor",
            "data_vencimento",
            "data_pagamento",
            "link_pagamento_ou_pix",
            "comprovante",
            "observacoes",
        ]
        widgets = {
            "data_vencimento": forms.DateInput(attrs={"type": "date"}),
            "data_pagamento": forms.DateInput(attrs={"type": "date"}),
            "observacoes": forms.Textarea(attrs={"rows": 2}),
        }


class ParcelaAtualizacaoForm(forms.ModelForm):
    class Meta:
        model = Parcela
        fields = [
            "data_pagamento",
            "link_pagamento_ou_pix",
            "comprovante",
            "observacoes",
        ]
        widgets = {
            "data_pagamento": forms.DateInput(attrs={"type": "date"}),
            "observacoes": forms.Textarea(attrs={"rows": 2}),
        }

    def clean(self):
        cleaned_data = super().clean()
        data_pagamento = cleaned_data.get("data_pagamento")
        comprovante_novo = cleaned_data.get("comprovante")
        comprovante_existente = bool(getattr(self.instance, "comprovante", None))

        if data_pagamento and not comprovante_novo and not comprovante_existente:
            self.add_error("comprovante", "Comprovante obrigatorio para marcar a parcela como paga.")

        return cleaned_data
