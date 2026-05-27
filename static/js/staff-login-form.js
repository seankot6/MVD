document.addEventListener('DOMContentLoaded', function () {
    var form = document.getElementById('staff-login-form');
    if (!form) return;
    var codeInput = document.getElementById('staff_code');
    var submitBtn = document.getElementById('staff-login-btn');

    function updateBtn() {
        var ok = codeInput.value.trim().length >= 3;
        submitBtn.disabled = !ok;
    }

    codeInput.addEventListener('input', updateBtn);
    updateBtn();
});
