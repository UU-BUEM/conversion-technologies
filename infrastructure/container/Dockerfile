FROM continuumio/miniconda3:24.1.2-0 AS builder

COPY infrastructure/env/conversion_env.yml /tmp/conversion_env.yml
RUN conda env create -f /tmp/conversion_env.yml \
    && conda clean -afy \
    && rm /tmp/conversion_env.yml

FROM continuumio/miniconda3:24.1.2-0

LABEL org.opencontainers.image.source="https://github.com/UU-BUEM/conversion-technologies"
LABEL org.opencontainers.image.description="Conversion technologies module for UU-BUEM"
LABEL org.opencontainers.image.licenses="MIT"

COPY --from=builder /opt/conda/envs/conversion_env /opt/conda/envs/conversion_env

ENV PATH=/opt/conda/envs/conversion_env/bin:$PATH
ENV CONDA_DEFAULT_ENV=conversion_env
ENV PYTHONPATH=/app/src

WORKDIR /app
CMD ["python", "-m", "conversion_technologies", "--help"]
