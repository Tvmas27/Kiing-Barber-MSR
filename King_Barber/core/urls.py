from django.urls import path
from . import views
urlpatterns = [
    path('', views.index, name='index'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    
    # API Endpoints
    path('api/reservas/', views.DashboardDataView.as_view(), name='api_reservas'),
    path('api/reservas/crear/', views.CrearReservaView.as_view(), name='api_crear_reserva'),
    path('api/reservas/cancelar/', views.CancelarReservaView.as_view(), name='api_cancelar_reserva'),
    path('api/reservas/ocupadas/', views.ObtenerHorasOcupadasView.as_view(), name='api_horas_ocupadas'),
    path('api/reservas/exportar/', views.ExportarReservasView.as_view(), name='api_exportar_reservas'),
    path('api/reservas/bloquear-dia/', views.BloquearDiaView.as_view(), name='api_bloquear_dia'),
    path('api/reservas/dias-bloqueados/', views.ObtenerDiasBloqueadosView.as_view(), name='api_dias_bloqueados'),
    path('api/reservas/<str:doc_id>/', views.ReservaDetailView.as_view(), name='api_reserva_detail'),
]
