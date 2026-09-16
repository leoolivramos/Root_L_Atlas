FROM python:3.11-slim

# Dependências do sistema para gdal, osmium, ogr2ogr
RUN apt-get update && apt-get install -y --no-install-recommends \
    gdal-bin \
    libgdal-dev \
    libpq-dev \
    osmium-tool \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Instala dependências Python
COPY pyproject.toml ./
RUN pip install --no-cache-dir hatchling && \
    pip install --no-cache-dir -e ".[dev]" || \
    pip install --no-cache-dir \
        geopandas pyogrio pyarrow shapely fiona rasterio pyproj \
        duckdb duckdb-engine httpx aiohttp boto3 tqdm pysus \
        pandera prefect prefect-sqlalchemy psycopg2-binary sqlalchemy \
        pyyaml python-dotenv loguru tenacity rich typer

COPY . .

# Cria estrutura de diretórios do Lakehouse
RUN mkdir -p /data/bronze /data/silver /data/gold

CMD ["python", "flows/main_pipeline.py", "run"]
