FROM python:3.11-slim

WORKDIR /work

COPY requirements.txt app.py /work/

RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 7861

CMD ["python", "app.py"]