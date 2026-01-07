import os
from dotenv import load_dotenv
from google import genai

load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")

if not api_key:
    print("ERRO: Chave não encontrada no .env")
else:
    try:
        client = genai.Client(api_key=api_key)
        print("Testando com o modelo 'gemini-flash-latest'...")

        # MUDAMOS AQUI: Usando o apelido genérico que apareceu na sua lista
        response = client.models.generate_content(
            model="gemini-flash-latest",
            contents="Quem é você? Responda em 1 frase curta."
        )

        print(f"\nRESPOSTA DA IA: {response.text}")
        
    except Exception as e:
        print(f"\nDeu erro: {e}")