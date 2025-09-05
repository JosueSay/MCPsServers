"""
MCP server over stdio (no SDK).
Implements:
  - initialize
  - tools/list
  - tools/call for: { fel_validate, fel_render, fel_batch }

This server bridges your FEL XML -> Branded PDF logic to the MCP protocol using JSON-RPC 2.0.
It reads requests from STDIN and writes responses to STDOUT.

Dependencies:
  - Your existing modules: config.py, fel_pdf.py
  - Python stdlib only for the MCP transport (no SDK)
"""

import sys, json, os, glob
from typing import Any
from decimal import Decimal, ROUND_HALF_UP
from config import XML_PATH, LOGO_PATH, OUTPUT_PDF, DEFAULT_QR_SIZE, DEFAULT_TOP_BAR_HEIGHT
from fel_pdf import readFelXml, generatePdf


# ---------------------------
# JSON-RPC / MCP primitives
# ---------------------------
def sendResponse(msgId: Any, result: Any = None, error: dict[str, Any] | None = None) -> None:
    """Write a single JSON-RPC response to STDOUT."""
    payload = {"jsonrpc": "2.0", "id": msgId}
    if error is not None:
        payload["error"] = error
    else:
        payload["result"] = result
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def getCapabilities() -> dict[str, Any]:
    """Return minimal MCP capabilities (tools only)."""
    return {
        "protocolVersion": "2024-11-05",
        "serverInfo": {"name": "fel-stdio", "version": "0.1.0"},
        "capabilities": {"tools": {}}
    }


def listTools() -> dict[str, Any]:
    """Describe available tools and their JSON Schemas."""
    return {
        "tools": [
            {
                "name": "fel_validate",
                "description": "Validate FEL XML totals (subtotal, VAT 12%, total) and required fields.",
                "inputSchema": {
                    "type": "object",
                    "properties": {"xml_path": {"type": "string"}},
                    "required": ["xml_path"]
                },
            },
            {
                "name": "fel_render",
                "description": "Render branded PDF from FEL XML.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "xml_path": {"type": "string"},
                        "logo_path": {"type": ["string", "null"]},
                        "theme": {"type": ["string", "null"]},
                        "out_path": {"type": ["string", "null"]}
                    },
                    "required": ["xml_path"]
                },
            },
            {
                "name": "fel_batch",
                "description": "Render a directory of FEL XMLs; outputs manifest.json",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "dir_xml": {"type": "string"},
                        "out_dir": {"type": ["string", "null"]}
                    },
                    "required": ["dir_xml"]
                },
            }
        ]
    }


# ---------------------------
# Business logic wrappers
# ---------------------------
def parseMoney(value: Any) -> Decimal:
    """Parse money strings like '1,234.56' safely into Decimal."""
    return Decimal(str(value).replace(",", ""))


def validateFel(xmlPath: str) -> dict[str, Any]:
    """
    Validate a FEL XML:
      - Check VAT (12%) consistency and total = subtotal + VAT
      - Check required fields exist
    Returns: { ok: bool, issues: [str], totals: {subtotal, iva, total} }
    """
    data = readFelXml(xmlPath)
    issues: list[str] = []

    subtotal = parseMoney(data["subtotal"])
    iva = parseMoney(data["iva"])
    total = parseMoney(data["total"])

    expectedIva = (subtotal * Decimal("0.12")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    expectedTotal = (subtotal + expectedIva).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    if abs(iva - expectedIva) > Decimal("0.01"):
        issues.append(f"VAT mismatch: expected {expectedIva} got {iva}")
    if abs(total - expectedTotal) > Decimal("0.01"):
        issues.append(f"Total mismatch: expected {expectedTotal} got {total}")

    for key in ["numero_autorizacion", "nit", "id_receptor", "monto"]:
        if not data.get(key):
            issues.append(f"Missing field: {key}")

    return {
        "ok": len(issues) == 0,
        "issues": issues,
        "totals": {"subtotal": str(subtotal), "iva": str(iva), "total": str(total)}
    }


def renderFel(xmlPath: str, logoPath: str | None, theme: str | None, outPath: str | None) -> dict[str, Any]:
    """
    Render a branded PDF from a FEL XML using ReportLab.
    Uses defaults from config.py when arguments are None.
    """
    logo = logoPath or LOGO_PATH
    out = outPath or OUTPUT_PDF
    # theme is available for future branching; not used here directly
    generatePdf(
        xmlPath=xmlPath,
        logoPath=logo,
        outputPdf=out,
        topBarHeight=DEFAULT_TOP_BAR_HEIGHT,
        qrSize=DEFAULT_QR_SIZE,
    )
    return {"ok": True, "pdf_path": out}


def batchFel(dirXml: str, outDir: str | None) -> dict[str, Any]:
    """
    Render all *.xml inside dirXml to PDFs, write a manifest.json with results.
    Returns: { ok, count, out_dir, manifest_path }
    """
    outDir = outDir or os.path.join("data", "out")
    os.makedirs(outDir, exist_ok=True)

    manifest = []
    for xml in sorted(glob.glob(os.path.join(dirXml, "*.xml"))):
        pdfPath = os.path.join(outDir, os.path.splitext(os.path.basename(xml))[0] + ".pdf")
        generatePdf(
            xmlPath=xml,
            logoPath=LOGO_PATH,
            outputPdf=pdfPath,
            topBarHeight=DEFAULT_TOP_BAR_HEIGHT,
            qrSize=DEFAULT_QR_SIZE,
        )
        manifest.append({"xml": xml, "pdf": pdfPath})

    manifestPath = os.path.join(outDir, "manifest.json")
    with open(manifestPath, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    return {"ok": True, "count": len(manifest), "out_dir": outDir, "manifest_path": manifestPath}


def callTool(name: str, args: dict[str, Any]) -> dict[str, Any]:
    """Dispatch a tools/call to the correct FEL operation."""
    if name == "fel_validate":
        return validateFel(args["xml_path"])
    if name == "fel_render":
        return renderFel(args["xml_path"], args.get("logo_path"), args.get("theme"), args.get("out_path"))
    if name == "fel_batch":
        return batchFel(args["dir_xml"], args.get("out_dir"))
    raise ValueError(f"Unknown tool {name}")


# ---------------------------
# Main JSON-RPC loop (stdio)
# ---------------------------
def main() -> None:
    """
    Main stdio loop:
      - parse one JSON-RPC request per line
      - route to MCP methods
      - write JSON-RPC response
    """
    for line in sys.stdin:
        try:
            req = json.loads(line)
            method = req.get("method")
            msgId = req.get("id")

            if method == "initialize":
                sendResponse(msgId, getCapabilities()); continue
            if method == "tools/list":
                sendResponse(msgId, listTools()); continue
            if method == "tools/call":
                params = req.get("params", {})
                name = params.get("name")
                arguments = params.get("arguments", {})
                result = callTool(name, arguments)
                # MCP result envelope: content is an array of blocks
                sendResponse(msgId, {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}]})
                continue

            sendResponse(msgId, error={"code": -32601, "message": f"Method not found: {method}"})
        except Exception as e:
            sendResponse(req.get("id"), error={"code": -32000, "message": str(e)})


if __name__ == "__main__":
    main()