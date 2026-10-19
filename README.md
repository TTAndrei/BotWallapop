# BotWallapop

Bot que busca en Wallapop y **filtra la morralla por ti**: cajas vacías, otras
versiones del producto (8 GB, Ti…), PCs enteros, accesorios, anuncios de "busco/compro",
piezas estropeadas… Te quedas solo con lo interesante, ordenado por precio y con
los chollos marcados 🔥.

No necesita instalar nada: solo Python 3.11 o superior.

## Uso rápido

```bash
cp busquedas.example.toml busquedas.toml   # edita tu ubicación y tus búsquedas
python -m wallabot buscar                  # busca una vez y enseña lo interesante
```

Ejemplo de salida:

```
═══ RTX 3060 12GB — «rtx 3060 12gb» ═══
Revisados 160 · interesantes 14 · descartados 146
   - título contiene «8gb»: 31
   - título contiene «pc»: 22
   - título contiene «ti»: 9
   ...
Precio mediano de lo interesante: 180 €  (🔥 = ≥15 % más barato)

      140 €  🔥 Zotac RTX3060 12G  (Madrid · envío)
             https://es.wallapop.com/item/...
      170 €  MSI RTX 3060 Ventus 12GB  (Valencia)
             https://es.wallapop.com/item/...
```

Opciones útiles:

| Comando | Qué hace |
|---|---|
| `python -m wallabot buscar --descartados` | Lista también lo descartado y **por qué** (para afinar los filtros) |
| `python -m wallabot buscar --html resultados.html` | Guarda una página para **elegir ofertas y contactar** (ver abajo) |
| `python -m wallabot buscar --orden fecha` | Ordena por más reciente en vez de por precio |
| `python -m wallabot -n "RTX 3060 12GB" buscar` | Ejecuta solo esa búsqueda |
| `python -m wallabot vigilar -i 10` | Repite cada 10 min y avisa **solo de anuncios nuevos** |
| `python -m wallabot vigilar --una-vez` | Una pasada, para lanzarlo desde cron |

## Cómo se configuran los filtros

Cada búsqueda es un bloque `[[search]]` en `busquedas.toml`. El ejemplo incluido ya
está preparado para la RTX 3060 de 12 GB:

```toml
[[search]]
name = "RTX 3060 12GB"
query = "rtx 3060 12gb"      # lo que se escribe en el buscador de Wallapop
min_price = 200              # quita cajas, cables, "gangas" falsas
max_price = 400
require = ["3060"]           # obligatorio en el título
require_any = ["12gb"]       # obligatorio en título o descripción
exclude_title = ["8gb", "ti", "pc", "ordenador", "torre", "busco", ...]
exclude_any = ["solo caja", "averiada", "para piezas", ...]
```

| Clave | Significado |
|---|---|
| `require` | Términos que deben aparecer en el **título**. Una lista interna son alternativas: `[["3060"], ["12gb", "doce gigas"]]` |
| `require_any` | Igual, pero vale con que aparezcan en el título **o** la descripción |
| `exclude_title` | Si el **título** contiene alguno, se descarta |
| `exclude_any` | Si el título **o la descripción** contienen alguno, se descarta |
| `min_price` / `max_price` | Rango de precio (también se envía a Wallapop, así no se gastan páginas en basura) |
| `include_reserved` | `false` (por defecto) ignora los reservados |
| `shipping_only` | Solo anuncios con envío |
| `max_age_days` | Ignora anuncios más antiguos |
| `latitude`, `longitude`, `distance_km` | Dónde buscar y a qué distancia (sin `distance_km`, toda España) |
| `order_by` | `newest`, `price_low_to_high`, `price_high_to_low`, `closest`, `most_relevance` |
| `max_pages` | Cuántas páginas de resultados revisar |
| `category_id` | Opcional: ID de categoría de Wallapop |

Lo que pongas en `[defaults]` se aplica a todas las búsquedas.

**Cómo se comparan los textos** (para no tener que escribir 20 variantes):

- Mayúsculas, tildes y signos dan igual: `portatil` encuentra "Portátil".
- Las capacidades se unifican: `12gb` encuentra "12 GB", "12GB", "12G", "12 gigas".
- Letras y números se separan: `ti` encuentra "3060Ti" y `i5` encuentra "i5-12400".
- Se buscan palabras completas: `ti` **no** encuentra "tienda", `pc` no encuentra "pcie".
- Si necesitas algo más fino, empieza el término por `re:` y es una expresión regular
  sobre el texto ya normalizado. Ej: `re:^ caja ` = el título **empieza** por "caja"
  (así "Caja RTX 3060" se descarta pero "RTX 3060 con caja original" no).

**Consejo:** la primera vez lanza `buscar --descartados` y repasa los motivos. Si se
cuela basura, añade la palabra a `exclude_title`; si se descarta algo bueno, mira qué
término lo ha tirado y quítalo o hazlo más concreto.

## Elegir ofertas y escribir a los vendedores

`buscar --html resultados.html` genera una página (funciona bien en el móvil) donde:

- Marcas **Me interesa** en las ofertas que te gustan y filtras por *Me interesan*,
  *Por contactar* o *Contactadas*, o solo las de Cataluña.
- **Copiar mensaje y abrir** copia el mensaje para el vendedor y abre el anuncio
  (en el móvil se abre la app de Wallapop). Solo tienes que pegarlo en el chat y enviar.
- El mensaje cambia según dónde esté el anuncio: si está fuera de tu zona pregunta
  si lo puede enviar. Se configura en la sección `[mensaje]` de `busquedas.toml`
  (también se puede editar en la propia página).

El bot **no envía los mensajes él solo** a propósito: Wallapop no tiene una API pública
para el chat, habría que darle tu usuario y contraseña, y los mensajes automáticos van
contra sus condiciones de uso, así que te podrían bloquear la cuenta.

## Avisos en Telegram (opcional)

En modo `vigilar` el bot puede mandarte cada anuncio nuevo por Telegram:

1. Habla con [@BotFather](https://t.me/BotFather), crea un bot y copia el token.
2. Escribe cualquier cosa a tu bot y abre
   `https://api.telegram.org/bot<TOKEN>/getUpdates` para ver tu `chat.id`.
3. Exporta las variables y lánzalo:

```bash
export TELEGRAM_BOT_TOKEN="123456:ABC..."
export TELEGRAM_CHAT_ID="123456789"
python -m wallabot vigilar -i 10
```

La primera pasada solo memoriza lo que ya hay (en `vistos.json`) para no inundarte;
a partir de ahí solo avisa de lo nuevo. Usa `--avisar-existentes` si quieres todo.

## Tests

```bash
python -m unittest -v
```

Los tests comprueban los filtros de la 3060 12 GB contra anuncios típicos (cajas,
versiones de 8 GB y Ti, PCs, portátiles, "busco", averiadas…) y el parseo de las
respuestas de la API.

## Notas

- Usa la API pública que usa la propia web de Wallapop. No es oficial y Wallapop la
  cambia de vez en cuando; el parser acepta los formatos conocidos, pero si un día
  deja de devolver resultados, probablemente haya cambiado.
- No abuses del intervalo de `vigilar` (10 min o más está bien) para no saturar ni
  arriesgarte a un bloqueo temporal.
