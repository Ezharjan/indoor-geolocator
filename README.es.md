# indoor-geolocator

[English](README.md) · [简体中文](README.zh-CN.md) · [Português](README.pt-BR.md) · [Français](README.fr.md) · **Español** · [日本語](README.ja.md) · [Deutsch](README.de.md)

Una skill para agentes que averigua **dónde se tomó una foto de interior**: una habitación de hotel, un
piso, un restaurante, una tienda, una estación, un museo, un aula, un coche. Devuelve el lugar, la
dirección, las coordenadas con un radio de error y un nivel de confianza que las pruebas realmente
respaldan. Además deja una carpeta de caso ordenada que muestra cada paso del razonamiento.

Es una herramienta OSINT de código abierto para la geolocalización de imágenes con agentes de IA: razonamiento al estilo GeoGuessr para interiores, apoyado en búsqueda inversa de imágenes, OCR, metadatos EXIF y verificación con fotos de referencia.

**Página del proyecto y demostración interactiva:** https://ezharjan.github.io/indoor-geolocator/

Adjunta una foto e invoca la skill. No hace falta ningún prompt. La respuesta llega en el idioma del
usuario y tiene esta forma (los valores son ilustrativos):

```
📍 <Lugar> — <dirección, ciudad, país>
   51.044560, -114.064700 (WGS84) ± 60 m · nivel: site · confianza: MEDIUM
Por qué: ... las 2 a 4 pruebas decisivas, cada una con su fuente y cómo se verificó
Verificado contra: ... las fotos de referencia comparadas, los rasgos que coincidieron, el rival que se probó
Mejor pista (sin verificar): ... un candidato más fino, sus coordenadas (el punto más probable) y la prueba que lo confirmaría
Alternativas: ... el segundo clasificado, su probabilidad y la prueba que los separaría
Sin verificar / límites: ... lo que no se pudo comprobar y por qué
Carpeta del caso: .../photo-geolocation (REPORT.md contiene todo el razonamiento)
```

## Qué hace

La skill da al modelo un flujo de trabajo estricto, que antepone la exactitud, y una caja de herramientas
de línea de comandos (`scripts/igl.py`, Python 3.9+, Pillow). Cada observación entra en un único registro,
y la clasificación y la confianza se calculan a partir de ese registro en lugar de afirmarse.

Las fotos de interiores se localizan mal por un puñado de razones, y el flujo está construido en torno a
ellas: una sala parecida se toma por el lugar, se conserva el primer candidato verosímil, la salida de una
máquina (OCR sobre una alfombra, la etiqueta de un buscador, una búsqueda que nunca se ejecutó) se lee
como un hecho, un objeto portátil se lee como el edificio, una marca se toma por una sucursal, y la
precisión se inventa.

1. **Entrada.** Copia la foto byte a byte. Lee EXIF, GPS, XMP, IPTC, ICC, la miniatura incrustada (un
   recorte o una edición se nota), el patrón del nombre de archivo, los marcadores de IA y las
   credenciales de contenido C2PA, y convierte el desfase UTC en husos horarios. Comprueba en cinco
   segundos a qué servicios en línea llega la caja de herramientas.
2. **Primero las hipótesis.** Se registran de dos a cuatro hipótesis ordenadas antes de cualquier salida
   de herramienta (defensa contra el anclaje).
3. **Leer toda la foto.**
   - OCR filtrado por precisión (la textura no se informa como texto), códigos QR y códigos de barras
     con interpretación del contenido (códigos de pago EMV, facturas QR suizas, SEPA, UPI, Wi-Fi,
     vCards, prefijos GS1), minería de texto (teléfonos hasta la ciudad, dominios, precios, códigos
     postales, unidades, términos fiscales).
   - Un catálogo de unas 200 pistas, leído por el agente sobre teselas superpuestas: portadores de
     identidad (nombres, arte único, la vista), estándares fijos (enchufes, interruptores, fontanería,
     señales de seguridad) y referencias locales (un cuadro de un monumento local, un mapa, un folleto).
