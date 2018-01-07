FROM python:2

WORKDIR /usr/src/
COPY app /usr/src/app
RUN pip install -r app/requirements.txt

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app.main:app"]
