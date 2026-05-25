document.addEventListener('DOMContentLoaded', function () {
    var form = document.getElementById('register-form');
    if (!form) return;

    var roleCitizen = document.getElementById('role-citizen');
    var roleStaff = document.getElementById('role-staff');
    var citizenExtra = document.getElementById('citizen-extra-fields');
    var citizenConsent = document.getElementById('citizen-consent');
    var consentCheckbox = document.getElementById('consent');
    var staffHint = document.getElementById('staff-hint');
    var submitBtn = document.getElementById('submit-btn');

    function setStaffMode(isStaff) {
        citizenExtra.classList.toggle('d-none', isStaff);
        citizenConsent.classList.toggle('d-none', isStaff);
        staffHint.classList.toggle('d-none', !isStaff);
        consentCheckbox.required = !isStaff;
        submitBtn.textContent = isStaff ? 'Зарегистрироваться и получить код' : 'Зарегистрироваться';
    }

    function updateMode() {
        setStaffMode(roleStaff.checked);
    }

    roleCitizen.addEventListener('change', updateMode);
    roleStaff.addEventListener('change', updateMode);
    updateMode();
});
