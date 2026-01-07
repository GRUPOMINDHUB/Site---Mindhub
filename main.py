import os.path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# CONFIGURAÇÕES
# Escopo de permissão: Ler e Escrever (Full Access)
SCOPES = ['https://www.googleapis.com/auth/drive']
# O ID da pasta "BANCO DE CONHECIMENTO" que você mandou
FOLDER_ID = '1QZ7yhuOBW0HPzzZmtlZs0XCBsxFId7pG'

def main():
    creds = None
    
    # 1. Verifica se já existe login salvo (token.json)
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    
    # 2. Se não tiver login válido, abre o navegador para logar
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except:
                os.remove('token.json')
                return main()
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            # Abre o navegador e espera você clicar em "Permitir"
            creds = flow.run_local_server(port=0)
        
        # Salva o login para a próxima vez não precisar de navegador
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    try:
        # 3. Conecta ao Google Drive
        service = build('drive', 'v3', credentials=creds)
        print("Conexão realizada! Buscando arquivos...")

        # 4. Lista o que tem na pasta específica
        results = service.files().list(
            q=f"'{FOLDER_ID}' in parents and trashed=false",
            fields="files(id, name, mimeType)"
        ).execute()
        
        items = results.get('files', [])

        if not items:
            print('A pasta está vazia ou não foi encontrada.')
        else:
            print(f'\n--- ARQUIVOS ENCONTRADOS ({len(items)}) ---')
            for item in items:
                print(f"[ARQUIVO] {item['name']} \n   -> ID: {item['id']}")
            print('-------------------------------------------')

    except Exception as e:
        print(f"\nERRO: {e}")
        print("Dica: Verifique se o arquivo credentials.json está na pasta e se seu usuário tem acesso à pasta do Drive.")

if __name__ == '__main__':
    main()