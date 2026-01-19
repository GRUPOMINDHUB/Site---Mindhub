FROM python:3.10-slim

WORKDIR /app

# Instala dependências do sistema necessárias
RUN apt-get update && apt-get install -y \
    build-essential \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Copia apenas o requirements primeiro para otimizar o cache
COPY requirements.txt .

# Instala as dependências permitindo que o pip resolva os conflitos
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copia o restante dos arquivos
COPY . .

# Expõe a porta que o Cloud Run exige
EXPOSE 8080

# Garante que o servidor rode na porta 8080
CMD ["python", "servidor.py"]