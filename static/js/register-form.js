document.addEventListener('DOMContentLoaded', function () {
    var form = document.getElementById('register-form');
    if (!form) return;

    var roleCitizen = document.getElementById('role-citizen');
    var roleStaff = document.getElementById('role-staff');
    var citizenExtra = document.getElementById('citizen-extra-fields');
    var citizenConsent = document.getElementById('citizen-consent');
    var consentCheckbox = document.getElementById('consent');
    var staffHint = document.getElementById('staff-hint');
    var staffBox = document.getElementById('staff-register-box');
    var staffCode = document.getElementById('register-staff-code');
    var submitBtn = document.getElementById('submit-btn');

    function updateSubmitState() {
        var isStaff = roleStaff.checked;
        var allowed = isStaff ? staffCode.value.trim().length > 0 : consentCheckbox.checked;
        submitBtn.disabled = !allowed;
        submitBtn.classList.toggle('disabled', !allowed);
    }

    function setStaffMode(isStaff) {
        citizenExtra.classList.toggle('d-none', isStaff);
        citizenConsent.classList.toggle('d-none', isStaff);
        staffHint.classList.toggle('d-none', !isStaff);
        staffBox.classList.toggle('d-none', !isStaff);
        consentCheckbox.required = !isStaff;
        staffCode.required = isStaff;
        if (isStaff) {
            consentCheckbox.checked = false;
        } else {
            staffCode.value = '';
        }
        submitBtn.textContent = isStaff ? 'Зарегистрироваться как сотрудник' : 'Зарегистрироваться';
        updateSubmitState();
    }

    function updateMode() {
        setStaffMode(roleStaff.checked);
    }

    consentCheckbox.addEventListener('change', updateSubmitState);
    staffCode.addEventListener('input', updateSubmitState);

    form.addEventListener('submit', function (e) {
        if (roleStaff.checked) {
            if (!staffCode.value.trim()) {
                e.preventDefault();
                alert('Введите служебный код доступа сотрудника.');
            }
        } else if (!consentCheckbox.checked) {
            e.preventDefault();
            alert('Для регистрации необходимо согласие на обработку персональных данных.');
        }
    });

    roleCitizen.addEventListener('change', updateMode);
    roleStaff.addEventListener('change', updateMode);
    updateMode();
});
