FROM python:2

WORKDIR /usr/src/app
COPY app /usr/src/app
RUN pip install -r requirements.txt

CMD ["python", "main.py"]
