# CONNECTORS.md - Integración con la Nube

Pegaso no utiliza APIs inestables para las nubes. Utilizamos **Sincronización por Carpeta**, que es el método más robusto y seguro.

## 📁 Google Drive
1. Instala `rclone`.
2. Configura un remoto `gdrive:`.
3. Monta o sincroniza en `./data/cloud_sync/gdrive`:
   ```bash
   rclone bisync gdrive: /home/jmpicon/Documentos/Pegaso/data/cloud_sync/gdrive --resync
   ```

## 🍎 iCloud
Linux no tiene cliente oficial. 
- **Opción A:** En un Mac o Windows con iCloud oficial, usa **Syncthing** para compartir la carpeta de iCloud con `./data/cloud_sync/icloud` en tu Slimbook.
- **Opción B:** Usa `icloud-drive-docker` (contenedor de terceros que simula el cliente).

## 🔋 Proton
- **Drive:** Actualmente solo vía exportación manual o `rclone` (si el soporte experimental está activo).
- **Mail:** Usa **Proton Bridge** en tu SlimOS y configura el conector IMAP en `src/tools/email.py` (Próximamente).

## 🛡️ Regla de Oro
Pegaso solo lee el contenido una vez que está físicamente en `./data/cloud_sync`.
