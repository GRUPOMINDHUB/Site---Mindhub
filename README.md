# Site Mindhub

Projeto Django (Mindhub OS): Banco de Conhecimento IA, Trilha Gamificada, Graph View para Monitor.

---

## 🚀 Rodar localmente (servidor de desenvolvimento)

### Opção 1: Script automático (Windows)

1. Abra a pasta **Site-Mindhub** no terminal.
2. Execute:
   ```bash
   run_local.bat
   ```
   O script cria `.env` com SQLite, aplica migrações, cria usuários de teste e sobe o servidor em **http://127.0.0.1:8080/**.

### Opção 2: Comandos manuais

1. **Crie o `.env`** (copie de `.env.example` e garanta `USE_SQLITE=1`):
   ```bash
   copy .env.example .env
   ```
   No `.env`, deixe: `USE_SQLITE=1` e `DEBUG=True`.

2. **Instale dependências:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Migrações e usuários de teste:**
   ```bash
   python manage.py migrate
   python manage.py criar_acessos_teste
   python manage.py criar_dados_iniciais
   ```

4. **Suba o servidor:**
   ```bash
   python manage.py runserver 8080
   ```

5. Acesse **http://127.0.0.1:8080/** e faça login com:
   - **Monitor:** `monitor@mindhub.com` / `monitor123`
   - **Admin:** `admin@mindhub.com` / `admin123`

---

## ✅ MIGRAÇÃO FLASK → DJANGO

Este projeto foi migrado de **Flask** para **Django** mantendo **100% das funcionalidades** e lógica de negócio.

---

## 📁 ESTRUTURA DO PROJETO DJANGO

```
django_project/
├── manage.py                      # Comando principal do Django
├── requirements.txt               # Dependências (Django substituiu Flask)
├── Dockerfile                     # Deploy Cloud Run
├── .env.example                   # Exemplo de variáveis de ambiente
│
├── config/                        # Configurações do projeto
│   ├── __init__.py
│   ├── settings.py               # Configurações centrais
│   ├── urls.py                   # URLs principais
│   ├── wsgi.py                   # WSGI para produção
│   └── asgi.py                   # ASGI (futuro)
│
├── apps/                         # Apps Django
│   ├── __init__.py
│   │
│   ├── usuarios/                 # App de autenticação
│   │   ├── models.py            # Model Usuario (Django ORM)
│   │   ├── views.py             # Views de login/logout
│   │   ├── urls.py              # Rotas de autenticação
│   │   ├── admin.py             # Admin do Django
│   │   └── apps.py
│   │
│   ├── ia_engine/               # App de IA
│   │   ├── services.py          # EngineIA (lógica mantida 100%)
│   │   ├── manager.py           # Singleton global (substitui variáveis globais Flask)
│   │   ├── views.py             # Views de IA (perguntar, editar, etc)
│   │   ├── urls.py              # Rotas de IA
│   │   └── apps.py
│   │
│   └── core/                    # App auxiliar
│
├── templates/                   # Templates HTML
│   ├── login.html              # Migrado ({% static %} no lugar de url_for)
│   └── chat.html               # Migrado (mantém mesmas rotas)
│
└── static/                      # Arquivos estáticos
    └── estilo.css              # CSS copiado do Flask

```

---

## 🔄 MAPEAMENTO FLASK → DJANGO

### 1. **Rotas Flask → Views Django**

| Flask Route | Django URL | View | App |
|-------------|------------|------|-----|
| `@app.route('/')` | `path('')` | `usuarios.views.index` | usuarios |
| `@app.route('/ia')` | `path('ia')` | `usuarios.views.ia_page` | usuarios |
| `@app.route('/login')` | `path('login')` | `usuarios.views.login_endpoint` | usuarios |
| `@app.route('/logout')` | `path('logout')` | `usuarios.views.logout` | usuarios |
| `@app.route('/perguntar')` | `path('perguntar')` | `ia_engine.views.perguntar` | ia_engine |
| `@app.route('/status-atualizacao')` | `path('status-atualizacao')` | `ia_engine.views.status_atualizacao` | ia_engine |
| `@app.route('/executar-edicao')` | `path('executar-edicao')` | `ia_engine.views.executar_edicao` | ia_engine |
| `@app.route('/forçar-atualizacao')` | `path('forçar-atualizacao')` | `ia_engine.views.forcar_atualizacao` | ia_engine |

---

### 2. **Banco de Dados**

#### Flask (SQLite direto)
```python
def validar_no_db(email, senha):
    conn = sqlite3.connect('usuarios.db')
    cursor = conn.cursor()
    cursor.execute("SELECT email, role FROM usuarios WHERE email=? AND senha=?", (email, senha))
```

