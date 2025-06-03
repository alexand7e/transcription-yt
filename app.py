import streamlit as st
from yt_dlp import YoutubeDL
from pydub import AudioSegment
import speech_recognition as sr
import os
import uuid

# --- Funções Auxiliares ---

def baixar_audio_youtube(url, output_path="audio_temp"):
    """Baixa o áudio de um URL do YouTube e salva como MP3."""
    if not os.path.exists(output_path):
        os.makedirs(output_path)

    # Gera um nome de arquivo único para evitar conflitos
    filename = f"{uuid.uuid4()}.mp3"
    filepath = os.path.join(output_path, filename)

    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'outtmpl': os.path.join(output_path, '%(id)s.%(ext)s'), # Usar ID do vídeo para nome temporário
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
    }
    try:
        with YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)
            downloaded_file_path_template = ydl.prepare_filename(info_dict)
            # O nome do arquivo real pode variar um pouco (ex: .webm antes da conversão)
            # Precisamos encontrar o arquivo .mp3 resultante
            base_name = info_dict.get('id', 'audio')
            possible_mp3_path = os.path.join(output_path, f"{base_name}.mp3")

            if os.path.exists(possible_mp3_path):
                os.rename(possible_mp3_path, filepath) # Renomeia para o nome único
                st.session_state.messages.append(f"Áudio baixado e convertido para MP3: {filepath}")
                return filepath
            else:
                # Tenta encontrar o arquivo baixado se o nome exato não corresponder
                for f in os.listdir(output_path):
                    if f.startswith(base_name) and f.endswith('.mp3'):
                        os.rename(os.path.join(output_path, f), filepath)
                        st.session_state.messages.append(f"Áudio baixado e convertido para MP3: {filepath}")
                        return filepath
                st.session_state.error_messages.append(f"Erro: Não foi possível encontrar o arquivo MP3 convertido para {url}.")
                return None
    except Exception as e:
        st.session_state.error_messages.append(f"Erro ao baixar/converter áudio de {url}: {str(e)}")
        return None

def particionar_audio(caminho_audio, tamanho_chunk_ms=60000, overlap_ms=5000):
    """Particiona o áudio em chunks menores com sobreposição."""
    if not caminho_audio or not os.path.exists(caminho_audio):
        st.session_state.error_messages.append(f"Arquivo de áudio não encontrado: {caminho_audio}")
        return []

    try:
        audio = AudioSegment.from_mp3(caminho_audio)
    except Exception as e:
        st.session_state.error_messages.append(f"Erro ao carregar o arquivo MP3 ({caminho_audio}): {e}")
        return []

    chunks = []
    duracao_total_ms = len(audio)
    inicio_ms = 0
    chunk_id = 0
    temp_chunk_dir = "audio_chunks_temp"
    if not os.path.exists(temp_chunk_dir):
        os.makedirs(temp_chunk_dir)

    while inicio_ms < duracao_total_ms:
        fim_ms = min(inicio_ms + tamanho_chunk_ms, duracao_total_ms)
        chunk = audio[inicio_ms:fim_ms]
        nome_chunk = os.path.join(temp_chunk_dir, f"chunk_{uuid.uuid4()}_{chunk_id}.wav") # SpeechRecognition prefere WAV
        chunk.export(nome_chunk, format="wav")
        chunks.append(nome_chunk)
        st.session_state.messages.append(f"Chunk {chunk_id + 1} criado: {nome_chunk}")
        chunk_id += 1
        if fim_ms == duracao_total_ms:
            break
        inicio_ms += (tamanho_chunk_ms - overlap_ms) # Avança com sobreposição

    return chunks

def transcrever_chunk_audio(caminho_chunk):
    """Transcreve um chunk de áudio usando o Google Speech Recognition."""
    r = sr.Recognizer()
    try:
        with sr.AudioFile(caminho_chunk) as source:
            audio_data = r.record(source)  # lê o arquivo de áudio inteiro
        # Reconhecimento de fala usando o Google Web Speech API
        texto = r.recognize_google(audio_data, language='pt-BR')
        st.session_state.messages.append(f"Transcrição do chunk {os.path.basename(caminho_chunk)}: Sucesso")
        return texto
    except sr.UnknownValueError:
        st.session_state.warning_messages.append(f"Google Speech Recognition não conseguiu entender o áudio do chunk: {os.path.basename(caminho_chunk)}")
        return ""
    except sr.RequestError as e:
        st.session_state.error_messages.append(f"Não foi possível solicitar resultados do serviço Google Speech Recognition para {os.path.basename(caminho_chunk)}; {e}")
        return ""
    except Exception as e:
        st.session_state.error_messages.append(f"Erro desconhecido na transcrição do chunk {os.path.basename(caminho_chunk)}: {e}")
        return ""

