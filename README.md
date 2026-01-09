# neosearch

The favorite url search engine for people with bad memory :link:

## cli mode

```sh
cd cli/
python3 -m venv .venv
source .venv/bin/activate
pip3 install -r requirements.txt
python3 neosearch.py
# python3 -m unittest test_neosearch.py
```

## server mode

```sh
pip install fastapi uvicorn
uvicorn neosearch:app --reload
```

### using curl to interact

search using filters
```bash
curl -X GET "http://127.0.0.1:8000/search?keyword=example&repository=repo1&field=name"
```

add new repository
```bash
curl -X POST "http://localhost:8000/repositories/add" \
-H "Content-Type: application/json" \
-d '{"path": "path/repository.json"}'
```

remove repository
```bash
curl -X POST "http://localhost:8000/repositories/delete" \
-H "Content-Type: application/json" \
-d '{"path": "/caminho/para/repositorio.json"}'
```

list all repositories
```bash
curl -X GET "http://localhost:8000/repositories/list"
```

find word in all repositories
```bash
curl -X GET "http://localhost:8000/search?keyword=exemplo"
```

find word in especific repository
```bash
curl -X GET "http://localhost:8000/search?keyword=exemplo&repository=nome_do_repositorio"
```

find all
```bash
curl -X GET "http://localhost:8000/search"
```

## build

```sh
pip install pyinstaller
pyinstaller --onefile --distpath ./dist --name neosearch main.py
```

  The nginx SSL error is resolved. Your application should now be accessible at:
  - http://localhost (nginx reverse proxy)
  - http://localhost:8080 (direct frontend access)
  - http://localhost:8000 (direct backend access)