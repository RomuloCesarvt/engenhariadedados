"""
Autoriza o app da RD Station Marketing e grava as credenciais OAuth no engine/.env.

Uso, na raiz do repositório:
    python engine/rd_oauth.py

Antes, crie um app em https://appstore.rdstation.com/pt-BR/publisher com a URL de callback
    http://localhost:8791/callback

O client_secret e o refresh_token vão direto para o engine/.env e nunca aparecem na tela.
"""

import getpass
import http.server
import os
import re
import secrets
import sys
import threading
import urllib.parse
import webbrowser

import httpx

ENV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
PORTA = 8791
CALLBACK = f"http://localhost:{PORTA}/callback"
AUTORIZAR = "https://api.rd.services/auth/dialog"
TOKEN = "https://api.rd.services/auth/token"
ESPERA_SEGUNDOS = 300


def gravar_env(valores: dict) -> None:
    """Atualiza (ou acrescenta) as chaves no engine/.env sem mexer nas demais linhas."""
    conteudo = open(ENV_PATH, encoding="utf-8").read() if os.path.exists(ENV_PATH) else ""
    for chave, valor in valores.items():
        linha = f'{chave}="{valor}"'
        if re.search(rf"^{chave}=", conteudo, flags=re.M):
            conteudo = re.sub(rf"^{chave}=.*$", lambda _m: linha, conteudo, count=1, flags=re.M)
        else:
            conteudo = conteudo.rstrip("\n") + "\n" + linha + "\n"
    with open(ENV_PATH, "w", encoding="utf-8") as f:
        f.write(conteudo)


def capturar_codigo(state_esperado: str):
    """Sobe um servidor local só para receber o redirecionamento da RD e extrair o código."""
    resultado = {}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            url = urllib.parse.urlparse(self.path)
            if url.path != "/callback":
                self.send_response(404)
                self.end_headers()
                return
            q = urllib.parse.parse_qs(url.query)
            if q.get("state", [None])[0] != state_esperado:
                resultado["erro"] = "state inválido (a resposta não corresponde a esta autorização)"
            elif "code" in q:
                resultado["code"] = q["code"][0]
            else:
                resultado["erro"] = q.get("error_description", q.get("error", ["autorização negada"]))[0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            mensagem = "Autorização recebida. Pode voltar ao terminal." if "code" in resultado else f"Falhou: {resultado.get('erro')}"
            self.wfile.write(f"<p style='font-family:sans-serif'>{mensagem}</p>".encode("utf-8"))

        def log_message(self, *args):
            pass

    try:
        servidor = http.server.HTTPServer(("127.0.0.1", PORTA), Handler)
    except OSError:
        return None, f"porta {PORTA} ocupada"

    servidor.timeout = 1
    fim = threading.Event()
    threading.Timer(ESPERA_SEGUNDOS, fim.set).start()
    while not fim.is_set() and "code" not in resultado and "erro" not in resultado:
        servidor.handle_request()
    servidor.server_close()
    return resultado.get("code"), resultado.get("erro")


def main() -> int:
    print("Autorização da RD Station Marketing\n")
    print(f"O app precisa ter a URL de callback: {CALLBACK}\n")
    try:
        from dotenv import load_dotenv

        load_dotenv(ENV_PATH)
    except ImportError:
        pass
    client_id = os.getenv("RD_STATION_CLIENT_ID", "").strip()
    client_secret = os.getenv("RD_STATION_CLIENT_SECRET", "").strip()
    if client_id and client_secret:
        print("Usando RD_STATION_CLIENT_ID e RD_STATION_CLIENT_SECRET do engine/.env.")
    else:
        try:
            client_id = input("Client ID do app: ").strip()
            client_secret = getpass.getpass("Client Secret (não aparece ao digitar): ").strip()
        except EOFError:
            print("Preencha RD_STATION_CLIENT_ID e RD_STATION_CLIENT_SECRET no engine/.env ou rode o script num terminal.")
            return 1
    if not client_id or not client_secret:
        print("Client ID e Client Secret são obrigatórios.")
        return 1

    state = secrets.token_urlsafe(16)
    url = f"{AUTORIZAR}?" + urllib.parse.urlencode({"client_id": client_id, "redirect_uri": CALLBACK, "state": state})
    print("\nAbrindo o navegador para você autorizar a conta da RD...")
    print(f"Se não abrir, acesse:\n{url}\n")
    webbrowser.open(url)

    code, erro = capturar_codigo(state)
    if not code:
        if erro:
            print(f"Não foi possível capturar automaticamente ({erro}).")
        try:
            colado = input("Cole aqui a URL completa para onde a RD redirecionou depois de autorizar: ").strip()
        except EOFError:
            print("Tempo esgotado sem autorização. Rode o script de novo e autorize na tela da RD.")
            return 1
        q = urllib.parse.parse_qs(urllib.parse.urlparse(colado).query)
        code = q.get("code", [None])[0]
        if not code:
            print("A URL não contém o código de autorização.")
            return 1

    resposta = httpx.post(TOKEN, json={"client_id": client_id, "client_secret": client_secret, "code": code}, timeout=30)
    if resposta.status_code != 200:
        print(f"A RD recusou a troca do código (HTTP {resposta.status_code}). Confira o Client ID, o Secret e a URL de callback.")
        return 1

    dados = resposta.json()
    gravar_env({
        "RD_STATION_CLIENT_ID": client_id,
        "RD_STATION_CLIENT_SECRET": client_secret,
        "RD_STATION_REFRESH_TOKEN": dados["refresh_token"],
    })
    print("\nCredenciais gravadas no engine/.env.")

    teste = httpx.get(
        "https://api.rd.services/platform/segmentations",
        headers={"Authorization": f"Bearer {dados['access_token']}"},
        timeout=30,
    )
    if teste.status_code == 200:
        segs = teste.json().get("segmentations", [])
        print(f"Conexão confirmada: {len(segs)} segmentação(ões) encontradas na conta.")
        return 0
    print(f"As credenciais foram gravadas, mas a leitura de teste respondeu HTTP {teste.status_code}.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
