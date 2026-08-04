# Token Analyzer — Optimización de Rendimiento

## De 231 segundos a menos de 5 segundos en ejecuciones sucesivas

---

## El punto de partida

Token Analyzer es una herramienta que procesa archivos Excel con miles de mensajes de citas médicas para analizar, traducir y optimizar su contenido antes de enviarlo a un LLM. El pipeline completo recorre cada mensaje detectando su idioma, extrayendo el esquema médico mediante heurística de keywords, contando tokens con tiktoken, traduciéndolo de español a inglés, optimizando el texto para eliminar frases redundantes y finalmente calculando el ahorro de tokens junto con una proyección de costos a escala. Al ejecutar este pipeline sobre un archivo real con aproximadamente nueve mil mensajes, el sistema tardaba 231 segundos en completarse. De ese tiempo, 230.9 segundos —el 99.7% del total— se consumían exclusivamente en la fase de traducción. Las otras fases del pipeline, como la agrupación de mensajes, la extracción de esquemas médicos o el conteo de tokens, se resolvían en menos de un segundo.

---

## El diagnóstico: ¿por qué 230 segundos?

El cuello de botella estaba claramente identificado. La traducción se realizaba mediante Google Translate a través de la librería `deep-translator`, que por cada invocación abría una conexión HTTP nueva con su correspondiente resolución DNS y handshake TLS. Para procesar los nueve mil mensajes, el sistema los agrupaba en veinte lotes según su esquema médico, y cada lote invocaba una función llamada `_traducir_lote` que concatenaba los textos con un separador especial y los enviaba en una sola petición HTTP. El problema surgía cuando el lote superaba los 4500 caracteres: en ese caso la función se dividía recursivamente en mitades, cada una generando su propia petición HTTP, y así sucesivamente hasta que cada fragmento cupiera en el límite. Esta división recursiva inflaba artificialmente el conteo: aunque solo había nueve mil mensajes reales, el sistema reportaba 70.773 textos procesados y 885 peticiones HTTP a Google Translate. Con diez workers concurrentes, cada petición tardaba en promedio 2.6 segundos entre conexión y respuesta, acumulando los 231 segundos totales. La causa raíz era doble: demasiadas peticiones HTTP y cada una con el overhead completo de establecer una conexión nueva.

---

## La estrategia de solución

Abordamos el problema en tres frentes complementarios. El primer frente, y el de mayor impacto, consistió en eliminar por completo las peticiones HTTP reemplazando Google Translate por un modelo de traducción neuronal ejecutado localmente. El segundo frente fue implementar una caché persistente para que ningún texto se tradujera más de una vez, ni siquiera entre reinicios del servidor. El tercer frente agrupó una serie de micro-optimizaciones que, aunque individualmente modestas, en conjunto aportaban una mejora significativa: compilación de expresiones regulares a nivel módulo, cacheo del encoding de tiktoken, conversión de listas de keywords a frozensets para búsqueda en tiempo constante, eliminación de una doble clasificación que se ejecutaba innecesariamente sobre los mismos datos, y lectura de archivos Excel directamente desde memoria sin pasar por archivos temporales en disco.

---

## Sustituyendo Google Translate por MarianMT

La decisión arquitectónica más importante fue migrar de un servicio externo de traducción a un modelo completamente local. Elegimos los modelos MarianMT de Helsinki-NLP, específicamente `opus-mt-es-en` para la dirección español a inglés y `opus-mt-en-es` para la dirección inversa. Son modelos de aproximadamente 74 millones de parámetros y 300 megabytes cada uno, diseñados específicamente para traducción y lo suficientemente ligeros para ejecutarse en CPU. La carga del modelo se implementó de forma lazy: solo se descarga de HuggingFace Hub y se carga en memoria la primera vez que se necesita una traducción, y permanece residente durante toda la vida del servidor. La inferencia se realiza con `torch.inference_mode`, que desactiva el cálculo de gradientes y reduce el consumo de memoria, procesando los textos en batches de 128 con padding y truncamiento automáticos. Se configuró `max_new_tokens` en 128 tokens, ya que las traducciones de mensajes médicos rara vez superan los 25 tokens de salida. El resultado fue la eliminación total de las llamadas HTTP: 885 peticiones de red se convirtieron en cero.

---

## Traducción unificada en lugar de lotes por grupo

El segundo cambio estructural fue reorganizar el pipeline de traducción. En la versión original, cada uno de los veinte grupos de mensajes invocaba `_traducir_lote` de forma independiente dentro de su worker del ThreadPoolExecutor, lo que además de multiplicar las peticiones HTTP provocaba la división recursiva cuando el lote superaba los 4500 caracteres. En la nueva arquitectura, antes de lanzar ningún worker, se recolectan todos los textos únicos de todos los grupos —desduplicados, porque muchos mensajes idénticos aparecen en distintas posiciones— y se traducen en una sola pasada de inferencia con MarianMT. El resultado se almacena en un diccionario que mapea cada texto original a su traducción, y luego los workers solo necesitan consultar ese diccionario para obtener la traducción ya hecha, dedicándose exclusivamente a optimizar el texto y contar tokens. Esto eliminó tanto la división recursiva como la inflación artificial del conteo de textos, reduciendo el trabajo real de traducción a exactamente los textos únicos del archivo Excel.

