# Análisis por Capas (modelo TCP/IP)

Para este análisis se utilizó el modelo TCP/IP de 4 capas `Acceso a red -> Internet -> Transporte -> Aplicación`.

## 1. Capa de Acceso a red (enlace + física)

Transmisión local en Ethernet: tramas con **MAC origen/destino**, MTU $\approx$ 1500 B.

- En el **Frame 20** se ven las MAC del host WSL (`00:15:5d:85:3f:8b`) y del gateway/bridge (`00:15:5d:1c:a2:25`).
- Los segmentos con **1466 B** de "TLSv1.3 Application Data" (p. ej. frames **76–79**) cuadran con **TCP payload \~1400 B** + **cabeceras IP/TCP** para no superar la MTU Ethernet (\~1500 B).
- Filtro útil: `ip.addr == 34.143.73.2`.

## 2. Capa de Internet (IP)

Direccionamiento y enrutamiento **IP**. También se captó **NAT**: el cliente usa IP **privada** y sale con IP **pública** a Internet (**IP\:puerto privado <-> IP\:puerto público**) y los rangos **RFC1918** (10/8, 172.16/12, 192.168/16).

- **Cliente:** `172.20.126.187` (rango privado 172.16–172.31).
- **Servidor (Cloud Run):** `34.143.73.2` (IP pública, puede cambiar por balanceo).
- Filtros que usaste:

  - Por **destino**: `ip.addr == 34.143.73.2`
  - Para **SNI** (descubrir IP real del MCP):
    `tls.handshake.extensions_server_name contains "ow-mcp-server-43787671200.us-central1.run.app"`

## 3. Capa de Transporte (TCP)

**TCP** provee comunicación **orientada a conexión**, confiable: **3-way handshake**, números de **secuencia/ack**, **control de flujo/ventana**, **retransmisión**, **SACK**, **escalado de ventana**, y cierre **ordenado (FIN/ACK)** (el `SYN` cuenta como **1 byte lógico** y por eso el `ACK` incrementa en +1).

- **Establecimiento (3-way handshake)**

  - **\[17]** `SYN` cliente -> servidor
  - **\[18]** `SYN+ACK` servidor -> cliente
  - **\[19]** `ACK` cliente -> servidor
    (con **MSS**, **Window Scale**, **SACK Permitted** en opciones TCP).
- **Datos cifrados fluyendo sobre TCP:**
  tras el TLS handshake, ves `TLS Application Data` (p. ej. **30–32** cliente->servidor y **76–79** servidor->cliente).
- **Cierre ordenado:**
  - **\[145]** Cliente envía `FIN,ACK`
  - **\[147]** Servidor responde `FIN,ACK`
  - **\[148]** Cliente `ACK` final

## 4. Capa de Aplicación

Aquí viven los protocolos de aplicación. Como se vió en el curso MCP es un protocolo de capa de aplicación, junto con HTTP/DNS, etc.

- **TLS 1.3 sobre TCP/443** protege la aplicación:
  - **\[20]** `TLS ClientHello` (SNI del MCP; **ALPN: http/1.1**)
  - **\[22]** `TLS ServerHello + ChangeCipherSpec` (negocia **TLS 1.3**)
  - Desde el reensamblado (frame **26**) todo es **`TLS Application Data`** (cifrado).
- **Contenido real (JSON-RPC del MCP)**: no es visible en Wireshark por el cifrado pero se evidencia con logs para `initialize`, `tools/list`, `tools/call`. En este proceso la app se comunican por pares a través de esta capa.

## Referencias de apoyo

- Notas del curso.
- [IBM (lectura complementaria del stack TCP/IP)](https://www.ibm.com/docs/es/aix/7.2.0?topic=protocol-tcpip-protocols)
