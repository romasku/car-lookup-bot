FROM python:3.11.4-slim

WORKDIR /app

ADD requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

ADD . .

RUN python setup.py develop

CMD car-lookup-bot
