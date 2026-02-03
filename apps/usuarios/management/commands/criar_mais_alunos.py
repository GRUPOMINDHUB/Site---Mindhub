"""
Cria mais 20 alunos com distribuição de notas:
  6 com nota 5, 5 com nota 4, 4 com nota 3, 5 com nota 1.

Uso:
    python manage.py criar_mais_alunos
"""
from django.core.management.base import BaseCommand
from apps.usuarios.models import Usuario, RoleChoices
from apps.trilha.models import NotaSaude


NOMES_ALUNOS = [
    'Lucas Ferreira', 'Julia Rodrigues', 'Rafael Souza', 'Fernanda Lima',
    'Bruno Alves', 'Camila Ribeiro', 'Diego Martins', 'Amanda Costa',
    'Gabriel Oliveira', 'Larissa Santos', 'Matheus Pereira', 'Isabela Nunes',
    'Leonardo Carvalho', 'Beatriz Gomes', 'Thiago Rocha', 'Mariana Dias',
    'Felipe Araújo', 'Carolina Mendes', 'Gustavo Barbosa', 'Patricia Lopes',
]


class Command(BaseCommand):
    help = 'Cria 20 alunos: 6 nota 5, 5 nota 4, 4 nota 3, 5 nota 1'

    def handle(self, *args, **options):
        # Distribuição: 6 nota 5, 5 nota 4, 4 nota 3, 5 nota 1
        distribuicao = (
            [5] * 6 +   # 6 alunos nota 5
            [4] * 5 +   # 5 alunos nota 4
            [3] * 4 +   # 4 alunos nota 3
            [1] * 5     # 5 alunos nota 1
        )

        # Descobrir próximo número de aluno (aluno6, aluno7, ...)
        existentes = Usuario.objects.filter(
            email__startswith='aluno',
            email__endswith='@mindhub.com',
            role=RoleChoices.ALUNO
        ).count()
        inicio = existentes + 1

        self.stdout.write(f'Criando 20 alunos (aluno{inicio} a aluno{inicio + 19})...\n')

        criados = 0
        for i, (nome, nota) in enumerate(zip(NOMES_ALUNOS, distribuicao)):
            num = inicio + i
            email = f'aluno{num}@mindhub.com'
            senha = 'aluno123'

            usuario, created = Usuario.objects.update_or_create(
                email=email,
                defaults={
                    'nome': nome,
                    'senha': senha,
                    'role': RoleChoices.ALUNO,
                    'ativo': True,
                }
            )
            usuario.senha = senha
            usuario.save()

            # Cria registro de nota para que o Graph View mostre a cor correta
            NotaSaude.objects.create(aluno=usuario, nota=nota, automatica=False)

            status = 'Criado' if created else 'Atualizado'
            self.stdout.write(
                self.style.SUCCESS(f'  {status}: {email} ({nome}) - Nota {nota}')
            )
            criados += 1

        self.stdout.write(
            self.style.SUCCESS(f'\nConcluído: {criados} alunos criados/atualizados.')
        )
        self.stdout.write('Senha de todos: aluno123')