4. **Encontrar candidatos.**
   - **Búsqueda inversa de imágenes** sin interfaz en Yandex, TinEye y Baidu, con Google Lens y Bing
     mediante una herramienta de navegador. Cada resultado se compara con la foto y se clasifica como
     **COPY** (la misma fotografía: procedencia), **SAME SCENE** / **PARTIAL** (estructura coincidente)
     o **unconfirmed**.
   - **Búsqueda de imágenes por texto** (`refs`): búsquedas de imágenes de un lugar, o de todos los
     lugares de un tipo en una zona. Las imágenes se comparan con la foto y se muestran **de la más
     parecida a la menos parecida** (DINOv2), de modo que el lugar correcto aflora aunque ningún pie de
     foto lo describa. En una prueba, dos búsquedas genéricas de bares de hotel en un estado de EE. UU.
     colocaron el bar real en primer lugar entre 100 imágenes de bares distintos.
   - Nombres, teléfonos, URL y nombres de Wi-Fi con la búsqueda web del propio agente; estándares fijos
     cruzados entre 250 países sin conexión; todos los lugares de un tipo enumerados desde
     OpenStreetMap y Wikidata; anuncios y redes sociales (centrados en lugares).
5. **Verificar: la barrera entre una pista y una respuesta.** Primero se escribe una prueba de
   falsación. Las fotos del propio candidato se ponen junto a la foto, y se cuentan rasgos fijos
   concretos (ventanas, techo, elementos empotrados, la vista, arte hecho para el lugar; el mobiliario
   solo demuestra un diseño). El rival más cercano pasa por la misma comparación. Si el rival también
   «coincide», los rasgos son un diseño compartido: la coincidencia se registra para la zona del
   grupo, y los lugares siguen siendo pistas.
6. **Coherencia.** Huso horario, sol, tiempo, estación y estándares se contrastan con el candidato, se
   argumenta a favor del segundo clasificado, y el paso decisivo se repite de otra manera.
7. **Decisión.** La respuesta es el nivel más fino que las pruebas verifican. Un lugar sin verificar
   dentro de una zona verificada se informa como la mejor pista, con sus propias coordenadas (el punto
   más probable), nunca como la respuesta. La carpeta del caso se finaliza y se depura.

### Reglas de exactitud integradas en el código

- **Topes por estado.** El peso de una pista está limitado por cómo se obtuvo: una inferencia ≤3, una
  observación ≤6, un informe de terceros ≤10, metadatos del archivo o una copia rastreada de la foto
  ≤20, texto leído en un recorte ampliado o un resultado calculado ≤50, una coincidencia con imágenes
  de referencia independientes ≤100. La etiqueta de un buscador es una pista (≤3), diga lo que diga.
- **Pistas que identifican y pistas de categoría.** Una pista decisiva (un nombre leído en la foto, un
  código decodificado, GPS, una copia rastreada, una referencia coincidente) identifica un solo lugar y
  se pondera contra todas las alternativas juntas: LR 50 significa unos 50:1, por muchos rivales que se
  hayan listado. Una pista de categoría (un tipo de enchufe, un idioma, un estilo) compite con cada
  alternativa una a una, de modo que solo varias juntas deciden un país.
- **Coincidencias auditables.** Una pista `matched` debe nombrar al menos tres rasgos fijos concretos y
  citar el archivo de la comparación. Una copia de la foto se rechaza como coincidencia: es
  procedencia, registrada como `traced` con su página.
- **El control con el rival.** Una coincidencia con una referencia solo alcanza HIGH cuando un lugar
  rival pasó por la misma comparación, o cuando un segundo linaje decisivo (un nombre leído en la foto,
  GPS, una copia rastreada) señala el mismo lugar.
- **Un lugar necesita una pista decisiva.** El parecido, las etiquetas de buscadores y los pies de foto
  dejan un lugar en LOW, por muchos que coincidan: esa combinación es exactamente lo que produce un
  doble.
- **Linajes independientes.** El acuerdo solo cuenta entre fuentes independientes (image, text,
  metadata, web, engine, map, reference, geometry). Cinco pistas de decoración son un solo linaje.
- **Un tablero abierto y coherente.** Las alternativas no listadas conservan una cuota en todos los
  niveles, una ciudad nunca es más segura que su país, y una contradicción contra un país también
  bloquea HIGH para el hotel que está en él.
