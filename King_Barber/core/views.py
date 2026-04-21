from django.shortcuts import render
from django.http import HttpResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from firebase_admin import firestore
import csv
import datetime
import unicodedata

DEFAULT_WEEKLY_SCHEDULE = {
    "0": {"activo": True, "inicio": "11:00", "fin": "17:00"},  # Domingo
    "1": {"activo": True, "inicio": "11:00", "fin": "17:00"},  # Lunes
    "2": {"activo": True, "inicio": "11:00", "fin": "17:00"},  # Martes
    "3": {"activo": True, "inicio": "11:00", "fin": "17:00"},  # Miercoles
    "4": {"activo": True, "inicio": "11:00", "fin": "17:00"},  # Jueves
    "5": {"activo": True, "inicio": "11:00", "fin": "17:00"},  # Viernes
    "6": {"activo": True, "inicio": "18:00", "fin": "20:00"},  # Sabado
}


def get_firestore_client():
    try:
        return firestore.client()
    except Exception:
        return None


def normalize_name(value):
    value = str(value or '').strip().lower()
    value = ''.join(
        char for char in unicodedata.normalize('NFD', value)
        if unicodedata.category(char) != 'Mn'
    )
    return ' '.join(value.split())


def normalize_phone(value):
    return ''.join(char for char in str(value or '') if char.isdigit())


def parse_hour_to_int(time_str):
    try:
        hour_str, minute_str = str(time_str).split(':')
        hour = int(hour_str)
        minute = int(minute_str)
        if minute != 0 or hour < 0 or hour > 23:
            return None
        return hour
    except Exception:
        return None


def build_hour_range(start_time, end_time):
    start_hour = parse_hour_to_int(start_time)
    end_hour = parse_hour_to_int(end_time)
    if start_hour is None or end_hour is None or start_hour > end_hour:
        return []
    return [f"{hour:02d}:00" for hour in range(start_hour, end_hour + 1)]


def get_weekly_schedule(db=None):
    schedule = {day: config.copy() for day, config in DEFAULT_WEEKLY_SCHEDULE.items()}
    if db is None:
        db = get_firestore_client()
    if db is None:
        return schedule

    try:
        doc = db.collection('configuracion').document('horarios_atencion').get()
        if not doc.exists:
            return schedule

        data = doc.to_dict() or {}
        stored_days = data.get('dias', {})
        for day in schedule.keys():
            day_cfg = stored_days.get(day)
            if isinstance(day_cfg, dict):
                active = bool(day_cfg.get('activo', schedule[day]['activo']))
                start = str(day_cfg.get('inicio', schedule[day]['inicio']))
                end = str(day_cfg.get('fin', schedule[day]['fin']))
                schedule[day] = {
                    'activo': active,
                    'inicio': start,
                    'fin': end,
                }
    except Exception:
        return schedule

    return schedule


def get_available_hours_for_date(date_str, db=None):
    try:
        parsed_date = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        # Fallback a horario de lunes si la fecha es invalida
        fallback = DEFAULT_WEEKLY_SCHEDULE["1"]
        return build_hour_range(fallback['inicio'], fallback['fin'])

    schedule = get_weekly_schedule(db)
    # Convertimos Python weekday (lunes=0...domingo=6) a JS day (domingo=0...sabado=6)
    js_day_index = str((parsed_date.weekday() + 1) % 7)
    day_cfg = schedule.get(js_day_index, DEFAULT_WEEKLY_SCHEDULE[js_day_index])

    if not day_cfg.get('activo', True):
        return []

    return build_hour_range(day_cfg.get('inicio'), day_cfg.get('fin'))

def index(request):
    return render(request, 'core/home.html')

class DashboardDataView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            db = get_firestore_client()
            if db is None:
                return Response({"status": "success", "count": 0, "reservas": []})
            reservas_ref = db.collection('reservas')
            docs = reservas_ref.stream()
            
            reservas = []
            for doc in docs:
                data = doc.to_dict()
                data['id'] = doc.id  # Incluimos el ID del documento
                # Convertir timestamps a string si es necesario
                if 'creadoEn' in data:
                    data['creadoEn'] = str(data['creadoEn'])
                reservas.append(data)
                
            return Response({
                "status": "success",
                "count": len(reservas),
                "reservas": reservas
            })
        except Exception as e:
            return Response({"status": "error", "message": str(e)}, status=500)

class ReservaDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, doc_id):
        try:
            db = get_firestore_client()
            if db is None:
                return Response({"status": "error", "message": "Firebase no está configurado en este entorno"}, status=503)
            db.collection('reservas').document(doc_id).delete()
            return Response({"status": "success", "message": "Reserva eliminada"})
        except Exception as e:
            return Response({"status": "error", "message": str(e)}, status=500)

