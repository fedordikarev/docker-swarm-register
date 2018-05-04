FROM python:3.6-alpine
MAINTAINER Fedor Dikarev <fedor.dikarev@gmail.com>

COPY requirements.txt /
RUN pip3 install -r requirements.txt

COPY consul_registrator.py /app/
ENTRYPOINT ["python", "/app/consul_registrator.py"]
