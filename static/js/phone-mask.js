(function () {
    const DIGIT_SLOTS = [4, 5, 6, 9, 10, 11, 13, 14, 16, 17];
    const MAX_DIGITS = 10;

    function extractDigits(value) {
        let digits = (value || '').replace(/\D/g, '');
        if (digits.startsWith('7') || digits.startsWith('8')) {
            digits = digits.slice(1);
        }
        return digits.slice(0, MAX_DIGITS);
    }

    function formatPhone(digits) {
        const chars = digits.split('');
        while (chars.length < MAX_DIGITS) {
            chars.push('_');
        }
        return `+7 (${chars[0]}${chars[1]}${chars[2]}) ${chars[3]}${chars[4]}${chars[5]}-${chars[6]}${chars[7]}-${chars[8]}${chars[9]}`;
    }

    function digitIndexFromCursor(pos) {
        for (let i = 0; i < DIGIT_SLOTS.length; i++) {
            if (pos <= DIGIT_SLOTS[i]) {
                return i;
            }
        }
        return MAX_DIGITS - 1;
    }

    function cursorForDigitIndex(index) {
        return DIGIT_SLOTS[Math.min(index, MAX_DIGITS - 1)];
    }

    function toSubmitValue(digits) {
        return digits ? `+7${digits}` : '';
    }

    function initPhoneInput(input) {
        if (input.dataset.phoneMaskReady) {
            return;
        }
        input.dataset.phoneMaskReady = '1';
        input.setAttribute('inputmode', 'numeric');
        input.setAttribute('autocomplete', 'tel');

        function ensureTemplate() {
            const digits = extractDigits(input.value);
            input.value = formatPhone(digits);
            return digits;
        }

        function setCursor(index) {
            const pos = cursorForDigitIndex(index);
            input.setSelectionRange(pos, pos);
        }

        input.addEventListener('focus', function () {
            const digits = extractDigits(input.value);
            input.value = formatPhone(digits);
            setCursor(digits.length < MAX_DIGITS ? digits.length : MAX_DIGITS - 1);
        });

        input.addEventListener('click', function () {
            const digits = extractDigits(input.value);
            const index = digitIndexFromCursor(input.selectionStart);
            setCursor(Math.min(index, digits.length));
        });

        input.addEventListener('keydown', function (e) {
            if (e.key === 'Tab' || e.ctrlKey || e.metaKey || e.altKey) {
                return;
            }

            if (e.key === 'ArrowLeft' || e.key === 'ArrowRight' || e.key === 'Home' || e.key === 'End') {
                setTimeout(function () {
                    const digits = extractDigits(input.value);
                    const index = digitIndexFromCursor(input.selectionStart);
                    setCursor(Math.min(index, digits.length));
                }, 0);
                return;
            }

            let digits = extractDigits(input.value);
            let index = digitIndexFromCursor(input.selectionStart);

            if (/^\d$/.test(e.key)) {
                e.preventDefault();
                if (digits.length >= MAX_DIGITS) {
                    setCursor(MAX_DIGITS - 1);
                    return;
                }
                index = Math.min(index, digits.length);
                digits = digits.slice(0, index) + e.key + digits.slice(index);
                digits = digits.slice(0, MAX_DIGITS);
                input.value = formatPhone(digits);
                setCursor(Math.min(index + 1, MAX_DIGITS - 1));
                return;
            }

            if (e.key === 'Backspace') {
                e.preventDefault();
                if (!digits.length) {
                    input.value = formatPhone('');
                    setCursor(0);
                    return;
                }
                index = Math.min(index, digits.length - 1);
                digits = digits.slice(0, index) + digits.slice(index + 1);
                input.value = formatPhone(digits);
                setCursor(index);
                return;
            }

            if (e.key === 'Delete') {
                e.preventDefault();
                if (!digits.length) {
                    return;
                }
                index = Math.min(index, digits.length - 1);
                digits = digits.slice(0, index) + digits.slice(index + 1);
                input.value = formatPhone(digits);
                setCursor(index);
                return;
            }

            if (e.key.length === 1) {
                e.preventDefault();
            }
        });

        input.addEventListener('paste', function (e) {
            e.preventDefault();
            const pasted = (e.clipboardData || window.clipboardData).getData('text');
            const digits = extractDigits(pasted);
            input.value = formatPhone(digits);
            setCursor(Math.min(digits.length, MAX_DIGITS - 1));
        });

        input.addEventListener('blur', function () {
            const digits = extractDigits(input.value);
            if (!digits.length) {
                input.value = '';
            } else {
                input.value = formatPhone(digits);
            }
        });

        const form = input.closest('form');
        if (form && !form.dataset.phoneSubmitReady) {
            form.dataset.phoneSubmitReady = '1';
            form.addEventListener('submit', function () {
                form.querySelectorAll('input[type="tel"], input.phone-input').forEach(function (phoneInput) {
                    const digits = extractDigits(phoneInput.value);
                    phoneInput.value = toSubmitValue(digits);
                });
            });
        }
    }

    function initAll() {
        document.querySelectorAll('input[type="tel"], input.phone-input').forEach(initPhoneInput);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initAll);
    } else {
        initAll();
    }
})();
