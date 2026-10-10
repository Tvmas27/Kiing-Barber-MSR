from django.conf import settings
from django.shortcuts import render
from django.http import HttpResponse
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.throttling import AnonRateThrottle
from firebase_admin import firestore
from google.api_core.exceptions import AlreadyExists
import csv
import datetime
import logging
import re


logger = logging.getLogger(__name__)
AVAILABLE_SERVICES = frozenset({'corte', 'barba', 'cejas', 'visos', 'permanente', 'combo'})
AVAILABLE_HOURS = frozenset(f'{hour:02d}:00' for hour in range(11, 23))
PHONE_PATTERN = re.compile(r'^[0-9+() .-]{7,20}$')


class BookingThrottle(AnonRateThrottle):
    scope = 'booking'


class CancellationThrottle(AnonRateThrottle):
    scope = 'cancellation'


def _clean_reservation(data):
    required_fields = ('nombre', 'servicio', 'dia', 'hora', 'telefono')
    if any(not isinstance(data.get(field), str) for field in required_fields):
        raise ValueError('Los datos de la reserva no son válidos')

    clean_data = {field: data[field].strip() for field in required_fields}
    if not 2 <= len(clean_data['nombre']) <= 100:
        raise ValueError('El nombre no es válido')
    if clean_data['servicio'] not in AVAILABLE_SERVICES:
        raise ValueError('El servicio no es válido')
    if clean_data['hora'] not in AVAILABLE_HOURS:
        raise ValueError('La hora no es válida')
    if not PHONE_PATTERN.fullmatch(clean_data['telefono']):
        raise ValueError('El teléfono no es válido')

    try:
        reservation_date = datetime.date.fromisoformat(clean_data['dia'])
    except ValueError as exc:
        raise ValueError('La fecha no es válida') from exc
    if reservation_date < timezone.localdate():
        raise ValueError('La fecha debe ser futura')
    return clean_data


def _safe_error(operation, exc):
    logger.exception('Error en %s: %s', operation, exc)
    return Response({'status': 'error', 'message': 'No se pudo completar la operación'}, status=500)


def get_firestore_client():
    try:
        return firestore.client()
    except Exception:
        return None

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
    throttle_classes = [BookingThrottle]

    def post(self, request):
        try:
            clean_data = _clean_reservation(request.data)

            db = get_firestore_client()
            if db is None:
                return Response({"status": "error", "message": "Firebase no está configurado en este entorno"}, status=503)
            
            # Verificar si el día está bloqueado
            bloqueo_ref = db.collection('dias_bloqueados').document(clean_data['dia'])
            if bloqueo_ref.get().exists:
                return Response({"status": "error", "message": "Este día no está disponible para reservas."}, status=400)

            reservas_ref = db.collection('reservas')

            clean_data['creadoEn'] = firestore.SERVER_TIMESTAMP
            reservation_id = f"{clean_data['dia']}_{clean_data['hora'].replace(':', '-')}"
            reservas_ref.document(reservation_id).create(clean_data)
            
            return Response({"status": "success", "message": "Reserva creada exitosamente"})
        except ValueError as e:
            return Response({'status': 'error', 'message': str(e)}, status=400)
        except AlreadyExists:
            return Response({'status': 'error', 'message': 'Horario no disponible'}, status=400)
        except Exception as e:
            return _safe_error('crear reserva', e)

class ObtenerHorasOcupadasView(APIView):
    permission_classes = []

    def get(self, request):
        dia = request.query_params.get('dia')
        if not dia:
            return Response({"status": "error", "message": "Falta el parámetro 'dia'"}, status=400)
        try:
            datetime.date.fromisoformat(dia)
        except ValueError:
            return Response({'status': 'error', 'message': 'La fecha no es válida'}, status=400)
        
        try:
            db = get_firestore_client()
            if db is None:
                return Response({"status": "success", "dia": dia, "horas_ocupadas": [], "bloqueado": False})
            
            # Verificar si el día está bloqueado
            bloqueo_ref = db.collection('dias_bloqueados').document(dia)
            if bloqueo_ref.get().exists:
                # Si está bloqueado, devolvemos todas las horas como ocupadas
                todas_horas = [
                    "11:00", "12:00", "13:00", "14:00", "15:00", "16:00", 
                    "17:00", "18:00", "19:00", "20:00", "21:00", "22:00"
                ]
                return Response({
                    "status": "success",
                    "dia": dia,
                    "horas_ocupadas": todas_horas,
                    "bloqueado": True,
                    "mensaje": "Este día no está disponible."
                })

            reservas = db.collection('reservas').where('dia', '==', dia).stream()
            horas_ocupadas = [doc.to_dict().get('hora') for doc in reservas]
            
            return Response({
                "status": "success",
                "dia": dia,
                "horas_ocupadas": horas_ocupadas,
                "bloqueado": False
            })
        except Exception as e:
            return _safe_error('consultar disponibilidad', e)