- **Fallo honesto.** Una búsqueda bloqueada o que nunca empezó se informa como tal, nunca como «sin
  resultados». Las imágenes sin confirmar nunca se califican de «diferentes».
- **Barrera de cobertura.** Trece métodos principales deben terminar cada uno como results, no_results
  o not_applicable antes de que `check` pase; `check` también señala un sitio sin comparación con
  referencias o sin rival, un rival que también coincidió y búsquedas inversas que nunca se ejecutaron.

## Instalación

### Instalar con un solo prompt

En Claude Code, o en cualquier agente que pueda ejecutar comandos de shell, basta con decir: **«Instala la skill indoor-geolocator desde https://github.com/Ezharjan/indoor-geolocator»**. El resto de esta sección está escrito para el agente.

**Instrucciones para agentes de IA.** Para instalar esta skill al usuario, ejecuta:

```bash
curl -L -o indoor-geolocator.zip https://github.com/Ezharjan/indoor-geolocator/releases/latest/download/indoor-geolocator.zip
mkdir -p ~/.claude/skills && unzip -o indoor-geolocator.zip -d ~/.claude/skills    # crea ~/.claude/skills/indoor-geolocator/
python3 -m pip install -r ~/.claude/skills/indoor-geolocator/requirements.txt
python3 ~/.claude/skills/indoor-geolocator/scripts/igl.py doctor                   # informa de qué funciona y qué falta
```

- En Windows, la carpeta de skills es `%USERPROFILE%\.claude\skills\`: descomprime con `Expand-Archive` y llama a `python` en lugar de `python3`.
- No instales los extras opcionales en silencio. Muestra al usuario lo que `doctor` señala como ausente y ofrece `requirements-optional.txt`, porque esos paquetes son grandes.
- Comprueba que `~/.claude/skills/indoor-geolocator/SKILL.md` existe y luego dile al usuario que la skill está disponible en una sesión nueva como `/indoor-geolocator`.
- En una conversación de claude.ai o Claude Desktop, un agente no puede añadir una skill por sí mismo. Dale al usuario el enlace del zip de arriba y los tres pasos de subida de abajo.

**claude.ai, Claude Desktop y Cowork.**
1. Asegúrate de que la ejecución de código está activada (*Settings → Capabilities*). El acceso a la red
   para la ejecución de código ayuda (la caja de herramientas llega entonces por sí misma a los
   servicios de mapas y de búsqueda inversa); sin él, el agente hace esos pasos con sus propias
   herramientas de búsqueda web, fetch y navegador.
2. Abre *Customize → Skills*, haz clic en **+**, elige **+ Create skill → Upload a skill** y selecciona
   `indoor-geolocator.zip`.
3. Adjunta una foto e invoca la skill, o simplemente pregunta «¿dónde se tomó esto?».

El zip contiene la carpeta `indoor-geolocator/` en su nivel superior, como exige la subida.

**Claude Code.** Copia la carpeta `indoor-geolocator/` en `~/.claude/skills/` (todos los proyectos) o
`<project>/.claude/skills/` (un proyecto). Invócala con `/indoor-geolocator`, o deja que Claude la
recoja cuando compartas una foto de interior.

**Otros agentes** (Codex, Gemini CLI, Cursor, …): apunta el agente a `indoor-geolocator/SKILL.md`. La
caja de herramientas es una CLI de Python sencilla.

**Dependencias.** Pillow es obligatorio, y también `tzdata` en Windows. Todo lo demás es opcional y solo
habilita su método.

```bash
pip install -r indoor-geolocator/requirements.txt             # Pillow (+ tzdata, necesario en Windows)
pip install -r indoor-geolocator/requirements-optional.txt    # OpenCV + numpy, Playwright, onnxruntime, phonenumbers, HEIC, RapidOCR
playwright install chromium                                   # búsqueda inversa sin interfaz, búsqueda de imágenes, capturas de páginas
# Motor de OCR (recomendado): tesseract con paquetes de idiomas
#   apt install tesseract-ocr-all  |  brew install tesseract tesseract-lang  |  winget install UB-Mannheim.TesseractOCR
python indoor-geolocator/scripts/igl.py doctor                 # qué funciona aquí, qué falta
```

Tres extras son los que más importan para la exactitud: OpenCV (las pruebas COPY / SAME SCENE),
Playwright con Chromium (búsqueda inversa de imágenes y búsqueda de imágenes) y onnxruntime (imágenes
ordenadas por parecido con la foto). El modelo de similitud (DINOv2 ViT-S/14, 24 MB, Apache-2.0) no forma
parte de la skill: se descarga una vez desde huggingface.co en el primer uso y se comprueba con un
SHA-256. `IGL_NO_EMBED=1` lo desactiva.

## Usar la caja de herramientas directamente

```bash
IGL="python3 indoor-geolocator/scripts/igl.py"
$IGL init photo.jpg                                    # carpeta del caso + metadatos + cuadrícula + comprobación de red
$IGL note CASE "Hypotheses: 1) ... 2) ..." --kind hypothesis --status inferred --source image
$IGL scan CASE                                         # OCR, QR/códigos de barras, señales de texto, teselas de barrido
$IGL crop CASE --cell C3:D4 --enhance auto --label socket
$IGL revsearch CASE --cell B2:C3 --flip                # Yandex, TinEye, Baidu; cada resultado clasificado frente a la foto
$IGL share CASE --cell B2:C3                           # enlaces para Google Lens y Bing (copia temporal)
$IGL countries --plug G --currency £ --drive left --case CASE --clue N2
$IGL refs CASE "hotel lounge sea view Poole"           # imágenes de toda una zona, las más parecidas primero
$IGL geo poi --tag tourism=hotel --area "Poole" --case CASE --add site --parent C3
$IGL refs CASE "Hotel Name Poole lounge" --for C12     # las fotos de un candidato junto a la tuya
$IGL compare CASE --refs E14 --pick 3,7 --for C12      # comparación grande lado a lado + pruebas de coincidencia
$IGL note CASE "Matches a traveller photo (2023)" --kind match --status matched --source reference --file E16 \
     --features "arched window pair; coffered ceiling 3x4; green marble fireplace" --for C12:60 --why "..."
