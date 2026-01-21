import os
import io
import pandas as pd
from docx import Document
from dotenv import load_dotenv
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload
import os
from io import BytesIO
from docx import Document
import pandas as pd
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_community.vectorstores import FAISS
from langchain_community.document_loaders import PyPDFLoader, UnstructuredExcelLoader, Docx2txtLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

# AJUSTE PARA LANGCHAIN v1.0.5 (Usando o pacote classic)
from langchain_classic.chains import ConversationalRetrievalChain
from langchain_classic.memory import ConversationBufferMemory
from langchain_core.prompts import PromptTemplate


load_dotenv()

PASTA_DRIVE_ID = "1KHOOf3uLPaWHnDahcRNl1gIYhMT8v4rE"
ARQUIVO_CREDENCIAIS = "credentials.json"

class EngineIA:
    def __init__(self):
        if not os.path.exists(ARQUIVO_CREDENCIAIS):
            print(f"❌ ERRO: Arquivo '{ARQUIVO_CREDENCIAIS}' não encontrado.")
            raise FileNotFoundError(ARQUIVO_CREDENCIAIS)

        self.creds = service_account.Credentials.from_service_account_file(ARQUIVO_CREDENCIAIS)
        self.service = build("drive", "v3", credentials=self.creds)
        # No seu __init__
        self.embeddings = OpenAIEmbeddings(api_key=os.getenv("OPENAI_API_KEY"))

    def carregar_arquivos_recursivo(self, folder_id, path_nome="empresa"):
        documentos_finais = []
        page_token = None
        
        while True:
            query = f"'{folder_id}' in parents and trashed = false"
            results = self.service.files().list(
                q=query, 
                fields="nextPageToken, files(id, name, mimeType)", 
                pageToken=page_token
            ).execute()
            
            for f in results.get('files', []):
                if f['mimeType'] == 'application/vnd.google-apps.folder':
                    print(f"📁 Acessando pasta: {path_nome}/{f['name']}")
                    documentos_finais.extend(self.carregar_arquivos_recursivo(f['id'], f"{path_nome}/{f['name']}"))
                    continue

                nome_arquivo = f['name']
                ext = os.path.splitext(nome_arquivo)[1].lower()
                mime = f['mimeType']
                export_mime = None

                if mime == 'application/vnd.google-apps.document':
                    export_mime = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
                    ext = '.docx'
                elif mime == 'application/vnd.google-apps.spreadsheet':
                    export_mime = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                    ext = '.xlsx'

                if ext in ['.pdf', '.docx', '.xlsx', '.xls'] or export_mime:
                    print(f"📄 Lendo: {nome_arquivo}")
                    temp_path = f"temp_{f['id']}{ext}"
                    
                    try:
                        if export_mime:
                            request_media = self.service.files().export_media(fileId=f['id'], mimeType=export_mime)
                        else:
                            request_media = self.service.files().get_media(fileId=f['id'])
                        
                        fh = io.BytesIO()
                        downloader = MediaIoBaseDownload(fh, request_media)
                        done = False
                        while not done:
                            _, done = downloader.next_chunk()
                        
                        with open(temp_path, "wb") as out:
                            out.write(fh.getvalue())

                        # Define o Loader correto
                        if ext == '.pdf':
                            loader = PyPDFLoader(temp_path)
                        elif ext == '.docx':
                            loader = Docx2txtLoader(temp_path)
                        else:
                            loader = UnstructuredExcelLoader(temp_path, mode="elements")

                        # CARREGA E INJETA O ID (Aqui é o lugar certo!)
                        docs = loader.load()
                        for d in docs:
                            # Injeta os dados técnicos no texto para a IA ler
                            d.page_content = f"ARQUIVO_ID: {f['id']}\nNOME_ARQUIVO: {nome_arquivo}\n{d.page_content}"
                            
                            d.metadata.update({
                                "setor": path_nome.split('/')[-1],
                                "origem": nome_arquivo,
                                "file_id": f['id']
                            })
                        documentos_finais.extend(docs)
                        
                    except Exception as e:
                        print(f"❌ Erro em {nome_arquivo}: {e}")
                    finally:
                        if os.path.exists(temp_path):
                            os.remove(temp_path)
            
            page_token = results.get('nextPageToken')
            if not page_token: break
                
        return documentos_finais

    def inicializar_sistema(self):
        print("🚀 Inicializando Engine de IA...")
        documentos = self.carregar_arquivos_recursivo(PASTA_DRIVE_ID)
        
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1500, chunk_overlap=100)
        chunks = text_splitter.split_documents(documentos)
        vector_db = FAISS.from_documents(chunks, self.embeddings)

        template = """
        Você é um Mediador estratégico do Grupo Mindhub, especializado em auditoria e gestão de dados corporativos.

        DIRETRIZES DE RESPOSTA:
        1. INTERPRETAÇÃO FLEXÍVEL: Entenda que termos como 'alunos', 'inscritos', 'clientes' ou 'pessoas' referem-se às entidades e empresas listadas nas fichas do Google Drive.
        2. FIDELIDADE AOS DADOS: Para perguntas diretas, responda estritamente com base nas informações encontradas no CONTEXTO.
        3. DISTINÇÃO DE CONSELHOS: Se você identificar uma oportunidade de melhoria ou algo não solicitado que agregue valor, você deve obrigatoriamente iniciar esse parágrafo com o rótulo "CONSELHO ESTRATÉGICO:".
        4. SEPARAÇÃO DE FATOS: Mantenha os dados técnicos separados das sugestões.
        5. FORMATAÇÃO: Use quebras de linha, listas (bullet points) e negrito para organizar as informações e facilitar a leitura, evite ficar usando **, e permita-se usar emojis.
        6. O CONSELHO ESTRATEGICO TEM QUE CONSOLIDAR COM A PERGUNTA DO USUARIO, PROIBIDO CONSELHOS SEM ESTAR LINKADO A PERGUNTA DO USUARIO
        7. CAPACIDADE DE EDIÇÃO: Você deve decidir como o arquivo será alterado com base no pedido do usuário.
        - Se o usuário pedir para APAGAR TUDO ou LIMPAR: Use o comando [AÇÃO: LIMPAR]
        - Se o usuário pedir para MUDAR algo específico (ex: trocar email): Use o comando [AÇÃO: SUBSTITUIR | DE: texto_antigo | PARA: texto_novo]
        - Se o usuário apenas quiser ADICIONAR algo: Use o comando [AÇÃO: ADICIONAR]

        Formate EXATAMENTE assim na sua sugestão:
            [SUGESTÃO DE EDIÇÃO]
            Arquivo: {{nome_do_arquivo}}
            ID: {{id_do_arquivo}}
            Alteração: [AÇÃO: ... | DETALHES: ...]".

        CONTEXTO:
        {context}

        PERGUNTA DO USUÁRIO:
        {question}

        RESPOSTA:
        """

        return ConversationalRetrievalChain.from_llm(
            llm=ChatOpenAI(model="gpt-4o", temperature=0, api_key=os.getenv("OPENAI_API_KEY")),
            retriever=vector_db.as_retriever(search_kwargs={"k": 100}),
            memory=ConversationBufferMemory(memory_key="chat_history", return_messages=True, output_key="answer"),
            combine_docs_chain_kwargs={"prompt": PromptTemplate(template=template, input_variables=["context", "question"])}
        )
    
    def editar_e_salvar_no_drive(self, file_id, nome_arquivo, novas_infos):
        try:
            ext = os.path.splitext(nome_arquivo)[1].lower()
            temp_path = os.path.join("/tmp", f"temp_edit_{file_id}{ext}")
            
            # 1. BAIXA O ARQUIVO
            # Tentativa de download direto
            try:
                request = self.service.files().get_media(fileId=file_id)
                fh = BytesIO()
                downloader = MediaIoBaseDownload(fh, request)
                done = False
                while not done:
                    _, done = downloader.next_chunk()
            except Exception:
                # Se falhar, tenta exportar (caso seja um Google Doc nativo)
                mime_export = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' if ext == '.docx' else 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                request = self.service.files().export_media(fileId=file_id, mimeType=mime_export)
                fh = BytesIO()
                downloader = MediaIoBaseDownload(fh, request)
                done = False
                while not done:
                    _, done = downloader.next_chunk()

            # Salva o conteúdo baixado no arquivo temporário para as bibliotecas lerem
            with open(temp_path, 'wb') as f:
                f.write(fh.getbuffer())

            # 2. EDITA POR TIPO
            mime_type = ""
            if ext in ['.xlsx', '.xls']:
                mime_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                df = pd.read_excel(temp_path)
                # Adiciona nova linha
                nova_linha = pd.DataFrame([{"Auditoria": "MindLink", "Info": novas_infos}])
                df = pd.concat([df, nova_linha], ignore_index=True)
                df.to_excel(temp_path, index=False)
            elif ext == '.docx':
                mime_type = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
                doc = Document(temp_path)
                
                # 1. TOMADA DE DECISÃO: LIMPAR TUDO
                if "[AÇÃO: LIMPAR]" in novas_infos.upper():
                    # Esvazia todos os parágrafos existentes
                    for p in doc.paragraphs:
                        p.text = ""
                    # Adiciona uma marca d'água de que foi limpo (opcional)
                    doc.add_paragraph("Arquivo limpo via MindLink conforme solicitado.")

                # 2. TOMADA DE DECISÃO: SUBSTITUIR ESPECÍFICO
                elif "AÇÃO: SUBSTITUIR" in novas_infos.upper():
                    try:
                        # Extrai os termos (Ex: [AÇÃO: SUBSTITUIR | DE: x@a.com | PARA: y@b.com])
                        termo_antigo = novas_infos.split("| DE:")[1].split("| PARA:")[0].strip()
                        termo_novo = novas_infos.split("| PARA:")[1].replace("]", "").strip()
                        
                        # Percorre o documento trocando o texto
                        for p in doc.paragraphs:
                            if termo_antigo in p.text:
                                p.text = p.text.replace(termo_antigo, termo_novo)
                    except Exception:
                        # Se a IA errar o formato, ele apenas adiciona para não perder o dado
                        doc.add_paragraph(f"\n[Falha na substituição, dado adicionado]: {novas_infos}")

                # 3. TOMADA DE DECISÃO: APENAS ADICIONAR (Padrão)
                else:
                    doc.add_paragraph(f"\n--- ATUALIZAÇÃO MINDLINK ---\n{novas_infos}")

                doc.save(temp_path)
            # 3. FAZ O UPLOAD (O ERRO ESTAVA AQUI)
            # É necessário abrir o arquivo em modo binário ('rb') para o upload
            with open(temp_path, 'rb') as f:
                media = MediaIoBaseUpload(f, mimetype=mime_type, resumable=True)
                self.service.files().update(
                    fileId=file_id,
                    media_body=media
                ).execute()
            
            # Limpeza
            if os.path.exists(temp_path): 
                os.remove(temp_path)
            return True

        except Exception as e:
            # IMPORTANTE: Isso enviará o erro real para o seu Log do Cloud Run
            print(f"ERRO CRÍTICO NA GRAVAÇÃO: {str(e)}")
            return False