class CrearReservaView(APIView):
    permission_classes = [] # Público

    def post(self, request):
        try:
            data = request.data
            # Validación básica
            required_fields = ['nombre', 'servicio', 'dia', 'hora', 'telefono']
            for field in required_fields:
                if field not in data:
                    return Response({"status": "error", "message": f"Falta el campo {field}"}, status=400)
            
            # Limpiar datos (strip whitespace)
            clean_data = {
                'nombre': data['nombre'].strip(),
                'servicio': data['servicio'],
                'dia': data['dia'],
                'hora': data['hora'],
                'telefono': data['telefono'].strip()
            }

            available_hours = get_available_hours_for_date(clean_data['dia'], db)
            if clean_data['hora'] not in available_hours:
                return Response({"status": "error", "message": "La hora seleccionada no está disponible."}, status=400)

            db = get_firestore_client()
            if db is None:
                return Response({"status": "error", "message": "Firebase no está configurado en este entorno"}, status=503)
            
            # Verificar si el día está bloqueado
            bloqueo_ref = db.collection('dias_bloqueados').document(clean_data['dia'])
            if bloqueo_ref.get().exists:
                return Response({"status": "error", "message": "Este día no está disponible para reservas."}, status=400)

            bloqueo_hora_id = f"{clean_data['dia']}_{clean_data['hora'].replace(':', '-') }"
            bloqueo_hora_ref = db.collection('horas_bloqueadas').document(bloqueo_hora_id)
            if bloqueo_hora_ref.get().exists:
                return Response({"status": "error", "message": "Esta hora fue bloqueada por administración."}, status=400)

            reservas_ref = db.collection('reservas')

            # Verificar disponibilidad
            query = reservas_ref.where('dia', '==', clean_data['dia']).where('hora', '==', clean_data['hora']).stream()
            if any(query):
                return Response({"status": "error", "message": "Horario no disponible"}, status=400)

            # Agregar timestamp
            clean_data['creadoEn'] = firestore.SERVER_TIMESTAMP

            reservas_ref.add(clean_data)
            
            return Response({"status": "success", "message": "Reserva creada exitosamente"})
        except Exception as e:
            return Response({"status": "error", "message": str(e)}, status=500)

class ObtenerHorasOcupadasView(APIView):
    permission_classes = []

    def get(self, request):
        dia = request.query_params.get('dia')
        if not dia:
            return Response({"status": "error", "message": "Falta el parámetro 'dia'"}, status=400)
        
        try:
            db = get_firestore_client()
            available_hours = get_available_hours_for_date(dia, db)
            if db is None:
                return Response({
                    "status": "success",
                    "dia": dia,
                    "horas_ocupadas": [],
                    "horas_disponibles": available_hours,
                    "bloqueado": False
                })
            
            # Verificar si el día está bloqueado
            bloqueo_ref = db.collection('dias_bloqueados').document(dia)
            if bloqueo_ref.get().exists:
                # Si está bloqueado, devolvemos todas las horas como ocupadas
                return Response({
                    "status": "success",
                    "dia": dia,
                    "horas_ocupadas": available_hours,
                    "horas_disponibles": available_hours,
                    "bloqueado": True,
                    "mensaje": "Este día no está disponible."
                })

            reservas = db.collection('reservas').where('dia', '==', dia).stream()
            horas_ocupadas = [doc.to_dict().get('hora') for doc in reservas]

            bloqueos_hora = db.collection('horas_bloqueadas').where('dia', '==', dia).stream()
            horas_bloqueadas = [doc.to_dict().get('hora') for doc in bloqueos_hora if doc.to_dict().get('hora')]
            horas_ocupadas = list(set(horas_ocupadas + horas_bloqueadas))
            
            return Response({
                "status": "success",
                "dia": dia,
                "horas_ocupadas": horas_ocupadas,
                "horas_disponibles": available_hours,
                "bloqueado": False
            })
        except Exception as e:
            return Response({"status": "error", "message": str(e)}, status=500)


