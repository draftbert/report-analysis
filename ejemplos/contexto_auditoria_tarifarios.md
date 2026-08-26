# Design thinking — Auditoría de Transporte e-Commerce: tarifarios y asignación de transportistas (SCA)

## Motivo de la auditoría
El coste de transporte se ha incorporado como criterio directo de asignación de transportistas en pedidos de e-Commerce a través de la herramienta SCA, cuyo desarrollo sigue en curso. El coste que utiliza SCA se estima a partir de las facturas validadas en la Herramienta de Costes (HC) mediante el algoritmo Cost Pricing Flash (CPF). Un tarifario desactualizado o una estimación sesgada se traslada directamente a la elección del transportista, con impacto en coste y servicio.

## Objetivo previsto
Asegurar la integridad de los tarifarios que alimentan la asignación de transportistas en SCA y evaluar el proceso de carga, actualización y gobierno del maestro de tarifas.

## Riesgos a cubrir
- Tarifarios cargados en HC que no reflejan las condiciones acordadas con los couriers.
- Estimaciones de coste de CPF sesgadas para casuísticas concretas (COD, zonas remotas, linehaul, peso/volumen).
- Falta de trazabilidad entre los acuerdos negociados por Operativa y las tarifas cargadas.
- Facturaciones indebidas por errores de integración o de datos maestros.

## Alcance previsto
Operativa e-Commerce en los mercados donde SCA/CPF está implantado; tarifarios de última milla de los principales couriers; flujo HC → Snowflake → CPF → SCA. Periodo: ejercicio en curso y último cierre de facturación disponible.

## Principales magnitudes (a confirmar en el trabajo de campo)
- Couriers con tarifario cargado en HC: 38
- Mercados con SCA/CPF operativo: 12
- Pedidos e-Commerce valorados por HC en el último año: 41,6 M
- Reclamaciones de transporte relacionadas con tarifas (primer semestre): importe aproximado de 1,4 M€

## Áreas implicadas
Transporte e-Commerce (Operativa), equipos de validación de facturas (BDO, Serviguide, Inditex China), Central e-Commerce, Transport Business Analytics, Tecnología (SCA/CPF).
