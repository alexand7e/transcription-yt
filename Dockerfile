# Use uma imagem base oficial do Python
FROM python:3.10-slim

# Define o diretório de trabalho no contêiner
WORKDIR /app

# Instala o FFmpeg (essencial para pydub)
# E git (yt-dlp pode precisar em alguns casos para baixar informações)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copia o arquivo de dependências primeiro para aproveitar o cache do Docker
COPY requirements.txt ./

# Instala as dependências Python
RUN pip install --no-cache-dir -r requirements.txt

# Copia o restante do código da aplicação para o diretório de trabalho
COPY . .

# Expõe a porta que o Streamlit usa por padrão
EXPOSE 8501

# Define variáveis de ambiente para o Streamlit (opcional, mas bom para configuração)
ENV STREAMLIT_SERVER_PORT=8501
ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0
ENV STREAMLIT_SERVER_HEADLESS=true

# Comando para rodar a aplicação Streamlit quando o contêiner iniciar
# O --server.enableCORS=false pode ser útil dependendo da configuração com Traefik,
# mas comece sem ele e adicione se necessário.
# O --server.fileWatcherType=none desabilita o observador de arquivos,
# o que é bom para produção e pode economizar recursos.
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0", "--server.fileWatcherType=none"]