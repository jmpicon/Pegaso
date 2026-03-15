# SECURITY.md - Modelo de Amenazas y Seguridad

Pegaso está diseñado bajo el principio de **Zero Trust Local**.

## Capas de Seguridad
1. **Sandboxing:** La API está en un contenedor Docker con privilegios limitados.
2. **Allowlist de Carpetas:** Pegaso NO puede leer nada fuera de las carpetas especificadas en `config/permissions.yaml`. Por defecto, el montaje es `:ro` (Solo Lectura).
3. **Privacidad de Internet:** Las búsquedas pasan por SearXNG, eliminando cookies y trackers antes de enviarlos a motores externos.
4. **Secretos:** No se persisten claves API de terceros en el historial de chat (filtro de PII planeado).
5. **Auditoría:** Todas las lecturas de archivos y ejecuciones de comandos se registran en `data/audit.log`.

## Recomendaciones
- No habilitar el permiso de escritura en `Vault` a menos que sea necesario para el auto-resumen.
- Usar `Authentik` para el acceso remoto si decides abrir puertos (Perfil Enterprise).
