FROM python:3.10

RUN mkdir /app
WORKDIR /app

COPY main.py requirements.txt /app/
COPY .gitconfig /root/.gitconfig
RUN pip3 install --upgrade pip
RUN pip3 install -r requirements.txt

ENTRYPOINT ["python3", "/app/main.py"]