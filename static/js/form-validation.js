document.addEventListener('DOMContentLoaded', function () {
    var form = document.getElementById('register-form');
    if (!form) return;

    function validatePassword(password) {
        if (password.length < 8) return 'Минимум 8 символов';
        if (!/[A-ZА-Я]/.test(password)) return 'Нужна заглавная буква';
        if (!/[a-zа-я]/.test(password)) return 'Нужна строчная буква';
        if (!/\d/.test(password)) return 'Нужна цифра';
        return '';
    }

    form.addEventListener('submit', function (e) {
        var password = document.getElementById('password').value;
        var password2 = document.getElementById('password2').value;
        var pwdError = document.getElementById('password-error');
        var pwd2Error = document.getElementById('password2-error');
        var msg = validatePassword(password);
        pwdError.textContent = msg;
        pwd2Error.textContent = password !== password2 ? 'Пароли не совпадают' : '';
        if (msg || password !== password2 || !form.checkValidity()) {
            e.preventDefault();
            form.reportValidity();
        }
    });
});
