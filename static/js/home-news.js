(function () {
    var banner = document.getElementById('news-banner');
    if (!banner) return;

    var titleEl = document.getElementById('news-title');
    var textEl = document.getElementById('news-text');
    var dateEl = document.getElementById('news-date');
    var counterEl = document.getElementById('news-counter');
    var dotsEl = document.getElementById('news-dots');
    var prevBtn = document.getElementById('news-prev');
    var nextBtn = document.getElementById('news-next');
    var items = Array.isArray(window.MVD_INITIAL_NEWS) ? window.MVD_INITIAL_NEWS.slice() : [];
    var index = 0;
    var rotateMs = 10000;
    var refreshMs = 5 * 60 * 1000;
    var timer = null;
    var touchStartX = 0;

    function formatDate(iso) {
        if (!iso) return '';
        var parts = iso.split('-');
        if (parts.length !== 3) return iso;
        return parts[2] + '.' + parts[1] + '.' + parts[0];
    }

    function renderDots() {
        if (!dotsEl) return;
        dotsEl.innerHTML = '';
        items.forEach(function (_, i) {
            var dot = document.createElement('button');
            dot.type = 'button';
            dot.className = 'news-dot' + (i === index ? ' active' : '');
            dot.setAttribute('aria-label', 'Новость ' + (i + 1));
            dot.addEventListener('click', function () {
                showItem(i, true);
            });
            dotsEl.appendChild(dot);
        });
    }

    function showItem(i, userAction) {
        if (!items.length) {
            titleEl.textContent = 'Новостей пока нет';
            textEl.textContent = '';
            dateEl.textContent = '';
            if (counterEl) counterEl.textContent = '';
            return;
        }
        index = ((i % items.length) + items.length) % items.length;
        var item = items[index];
        banner.classList.add('news-banner--fade');
        setTimeout(function () {
            titleEl.textContent = item.title || '';
            textEl.textContent = item.text || '';
            dateEl.textContent = formatDate(item.date);
            if (counterEl) {
                counterEl.textContent = (index + 1) + ' / ' + items.length;
            }
            renderDots();
            banner.classList.remove('news-banner--fade');
        }, 150);
        if (userAction) {
            scheduleRotate();
        }
    }

    function scheduleRotate() {
        if (timer) clearInterval(timer);
        if (items.length < 2) return;
        timer = setInterval(function () {
            showItem(index + 1, false);
        }, rotateMs);
    }

    function fetchNews() {
        var url = window.MVD_NEWS_API;
        if (!url) return;
        fetch(url, { cache: 'no-store' })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (Array.isArray(data) && data.length) {
                    items = data;
                    if (index >= items.length) index = 0;
                    showItem(index, false);
                    scheduleRotate();
                }
            })
            .catch(function () {});
    }

    if (prevBtn) {
        prevBtn.addEventListener('click', function () {
            showItem(index - 1, true);
        });
    }
    if (nextBtn) {
        nextBtn.addEventListener('click', function () {
            showItem(index + 1, true);
        });
    }

    banner.addEventListener('touchstart', function (e) {
        touchStartX = e.changedTouches[0].screenX;
    }, { passive: true });

    banner.addEventListener('touchend', function (e) {
        var diff = e.changedTouches[0].screenX - touchStartX;
        if (Math.abs(diff) < 40) return;
        if (diff < 0) {
            showItem(index + 1, true);
        } else {
            showItem(index - 1, true);
        }
    }, { passive: true });

    showItem(0, false);
    scheduleRotate();
    setInterval(fetchNews, refreshMs);
})();
