@echo off
chcp 65001 >nul
echo ========================================
echo   Site Mindhub - Servidor Local
echo ========================================
echo.

cd /d "%~dp0"

REM Cria .env com SQLite se não existir
if not exist .env (
    echo Criando .env para uso com SQLite...
    (
        echo USE_SQLITE=1
        echo DEBUG=True
        echo SECRET_KEY=Mindhub@1417!
    ) > .env
    echo .env criado.
    echo.
)

REM Garante variável para esta sessão
set USE_SQLITE=1

echo Aplicando migrações...
python manage.py migrate --noinput
if errorlevel 1 (
    echo ERRO nas migrações. Verifique se as dependências estão instaladas: pip install -r requirements.txt
    pause
    exit /b 1
)
echo.

echo Criando usuários de teste (admin, monitor, alunos)...
python manage.py criar_acessos_teste
echo.

echo Criando dados iniciais da trilha (mundos e steps)...
python manage.py criar_dados_iniciais
echo.

echo Iniciando servidor em http://127.0.0.1:8080/
echo.
echo Acessos: monitor@mindhub.com / monitor123
echo          admin@mindhub.com / admin123
echo.
python manage.py runserver 8080

pause
