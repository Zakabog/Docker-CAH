FROM python:3.8.2
ADD . /code
WORKDIR /code
#RUN pip3 install -r requirements.txt
RUN pip3 install six
RUN pip3 install flask-sse
RUN pip3 install redis
RUN pip3 install flask
RUN pip3 install flask-sse
CMD python app.py