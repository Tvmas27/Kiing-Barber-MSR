# 💈 King Barber - Sistema de Reservas

Aplicación web para gestión de citas de una barbería, construida con Django y Firebase.

## Resumen

El proyecto incluye una landing pública, un formulario de reservas, un dashboard de administración y una API interna para consultar, crear, cancelar y exportar reservas.

## Estructura

- `King_Barber/King_Barber/`: configuración principal de Django.
- `King_Barber/core/`: app principal con vistas, URLs, templates y estáticos.
- `render.yaml`: despliegue para Render.
- `requirements.txt`: dependencias del proyecto.
- `runtime.txt`: versión de Python.

## Stack

- Backend: Python 3.13, Django 5.2, Django REST Framework.
- Datos: Firebase Firestore.
- Frontend: HTML, Tailwind CSS por CDN y JavaScript vanilla.
- Despliegue: Render con Gunicorn y WhiteNoise.

## Variables de entorno

Usa `King_Barber/.env.example` como base y crea tu `.env` local en `King_Barber/`.

Variables principales:

- `DEBUG`
- `SECRET_KEY`
- `ALLOWED_HOSTS`
- `CORS_ALLOWED_ORIGINS`
- `CSRF_TRUSTED_ORIGINS`
- `FIREBASE_CREDENTIALS`
- `ADMIN_USER`
- `ADMIN_PASS`

Notas rápidas:

- `FIREBASE_CREDENTIALS` puede ser una ruta local en desarrollo o el JSON completo en Render.
- `ADMIN_USER` y `ADMIN_PASS` controlan el acceso al dashboard personalizado.

## Ejecución local

1. Crear y activar un entorno virtual.
2. Instalar dependencias con `pip install -r requirements.txt`.
3. Copiar `King_Barber/.env.example` a `King_Barber/.env` y ajustar los valores.
4. Ejecutar:

```bash
cd King_Barber
python manage.py migrate
python manage.py runserver
```

## Despliegue en Render

Render usa `render.yaml` como blueprint.

- Build: instala dependencias, ejecuta `collectstatic` y luego migraciones.
- Start: `gunicorn King_Barber.wsgi:application`.
- Secretos: `SECRET_KEY` y `FIREBASE_CREDENTIALS`.
- Dominios: `ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS` y `CSRF_TRUSTED_ORIGINS` deben apuntar al dominio real.

## API

| Método | Endpoint | Uso |
| --- | --- | --- |
| `POST` | `/api/token/` | Login del dashboard |
| `POST` | `/api/reservas/crear/` | Crear reserva |
| `GET` | `/api/reservas/` | Listar reservas |
| `GET` | `/api/reservas/exportar/` | Exportar CSV |
| `DELETE` | `/api/reservas/<id>/` | Eliminar reserva |

## Notas

- La credencial de Firebase no debe commitearse.
- Las credenciales del dashboard deben vivir solo en variables de entorno.

