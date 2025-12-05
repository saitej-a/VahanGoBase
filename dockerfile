FROM python:slim
WORKDIR /App
COPY . /App
RUN pip3 install -r requirements.txt
EXPOSE 8000

