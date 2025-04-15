from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from typing import List, Optional
import time
import os
import json
import requests
import yaml
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware


app = FastAPI()

CONFIG_PATH = "config.yaml"
CONFIG_ENV_VAR = "CONFIG_FILE_PATH"
RATE_LIMIT_DURATION = 60  # 1 minuto
RATE_LIMIT_REQUESTS = 30  # 30 requisições por minuto
request_history = {}


app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://bookmarks.apolzek.io"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check():
    return {"status": "healthy"}

@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    client_ip = request.client.host
    current_time = time.time()
    
    # Limpe requisições antigas
    for ip in list(request_history.keys()):
        request_history[ip] = [t for t in request_history[ip] if current_time - t < RATE_LIMIT_DURATION]
        if not request_history[ip]:
            del request_history[ip]
    
    # Verifique o limite de taxa
    if client_ip in request_history and len(request_history[client_ip]) >= RATE_LIMIT_REQUESTS:
        return JSONResponse(
            status_code=429,
            content={"detail": "Limite de taxa excedido. Por favor, tente novamente mais tarde."}
        )
    
    # Adicione requisição ao histórico
    if client_ip not in request_history:
        request_history[client_ip] = []
    request_history[client_ip].append(current_time)
    
    # Processe a requisição
    response = await call_next(request)
    return response


class RepositoryAddRequest(BaseModel):
    path: str

class RepositoryDeleteRequest(BaseModel):
    path: str

def load_config():
    """
    Carrega o arquivo de configuração YAML automaticamente.
    Primeiro tenta carregar do caminho local, depois de uma variável de ambiente.
    """
    config_path = os.getenv(CONFIG_ENV_VAR, CONFIG_PATH)
    if not os.path.exists(config_path):
        raise HTTPException(status_code=404, detail="Configuration file not found.")
    with open(config_path, 'r', encoding='utf-8') as file:
        return yaml.safe_load(file)

def save_config(config):
    """
    Salva o arquivo de configuração YAML no caminho local.
    """
    with open(CONFIG_PATH, 'w', encoding='utf-8') as file:
        yaml.dump(config, file)

def validate_repository(repo: str):
    """
    Valida um repositório (URL ou arquivo local).
    """
    try:
        if repo.startswith("http://") or repo.startswith("https://"):
            response = requests.get(repo)
            response.raise_for_status()
            data = response.json()
            return True, "OK"
        else:
            if not os.path.exists(repo):
                return False, "File not found"
            with open(repo, 'r', encoding='utf-8') as file:
                data = json.load(file)
            return True, "OK"
    except Exception as e:
        return False, f"Invalid format: {str(e)}"

@app.post("/repositories/add")
def add_repository(repo: RepositoryAddRequest):
    """
    Adiciona um repositório à lista de repositórios no arquivo de configuração YAML.
    """
    config = load_config()
    if repo.path in config.get("local_files", []):
        raise HTTPException(status_code=400, detail="Repository already exists.")
    config.setdefault("local_files", []).append(repo.path)
    save_config(config)
    return {"message": "Repository added successfully."}

@app.post("/repositories/delete")
def delete_repository(repo: RepositoryDeleteRequest):
    """
    Remove um repositório da lista de repositórios no arquivo de configuração YAML.
    """
    config = load_config()
    if repo.path not in config.get("local_files", []):
        raise HTTPException(status_code=404, detail="Repository not found.")
    config["local_files"].remove(repo.path)
    save_config(config)
    return {"message": "Repository deleted successfully."}

@app.get("/repositories/list")
def list_repositories():
    """
    Lista todos os repositórios configurados no arquivo de configuração YAML.
    """
    config = load_config()
    return {"repositories": config.get("local_files", [])}

@app.get("/search")
def search(
    keyword: Optional[str] = Query(None, description="Palavra-chave para busca"),
    repository: Optional[str] = Query(None, description="Filtrar por repositório específico"),
    field: Optional[str] = Query(None, description="Campo específico para busca")
):
    """
    Realiza uma busca nos repositórios configurados.
    """
    config = load_config()
    repositories = config.get("local_files", [])
    results = []

    for repo in repositories:
        is_valid, message = validate_repository(repo)
        if not is_valid:
            continue

        if repo.startswith("http://") or repo.startswith("https://"):
            response = requests.get(repo)
            data = response.json()
        else:
            with open(repo, 'r', encoding='utf-8') as file:
                data = json.load(file)

        # Filtra os dados com base nos parâmetros
        if keyword and field:
            if field == "tags":
                filtered = [entry for entry in data if field in entry and any(keyword.lower() in tag.lower() for tag in entry[field])]
            else:
                filtered = [entry for entry in data if field in entry and keyword.lower() in str(entry[field]).lower()]
        elif keyword:
            filtered = [entry for entry in data if any(keyword.lower() in str(entry[f]).lower() for f in entry)]
        else:
            filtered = data

        if repository:
            filtered = [entry for entry in filtered if entry.get("repository") == repository]

        results.extend(filtered)

    return {"results": results}