class HorariosAtencionView(APIView):
    permission_classes = []

    def get(self, request):
        dia = request.query_params.get('dia')
        db = get_firestore_client()

        if dia:
            return Response({
                "status": "success",
                "dia": dia,
                "horas_disponibles": get_available_hours_for_date(dia, db)
            })

        schedule = get_weekly_schedule(db)
        return Response({"status": "success", "dias": schedule})

    def post(self, request):
        if not request.user or not request.user.is_authenticated:
            return Response({"status": "error", "message": "No autorizado"}, status=401)

        input_days = request.data.get('dias')
        if not isinstance(input_days, dict):
            return Response({"status": "error", "message": "Formato inválido para horarios"}, status=400)

        sanitized = {}
        for day in ["0", "1", "2", "3", "4", "5", "6"]:
            cfg = input_days.get(day, DEFAULT_WEEKLY_SCHEDULE[day])
            if not isinstance(cfg, dict):
                cfg = DEFAULT_WEEKLY_SCHEDULE[day]

            active = bool(cfg.get('activo', True))
            start = str(cfg.get('inicio', DEFAULT_WEEKLY_SCHEDULE[day]['inicio']))
            end = str(cfg.get('fin', DEFAULT_WEEKLY_SCHEDULE[day]['fin']))

            if active and not build_hour_range(start, end):
                return Response({
                    "status": "error",
                    "message": f"Rango horario invalido para el dia {day}."
                }, status=400)

            sanitized[day] = {
                'activo': active,
                'inicio': start,
                'fin': end,
            }

        db = get_firestore_client()
        if db is None:
            return Response({"status": "error", "message": "Firebase no está configurado en este entorno"}, status=503)

        db.collection('configuracion').document('horarios_atencion').set({
            'dias': sanitized,
            'actualizado_por': request.user.username,
            'actualizado_en': firestore.SERVER_TIMESTAMP,
        }, merge=True)

        return Response({"status": "success", "dias": sanitized})

class CancelarReservaView(APIView):
    permission_classes = []

    def post(self, request):
        try:
            data = request.data
            nombre = data.get('nombre', '').strip()
            telefono = data.get('telefono', '').strip()
            dia = data.get('dia')
            hora = data.get('hora')

            if not all([nombre, telefono, dia, hora]):
                return Response({"status": "error", "message": "Faltan datos para cancelar"}, status=400)

            db = get_firestore_client()
            if db is None:
                return Response({"status": "error", "message": "Firebase no está configurado en este entorno"}, status=503)

            input_name = normalize_name(nombre)
            input_phone = normalize_phone(telefono)

            # Buscar por día y hora, y luego comparar nombre/teléfono normalizados.
            # Esto evita falsos negativos por espacios, guiones, +56 o tildes.
            reservas = db.collection('reservas')\
                .where('dia', '==', dia)\
                .where('hora', '==', hora)\
                .stream()

            found = False
            for doc in reservas:
                doc_data = doc.to_dict()
                stored_name = normalize_name(doc_data.get('nombre', ''))
                stored_phone = normalize_phone(doc_data.get('telefono', ''))

                if stored_name == input_name and stored_phone == input_phone:
                    doc.reference.delete()
                    found = True
            
            if found:
                return Response({"status": "success", "message": "Reserva cancelada correctamente"})
            else:
                return Response({"status": "error", "message": "No encontramos una reserva con esos datos. Verifica que el nombre y teléfono sean correctos."}, status=404)

        except Exception as e:
            return Response({"status": "error", "message": str(e)}, status=500)

class ExportarReservasView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Configurar respuesta CSV
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="reservas_{datetime.date.today()}.csv"'

        writer = csv.writer(response)
        writer.writerow(['ID', 'Nombre', 'Servicio', 'Día', 'Hora', 'Teléfono', 'Creado En'])

        try:
            db = get_firestore_client()
            if db is None:
                return HttpResponse("Firebase no está configurado en este entorno", status=503)
            reservas = db.collection('reservas').stream()

            for doc in reservas:
                data = doc.to_dict()
                writer.writerow([
                    doc.id,
                    data.get('nombre', ''),
                    data.get('servicio', ''),
                    data.get('dia', ''),
                    data.get('hora', ''),
                    data.get('telefono', ''),
                    data.get('creadoEn', '')
                ])

        except Exception as e:
            print(f"Error exportando: {e}")
            return HttpResponse("Error generando CSV", status=500)

        return response


def dashboard_view(request):
    return render(request, 'core/dashboard.html')

