@echo off
echo [1/3] Bagimliliklar yukleniyor...
pip install fastapi "uvicorn[standard]" pydantic PyJWT openai python-dotenv -q
echo [2/3] Veritabani olusturuluyor...
python database/setup.py
echo [3/3] Sunucu baslatiliyor...
echo.
echo  API:      http://localhost:8000/docs
echo  Frontend: http://localhost:8000/
echo  Admin:    admin / admin123
echo.
uvicorn api.main:app --reload --port 8000
