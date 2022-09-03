# syntax=docker/dockerfile:1
FROM python:3.9
# Stuff for casperjs / phantomjs tests
COPY --from=vitr/casperjs /opt/casperjs/ /opt/casperjs
COPY --from=vitr/casperjs /usr/local/bin/phantomjs /usr/local/bin/phantomjs
ENV PATH="/opt/casperjs/bin/:$PATH"
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
RUN pip install Werkzeug
COPY scripts/patch-django-3.2-memcached-sync.patch /code/
RUN cd ~/.local/lib/python3.9/site-packages/django && patch -p2 < /code/patch-django-3.2-memcached-sync.patch

