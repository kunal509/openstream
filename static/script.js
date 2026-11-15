(function () {
    'use strict';

    // ---------- Elements ----------
    var searchInput = document.getElementById('searchInput');
    var cards = Array.prototype.slice.call(document.querySelectorAll('.movie-card'));
    var noResults = document.getElementById('noResults');
    var modal = document.getElementById('videoModal');
    var closeBtn = document.getElementById('closeBtn');
    var video = document.getElementById('moviePlayer');
    var modalTitle = document.getElementById('modalTitle');
    var playerError = document.getElementById('playerError');
    var heroBtn = document.getElementById('heroPlay');
    var lastFocus = null;

    // ---------- Poster fallback (missing / broken image) ----------
    function posterFallback(img) {
        var box = document.createElement('div');
        box.className = 'thumb-fallback';
        box.textContent = img.getAttribute('data-title') || img.alt || 'No poster';
        img.replaceWith(box);
    }
    document.querySelectorAll('.thumbnail img').forEach(function (img) {
        img.addEventListener('error', function () { posterFallback(img); });
        if (img.complete && img.naturalWidth === 0) posterFallback(img);
    });

    // ---------- Search ----------
    if (searchInput) {
        searchInput.addEventListener('input', function () {
            var q = searchInput.value.trim().toLowerCase();
            var shown = 0;
            cards.forEach(function (card) {
                var match = (card.getAttribute('data-title') || '').toLowerCase().indexOf(q) !== -1;
                card.style.display = match ? '' : 'none';
                if (match) shown++;
            });
            if (noResults) noResults.hidden = shown !== 0 || cards.length === 0;
        });
    }

    // ---------- Player (Plyr, with native fallback if the CDN is blocked) ----------
    var player = null;
    if (video && window.Plyr) {
        player = new Plyr(video, { settings: ['speed'], keyboard: { focused: true, global: false } });
    }

    function mimeFor(url) {
        return url.toLowerCase().split('?')[0].endsWith('.webm') ? 'video/webm' : 'video/mp4';
    }

    function openMovie(url, title) {
        if (!url || !modal) return;
        lastFocus = document.activeElement;
        playerError.hidden = true;
        modalTitle.textContent = title || '';
        modal.classList.add('open');
        document.body.classList.add('modal-open');
        closeBtn.focus();

        if (player) {
            player.source = { type: 'video', title: title || '', sources: [{ src: url, type: mimeFor(url) }] };
            setTimeout(function () {
                var p = player.play();
                if (p && p.catch) p.catch(function () { /* user can press play */ });
            }, 150);
        } else {
            video.controls = true;
            video.src = url;
            var p2 = video.play();
            if (p2 && p2.catch) p2.catch(function () {});
        }
    }

    function closeMovie() {
        if (!modal.classList.contains('open')) return;
        if (player) { player.pause(); player.stop(); } else { video.pause(); video.removeAttribute('src'); video.load(); }
        modal.classList.remove('open');
        document.body.classList.remove('modal-open');
        if (lastFocus && lastFocus.focus) lastFocus.focus();
    }

    if (video) {
        video.addEventListener('error', function () {
            if (modal.classList.contains('open')) {
                playerError.hidden = false;
            }
        });
    }

    cards.forEach(function (card) {
        function play() { openMovie(card.getAttribute('data-video'), card.getAttribute('data-title')); }
        card.addEventListener('click', play);
        card.addEventListener('keydown', function (e) {
            if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); play(); }
        });
    });

    if (heroBtn) {
        heroBtn.addEventListener('click', function () {
            openMovie(heroBtn.getAttribute('data-video'), heroBtn.getAttribute('data-title'));
        });
    }

    if (closeBtn) closeBtn.addEventListener('click', closeMovie);
    if (modal) modal.addEventListener('click', function (e) { if (e.target === modal) closeMovie(); });
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape') closeMovie(); });
})();
