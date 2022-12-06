FROM python:3.6

ENV PYTHONUNBUFFERED 1

RUN mkdir /code

WORKDIR /code

ADD requirements.txt /code/
RUN pip install --no-cache-dir -r requirements.txt

ADD deploy.py /code/
ADD deploy_linked.py /code/

ADD start_script.sh /code/
ADD wait_for_it.sh /code/

ENTRYPOINT ./start_script.sh
