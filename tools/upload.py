"""upload simulator."""
import requests

URL = 'http://localhost:8000/upload'
FILE_PATH = '../config.yml'

with open(FILE_PATH, 'rb') as file:
    files = {'file': (FILE_PATH, file, 'application/x-yaml')}
    response = requests.post(URL, files=files, timeout=5)

print(response.json())
