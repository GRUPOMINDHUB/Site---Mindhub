import os
import json
import re
import unicodedata
import requests
from dotenv import load_dotenv

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaInMemoryUpload

from groq import Groq

# ================= CONFIG =================

load_dotenv()

SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/documents"
]

FOLDER_ID_RAIZ = "1QZ7yhuOBW0HPzzZmtlZs0XCBsxFId7pG"

MODEL_GROQ = "llama-3.3-70b-versatile"
MODEL_HF = "HuggingFaceH4/zephyr-7b-beta"

MAX_FILES_ANALISADOS = 400
MAX_ARQUIVOS_LIDOS = 8

IA_ESCOLHIDA = None  # groq | hf

# ================= AUTH GOOGLE =================

def conectar_google():
    creds = None

    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                "credentials.json", SCOPES
            )
            creds = flow.run_local_server(port=0)

        with open("token.json", "w") as token:
            token.write(creds.to_json())

    drive = build("drive", "v3", credentials=creds)
    docs = build("docs", "v1", credentials=creds)
    return drive, docs

drive, docs = conectar_google()

# ================= IA CLIENTS =================

groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
HF_API_KEY = os.getenv("HF_API_KEY")

# ================= UTIL =================

def normalizar(txt):
    if not txt:
        return ""
    txt = unicodedata.normalize("NFD", txt)
    txt = "".join(c for c in txt if unicodedata.category(c) != "Mn")
    txt = txt.lower()
    txt = txt.replace("&", " e ").replace("+", " e ")
    txt = re.sub(r"[^a-z0-9]", " ", txt)
    return " ".join(txt.split())

def similaridade(a, b):
    a = set(a.split())
    b = set(b.split())
    if not a or not b:
        return 0
    return len(a & b) / len(a | b)

# ================= DRIVE =================

def listar_itens(pasta_id, lista):
    q = f"'{pasta_id}' in parents and trashed=false"
    res = drive.files().list(
        q=q,
        fields="files(id,name,mimeType)",
        pageSize=1000
    ).execute()

    for f in res.get("files", []):
        lista.append(f)
        if "folder" in f["mimeType"]:
            listar_itens(f["id"], lista)

def ler_arquivo(file_id, mime):
    try:
        if "google-apps.document" in mime:
            txt = drive.files().export_media(
                fileId=file_id,
                mimeType="text/plain"
            ).execute()
            return txt.decode("utf-8")

        if "text" in mime or mime.endswith("json"):
            txt = drive.files().get_media(fileId=file_id).execute()
            return txt.decode("utf-8")
    except:
        return None

def atualizar_arquivo_texto(file_id, novo_texto):
    media = MediaInMemoryUpload(
        novo_texto.encode("utf-8"),
        mimetype="text/plain"
    )
    drive.files().update(
        fileId=file_id,
        media_body=media
    ).execute()

def atualizar_google_doc(doc_id, novo_texto):
    doc = docs.documents().get(documentId=doc_id).execute()
    body = doc.get("body", {}).get("content", [])

    end_index = 1
    for elem in body:
        if "endIndex" in elem:
            end_index = max(end_index, elem["endIndex"])

    requests = []

    if end_index > 1:
        requests.append({
            "deleteContentRange": {
                "range": {"startIndex": 1, "endIndex": end_index - 1}
            }
        })

    requests.append({
        "insertText": {
            "location": {"index": 1},
            "text": novo_texto
        }
    })

    docs.documents().batchUpdate(
        documentId=doc_id,
        body={"requests": requests}
    ).execute()

# ================= IA =================

def responder_ia(prompt):
    if IA_ESCOLHIDA == "groq":
        r = groq_client.chat.completions.create(
            model=MODEL_GROQ,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2
        )
        return r.choices[0].message.content

    if IA_ESCOLHIDA == "hf":
        url = f"https://api-inference.huggingface.co/models/{MODEL_HF}"
        headers = {
            "Authorization": f"Bearer {HF_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "inputs": prompt,
            "parameters": {
                "max_new_tokens": 800,
                "temperature": 0.2,
                "return_full_text": False
            }
        }

        r = requests.post(url, headers=headers, json=payload, timeout=60)
        r.raise_for_status()
        data = r.json()
        return data[0]["generated_text"]

    return "IA nao configurada"

def detectar_intencao(pergunta):
    p = normalizar(pergunta)
    for v in ["editar", "alterar", "corrigir", "mudar", "reescrever", "adicionar", "remover", "apagar"]:
        if v in p:
            return "EDITAR"
    return "CONSULTAR"

def agente(pergunta):
    print("\n🤖 pensando...")

    intencao = detectar_intencao(pergunta)
    pergunta_n = normalizar(pergunta)

    itens = []
    listar_itens(FOLDER_ID_RAIZ, itens)
    itens = itens[:MAX_FILES_ANALISADOS]

    rank = []
    for i in itens:
        rank.append((similaridade(pergunta_n, normalizar(i["name"])), i))

    rank.sort(reverse=True, key=lambda x: x[0])
    candidatos = rank[:MAX_ARQUIVOS_LIDOS]

    contexto = []

    for score, item in candidatos:
        entrada = {
            "nome": item["name"],
            "id": item["id"],
            "mime": item["mimeType"],
            "tipo": "PASTA" if "folder" in item["mimeType"] else "ARQUIVO"
        }

        if entrada["tipo"] == "ARQUIVO":
            txt = ler_arquivo(item["id"], item["mimeType"])
            if txt:
                entrada["conteudo"] = txt

        contexto.append(entrada)

    if intencao == "CONSULTAR":
        prompt = f"""
voce tem acesso a um drive.

pergunta:
{pergunta}

dados encontrados:
{contexto}

regras:
- responda da melhor forma possivel
- diga onde encontrou a informacao
- se nao existir, diga claramente
- nao invente nada
"""
        print("\n🧠 resposta:")
        print(responder_ia(prompt))
        return

    for item in contexto:
        if item["tipo"] == "ARQUIVO" and "conteudo" in item:
            prompt = f"""
voce deve editar um arquivo.

instrucao:
{pergunta}

conteudo atual:
{item["conteudo"]}

retorne APENAS o novo conteudo completo.
"""
            novo = responder_ia(prompt)

            if "google-apps.document" in item["mime"]:
                atualizar_google_doc(item["id"], novo)
            else:
                atualizar_arquivo_texto(item["id"], novo)

            print(f"\n✏️ arquivo '{item['nome']}' editado com sucesso.")
            return

    print("\n⚠️ nenhum arquivo encontrado para edicao.")

# ================= MAIN =================

def main():
    global IA_ESCOLHIDA

    print("=== AGENTE IA DRIVE ===")
    print("escolha a IA:")
    print("1 - Groq")
    print("2 - Hugging Face")

    op = input("> ").strip()

    IA_ESCOLHIDA = "groq" if op == "1" else "hf"

    print(f"\n✅ usando IA: {IA_ESCOLHIDA.upper()}")

    while True:
        q = input("\n👤 pergunta (ou sair): ")
        if q.lower() in ["sair", "exit"]:
            break
        if q.strip():
            agente(q)

if __name__ == "__main__":
    main()
