# ---- Base ----
FROM python:3.12-slim

# ---- Workdir ----
WORKDIR /app

# ---- Dependencies ----
# Use your requirements.txt from the root (already includes fastapi, uvicorn, requests, etc.)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ---- Code (only OW) ----
# Mark 'servers' as a package and copy only ow_mcp_server
COPY servers/__init__.py /app/servers/__init__.py
COPY servers/ow_mcp_server /app/servers/ow_mcp_server

# ---- Network ----
EXPOSE 8080

# ---- Startup ----
CMD ["uvicorn", "servers.ow_mcp_server.server_http:app", "--host", "0.0.0.0", "--port", "8080"]
