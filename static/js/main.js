// Inicializaciones y utilidades de Javascript global para Podología Web

document.addEventListener('DOMContentLoaded', function() {
    console.log("Podología Web inicializado correctamente.");

    // Auto-ocultar alertas de Bootstrap después de 5 segundos para mejorar UX
    var alerts = document.querySelectorAll('.alert-dismissible');
    alerts.forEach(function(alert) {
        setTimeout(function() {
            var bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        }, 5000);
    });

    // Validaciones o confirmaciones comunes
    var deleteButtons = document.querySelectorAll('.confirm-delete');
    deleteButtons.forEach(function(btn) {
        btn.addEventListener('click', function(e) {
            if (!confirm('¿Estás seguro de que deseas eliminar este elemento de forma permanente?')) {
                e.preventDefault();
            }
        });
    });
});
