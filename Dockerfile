FROM python:3.6-alpine

WORKDIR /opt/forge

RUN apk update && \
    apk add build-base libffi-dev openssl-dev

ADD . /opt/forge

RUN pip install -r requirements.txt

EXPOSE 8000
ENTRYPOINT ["python3", "acforge.py"]
