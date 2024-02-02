web: gunicorn app.main:app --max-requests 1000
clock: python app/jobs.py
dev: flask run -p 5550
upgrade: flask db upgrade