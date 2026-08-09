# Decisiones

## 2026-08-09

### Mantener separado cualquier inventario externo

Los inventarios operativos pertenecen fuera de este repositorio. Esta
adaptación no instala componentes de otras herramientas, no cambia su
configuración y no ejecuta sus rutinas.

### No migrar secretos ni sesiones

Este fork no copia ni traslada alias, handles, referencias de proxy,
contraseñas, cookies, tokens, sesiones, claves Apple o identificadores
completos de dispositivo. Cualquier inventario externo queda fuera del código,
del ZIP y del repositorio público.

### Distribuir solo el diagnóstico

La copia local y su ZIP contienen una interfaz diagnóstica. No aceptan cuentas,
proxies, claves Apple o identificadores de teléfono. Los verbos heredados no
están registrados y el parser los rechaza sin invocar ningún handler.

### Limitar el instalador a un helper

go-ios queda fijado por versión, URL, SHA-256 del ZIP y SHA-256 del binario
extraído. La instalación es transaccional y únicamente modifica `bin/ios` en
el Mac. No instala paquetes Python, no compila Swift y no firma ni instala
software en teléfonos.

### Diagnóstico mínimo y redactado

`diagnose` comprueba primero tipo, permiso, SHA-256 y versión de `bin/ios`.
Después solo ejecuta `ios list` e `ios info`. Exige el número y modelo
esperados, omite nombres e identificadores, y no carga cuentas, capturas,
configuración privada ni aplicaciones sociales.

### Fallar cerrado ante el runner ausente

El release original no publica la implementación personalizada requerida. No
se clona, compila o firma un sustituto. La garantía actual termina en el
diagnóstico USB y no se presenta como instalación de AutoWarmer en un iPhone.

### No inventar soporte de proxy

La versión original no ofrece una configuración funcional de proxy. Las
referencias externas no se inyectan en esta herramienta.
