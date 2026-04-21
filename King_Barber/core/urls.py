from django.urls import path
from . import views
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

urlpatterns = [
    path('', views.index, name='index'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    
    # API Endpoints
    path('api/reservas/', views.DashboardDataView.as_view(), name='api_reservas'),
    path('api/reservas/crear/', views.CrearReservaView.as_view(), name='api_crear_reserva'),
    path('api/reservas/cancelar/', views.CancelarReservaView.as_view(), name='api_cancelar_reserva'),
    path('api/reservas/ocupadas/', views.ObtenerHorasOcupadasView.as_view(), name='api_horas_ocupadas'),
    path('api/reservas/horarios/', views.HorariosAtencionView.as_view(), name='api_horarios_atencion'),
    path('api/reservas/exportar/', views.ExportarReservasView.as_view(), name='api_exportar_reservas'),
    path('api/reservas/bloquear-dia/', views.BloquearDiaView.as_view(), name='api_bloquear_dia'),
    path('api/reservas/dias-bloqueados/', views.ObtenerDiasBloqueadosView.as_view(), name='api_dias_bloqueados'),
    path('api/reservas/bloquear-hora/', views.BloquearHoraView.as_view(), name='api_bloquear_hora'),
    path('api/reservas/horas-bloqueadas/', views.ObtenerHorasBloqueadasView.as_view(), name='api_horas_bloqueadas'),
    path('api/reservas/<str:doc_id>/', views.ReservaDetailView.as_view(), name='api_reserva_detail'),
    # path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'), # Reemplazado
    path('api/token/', views.CustomLoginView.as_view(), name='custom_login'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
]