$IGL refs CASE "Rival Hotel Poole lounge" --for C13    # el control con el rival
$IGL rank CASE
$IGL answer CASE C12 --summary "..."
$IGL check CASE
$IGL finalize CASE
```

`$IGL <command> -h` documenta todas las opciones. En Windows usa `python` en lugar de `python3`. Las
coordenadas del sur y del oeste funcionan tal como se escriben (`--at -33.86,151.21`).

## Qué obtienes

```
photo-geolocation/
├── REPORT.md       la respuesta, la mejor pista, la confianza por nivel, las pruebas, los candidatos, la cronología, los métodos, el tratamiento de datos
├── result.json     lo mismo en JSON legible por máquina (esquema igl.result/1)
├── case.json       el registro completo: pistas, candidatos, vínculos, exclusiones, intentos, marcas de tiempo
├── input/          la foto (copia exacta) y metadata.json
└── evidence/       solo los recortes, hojas, vistas de comparación y capturas que el registro cita
```

El trabajo de borrador (teselas, cachés, descargas) vive en `.work/` y lo borra `finalize`, que también
elimina todo archivo de prueba que nada cite. Una carpeta de caso existente nunca se sobrescribe.

## Privacidad y uso responsable

- **Las personas no son objetivos.** Sin reconocimiento facial y sin identificación de individuos.
  - La ropa, los uniformes, las insignias y los objetos personales se usan solo por lo que dicen del
    lugar.
  - La etnia aparente se trata como contexto débil y propenso al sesgo, nunca como exclusión.
  - En las redes sociales se buscan lugares, texto, etiquetas y la propia foto, nunca personas ni
    autores de publicaciones.
- **Viviendas particulares.** Ante una residencia particular identificable sin finalidad declarada, la
  skill pregunta una vez para qué es el resultado. Sin una finalidad legítima se detiene en el nivel de
  ciudad o barrio.
- **Ocultación.** Los nombres de particulares y las direcciones de domicilios quedan fuera de los
  informes. Las contraseñas de Wi-Fi, los IBAN y los nombres de las tarjetas de contacto se ocultan
  allí donde se decodifican o donde un buscador o una página los devuelve.
- **Subidas.** La búsqueda inversa de imágenes sube la foto (sin metadatos) a los buscadores. `share`
  coloca una copia sin metadatos en un alojamiento temporal (borrada al cabo de 1 a 3 horas) para Lens
  y Bing, y `revsearch` hace lo mismo por su cuenta cuando falla el formulario de subida de un buscador
  (`--no-share` lo impide). El informe enumera cada buscador y cada copia temporal. `refs` envía solo
  texto de búsqueda, y el modelo de similitud se ejecuta en local. Prefiere recortes sin personas; no
  se sube nada sin preguntar cuando el usuario marca una foto como privada.
- **Servicios.** La skill respeta las políticas de los servicios (Nominatim ≤1 petición/s, consultas
  Overpass acotadas, User-Agent identificable). Nunca inicia sesión en nombre de nadie, nunca resuelve
  CAPTCHA y nunca extrae datos en masa. Claves opcionales del usuario: `SERPAPI_KEY` para Google Lens
  dentro de `revsearch`, `WIGLE_API_NAME` / `WIGLE_API_TOKEN` para consultas de SSID de Wi-Fi.
  `IGL_USER_AGENT` establece un User-Agent personalizado.

Los resultados de geolocalización son estimaciones ponderadas por las pruebas, no certezas. Lee la
confianza, la mejor pista y la línea «sin verificar» antes de actuar a partir de una respuesta.

## Estructura del repositorio

```
.
├── indoor-geolocator/          LA skill (esta carpeta es lo que se instala)
│   ├── SKILL.md                flujo de trabajo, reglas de prueba, conducta, formato de respuesta
│   ├── LICENSE.txt             copia de LICENSE (el zip se entrega sin la raíz del repositorio)
│   ├── requirements*.txt
│   ├── references/             catálogo de pistas, guías de escenas y de búsqueda, ventana/luz, verificación,
│   │                           pruebas y confianza, fuentes y herramientas
│   ├── scripts/igl.py          la CLI; scripts/iglib/ contiene sus módulos
│   └── data/                   countries.json, gs1_prefixes.json (+ README con fuentes y licencias)
├── indoor-geolocator.zip       la misma skill, empaquetada para subirla
├── build_skill_zip.py          reconstruye y verifica el zip (ejecútalo tras cada cambio en la skill)
├── tools/build_data.py         herramienta de mantenimiento: reconstruye data/ desde Unicode CLDR y Wikipedia
├── tools/make_demo.py          herramienta de mantenimiento: reconstruye docs/demo/ con la versión actual
├── tests/                      batería de pruebas sin conexión (pytest; `pytest.ini` apunta a ella)
├── docs/                       página del proyecto (GitHub Pages) con el caso de demostración publicado
├── LICENSE
├── README.md                   este README en inglés
└── README.*.md                 traducciones (zh-CN, pt-BR, fr, es, ja, de)
```

## Desarrollo

```bash
python -m pytest                   # pruebas sin conexión: reglas del registro, topes, coincidencia, ordenación, analizadores, geometría;
                                   # y además docs frente a CLI, el zip frente a la carpeta de la skill, la página del proyecto frente al caso de demostración
