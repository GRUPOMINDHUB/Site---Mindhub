"""
Management command para criar dados iniciais da trilha.

Uso:
    python manage.py criar_dados_iniciais
"""
from django.core.management.base import BaseCommand
from apps.trilha.models import Mundo, Step, TipoValidacao


class Command(BaseCommand):
    help = 'Cria os 6 Mundos e Steps iniciais da trilha'
    
    def handle(self, *args, **options):
        self.stdout.write('Criando dados iniciais da trilha...\n')
        
        # Dados dos Mundos
        mundos_data = [
            {
                'numero': 1,
                'nome': 'Mês 1',
                'descricao': 'Aprenda os conceitos básicos de gestão de restaurante',
                'icone': 'book',
                'cor_primaria': '#e30613',
                'steps': [
                    {'titulo': 'Bem-vindo ao Mindhub', 'tipo': TipoValidacao.TEXTO, 'instrucoes': 'Apresente-se e conte seus objetivos.'},
                    {'titulo': 'Conhecendo a Plataforma', 'tipo': TipoValidacao.FOTO, 'instrucoes': 'Tire um print da tela inicial.'},
                    {'titulo': 'Meu Primeiro Relatório', 'tipo': TipoValidacao.FORMULARIO, 'instrucoes': 'Preencha o formulário de diagnóstico.'},
                ]
            },
            {
                'numero': 2,
                'nome': 'Mês 2',
                'descricao': 'Domine o controle financeiro do seu negócio',
                'icone': 'chart-line',
                'cor_primaria': '#28a745',
                'steps': [
                    {'titulo': 'Fluxo de Caixa', 'tipo': TipoValidacao.FOTO, 'instrucoes': 'Envie uma foto do seu fluxo de caixa atualizado.'},
                    {'titulo': 'CMV - Custo da Mercadoria', 'tipo': TipoValidacao.FORMULARIO, 'instrucoes': 'Calcule o CMV do mês.'},
                    {'titulo': 'DRE Simplificado', 'tipo': TipoValidacao.FOTO, 'instrucoes': 'Envie seu DRE do último mês.'},
                    {'titulo': 'Meta de Faturamento', 'tipo': TipoValidacao.TEXTO, 'instrucoes': 'Defina sua meta para os próximos 3 meses.'},
                ]
            },
            {
                'numero': 3,
                'nome': 'Mês 3',
                'descricao': 'Otimize as operações do dia a dia',
                'icone': 'cogs',
                'cor_primaria': '#ffc107',
                'steps': [
                    {'titulo': 'Checklist de Abertura', 'tipo': TipoValidacao.FOTO, 'instrucoes': 'Crie e envie seu checklist de abertura.'},
                    {'titulo': 'Checklist de Fechamento', 'tipo': TipoValidacao.FOTO, 'instrucoes': 'Crie e envie seu checklist de fechamento.'},
                    {'titulo': 'Ficha Técnica', 'tipo': TipoValidacao.FORMULARIO, 'instrucoes': 'Preencha a ficha técnica de 3 pratos.'},
                    {'titulo': 'Controle de Estoque', 'tipo': TipoValidacao.FOTO, 'instrucoes': 'Organize e fotografe seu estoque.'},
                ]
            },
            {
                'numero': 4,
                'nome': 'Mês 4',
                'descricao': 'Desenvolva e gerencie sua equipe',
                'icone': 'users',
                'cor_primaria': '#17a2b8',
                'steps': [
                    {'titulo': 'Organograma', 'tipo': TipoValidacao.FOTO, 'instrucoes': 'Crie o organograma da sua equipe.'},
                    {'titulo': 'Descrição de Cargos', 'tipo': TipoValidacao.TEXTO, 'instrucoes': 'Descreva as funções de cada cargo.'},
                    {'titulo': 'Reunião de Equipe', 'tipo': TipoValidacao.FOTO, 'instrucoes': 'Registre sua primeira reunião de alinhamento.'},
                    {'titulo': 'Feedback Individual', 'tipo': TipoValidacao.FORMULARIO, 'instrucoes': 'Faça feedback com 2 colaboradores.'},
                ]
            },
            {
                'numero': 5,
                'nome': 'Mês 5',
                'descricao': 'Atraia e fidelize clientes',
                'icone': 'bullhorn',
                'cor_primaria': '#6f42c1',
                'steps': [
                    {'titulo': 'Perfil do Cliente', 'tipo': TipoValidacao.TEXTO, 'instrucoes': 'Descreva seu cliente ideal.'},
                    {'titulo': 'Redes Sociais', 'tipo': TipoValidacao.FOTO, 'instrucoes': 'Envie print das suas redes atualizadas.'},
                    {'titulo': 'Campanha Promocional', 'tipo': TipoValidacao.FOTO, 'instrucoes': 'Crie e envie uma peça promocional.'},
                    {'titulo': 'Pesquisa de Satisfação', 'tipo': TipoValidacao.FORMULARIO, 'instrucoes': 'Aplique pesquisa com 10 clientes.'},
                ]
            },
            {
                'numero': 6,
                'nome': 'Mês 6',
                'descricao': 'Prepare seu negócio para crescer',
                'icone': 'trophy',
                'cor_primaria': '#fd7e14',
                'steps': [
                    {'titulo': 'Processos Documentados', 'tipo': TipoValidacao.FOTO, 'instrucoes': 'Documente 3 processos principais.'},
                    {'titulo': 'Indicadores (KPIs)', 'tipo': TipoValidacao.FORMULARIO, 'instrucoes': 'Defina seus 5 KPIs principais.'},
                    {'titulo': 'Plano de Expansão', 'tipo': TipoValidacao.TEXTO, 'instrucoes': 'Escreva seu plano de crescimento.'},
                    {'titulo': 'Apresentação Final', 'tipo': TipoValidacao.FOTO, 'instrucoes': 'Apresente sua evolução na trilha.'},
                ]
            },
        ]
        
        for mundo_data in mundos_data:
            steps_data = mundo_data.pop('steps')
            
            mundo, created = Mundo.objects.update_or_create(
                numero=mundo_data['numero'],
                aluno=None,
                defaults=mundo_data
            )
            
            status = 'Criado' if created else 'Atualizado'
            self.stdout.write(f'  {status}: Mundo {mundo.numero} - {mundo.nome}')
            
            for i, step_data in enumerate(steps_data, start=1):
                Step.objects.update_or_create(
                    mundo=mundo,
                    ordem=i,
                    defaults={
                        'titulo': step_data['titulo'],
                        'tipo_validacao': step_data['tipo'],
                        'instrucoes': step_data['instrucoes'],
                        'pontos': 10 * mundo.numero,  # Mais pontos em mundos avançados
                    }
                )
        
        total_mundos = Mundo.objects.count()
        total_steps = Step.objects.count()
        
        self.stdout.write(
            self.style.SUCCESS(f'\nConcluído: {total_mundos} mundos e {total_steps} steps criados/atualizados')
        )
