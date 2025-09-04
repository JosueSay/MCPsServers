import os

def loadSettings() -> dict:
    """Read environment variables and provide defaults for the engine."""
    return {
        "anthropicApiKey": os.getenv("ANTHROPIC_API_KEY", ""),
        "anthropicModel": os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514"),
        "mcpFelCmd": os.getenv("MCP_FEL_CMD", "python servers/fel_mcp_server/server_stdio.py"),
        "logDir": os.getenv("LOG_DIR", "./logs/sessions"),
        "routerDebug": os.getenv("ROUTER_DEBUG", "1") == "1",
        "systemPrompt": os.getenv(
            "SYSTEM_PROMPT",
            (
                "Eres un asistente general. Responde breve y directo en el idioma del usuario. "
                "Usa herramientas MCP solo si la petición es de facturas FEL (validar XML, generar PDF, procesar lote). "
                "Tras usar una herramienta, entrega una única respuesta breve sin pegar JSON."
            )
        ),
        # Minimal sandbox for paths
        "allowedRoots": [r"data/xml", r"data/out", r"data/logos"],
    }
