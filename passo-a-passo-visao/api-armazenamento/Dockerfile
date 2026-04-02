FROM python:3.11-slim

WORKDIR /code

COPY requirements.txt /code/

RUN pip install --no-cache-dir -r requirements.txt

COPY main.py /code/ 

EXPOSE 8082

CMD ["uvicorn", "main.py", "--host", "0.0.0.0", "--port", "8082"]