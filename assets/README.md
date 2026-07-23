# Assets visuales

Paquete original de pixel art moderno creado para Office Runner con la herramienta
integrada de generacion de imagenes. La direccion visual usa azul para el jugador,
ambar para saltar, rojo para peligro, morado para el jefe y verde para exito.

## Estructura

- `sprites/`: PNG transparentes listos para Pygame, incluido el ciclo de carrera
  de seis cuadros (`player_run_0` a `player_run_5`) y la pose de salto.
- `backgrounds/`: fondos RGB de 540x900.
- `ui/`: iconos transparentes de 72x72.
- `source/`: referencias y salidas originales para poder reconstruir los finales.

Los sprites se generaron sobre croma verde uniforme, se procesaron con
`remove_chroma_key.py` de la skill `imagegen` y se normalizaron mediante:

```powershell
python tools\build_visual_assets.py
```

El juego conserva fallbacks procedurales cuando falta cualquier archivo.
