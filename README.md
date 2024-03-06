#run project
uvicorn blockchain_backend:app --reload

#local swagger
http://127.0.0.1:8000/docs

# python: make requerments.txt
pip install pipreqs
pipreqs /path/to/project