FROM python:2

RUN mkdir -p /mis2018/app
RUN mkdir -p /mis2018/warehouse
RUN mkdir /mis2018/migrations
COPY /app/requirements.txt /mis2018/app
WORKDIR /mis2018
RUN pip install -r app/requirements.txt

CMD ["gunicorn", "--workers", "2", "--bind", "0.0.0.0:5000", "app.main:app"]
