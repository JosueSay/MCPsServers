# MCP Local

El MCP se concibe como un **servidor especializado en la gestión de facturas electrónicas FEL (XML de la SAT)**, cuyo propósito es transformar estos documentos en **PDFs estilizados** que integren la identidad visual de una empresa (logo, colores, tipografías), a la vez que se garantiza la **auditoría automática de cálculos** (subtotal, IVA 12 %, total) y la **construcción de la URL/QR de verificación** oficial.

El flujo se plantea como un proceso **totalmente automatizado y sin intervención manual**: desde la recepción del XML FEL hasta la obtención de un PDF coherente y personalizable. Esto soluciona la rigidez de los PDFs estándar generados por la SAT, permitiendo entregar documentos que no solo cumplen con los requisitos fiscales, sino que además **reflejan la marca** de la empresa.

## Funcionalidades principales

* **Validación atómica:** `xml_path ->` reporta inconsistencias (faltantes, totales, IVA).
* **Generación de PDF estilizado:** `xml_path, logo_path?, theme?, out? ->` produce el PDF con branding.
* **Procesamiento en lote:** `dir_xml, out_dir ->` genera múltiples PDFs y un *manifest* de resultados.

## Tecnologías

* **Python** como base.
* **ReportLab** para la composición de PDFs (con soporte para tipografías TTF locales como Montserrat o Roboto).
* **xml.etree / lxml** para parseo y validación de XML FEL.
* **reportlab.graphics.barcode.qr / qrcode** para el código QR de verificación.

El diseño es **100 % local**, sin dependencia de APIs externas, asegurando **privacidad y confiabilidad** en el manejo de datos fiscales.