---

## Caché SQLite persistente

Para evitar la retraducción en ejecuciones sucesivas, implementamos una caché basada en SQLite. La base de datos almacena cada traducción identificada por la tupla de idioma origen, idioma destino y texto original como clave primaria, garantizando que cada combinación se traduzca una sola vez. Se configuró con journal mode WAL para permitir lecturas concurrentes sin bloqueos y synchronous NORMAL para equilibrar velocidad con durabilidad. Un aspecto crítico fue la seguridad entre hilos: a diferencia de la primera implementación que intentaba compartir una única conexión SQLite entre el hilo principal y los workers del ThreadPoolExecutor —lo cual SQLite no permite por defecto—, la versión corregida abre y cierra una conexión nueva para cada operación de lectura o escritura, garantizando que múltiples workers puedan consultar y poblar la caché simultáneamente sin errores. El resultado práctico es que la primera ejecución del pipeline traduce todos los textos y los persiste; cualquier ejecución posterior encuentra todas las traducciones en caché y completa la fase de traducción en menos de una décima de segundo.

---

## Los problemas que enfrentamos y cómo los resolvimos

El primer obstáculo apareció al medir el rendimiento real de MarianMT en CPU. Con `max_new_tokens` configurado inicialmente en 512, cada batch de 128 textos tardaba aproximadamente ocho segundos, lo que para nueve mil textos únicos se traducía en más de diez minutos de procesamiento. La solución fue sencilla pero efectiva: reducir el límite de tokens generados a 128, ya que las traducciones de frases médicas —del estilo "Necesito cancelar mi cita de cardiología" transformado en "I need to cancel my cardiology appointment"— rara vez exceden los veinte tokens de salida. Con este ajuste, el rendimiento en CPU pasó de 50 a 73 textos por segundo, y en GPU con CUDA supera los mil textos por segundo.

El segundo problema fue un error de atributo al ejecutar el pipeline desde el servidor FastAPI: `'NoneType' object has no attribute 'execute'`. La causa era que la conexión SQLite se creaba en el hilo principal durante la inicialización, pero los workers del ThreadPoolExecutor no podían acceder a ella porque SQLite no permite compartir conexiones entre hilos. La solución consistió en eliminar la conexión persistente y en su lugar abrir y cerrar una conexión independiente para cada operación de lectura o escritura en la caché, garantizando thread-safety sin comprometer el rendimiento —una consulta SQLite con índice sobre la clave primaria tarda microsegundos.

El tercer problema ocurrió durante la carga concurrente del modelo MarianMT: varios workers intentaban inicializar el modelo simultáneamente, y el `import` anidado de `transformers` colisionaba entre hilos produciendo un `ImportError`. La solución fue doble: mover todas las importaciones de PyTorch y Transformers al nivel superior del módulo para que se resuelvan una sola vez al cargar el archivo, y proteger la inicialización del modelo con un `threading.Lock` y patrón double-check para garantizar que solo el primer hilo que llega ejecuta la carga mientras los demás esperan y luego encuentran el modelo ya disponible.

El cuarto problema era cosmético pero molesto: un warning de la librería Transformers que se repetía para cada batch de inferencia advirtiendo que `max_new_tokens` y `max_length` estaban ambos definidos. Esto llenaba la consola con cientos de líneas idénticas. La solución fue tan simple como sincronizar ambos valores tras cargar el modelo, estableciendo `model.generation_config.max_length = 256` para que coincida con el `max_new_tokens` de 128.

---

## El resultado final

El pipeline original tardaba 231 segundos, con 230 de ellos consumidos por 885 peticiones HTTP a Google Translate ejecutadas con división recursiva de lotes. Tras las optimizaciones, la primera ejecución en CPU tarda aproximadamente dos minutos —la mayor parte en la inferencia del modelo MarianMT sobre los textos no cacheados—, lo cual ya representa una mejora sustancial frente a los casi cuatro minutos originales. A partir de la segunda ejecución, cuando la caché SQLite ya contiene todas las traducciones, el pipeline completo se completa en menos de cinco segundos: la traducción se resuelve en menos de una décima de segundo mediante consultas a la base de datos, y el resto del tiempo se reparte entre la agrupación de mensajes, la extracción de esquemas médicos y el conteo de tokens en paralelo. Si se dispone de una GPU con CUDA, incluso la primera ejecución se completa en un rango de doce a veinte segundos. Se eliminó la dependencia de Google Translate y de cualquier API externa de pago. Se eliminaron 885 peticiones HTTP por ejecución. Se eliminó la lógica de división recursiva de lotes. Se eliminaron los archivos temporales en disco para la lectura de Excel. Y se eliminó la ejecución duplicada de la clasificación local de reseñas. A cambio, el proyecto ganó un traductor neuronal completamente offline, una caché persistente que sobrevive reinicios, inferencia optimizada con detección automática de GPU, y una arquitectura de traducción unificada que procesa todos los textos en una sola pasada.
