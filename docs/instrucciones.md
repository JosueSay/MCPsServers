# **Proyecto 1 – Implementación de Protocolo MCP en la Capa de Aplicación**

## **1. Introducción al protocolo MCP y contexto**

A finales de **noviembre de 2024**, la empresa **Anthropic** (creadora de Claude) presentó un nuevo estándar llamado **Model Control Protocol (MCP)**.
El objetivo de este protocolo es **habilitar la interoperabilidad entre herramientas y modelos de lenguaje (LLMs)**, como **ChatGPT, Claude, Copilot, Gemini**, entre otros.

Antes de MCP, cada proveedor definía su propio método de integración, lo que generaba problemas de compatibilidad y altos costos de adaptación. Un chatbot diseñado para un LLM no podía usar las mismas herramientas en otro sin cambios significativos en el código.

Con MCP, la comunicación se realiza mediante **JSON-RPC (Remote Procedure Call)**, lo que permite un intercambio estandarizado de mensajes entre clientes, servidores y anfitriones, independientemente del proveedor del LLM.
Esto significa que **un agente o chatbot puede descubrir, comprender y utilizar herramientas externas de forma unificada**, sin importar quién las provea.

## **2. Limitaciones actuales de los LLMs**

Los modelos de lenguaje son potentes para interpretar lenguaje natural y mantener conversaciones, pero tienen **limitaciones clave**:

* **Base de conocimiento estática**: Su información está limitada a la fecha de su último entrenamiento.
  Por ejemplo, un LLM entrenado hasta 2024 **no puede responder con datos actualizados** a menos que se le conecte a herramientas externas.
* **Dependencia de herramientas complementarias**: Funcionalidades como búsqueda web, ejecución de código o acceso a APIs externas deben habilitarse mediante integraciones específicas.
* **Falta de interoperabilidad**: Antes de MCP, una herramienta diseñada para un LLM no podía reutilizarse fácilmente en otro.

Con MCP, un LLM puede:

1. **Descubrir herramientas disponibles** (a través de un mensaje inicial del servidor).
2. **Entender cómo usarlas** (descripción, parámetros, formato de respuesta).
3. **Aplicarlas en contexto** dentro de la conversación con el usuario.

Ejemplo:

* Pregunta sin herramientas: *"¿Qué sucedió ayer?"* → El LLM no responde por falta de datos actualizados.
* Pregunta con herramienta web habilitada: *"¿Qué sucedió ayer?"* → El LLM consulta la web, obtiene datos y responde.

## **3. Arquitectura y actores en MCP**

En MCP existen tres roles principales:

1. **Servidor MCP**

   * Expone herramientas que ejecutan acciones (locales o remotas).
   * Ejemplo: un servidor MCP que consulta el clima o crea repositorios en GitHub.

2. **Cliente MCP**

   * Mantiene conexión con el servidor para descubrir y usar herramientas.
   * Traduce las peticiones del LLM al formato JSON-RPC esperado por el servidor.

3. **Anfitrión (Host)**

   * Aplicación que aloja clientes MCP y los conecta con el servidor.
   * Ejemplos: Cursor, VSCode, Claude Desktop, ChatGPT.

**Objetivo:** Permitir que cualquier LLM utilice cualquier servidor MCP, ampliando sus capacidades de interacción con el mundo real.

## **4. Objetivos del proyecto**

Implementar un **chatbot propio** capaz de:

* Conectarse a un LLM vía API (se sugiere Anthropic Claude por \$5 en créditos gratuitos).
* Mantener contexto en una sesión de conversación.
* Mostrar un **log detallado** de todas las interacciones y solicitudes a servidores MCP.
* Usar servidores MCP oficiales y desarrollados por el estudiante (locales y remotos).
* Demostrar interoperabilidad entre diferentes LLMs y servidores MCP.

## **5. Plan de desarrollo**

### **Primera fase – Chatbot con conexión a LLM**

1. **Conexión a la API del LLM**

   * Integrar un LLM mediante su API oficial.
   * Gestionar autenticación y manejo de tokens.
2. **Manejo de contexto de sesión**

   * Almacenar historial de conversación para mantener coherencia.
3. **Registro de interacciones**

   * Guardar cada solicitud y respuesta (incluyendo uso de herramientas) en un log.

> El chatbot debe poder listar herramientas disponibles y decidir si las usa o no, según el contexto.

### **Segunda fase – Servidores MCP**

#### **Parte 1: Uso de servidores oficiales**

* Integrar servidores MCP ya reconocidos (ej. *filesystem-mcp-server*, *git-mcp-server*).
* Ejemplo de demostración:

  * Solicitar al chatbot crear un repositorio.
  * Crear un archivo `README.md`.
  * Agregarlo y hacer commit mediante comandos MCP.

#### **Parte 2: Creación de un servidor MCP local**

* Implementar un servidor propio en la máquina local.
* Ejemplo (propuesto por profesor):

  * Servidor MCP que usa el motor de ajedrez Stockfish para analizar partidas y detectar el primer error cometido.
* Considerar:

  * Formato de entrada y salida.
  * Permisos y validación de uso.

#### **Parte 3: Uso de servidores MCP de terceros**

* Cada estudiante seleccionará **2 servidores MCP** y los integrará en su chatbot.
* Documentar instalación, uso y ejemplos.

#### **Parte 4: Servidor MCP remoto**

* Implementar un servidor en la nube (Google Cloud, Cloudflare, etc.).
* Retos:

  * Autenticación de usuarios.
  * Exposición pública segura.
  * Gestión de endpoints.
* Se pueden usar créditos gratuitos (Google Cloud ofrece \$300).
* Integrar el servidor remoto en el anfitrión.

## **6. Análisis de tráfico y mensajes**

Cuando el servidor remoto esté activo:

1. Usar **Wireshark** para capturar tráfico entre anfitrión y servidor.
2. Identificar:

   * Mensajes de sincronización.
   * Solicitudes (requests).
   * Respuestas (responses).
3. Documentar los **mensajes JSON-RPC** intercambiados.

## **7. Entregables**

* **Servidor MCP local** (repositorio independiente, público).
* **Cliente/Chatbot final** con integración MCP (repositorio con código, README y documentación).
* **Reporte técnico** con:

  * Especificaciones, parámetros y endpoints de servidores MCP desarrollados.
  * Análisis de la comunicación a nivel de capa de enlace, red, transporte y aplicación.
  * Conclusiones y comentarios.
* **Demostración funcional** antes de la fecha límite.

## **8. Evaluación y bonificaciones**

* 15% extra por implementar MCP **directamente en JSON-RPC sin SDK**, logrando al menos el 90% de las funcionalidades descritas.
* 15% extra por implementar **interfaz gráfica** (terminal enriquecida o chatbot web), aplicando principios de **HCI** y usabilidad.