class CancelarReservaView(APIView):
    permission_classes = []
    throttle_classes = [CancellationThrottle]

    def post(self, request):
        try:
            data = request.data
            nombre = data.get('nombre', '').strip() if isinstance(data.get('nombre'), str) else ''
            telefono = data.get('telefono', '').strip() if isinstance(data.get('telefono'), str) else ''
            dia = data.get('dia')
            hora = data.get('hora')

            if not all([nombre, telefono, dia, hora]):
                return Response({"status": "error", "message": "Faltan datos para cancelar"}, status=400)
            if len(nombre) > 100 or not PHONE_PATTERN.fullmatch(telefono):
                return Response({'status': 'error', 'message': 'Los datos no son válidos'}, status=400)
            try:
                datetime.date.fromisoformat(dia)
            except (TypeError, ValueError):
                return Response({'status': 'error', 'message': 'La fecha no es válida'}, status=400)
            if hora not in AVAILABLE_HOURS:
                return Response({'status': 'error', 'message': 'La hora no es válida'}, status=400)

            db = get_firestore_client()
            if db is None:
                return Response({"status": "error", "message": "Firebase no está configurado en este entorno"}, status=503)
            # Buscar la reserva por teléfono, día y hora (datos más exactos)
            reservas = db.collection('reservas')\
                .where('telefono', '==', telefono)\
                .where('dia', '==', dia)\
                .where('hora', '==', hora)\
                .stream()

            found = False
            for doc in reservas:
                doc_data = doc.to_dict()
                # Verificar nombre (case-insensitive)
                stored_name = doc_data.get('nombre', '').strip().lower()
                input_name = nombre.lower()

                if stored_name == input_name:
                    doc.reference.delete()
                    found = True
            
            if found:
                return Response({"status": "success", "message": "Reserva cancelada correctamente"})
            else:
                return Response({"status": "error", "message": "No encontramos una reserva con esos datos. Verifica que el nombre y teléfono sean correctos."}, status=404)

        except Exception as e:
            return _safe_error('cancelar reserva', e)

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
    return render(request, 'core/dashboard.html', {
        'firebase_config': settings.FIREBASE_WEB_CONFIG,
    })

class BloquearDiaView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            dia = request.data.get('dia')
            motivo = request.data.get('motivo', 'Fuerza mayor')
            
            if not isinstance(dia, str) or not isinstance(motivo, str) or not dia:
                return Response({'status': 'error', 'message': 'Los datos no son válidos'}, status=400)
            try:
                datetime.date.fromisoformat(dia)
            except ValueError:
                return Response({'status': 'error', 'message': 'La fecha no es válida'}, status=400)
            if len(motivo.strip()) > 200:
                return Response({'status': 'error', 'message': 'El motivo es demasiado largo'}, status=400)
                
            db = get_firestore_client()
            if db is None:
                return Response({"status": "error", "message": "Firebase no está configurado en este entorno"}, status=503)
            db.collection('dias_bloqueados').document(dia).set({
                'dia': dia,
                'motivo': motivo.strip() or 'Fuerza mayor',
                'bloqueado_por': request.user.username,
                'fecha_bloqueo': firestore.SERVER_TIMESTAMP
            })
            
            return Response({"status": "success", "message": f"Día {dia} bloqueado correctamente"})
        except Exception as e:
            return _safe_error('bloquear día', e)

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
            return _safe_error('desbloquear día', e)

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
