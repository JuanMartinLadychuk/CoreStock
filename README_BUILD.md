# Build & Release — CoreStack Pro

Guía para generar el ejecutable que el cliente descomprime y usa.
Objetivo: **cero Python instalado, cero consola, cero configuración manual**
en la PC del comerciante.

---

## 0. Preparación (una sola vez)

1. Copiá estos archivos a la raíz del proyecto (junto a `main.py`):
   - `paths.py`
   - `app_config.py`
   - `CoreStackPro.spec`
   - `version_info.txt`
   - `build.bat`
   - `requirements.txt` (o fusioná con el actual)
   - `README_USUARIO.txt`

2. Creá la carpeta `assets/` y poné ahí `icon.ico` (256x256, formato
   `.ico` real, no un `.png` renombrado). Si todavía no tenés icono,
   comentá las líneas `icon="assets/icon.ico"` en el `.spec`.

3. **Importante — wiring de rutas persistentes:** `init_db.py` y
   `db.py` hoy escriben `corestack.db` y leen `network.json` con
   rutas relativas a `__file__`. Cuando el `.exe` corre desde
   `_MEIPASS` (carpeta temporal de PyInstaller), esas rutas se
   pierden entre ejecuciones. Reemplazá:

   ```python
   _DB_FILE = pathlib.Path(__file__).parent / "corestack.db"
   ```

   por:

   ```python
   from paths import data_path
   _DB_FILE = pathlib.Path(data_path("corestack.db"))
   ```

   Mismo criterio para `network.json` y cualquier archivo que la app
   escriba (exports de Excel/PDF pueden seguir pidiendo ruta al
   usuario vía `filedialog`, esos están bien).

   **No te olvides de `neon_db.py`** — tiene el mismo patrón:

   ```python
   _CONFIG_FILE = Path(__file__).parent / "neon_config.json"
   ```

   por:

   ```python
   from paths import data_path
   _CONFIG_FILE = Path(data_path("neon_config.json"))
   ```

   Y en `init_db.py` → `ensure_db()`, la línea que lee `network.json`
   con `Path(__file__).parent / "network.json"` necesita el mismo
   cambio a `data_path("network.json")`.

4. Si vas a manejar credenciales de MariaDB / DSN de Neon por
   cliente sin recompilar, migrá esas lecturas a `app_config.py`
   (`load_config()`), que persiste en `data/config.ini`.

---

## 1. Compilar

Con Python 3.11+ instalado en tu PC de desarrollo:

```bat
build.bat
```

Esto:
1. Crea un `venv` limpio e instala dependencias.
2. Corre PyInstaller con `CoreStackPro.spec`.
3. Arma `dist/CoreStackPro/` con el `.exe` + carpetas `data/` y `logs/`.
4. Genera `CoreStackPro_v0.9.zip` listo para entregar.

---

## 2. Los 3 errores típicos y cómo resolverlos

### "ModuleNotFoundError: No module named 'X'" al abrir el .exe
PyInstaller no detectó un import dinámico. Agregalo a
`hiddenimports` en `CoreStackPro.spec` (sección
`dynamic_frame_modules` o `extra_hidden`) y recompilá.

### La app abre pero los datos "desaparecen" al reabrirla
Algún módulo está escribiendo en `_MEIPASS` (carpeta temporal,
se borra). Revisá que `init_db.py` / `db.py` usen `paths.data_path()`
como se indica en el paso 0.3.

### Windows Defender / SmartScreen marca el .exe como sospechoso
Es normal con `--onefile` o ejecutables sin firma. Por eso usamos
`--onedir`. Para eliminarlo del todo a futuro: certificado de firma
de código (Authenticode), ~100-250 USD/año.

---

## 3. Probar antes de entregar (checklist)

- [ ] Copiar **solo** `CoreStackPro_v0.9.zip` a una PC sin Python
- [ ] Descomprimir en `C:\CoreStackPro` (ruta sin tildes ni espacios
      raros, por las dudas con encoding de SQLite/MariaDB)
- [ ] Abrir `CoreStackPro.exe` → debe pedir login
- [ ] Login con `admin / admin123`
- [ ] Cargar una venta de prueba en POS
- [ ] Cerrar la app y volver a abrirla → la venta debe seguir ahí
- [ ] Revisar `logs/` → no debería haber errores

---

## 4. Próximo nivel: instalador real (opcional)

Cuando el ZIP ya funcione perfecto, el siguiente salto comercial es
un instalador con **Inno Setup** (gratis):
- Crea acceso directo en el Escritorio y Menú Inicio
- Permite desinstalar desde "Programas y características"
- Puede pedir permisos de admin para escribir en `C:\Program Files`
  (si hacés esto, `data/` debe ir a `%APPDATA%\CoreStackPro` en vez
  de junto al `.exe` — ajustar `paths.py` llegado el momento)

No es necesario para el lanzamiento inicial: el ZIP + `.exe` ya
resuelve "descomprimir y que ande".

---

## 5. Extra opcional: ConfigurarRed.exe

`configure_lan.py` es un script de consola interactivo (usa `input()`)
para configurar modo servidor/cliente. Si querés dárselo al soporte
técnico como herramienta separada (no al cliente final), compilalo
aparte — acá SÍ tiene sentido `--onefile` y `console=True` porque es
una utilidad de terminal:

```bat
pyinstaller configure_lan.py --onefile --name ConfigurarRed --console
```

Esto genera `dist\ConfigurarRed.exe`. Recordá que también lee/escribe
`network.json` con `__file__` — si lo distribuís junto al resto,
aplicale el mismo patch de `data_path()` que a `db.py`, o pedile al
técnico que lo corra **desde la carpeta `data/`** de la instalación.
