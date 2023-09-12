FROM python:3.10

RUN mkdir /app
WORKDIR /app

COPY main.py requirements.txt /app/
RUN pip3 install --upgrade pip
RUN pip3 install -r requirements.txt

ENTRYPOINT ["python3", "/app/main.py"]