def limpar_arquivos_temporarios(paths_arquivos, diretorios_temp=["audio_temp", "audio_chunks_temp"]):
    """Remove arquivos e diretórios temporários."""
    for path in paths_arquivos:
        try:
            if path and os.path.exists(path):
                os.remove(path)
        except Exception as e:
            st.session_state.warning_messages.append(f"Não foi possível remover o arquivo temporário {path}: {e}")

    for diretorio in diretorios_temp:
        if os.path.exists(diretorio):
            for item in os.listdir(diretorio):
                item_path = os.path.join(diretorio, item)
                try:
                    if os.path.isfile(item_path):
                        os.remove(item_path)
                except Exception as e:
                    st.session_state.warning_messages.append(f"Não foi possível remover o arquivo temporário {item_path}: {e}")
            # Opcional: remover o diretório em si se não for mais necessário e estiver vazio
            # try:
            #     if not os.listdir(diretorio): # Checa se está vazio
            #         os.rmdir(diretorio)
            # except Exception as e:
            #     st.session_state.warning_messages.append(f"Não foi possível remover o diretório temporário {diretorio}: {e}")


# --- Interface Streamlit ---

st.set_page_config(page_title="Transcrição de Vídeos do YouTube ▶️📝", layout="wide")

st.title("Transcrição de Áudio de Vídeos do YouTube 🎙️➡️📄")
st.markdown("Insira um ou mais URLs do YouTube (um por linha) para baixar o áudio, convertê-lo para MP3, particioná-lo e transcrevê-lo usando o Google Speech Recognition.")

# Inicializa o estado da sessão para mensagens
if 'messages' not in st.session_state:
    st.session_state.messages = []
if 'error_messages' not in st.session_state:
    st.session_state.error_messages = []
if 'warning_messages' not in st.session_state:
    st.session_state.warning_messages = []
if 'transcricoes_finais' not in st.session_state:
    st.session_state.transcricoes_finais = {}

urls_input = st.text_area("URLs do YouTube (um por linha):", height=150, key="urls_input_area")

col1, col2 = st.columns(2)

with col1:
    tamanho_chunk_min = st.number_input("Duração do Chunk (segundos):", min_value=10, max_value=300, value=60, step=5,
                                        help="Duração de cada segmento de áudio para transcrição. Valores menores podem ser mais rápidos para a API, mas geram mais requisições.")
with col2:
    overlap_seg = st.number_input("Sobreposição dos Chunks (segundos):", min_value=0, max_value=30, value=5, step=1,
                                 help="Quanto do final de um chunk deve se sobrepor ao início do próximo, para evitar cortes de palavras.")

tamanho_chunk_ms = tamanho_chunk_min * 1000
overlap_ms = overlap_seg * 1000


if st.button("Transcrever Áudios", type="primary", use_container_width=True):
    st.session_state.messages = []
    st.session_state.error_messages = []
    st.session_state.warning_messages = []
    st.session_state.transcricoes_finais = {}
    urls = [url.strip() for url in urls_input.splitlines() if url.strip()]

    if not urls:
        st.warning("Por favor, insira pelo menos um URL do YouTube.")
    else:
        progress_bar_geral = st.progress(0, text="Progresso Geral")
        status_geral = st.empty()
        arquivos_para_limpar = []

        for i, url in enumerate(urls):
            status_geral.info(f"Processando URL {i+1}/{len(urls)}: {url}")
            st.session_state.messages.append(f"--- Iniciando processamento para: {url} ---")
            caminho_audio_mp3 = None # Inicializa para garantir que existe no escopo de limpeza

            with st.spinner(f"Baixando e convertendo áudio de '{url}'..."):
                caminho_audio_mp3 = baixar_audio_youtube(url)
                if caminho_audio_mp3:
                    arquivos_para_limpar.append(caminho_audio_mp3)

            if caminho_audio_mp3:
                with st.spinner(f"Particionando áudio de '{url}'..."):
                    chunks_audio = particionar_audio(caminho_audio_mp3, tamanho_chunk_ms, overlap_ms)
                    arquivos_para_limpar.extend(chunks_audio)

                if chunks_audio:
                    transcricao_completa = []
                    st.session_state.messages.append(f"Total de {len(chunks_audio)} chunks para transcrever de '{url}'.")
                    progress_bar_url = st.progress(0, text=f"Transcrevendo chunks de {url}")

                    for j, chunk_path in enumerate(chunks_audio):
                        status_geral.info(f"Processando URL {i+1}/{len(urls)}: {url} (Transcrevendo chunk {j+1}/{len(chunks_audio)})")
                        with st.spinner(f"Transcrevendo chunk {j+1}/{len(chunks_audio)} de '{url}'..."):
                            texto_chunk = transcrever_chunk_audio(chunk_path)
                            if texto_chunk:
                                transcricao_completa.append(texto_chunk)
                        progress_bar_url.progress((j + 1) / len(chunks_audio), text=f"Transcrevendo chunks de {url} ({j+1}/{len(chunks_audio)})")

                    if transcricao_completa:
                        st.session_state.transcricoes_finais[url] = " ".join(transcricao_completa)
                        st.session_state.messages.append(f"Transcrição final para {url} concluída.")
                    else:
                        st.session_state.error_messages.append(f"Nenhuma transcrição pôde ser gerada para {url}.")
                    progress_bar_url.empty() # Limpa a barra de progresso específica do URL
                else:
                    st.session_state.error_messages.append(f"Não foi possível particionar o áudio de {url}.")
            else:
                st.session_state.error_messages.append(f"Download do áudio falhou para {url}. Verifique o URL e tente novamente.")

            progress_bar_geral.progress((i + 1) / len(urls), text="Progresso Geral")

        status_geral.success("Processamento concluído!")
        progress_bar_geral.empty() # Limpa a barra de progresso geral

        # Limpeza final
        limpar_arquivos_temporarios(arquivos_para_limpar)
        st.session_state.messages.append("Limpeza de arquivos temporários concluída.")


