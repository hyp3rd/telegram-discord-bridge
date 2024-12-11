curl -X POST http://127.0.0.1:8000/api/v1/bridge/
read CODE
curl -X POST http://127.0.0.1:8000/api/v1/auth/telegram -d '{"code":$CODE,"password":""}' -H 'Content-Type: application/json'