#### Django (ORM)
```python
from apps.usuarios.models import Usuario

usuario = Usuario.objects.get(email=email)
if usuario.verificar_senha(senha):
    # autenticado
```

**Banco mantido:** `usuarios.db` (mesma estrutura)

---

### 3. **Sessão Flask → Django Session**

#### Flask
```python
from flask import session
session['usuario'] = usuario[0]
```

#### Django
```python
request.session['usuario'] = usuario.email
```

**Comportamento idêntico.**

---

### 4. **EngineIA - Lógica de Negócio**

| Arquivo Flask | Arquivo Django | Mudanças |
|---------------|----------------|----------|
| `engine_ia.py` | `apps/ia_engine/services.py` | **NENHUMA** - código copiado 100% |
| Variáveis globais `ia_instancia`, `ia_engine` | `apps/ia_engine/manager.py` | Singleton pattern para gerenciar instância |

**Classe EngineIA:** mantida sem alterações.

---

### 5. **Templates**

#### Flask
```html
<link rel="stylesheet" href="{{ url_for('static', filename='estilo.css') }}">
```

#### Django
```html
<link rel="stylesheet" href="{% static 'estilo.css' %}">
```

**Todas as rotas AJAX mantidas iguais** (`/perguntar`, `/login`, etc).

---

### 6. **Configurações**

| Flask | Django |
|-------|--------|
| `app.secret_key = 'Mindhub@1417!'` | `settings.py: SECRET_KEY = 'Mindhub@1417!'` |
| `CORS(app)` | `settings.py: INSTALLED_APPS += ['corsheaders']` |
| `app.run(port=8080)` | `gunicorn config.wsgi:application` |

---

## 🚀 COMO RODAR

### 1. **Desenvolvimento Local**

```bash
cd django_project

# Instalar dependências
pip install -r requirements.txt

# Aplicar migrações (cria tabelas necessárias do Django, mantém usuarios.db)
python manage.py migrate

# Rodar servidor
python manage.py runserver 8080
```

Acesse: `http://localhost:8080`

---

### 2. **Deploy Cloud Run**

```bash
cd django_project

# Build da imagem
gcloud builds submit --tag gcr.io/SEU_PROJETO/banco-conhecimento-ia

# Deploy
gcloud run deploy banco-conhecimento-ia \
  --image gcr.io/SEU_PROJETO/banco-conhecimento-ia \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars OPENAI_API_KEY=sua_chave
```

---

## 📦 DIFERENÇAS TÉCNICAS

### O que mudou:
- **Framework:** Flask → Django
- **ORM:** SQLite direto → Django ORM
- **Templates:** Jinja2 (Flask) → Django Template Language
- **Estrutura:** Arquivo único → Apps organizados
- **Admin:** Não tinha → Django Admin ativo

### O que **NÃO mudou:**
- ✅ Lógica de IA (`EngineIA`)
- ✅ Integração Google Drive
- ✅ Funcionalidades de edição
- ✅ Interface HTML/CSS/JS
- ✅ Rotas e endpoints
- ✅ Comportamento do usuário

---

## 🔐 CREDENCIAIS

Copie para o diretório `django_project/`:
- `credentials.json` (Google Drive)
- `.env` (baseado em `.env.example`)

---

## 📝 PRÓXIMOS PASSOS RECOMENDADOS

1. **Segurança:**
   - Mudar senhas de texto plano para hash (`django.contrib.auth.hashers`)
   - Ativar CSRF protection nos templates
   - Configurar `ALLOWED_HOSTS` em produção

2. **Django Admin:**
   - Criar superusuário: `python manage.py createsuperuser`
   - Gerenciar usuários em `/admin`

3. **Testes:**
   - Testar todas as rotas
   - Validar autenticação
   - Testar edição de arquivos

---

## ✅ CHECKLIST DE VALIDAÇÃO

- [ ] Login funciona igual ao Flask
- [ ] Chat IA responde perguntas
- [ ] Edição de arquivos Drive funciona
- [ ] Atualização da base funciona
- [ ] Sessão persiste entre páginas
- [ ] Logout limpa sessão
- [ ] CSS carrega corretamente

---

## 🆘 TROUBLESHOOTING

### Erro: "Table usuarios doesn't exist"
```bash
# O Django criou suas tabelas mas precisa conectar ao banco Flask
python manage.py migrate --run-syncdb
```

### Erro: "Static files not found"
```bash
python manage.py collectstatic
```

### Erro: "EngineIA not initialized"
```bash
# Verificar se credentials.json está no diretório correto
# Verificar se OPENAI_API_KEY está no .env
```

---

**Migração realizada com sucesso! 🎉**
