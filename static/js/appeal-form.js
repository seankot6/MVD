document.addEventListener('DOMContentLoaded', function () {
    var consent = document.getElementById('consent');
    var submitBtn = document.getElementById('appeal-submit-btn');
    if (consent && submitBtn) {
        function updateSubmit() {
            submitBtn.disabled = !consent.checked;
        }
        consent.addEventListener('change', updateSubmit);
        updateSubmit();
        document.getElementById('appeal-form').addEventListener('submit', function (e) {
            if (!consent.checked) {
                e.preventDefault();
                alert('Отметьте согласие на обработку персональных данных.');
            }
        });
    }

    var textarea = document.getElementById('appeal_text');
    var counter = document.getElementById('char-count');
    if (textarea && counter) {
        var update = function () { counter.textContent = textarea.value.length; };
        textarea.addEventListener('input', update);
        update();
    }

    var fileInput = document.getElementById('file-input');
    var fileList = document.getElementById('file-list');
  var hiddenInput = document.getElementById('files-hidden');
    var selectedFiles = [];

    if (!fileInput || !fileList) return;

    function renderList() {
        fileList.innerHTML = '';
        selectedFiles.forEach(function (file, index) {
            var row = document.createElement('div');
            row.className = 'file-list-item';
            row.innerHTML = '<span>' + file.name + '</span><button type="button" class="btn btn-sm btn-outline-danger" data-index="' + index + '">Удалить</button>';
            fileList.appendChild(row);
        });
        var dt = new DataTransfer();
        selectedFiles.forEach(function (f) { dt.items.add(f); });
        if (hiddenInput) hiddenInput.files = dt.files;
    }

    fileInput.addEventListener('change', function () {
        Array.from(fileInput.files).forEach(function (f) { selectedFiles.push(f); });
        fileInput.value = '';
        renderList();
    });

    fileList.addEventListener('click', function (e) {
        if (e.target.dataset.index !== undefined) {
            selectedFiles.splice(Number(e.target.dataset.index), 1);
            renderList();
        }
    });
});
