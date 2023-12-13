web: gunicorn app.main:app --workers 2 --max-requests 300 --preload
clock: python app/jobs.py
dev: flask run -p 5550
upgrade: flask db upgrade