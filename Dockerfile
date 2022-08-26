# syntax=docker/dockerfile:1
FROM python:3.9
# Stuff for casperjs / phantomjs tests
RUN apt-get update
RUN apt-get install nodejs/stable-security -y
ENV PATH="/code/node_modules/.bin/:$PATH"
ENV OPENSSL_CONF=/etc/ssl
# Install pydici django env
RUN useradd -m pydici
USER pydici
ENV PATH="/home/pydici/.local/bin/:$PATH"
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
WORKDIR /code
COPY requirements*txt /code/
RUN pip install --upgrade pip
RUN pip install -r requirements.txt
RUN pip install -r requirements-sklearn.txt
RUN pip install -r requirements-nextcloudtag.txt
RUN pip install Werkzeug
COPY . /code/