python tools/build_data.py         # actualiza data/ (guarda las fuentes en caché en .data-src/; --offline reconstruye desde la caché)
python tools/make_demo.py          # reconstruye el caso de demostración en docs/demo/ con la versión actual
python build_skill_zip.py          # reconstruye indoor-geolocator.zip si la carpeta cambió; --check solo verifica
```

## Registro de cambios

### 2.0.0

La versión de la exactitud: construida contra la respuesta errónea más común, un lugar doble nombrado con
seguridad.

- **Encontrar.** Nuevo comando `refs`: búsqueda de imágenes por texto (Brave, Startpage) y páginas de
  galería, con cada imagen comparada con la foto. Las imágenes y los resultados de búsqueda inversa se
  ordenan por similitud visual (DINOv2, opcional), de modo que las referencias más probables son las
  primeras teselas que ve el agente.
- **Búsqueda inversa.** Cada resultado se clasifica como COPY / SAME SCENE / PARTIAL / unconfirmed
  frente a la foto. Una búsqueda que nunca empezó es `unavailable`, no `no_results`; alternativa por
  URL cuando falla un formulario de subida; Google Lens opcional mediante la clave SerpApi del usuario.
- **Verificación.** Las pistas `matched` deben nombrar tres rasgos y citar la comparación; las copias
  se rechazan como coincidencias y se registran como procedencia `traced`;
  `compare --refs E## --pick`; el control con el rival es obligatorio para HIGH; las coincidencias de
  diseño se registran para la zona, con los lugares como pistas.
