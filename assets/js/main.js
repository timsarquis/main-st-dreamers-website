document.querySelectorAll('[data-year]').forEach(el => { el.textContent = new Date().getFullYear(); });
// A Pages project site has a repository prefix; a future custom domain does not.
if (document.getElementById('home-link')) {
  const base = location.hostname.endsWith('.github.io') ? '/' + location.pathname.split('/').filter(Boolean)[0] + '/' : '/';
  document.querySelectorAll('a').forEach(a => { const href = a.getAttribute('href'); if (href && href.startsWith('./')) a.href = base + href.slice(2); });
  const css = document.querySelector('link[rel="stylesheet"]'); css.href = base + 'assets/css/styles.css';
}