class BloquearDiaView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            dia = request.data.get('dia')
            motivo = request.data.get('motivo', 'Fuerza mayor')
            
            if not dia:
                return Response({"status": "error", "message": "Falta el día"}, status=400)
                
            db = get_firestore_client()
            if db is None:
                return Response({"status": "error", "message": "Firebase no está configurado en este entorno"}, status=503)
            db.collection('dias_bloqueados').document(dia).set({
                'dia': dia,
                'motivo': motivo,
                'bloqueado_por': request.user.username,
                'fecha_bloqueo': firestore.SERVER_TIMESTAMP
            })
            
            return Response({"status": "success", "message": f"Día {dia} bloqueado correctamente"})
        except Exception as e:
            return Response({"status": "error", "message": str(e)}, status=500)

    def delete(self, request):
        try:
            dia = request.query_params.get('dia') or request.data.get('dia')
            
            if not dia:
                return Response({"status": "error", "message": "Falta el día"}, status=400)
                
            db = get_firestore_client()
            if db is None:
                return Response({"status": "error", "message": "Firebase no está configurado en este entorno"}, status=503)
            db.collection('dias_bloqueados').document(dia).delete()
            
            return Response({"status": "success", "message": f"Día {dia} desbloqueado"})
        except Exception as e:
            return Response({"status": "error", "message": str(e)}, status=500)

class ObtenerDiasBloqueadosView(APIView):
    permission_classes = []

    def get(self, request):
        try:
            db = get_firestore_client()
            if db is None:
                return Response({"status": "success", "dias": []})
            docs = db.collection('dias_bloqueados').stream()
            
            bloqueados = []
            for doc in docs:
                bloqueados.append(doc.to_dict())
                
            return Response({"status": "success", "dias": bloqueados})
        except Exception as e:
            return Response({"status": "error", "message": str(e)}, status=500)


class BloquearHoraView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            dia = request.data.get('dia')
            hora = request.data.get('hora')
            motivo = request.data.get('motivo', 'No disponible')

            if not dia or not hora:
                return Response({"status": "error", "message": "Faltan día u hora"}, status=400)

            db = get_firestore_client()
            if db is None:
                return Response({"status": "error", "message": "Firebase no está configurado en este entorno"}, status=503)

            available_hours = get_available_hours_for_date(dia, db)
            if hora not in available_hours:
                return Response({"status": "error", "message": "La hora indicada está fuera del horario disponible."}, status=400)

            doc_id = f"{dia}_{hora.replace(':', '-')}"
            db.collection('horas_bloqueadas').document(doc_id).set({
                'dia': dia,
                'hora': hora,
                'motivo': motivo,
                'bloqueado_por': request.user.username,
                'fecha_bloqueo': firestore.SERVER_TIMESTAMP
            })

            return Response({"status": "success", "message": f"Hora {hora} del día {dia} bloqueada"})
        except Exception as e:
            return Response({"status": "error", "message": str(e)}, status=500)

    def delete(self, request):
        try:
            dia = request.query_params.get('dia') or request.data.get('dia')
            hora = request.query_params.get('hora') or request.data.get('hora')

            if not dia or not hora:
                return Response({"status": "error", "message": "Faltan día u hora"}, status=400)

            db = get_firestore_client()
            if db is None:
                return Response({"status": "error", "message": "Firebase no está configurado en este entorno"}, status=503)

            doc_id = f"{dia}_{hora.replace(':', '-')}"
            db.collection('horas_bloqueadas').document(doc_id).delete()

            return Response({"status": "success", "message": f"Hora {hora} del día {dia} desbloqueada"})
        except Exception as e:
            return Response({"status": "error", "message": str(e)}, status=500)


class ObtenerHorasBloqueadasView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            db = get_firestore_client()
            if db is None:
                return Response({"status": "success", "horas": []})

            dia = request.query_params.get('dia')
            query = db.collection('horas_bloqueadas')
            if dia:
                query = query.where('dia', '==', dia)

            docs = query.stream()
            horas = [doc.to_dict() for doc in docs]

            return Response({"status": "success", "horas": horas})
        except Exception as e:
            return Response({"status": "error", "message": str(e)}, status=500)

import os
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth.models import User

class CustomLoginView(APIView):
    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')
        
        admin_user = os.getenv('ADMIN_USER')
        admin_pass = os.getenv('ADMIN_PASS')

        if not admin_user or not admin_pass:
            return Response({"detail": "Dashboard credentials are not configured"}, status=503)

        if username == admin_user and password == admin_pass:
            # Crear o recuperar un usuario "dummy" en Django para generar el token
            # Esto es necesario porque SimpleJWT necesita un objeto User
            try:
                user, created = User.objects.get_or_create(username=username)
                if created:
                    user.set_unusable_password()
                    user.save()
            except Exception:
                # Si falla la DB, usamos un token manual o simulado
                # Pero para mantener compatibilidad con el frontend que espera JWT:
                return Response({
                    "access": "token-dummy-acceso-permitido",
                    "refresh": "token-dummy-refresh",
                    "message": "Login exitoso (Modo Simple)"
                })

            # Generar token real si la DB funciona
            refresh = RefreshToken.for_user(user)
            return Response({
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            })
        else:
            return Response({"detail": "Credenciales incorrectas"}, status=401)


