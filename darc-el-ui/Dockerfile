FROM python:3.14-slim

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY darc-el-ui/pyproject.toml ./pyproject.toml
COPY darc-el-ui/README.md ./README.md
COPY darc-el-ui/manage.py ./manage.py
COPY darc-el-ui/darc_el_ui ./darc_el_ui
COPY darc-el-ui/dashboard ./dashboard
COPY LICENSE ./LICENSE

RUN uv pip install --system --no-cache .
RUN python manage.py migrate --noinput

CMD ["python", "manage.py", "runserver", "0.0.0.0:8081"]
