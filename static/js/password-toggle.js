document.addEventListener('DOMContentLoaded', function () {
    var eyeSvg =
        '<svg class="password-toggle-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">' +
        '<path fill="currentColor" d="M12 5C7 5 2.73 8.11 1 12c1.73 3.89 6 7 11 7s9.27-3.11 11-7c-1.73-3.89-6-7-11-7zm0 12a5 5 0 1 1 0-10 5 5 0 0 1 0 10zm0-8a3 3 0 1 0 .002 6.001A3 3 0 0 0 12 9z"/>' +
        '</svg>';
    var eyeOffSvg =
        '<svg class="password-toggle-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">' +
        '<path fill="currentColor" d="M12 7c2.76 0 5 2.24 5 5 0 .65-.13 1.26-.36 1.83l2.92 2.92c1.51-1.26 2.7-2.89 3.43-4.75-1.73-3.89-6-7-11-7-1.4 0-2.74.25-3.98.7l2.16 2.16C10.74 7.13 11.35 7 12 7zM2 4.27l2.28 2.28.46.46C3.08 8.3 1.78 10.02 1 12c1.73 3.89 6 7 11 7 1.55 0 3.03-.3 4.38-.84l.42.42L19.73 22 21 20.73 3.27 3 2 4.27zM7.53 9.8l1.55 1.55a3 3 0 0 0 3.22 3.22l1.55 1.55a5 5 0 0 1-6.32-6.32zm4.31 4.31-1.55-1.55a3 3 0 0 0-3.22-3.22L5.52 7.49A5 5 0 0 1 11.84 14.11z"/>' +
        '</svg>';

    document.querySelectorAll('input[type="password"]').forEach(function (input) {
        if (input.closest('.password-input-wrap')) {
            return;
        }

        var wrap = document.createElement('div');
        wrap.className = 'password-input-wrap';
        input.parentNode.insertBefore(wrap, input);
        wrap.appendChild(input);

        var btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'password-toggle-btn';
        btn.setAttribute('aria-label', 'Показать пароль');
        btn.innerHTML = eyeSvg;
        wrap.appendChild(btn);

        btn.addEventListener('click', function () {
            var visible = input.type === 'text';
            input.type = visible ? 'password' : 'text';
            btn.classList.toggle('is-visible', !visible);
            btn.setAttribute('aria-label', visible ? 'Показать пароль' : 'Скрыть пароль');
            btn.innerHTML = visible ? eyeSvg : eyeOffSvg;
        });
    });
});
