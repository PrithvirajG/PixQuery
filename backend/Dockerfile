FROM python:3.10-slim

RUN echo 'Acquire::http::Pipeline-Depth "0"; Acquire::http::No-Cache true;' > /etc/apt/apt.conf.d/99fixbadproxy

RUN apt-get update && apt-get install -y \
    build-essential \
    libgl1-mesa-glx \
    libglib2.0-0 \
    git \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
#COPY ./src /app/src
COPY requirements.txt .

RUN pip install -r requirements.txt
COPY . /app

CMD ["uvicorn", "api_main:app", "--host", "0.0.0.0", "--port", "8000"]