- **Confianza.** Las pistas decisivas se ponderan contra todo el campo (un lugar verificado ya no se
  diluye por los países no listados ni por los rivales que el agente enumeró); un lugar necesita una
  pista decisiva para MEDIUM; las etiquetas de buscadores tienen un tope de 3; las contradicciones
  bloquean HIGH a lo largo de la cadena; un sitio es al menos tan seguro como el sitio verificado que
  contiene.
- **Lectura.** La salida del OCR se filtra por precisión (se acabó el «texto» y las escrituras exóticas
  leídas en alfombras y techos); `scan` escribe una hoja con los recortes de texto; `crop --of` amplía
  cualquier imagen de prueba.
- **Robustez.** Alternativa Photon cuando Overpass no responde, descargas con reintentos, aviso de los
  límites de tasa en cada ejecución, métodos implicados por las pistas registradas, `log` con listas
  separadas por comas.
- **Salida.** Un marcador de mejor estimación (las coordenadas de la pista cuando la respuesta es más
  gruesa), una sección de verificación con el control del rival en el informe, tablas de candidatos
  que dicen qué es cada fila (la respuesta, un sitio que la contiene, la pista sin verificar, las
  alternativas fuera del tablero), `tools/make_demo.py` para reconstruir el caso de demostración, y
  pruebas que mantienen la página del proyecto fiel a ese caso y el zip fiel a la carpeta de la skill.

### 1.1.0

No se etiquetó ni se publicó por separado: estos cambios se publican por primera vez con la 2.0.0.

- Flujo reordenado en torno a las rutas de coincidencia exacta y a una barrera de verificación;
  hipótesis antes de la salida de las herramientas; reparto entre la caja de herramientas y las
  herramientas de búsqueda web, fetch y navegador del propio agente.
- Puntuación: un tablero abierto en todos los niveles, cuotas coherentes a lo largo de la cadena, las
  pistas de categoría no suben de nivel, barrera en la respuesta con una mejor pista aparte,
  comprobaciones previas al informe.
- Búsqueda inversa: se añade Baidu, hojas de contacto de imágenes similares, `share` para Lens y Bing
  por URL.
- `compare`: pruebas de casi duplicado, de misma fotografía y geométricas SIFT/RANSAC, con salas en
  espejo.
- Comprobación de red en `init`; `geo ... --print-url`; `note --for/--against` en una sola llamada;
  lector de C2PA.

### 1.0.0

Primera versión pública.

## Licencia

El código y la documentación se publican bajo la [MIT License](LICENSE). Los archivos de datos de
`indoor-geolocator/data/` conservan las licencias de sus fuentes:
- Campos de Unicode CLDR: [Unicode License v3](https://www.unicode.org/license.txt).
- Campos derivados de Wikipedia (tipos de enchufe, red eléctrica, lado de conducción, números de
  emergencia, prefijos GS1): [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/),
  © colaboradores de Wikipedia.

Los detalles están en [indoor-geolocator/data/README.md](indoor-geolocator/data/README.md).

Se adaptaron ideas de diseño de los proyectos de código abierto geo-sleuth, Geo-Guesser y Searching-skill:
reglas impuestas en el código, un tablero de candidatos por razón de verosimilitud, pruebas graduadas por
linaje, una barrera de cobertura de métodos, «la máquina ordena primero» con un orden de similitud DINOv2,
y verificación SIFT/RANSAC. El modelo de similitud es DINOv2 (Meta AI, Apache-2.0) en la exportación ONNX
publicada como `Xenova/dinov2-small`; se descarga en tiempo de ejecución y no se redistribuye aquí.
