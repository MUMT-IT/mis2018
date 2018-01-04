FROM python:2

WORKDIR /home/mis2018/
COPY app /home/mis2018/app
COPY main.py /home/mis2018/
COPY requirements.txt /home/mis2018
RUN pip install -r requirements.txt

CMD ["python", "main.py"]
