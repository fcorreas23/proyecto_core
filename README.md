# Proyecto Core GATE 1

Repositorio del proyecto Core de Skillnest. Este README ofrece una guía inicial para explorar y poner en marcha el proyecto.

## Cómo empezar

Estos pasos se completan de forma progresiva a lo largo de la Unidad U1.2, no todos el mismo día:

1. Clona este repositorio y entra a su carpeta:

   ```bash
   git clone https://github.com/fcorreas23/proyecto_core.git
   cd proyecto_core
   ```

2. Crea tu entorno virtual de Python y actívalo. Los comandos cambian según tu sistema operativo:

   **Windows (PowerShell)**

   ```powershell
   python -m venv venv
   venv\Scripts\Activate.ps1
   ```

   > Si usas la terminal `cmd` en vez de PowerShell, actívalo con `venv\Scripts\activate.bat`. Si PowerShell bloquea el script, ejecuta antes `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.

   **Linux / macOS**

   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

   Sabrás que el entorno está activo porque la terminal muestra `(venv)` al inicio de la línea.

3. Instala las dependencias del proyecto:

   ```bash
   pip install -r requirements.txt
   ```

4. Copia `.env.example` a un archivo nuevo llamado `.env` y completa ahí tu API key de Gemini en `GEMINI_API_KEY`:

   **Windows (PowerShell)**

   ```powershell
   Copy-Item .env.example .env
   ```

   **Linux / macOS**

   ```bash
   cp .env.example .env
   ```

   El archivo `.env` está en `.gitignore`: nunca lo subas al repositorio.

5. Ejecuta la aplicación:

   ```bash
   python src/consumir_api.py
   ```

## Estructura

- `src/`: todo el código fuente del proyecto va aquí.
- `prompts/`: banco de prompts de la miniaplicación (`banco.py`) y registro de las pruebas de consistencia (`registro_resultados.json`).
- `docs/`: documentación técnica del proyecto (diagramas, decisiones de arquitectura, notas).
- `requirements.txt`: dependencias de Python del proyecto, para que cualquier otra persona pueda reconstruir el entorno con un solo comando.
- `.env.example`: plantilla de las variables de entorno que el proyecto necesita, sin valores reales. El archivo `.env` real (con tus credenciales) nunca se commitea.
- `.gitignore`: le dice a Git qué archivos y carpetas ignorar (entre ellos, el entorno virtual y el archivo `.env`).

## Contribuciones

Mantén los cambios enfocados y verifica que las pruebas disponibles pasen antes de enviar una contribución.
