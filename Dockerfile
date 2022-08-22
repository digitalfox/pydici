# syntax=docker/dockerfile:1
FROM python:3.9
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
# Stuff for casperjs / phantomjs tests
RUN apt-get update
RUN apt-get install nodejs/stable-security -y
ENV PATH="/code/node_modules/.bin/:$PATH"
ENV OPENSSL_CONF=/etc/ssl


