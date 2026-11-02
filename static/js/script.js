
document.addEventListener("DOMContentLoaded", function () {
    console.log("Enterprise ERP Platform Loaded Successfully!");

    const alerts = document.querySelectorAll(".alert");

    alerts.forEach(function (alert) {
        setTimeout(function () {
            if (alert && alert.parentNode) {
                alert.remove();
            }
        }, 4000);
    });
});
