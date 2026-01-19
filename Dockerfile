FROM python:3.9
WORKDIR /mis2018
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "5", "--threads", "12", "app.main:app"]