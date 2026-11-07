# Frontend

La interfaz de Vita CRM se renderiza en el servidor con Django Templates. Tabler aporta el layout y los componentes visuales. HTMX actualiza fragmentos de página. El JavaScript propio queda en `static/js/app.js` y solo inicializa tooltips y popovers que Tabler no activa solo.

## Piezas

| Pieza | Versión | Dónde vive |
| --- | --- | --- |
| Django | 5.2.18 | `requirements.txt` |
| django-htmx | 1.29.0 | `requirements.txt`. Incluye HTMX 2.0.10 |
| Tabler | `@tabler/core` 1.6.1 | `static/vendor/tabler/css` y `static/vendor/tabler/js` |
| Tabler Icons | `@tabler/icons-webfont` 3.49.0 | `static/vendor/tabler/icons` |

Tabler ya incluye Bootstrap. No se carga otra copia de Bootstrap ni de HTMX. `{% htmx_script %}` inserta `htmx-2.min.js`. Con `DEBUG=True` django-htmx agrega además `django-htmx.js`, que solo muestra errores HTTP en la consola. No es una segunda copia de HTMX.

Los assets se sirven con los static files de Django. No hay pipeline de compilación ni CDN para CSS, JavaScript o iconos.

## Templates

Los templates globales están en `templates/`.

```text
templates/
├── base.html
├── layouts/dashboard.html
├── components/
│   ├── alert.html
│   ├── alerts.html
│   ├── breadcrumbs.html
│   ├── empty_state.html
│   ├── footer.html
│   ├── form_field.html
│   ├── navbar.html
│   ├── page_header.html
│   ├── pagination.html
│   └── sidebar.html
└── pages/
    ├── demo.html
    ├── demo_form.html
    └── demo_status.html
```

`base.html` define el documento: idioma `es`, viewport, CSS, `{% htmx_script %}`, Tabler y `app.js`. El `body` envía el token CSRF en cada request de HTMX:

```html
<body hx-headers='{"x-csrftoken": "{{ csrf_token }}"}'>
```

`layouts/dashboard.html` extiende `base.html` y arma la página de Tabler: sidebar, navbar, encabezado, mensajes, contenido y pie.

## Nueva página

1. Crear un template que extienda el layout.
2. Pasar `page_title`, `page_description` y `breadcrumbs` desde la view.
3. Registrar la URL en la app que corresponda.

```django
{% extends "layouts/dashboard.html" %}

{% block title %}Clientes · Vita CRM{% endblock %}

{% block page_actions %}
  <a class="btn btn-primary" href="{% url 'clientes:nuevo' %}">Nuevo</a>
{% endblock %}

{% block dashboard_content %}
  <div class="card">
    <div class="card-body">...</div>
  </div>
{% endblock %}
```

`breadcrumbs` es una lista de diccionarios. El último ítem es la página actual. Los anteriores pueden traer `url`:

```python
context = {
    "page_title": "Clientes",
    "page_description": "Listado de clientes activos.",
    "breadcrumbs": [
        {"label": "Vita CRM", "url": reverse("inicio")},
        {"label": "Clientes"},
    ],
}
```

La navegación principal está en `templates/components/sidebar.html`. Un ítem activo usa la clase `active` y `aria-current="page"`. La comparación actual mira `request.resolver_match.url_name`.

La navbar muestra el título de la página y, si hay sesión, el usuario. El enlace a Administración aparece solo para usuarios staff, porque esa ruta ya existe. No hay cierre de sesión fuera del admin.

## Componentes

Se incluyen con `{% include %}` y, cuando hace falta, `with`.

Campos de formulario:

```django
{% include "components/form_field.html" with field=form.nombre %}
```

El formulario hereda de `ui.forms.TablerForm`. Esa clase agrega `form-control` o `form-select`, `aria-describedby`, `aria-invalid` y `is-invalid`. El partial imprime label, ayuda y errores. Los mensajes de ayuda y de error usan los ids que el formulario declara.

Alertas de `django.contrib.messages`: el layout incluye `components/alerts.html`. Las categorías `success`, `error`, `warning` e `info` se mapean a las alertas de Tabler. `error` se muestra como `danger`. No hace falta JavaScript para verlas. El botón de cierre usa el comportamiento nativo de Tabler.

Tabla: envolverla en `.table-responsive` y usar `.table.table-vcenter.card-table` dentro de una card. Si no hay filas, incluir el estado vacío:

```django
{% include "components/empty_state.html" with title="Sin registros" message="No hay filas para mostrar." icon="ti-inbox" %}
```

Paginación, cuando exista un `page_obj` de Django:

```django
{% include "components/pagination.html" %}
```

El partial arma los links con `{% querystring %}`, así que conserva el resto de la consulta (por ejemplo `q`). Si el template se renderiza sin `request`, los links quedan en `?page=`.

Iconos: clase `ti` más el nombre, por ejemplo `<i class="ti ti-user" aria-hidden="true"></i>`. Si el icono es el único contenido de un botón, el botón necesita un nombre accesible.

## Estilos propios

`static/css/app.css` se carga después de Tabler. Ahí van ajustes que Tabler no cubre. Hoy solo alinea los iconos del menú y muestra el indicador de HTMX mientras hay un request. No redefinir componentes de Tabler en este archivo.

## HTMX

Las páginas principales se navegan con links normales. No hay `hx-boost` global.

