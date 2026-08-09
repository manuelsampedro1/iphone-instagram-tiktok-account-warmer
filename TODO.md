# Pendiente

## Bloqueos del material publicado

- El autor tendría que publicar un artefacto iOS instalable y su procedencia.
- El runner personalizado tendría que estar disponible como código completo,
  con URL oficial, commit inmutable, licencia y hash verificable.
- Ese runner debe implementar de forma comprobable `/wda/mw/tap` y
  `/wda/mw/swipe`; WebDriverAgent estándar no satisface el contrato actual.
- Cualquier revisión futura de esa capacidad requiere una aceptación separada
  de seguridad y compatibilidad con las reglas de las plataformas.

## Posible continuación segura

- Repetir la detección USB si se conecta un modelo distinto.
- Volver a ejecutar la suite y el diagnóstico tras cualquier cambio.
- Mantener cuentas, proxies y secretos fuera del paquete distribuible.

No hay tareas de instalación, configuración, ejecución o modificación de
herramientas externas dentro de este fork.
