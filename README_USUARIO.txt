=========================================
 CoreStack Pro v0.9 - Guia rapida
=========================================

INSTALACION
-----------
1. Descomprimi este ZIP completo en una carpeta fija, por ejemplo:
       C:\CoreStackPro\
   IMPORTANTE: no lo ejecutes desde dentro del ZIP ni desde la
   carpeta "Descargas" (algunos navegadores bloquean la escritura ahi).

2. Hace doble clic en CoreStackPro.exe

3. Si Windows muestra "Windows protegio tu PC":
       -> Click en "Mas info"
       -> Click en "Ejecutar de todas formas"
   Esto es normal en software nuevo que todavia no tiene firma
   digital. No es un virus.

PRIMER INICIO
-------------
- La primera vez que abris la app, se crea automaticamente:
    CoreStackPro\data\corestack.db     (tu base de datos local)
    CoreStackPro\data\network.json     (modo de red: server / client)
    CoreStackPro\logs\                 (registro de errores)

- Usuario y contrasena por defecto:
      usuario:     admin
      contrasena:  admin123
  CAMBIALA apenas entres, desde Configuracion -> Usuarios.

CONFIGURACION DE RED (varias terminales / cajas)
-------------------------------------------------
- La PRIMERA computadora que instales queda como "servidor"
  (modo "server" en data\network.json). Ahi vive la base de datos.

- En las OTRAS computadoras de la misma red, abri
  data\network.json con el Bloc de notas y configura:
      "mode": "client"
      "server_host": "<IP de la PC servidor>"
      "server_port": 5001
  (la IP del servidor la ves en Windows con "ipconfig", buscando
  "Direccion IPv4")

- Si preferis un asistente guiado en lugar de editar el JSON a mano,
  pedi al soporte tecnico la herramienta ConfigurarRed.exe (opcional).

RESPALDO (BACKUP)
-----------------
- Toda tu informacion vive en la carpeta "data". Para hacer un
  backup, simplemente copia esa carpeta a un pendrive o a la nube.

SOPORTE
-------
- Si algo falla, mandanos el archivo:
      CoreStackPro\logs\error.log
  junto con una descripcion de que estabas haciendo.