# --- Exibição de Logs e Resultados ---
st.divider()
st.subheader("Resultados da Transcrição")

if not st.session_state.transcricoes_finais and not st.session_state.error_messages and not st.session_state.warning_messages and not st.session_state.messages:
    st.caption("Aguardando URLs para processar...")
elif not st.session_state.transcricoes_finais and st.session_state.error_messages:
    st.info("Nenhuma transcrição foi gerada com sucesso. Verifique os logs de erro abaixo.")
elif not st.session_state.transcricoes_finais and not st.session_state.error_messages and (st.session_state.warning_messages or st.session_state.messages):
     st.info("Processamento concluído, mas nenhuma transcrição foi gerada. Verifique os logs abaixo.")


for url, transcricao in st.session_state.transcricoes_finais.items():
    with st.expander(f"Transcrição para: {url}", expanded=True):
        st.markdown(transcricao)
        st.download_button(
            label=f"Baixar Transcrição (.txt) - {url.split('v=')[-1] if '?v=' in url else url.split('/')[-1]}",
            data=transcricao,
            file_name=f"transcricao_{url.split('v=')[-1] if '?v=' in url else url.split('/')[-1]}.txt",
            mime="text/plain"
        )

# Abas para logs
tab_logs, tab_erros, tab_avisos = st.tabs(["📋 Logs de Processamento", "🛑 Logs de Erro", "⚠️ Logs de Aviso"])

with tab_logs:
    if st.session_state.messages:
        st.markdown("##### Mensagens de Processamento:")
        log_container_msg = st.container(height=200)
        for msg in reversed(st.session_state.messages): # Mostrar mais recentes primeiro
            log_container_msg.caption(msg)
    else:
        st.caption("Nenhuma mensagem de processamento.")

with tab_erros:
    if st.session_state.error_messages:
        st.markdown("##### Mensagens de Erro:")
        log_container_err = st.container(height=200)
        for err_msg in reversed(st.session_state.error_messages):
            log_container_err.error(err_msg)
    else:
        st.caption("Nenhum erro reportado.")

with tab_avisos:
    if st.session_state.warning_messages:
        st.markdown("##### Mensagens de Aviso:")
        log_container_warn = st.container(height=200)
        for warn_msg in reversed(st.session_state.warning_messages):
            log_container_warn.warning(warn_msg)
    else:
        st.caption("Nenhum aviso reportado.")

# Limpar logs manualmente, se desejado
if st.button("Limpar Logs e Resultados", use_container_width=True):
    st.session_state.messages = []
    st.session_state.error_messages = []
    st.session_state.warning_messages = []
    st.session_state.transcricoes_finais = {}
    # Limpa os diretórios temporários também, caso existam e não tenham sido limpos
    limpar_arquivos_temporarios([], ["audio_temp", "audio_chunks_temp"])
    st.rerun()

st.markdown("---")
st.caption("Desenvolvido com Streamlit, yt-dlp, Pydub e SpeechRecognition.")