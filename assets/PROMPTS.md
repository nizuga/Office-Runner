# Prompts de generación

Todos los assets se generaron con la herramienta integrada `image_gen` usando
el caso `stylized-concept`. No se usaron marcas ni personajes de terceros.

## Dirección visual

> Pixel art moderno de 32 bits para un runner de oficina: empleado de camisa
> azul visto desde atrás, PDF rojo perseguidor, jefe en traje morado, cajas
> ámbar, sillas rojas y oficina azul-gris al atardecer; perspectiva central de
> tres carriles, siluetas claras, paleta limitada, sin texto ni marcas.

## Jugador

> Hoja horizontal de exactamente tres poses del mismo empleado visto desde
> atrás: carrera A, carrera B con extremidades opuestas y salto con ambos brazos
> arriba. Misma escala, línea base, ropa, cabello y proporciones. Pixel art
> nítido sobre croma uniforme #00ff00, sin sombras, texto o elementos extra.

Para reemplazar el deslizamiento de dos poses se genero una segunda hoja con
seis cuadros, conservando exactamente el personaje anterior:

> Ciclo de carrera de seis cuadros en reticula 3x2, leido de izquierda a
> derecha: contacto del talon izquierdo, apoyo/compresion, impulso y vuelo;
> luego las mismas tres fases con la pierna derecha. Separacion fuerte de
> piernas, rodilla de paso flexionada y brazos en contramovimiento. Misma
> escala, linea base, ropa y proporciones en todos los cuadros; pixel art
> nitido sobre croma uniforme #00ff00, sin sombras, texto, bordes ni rejilla.

## Jefe

> Jefe de oficina aislado, cuerpo completo y vista frontal: cabello oscuro,
> cejas gruesas, traje morado, camisa blanca, corbata roja y puños en la cintura.
> Pixel art consistente con la referencia, croma #00ff00 y sin utilería.

## Obstáculos y perseguidor

> Silla ergonómica roja aislada, vista frontal, respaldo alto, apoyabrazos,
> columna y ruedas completas; silueta alta y legible como peligro.

> Monstruo-documento rojo aislado corriendo hacia la cámara, esquina blanca
> doblada, rostro enfadado, brazos y piernas; sin letras ni logotipos reales.

> Barrera horizontal continua de cinco cajas ámbar con cinta clara, una sola
> fila y misma línea base, pensada para cubrir los tres carriles.

Todos usan pixel art nítido, croma uniforme #00ff00, sin sombras proyectadas,
texto, marcas, fondos o elementos adicionales.

## Fondos

> Pasillo corporativo vacío al atardecer, cubículos y monitores fuera de la
> pista, ventanas con ciudad naranja, luces de oficina y señal de salida. Lienzo
> vertical 3:5, punto de fuga al 50% del ancho y 30% del alto, tres carriles
> despejados, centro del horizonte libre para el jefe.

> Variante de pausa de agua preservando geometría y encuadre: oficina nocturna
> tranquila, luz azul, plantas, dispensador de agua fuera de la pista y centro
> despejado para texto. Sin personajes, obstáculos o UI.

> Limpieza del fondo de gameplay: eliminar únicamente las líneas de carril y
> marcas transversales horneadas en el tapete, reconstruyéndolo con la misma
> textura azul; preservar exactamente oficina, perspectiva, iluminación y
> encuadre. Los carriles finales los dibuja el motor.

## Interfaz

> Hoja 2x2 con cuatro iconos: emblema de corredor azul y documento rojo; salto
> con brazos y flecha ámbar; esquive con torso y flechas rojas; estiramiento con
> brazos cruzados y destellos verdes. Insignias circulares azul marino, legibles
> a 48 px, sin palabras, bordes ni marcas, sobre croma #00ff00.
