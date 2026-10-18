// Local dependencies: no CDN access is needed to display answers.
function renderAnswer(markdown) {
    const target = document.getElementById('answer');
    if (!window.marked || !window.DOMPurify) {
        target.textContent = markdown;
        return;
    }
    const html = marked.parse(markdown, {gfm: true, breaks: true});
    target.innerHTML = DOMPurify.sanitize(html, {
        ALLOWED_TAGS: ['p', 'br', 'strong', 'em', 'del', 'code', 'pre',
            'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'ul', 'ol', 'li',
            'blockquote', 'hr', 'table', 'thead', 'tbody', 'tr', 'th', 'td', 'a'],
        ALLOWED_ATTR: ['href', 'title', 'start'],
        ALLOW_DATA_ATTR: false
    });
    target.classList.add('markdown');
    target.querySelectorAll('a').forEach(link => {
        const href = link.getAttribute('href') || '';
        if (!/^(https?:\/\/|mailto:|#)/i.test(href)) link.removeAttribute('href');
        link.setAttribute('rel', 'noopener noreferrer');
    });
}
