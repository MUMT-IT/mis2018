web: gunicorn app.main:app
clock: python app/jobs.py
dev: flask run -p 5550
upgrade: flask db upgrade