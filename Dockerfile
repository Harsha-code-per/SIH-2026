FROM python:3.12-slim
# tcpdump is the independent observer: the app cannot lie to it about what left
# the machine. libreoffice is absent on purpose -- deliverables are written with
# python-docx/openpyxl/python-pptx, not by shelling out to an office suite.
RUN apt-get update && apt-get install -y --no-install-recommends \
      tcpdump docker.io && rm -rf /var/lib/apt/lists/*
WORKDIR /srv
COPY requirements*.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY static ./static
COPY models.yaml ./
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8117"]
