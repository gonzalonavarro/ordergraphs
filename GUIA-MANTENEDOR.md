# Guía para el mantenedor

## Puesta en marcha (una sola vez)

1. En GitHub, crea un repositorio **público** llamado `ordergraphs` (botón **New**), sin README.
2. Sube los archivos de esta carpeta (ver abajo, "Subir los archivos").
3. **Settings → Pages**: en *Source* elige *Deploy from a branch*, rama `main`, carpeta `/docs`, y
   guarda. En un par de minutos la página queda en `https://gonzalonavarro.github.io/ordergraphs/`.
4. **Settings → Actions → General**: en *Workflow permissions* marca *Read and write permissions*
   y guarda.
5. **Actions → Set up labels → Run workflow**: crea las etiquetas `new-result`, `verified`,
   `invalid` y `approved`.
6. Comprueba en `data/site.json` que `repository` sea `gonzalonavarro/ordergraphs` y que el
   enlace del paper sea el correcto (ya vienen así). Si editas ese archivo en GitHub, la página se
   regenera sola.

## Día a día

* Cuando alguien envía un resultado, llega como un *issue* y te avisa GitHub por correo. A los
  pocos minutos un bot comenta si el grafo es completo y cuántas aristas tiene, y le pone la
  etiqueta `verified` o `invalid`.
* Para **aprobarlo**, abre el issue y agrégale la etiqueta `approved` (columna derecha,
  *Labels*). El resultado se agrega a la página y el issue se cierra solo.
* Para **rechazarlo**, cierra el issue con un comentario.
* Para **corregir** algo de un resultado ya publicado (por ejemplo, el comentario o la
  referencia), edita su `results/.../result.json` en GitHub; la página se regenera sola.
* Si un contribuyente manda un resultado por correo, puedes crear tú mismo el issue con el
  formulario (botón *Submit a new result* de la página) y aprobarlo.

## Cotas inferiores

* Las cotas inferiores llegan con otro formulario ("Lower-bound claim") y la etiqueta
  `lower-bound`. El bot no puede verificar la demostración: solo revisa que esté bien escrita, que
  traiga una referencia o enlace, y que la cota no supere el tamaño de un grafo ya verificado (en
  ese caso sería falsa).
* Al aprobarla con `approved`, se publica como **unverified claim**: aparece en la sección
  "Lower-bound claims" y en la tabla como un valor entre paréntesis con signo de interrogación,
  sin cambiar la cota ni las marcas de "optimal".
* Si más adelante la das por buena (por ejemplo, porque se publicó con revisión de pares), edita
  su `claims/NNNN-.../claim.json` en GitHub y cambia `"status": "claimed"` por
  `"status": "accepted"`. Entonces pasa a ser la cota de la tabla.

Solo el dueño del repositorio puede aprobar: la etiqueta `approved` puesta por otra persona no
tiene efecto.

## Límites contra el abuso

* Para enviar hace falta una cuenta de GitHub, que GitHub ya protege contra bots.
* La verificación corre en servidores de GitHub, gratis para repositorios públicos: no usa
  recursos tuyos ni del DCC.
* Cada envío tiene a lo más 5 minutos de verificación, se aceptan d entre 3 y 12, y cada persona
  puede pedir a lo más 5 verificaciones automáticas en 24 horas (tú no tienes límite). Si alguien
  edita un envío muchas veces seguidas, solo cuenta la última edición.
* Si alguna vez hay un ataque, en **Settings → Moderation options → Interaction limits** puedes
  restringir temporalmente quién abre issues (por ejemplo, solo cuentas con historial previo en
  el repositorio). Para bloquear a una persona: **Settings → Moderation options → Blocked users**.

## Página en el DCC

Para tener también `www.dcc.uchile.cl/gnavarro/ordergraphs`, sube allí el archivo
`dcc-redirect/index.html`, que redirige a la página de GitHub (edita antes la dirección).
