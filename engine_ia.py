import os
import io
from dotenv import load_dotenv
from google.oauth2 import service_account
from googleapiclient.discovery import build
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

                        if ext == '.pdf':
                            loader = PyPDFLoader(temp_path)
                        elif ext == '.docx':
                            loader = Docx2txtLoader(temp_path)
                        else:
                            loader = UnstructuredExcelLoader(temp_path, mode="elements")

                        docs = loader.load()
                        for d in docs:
                            d.metadata.update({
                                "setor": path_nome.split('/')[-1],
                                "origem": nome_arquivo
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
        5. FORMATAÇÃO: Use quebras de linha, listas (bullet points) e negrito para organizar as informações e facilitar a leitura, evite ficar usando "**", e permita-se usar emojis.
        6. O CONSELHO ESTRATEGICO TEM QUE CONSOLIDAR COM A PERGUNTA DO USUARIO, PROIBIDO CONSELHOS SEM ESTAR LINKADO A PERGUNTA DO USUARIO
        CONTEXTO:
        {context}

        PERGUNTA DO USUÁRIO:
        {question}

        RESPOSTA:
        """

        return ConversationalRetrievalChain.from_llm(
            llm=ChatOpenAI(model="gpt-4o", temperature=0, api_key=os.getenv("OPENAI_API_KEY")),
            retriever=vector_db.as_retriever(search_kwargs={"k": 40}),
            memory=ConversationBufferMemory(memory_key="chat_history", return_messages=True, output_key="answer"),
            combine_docs_chain_kwargs={"prompt": PromptTemplate(template=template, input_variables=["context", "question"])}
        )