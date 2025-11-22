FROM ubuntu:resolute-20251101

RUN apt-get upgrade -y && \
    apt-get update -y && \
    apt-get install less python3 pip vim python3.13-venv dos2unix binutils -y && \
    apt-get clean -y

COPY .. /opt

RUN rm -rf /opt/.venv && \
    rm -rf /opt/.git && \
    rm -rf /opt/.idea