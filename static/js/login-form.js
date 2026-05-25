document.addEventListener('DOMContentLoaded', function () {
    var form = document.getElementById('login-form');
    if (!form) return;

    var loginCitizen = document.getElementById('login-citizen');
    var loginStaff = document.getElementById('login-staff');
    var staffBox = document.getElementById('staff-login-box');
    var staffCode = document.getElementById('staff_code');
    var submitBtn = document.getElementById('login-submit-btn');

    function setStaffMode(isStaff) {
        staffBox.classList.toggle('d-none', !isStaff);
        staffCode.required = isStaff;
        if (!isStaff) {
            staffCode.value = '';
        }
        submitBtn.textContent = isStaff ? 'Войти как сотрудник' : 'Войти';
    }

    function updateMode() {
        setStaffMode(loginStaff.checked);
    }

    form.addEventListener('submit', function (e) {
        if (loginStaff.checked && !staffCode.value.trim()) {
            e.preventDefault();
            alert('Введите служебный код доступа сотрудника.');
        }
    });

    loginCitizen.addEventListener('change', updateMode);
    loginStaff.addEventListener('change', updateMode);
    updateMode();
});
