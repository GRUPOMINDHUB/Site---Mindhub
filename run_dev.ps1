$ErrorActionPreference = "Stop"
cd "$PSScriptRoot"

if (-not (Test-Path ".venv")) {
    Write-Host "Creating virtual environment..."
    & "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe" -m venv .venv
}

Write-Host "Activating virtual environment..."
& .venv\Scripts\Activate.ps1

if (Test-Path "requirements.txt") {
    Write-Host "Checking dependencies..."
    pip install -r requirements.txt
}

Write-Host "Applying migrations..."
python manage.py migrate --noinput

Write-Host "Ensuring test users..."
python manage.py criar_acessos_teste

Write-Host "Ensuring initial data..."
python manage.py criar_dados_iniciais

Write-Host "Starting server..."
Write-Host "Acesse: http://127.0.0.1:8080/"
Write-Host "Login Monitor: monitor@mindhub.com / monitor123"
Write-Host "Login Admin: admin@mindhub.com / admin123"

python manage.py runserver 8080
