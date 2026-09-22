FROM python:3.12-slim
# tcpdump is the independent observer: the app cannot lie to it about what left
# the machine. docker-cli launches the code sandbox (on Debian 13 the CLI is
# its own package; docker.io alone ships only docker-init).
RUN apt-get update && apt-get install -y --no-install-recommends \
      tcpdump docker-cli && rm -rf /var/lib/apt/lists/*
WORKDIR /srv
COPY requirements*.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Bake the embedding model into the image.
#
# fastembed fetches weights from HuggingFace on first use. In a container with
# no route out that fails at query time, and retrieval degrades to zero results
# while the rest of the system carries on -- which is how a document came to be
# written with nothing behind it. An air-gapped deployment must ship its models,
# not reach for them, so the download happens here at build time where a network
# still exists and a failure is a failed build rather than a silent one.
ENV FASTEMBED_CACHE_PATH=/srv/.models
RUN python -c "\
from fastembed import TextEmbedding; \
m = TextEmbedding(model_name='BAAI/bge-small-en-v1.5'); \
v = list(m.embed(['warm the cache'])); \
print('embedding model baked in, dim', len(v[0]))"

COPY app ./app
COPY static ./static
COPY models.yaml ./
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8117"]