Una view puede devolver la página completa o un fragmento. `django_htmx.middleware.HtmxMiddleware` expone `request.htmx`. Si la respuesta cambia según el header `HX-Request`, la view declara `Vary` con `@vary_on_headers("HX-Request")`.

```python
@vary_on_headers("HX-Request")
@require_http_methods(["GET"])
def estado(request):
    if request.htmx:
        return render(request, "pages/demo_status.html", context)
    return render(request, "pages/demo.html", context)
```

El fragmento no extiende `base.html` y no vuelve a cargar CSS ni HTMX.

En el template, el pedido y el destino quedan explícitos:

```html
<button
  type="button"
  hx-get="{% url 'ui:status' %}"
  hx-target="#status-panel"
  hx-swap="innerHTML"
  hx-indicator="#status-indicator"
>
  Actualizar estado
</button>
```

Un formulario que también funciona sin JavaScript conserva `method`, `action` y `{% csrf_token %}`:

```html
<form
  method="post"
  action="{% url 'ui:demo' %}"
  hx-post="{% url 'ui:demo' %}"
  hx-target="#demo-form-region"
  hx-swap="outerHTML"
  hx-disabled-elt="#demo-submit"
>
  {% csrf_token %}
</form>
```

El HTML devuelto por HTMX tiene que incluir otra vez `#demo-form-region` cuando el swap es `outerHTML`.

Respuestas:

- Un POST normal y válido redirige (POST/Redirect/GET) y muestra el mensaje con `django.contrib.messages`.
- Un POST de HTMX válido devuelve el fragmento con la confirmación. No se usa el redirect 302, porque HTMX no lo trata como una navegación completa.
- Un POST inválido, con o sin HTMX, vuelve a renderizar el formulario con errores y status 200. HTMX no intercambia un 422 salvo que se configure aparte.

`hx-disabled-elt` desactiva el botón mientras el request está en curso. El texto "Enviando…" o "Consultando…" está en un elemento `.htmx-indicator`, oculto hasta que HTMX agrega `.htmx-request`.

Las vistas de HTMX usan las mismas restricciones que el resto: CSRF activo, autoescape de templates y el control de acceso que corresponda. Sin sesión, un request HTMX no inserta el login dentro del fragmento: la respuesta trae `HX-Redirect` y el navegador carga la página de login completa. La demostración responde 404 cuando `DEBUG` es falso solo si ya hay sesión, tanto para un GET común como para HTMX.

## CSRF

El middleware CSRF sigue activo. No se usa `csrf_exempt`.

HTMX 2 hereda `hx-headers` desde `body` y manda `X-CSRFToken`. Los formularios POST normales incluyen además `{% csrf_token %}`.

## Tabler después de un swap

Collapse, dropdown, modal, alert y tabs siguen funcionando en HTML insertado por HTMX porque Tabler escucha esos `data-bs-toggle` en `document`.

Tooltips y popovers no. `static/js/app.js` crea cada instancia una sola vez, en la carga y en `htmx:afterSwap`, usando `window.tabler.bootstrap` y `getInstance` para no duplicarlas.

## Actualizar Tabler

1. Elegir una versión fija de `@tabler/core` y de `@tabler/icons-webfont`. No usar `@latest`.
2. Reemplazar solo los archivos listados en `static/vendor/tabler/VERSIONS.txt`.
3. No editar el CSS ni el JavaScript distribuidos.
4. Revisar que el layout (`.page`, `.navbar-vertical`, `.page-wrapper`) siga coincidiendo con la documentación de esa versión.
5. Anotar la versión nueva en `VERSIONS.txt` y en esta guía.

El CSS de iconos también nombra fuentes `woff` y `ttf`. Los navegadores actuales piden primero `woff2`, que es el archivo versionado. Los source maps de Tabler no están en el repositorio: las herramientas de desarrollo pueden registrar un 404 de `tabler.min.css.map` o `tabler.min.js.map`.

HTMX se actualiza junto con `django-htmx`. La versión por defecto del template tag es HTMX 2. No pasar `version=4`: esa línea sigue en beta.

## Pantalla de demostración

Toda vista exige una sesión. Quien no la tiene va al login del admin (`/admin/login/`) y, si entra, vuelve a la URL que había pedido. Ese formulario solo acepta un usuario activo y staff. `/admin/login/` queda público, igual que los archivos bajo `STATIC_URL`, para que la pantalla de login cargue su CSS y su JavaScript.

Con `DJANGO_DEBUG=True`, la ruta `/ui/` muestra el layout, un GET parcial (`/ui/estado/`) y un POST validado por `ui.forms.DemoForm`. No crea modelos ni guarda datos. Con `DEBUG=False` esas rutas responden 404 para un usuario autenticado. Sin sesión, la redirección al login ocurre antes.

El formulario de demostración usa `novalidate` para que los errores que se ven salgan de Django. En un formulario real se puede omitir `novalidate` si se quiere sumar la validación del navegador. La validación del servidor sigue siendo obligatoria.

## Pruebas

Dentro del contenedor:

```bash
docker compose exec web python manage.py check
docker compose exec web python manage.py test ui
docker compose exec web python manage.py collectstatic --noinput
```

`ui/tests.py` cubre la página completa, el fragmento GET, el POST válido e inválido, CSRF, el 405 de métodos no permitidos, la redirección al login y el 404 fuera de desarrollo.
