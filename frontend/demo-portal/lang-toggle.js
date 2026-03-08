// Shared language toggle functionality for all pages
let currentLang = 'hi';

function toggleLanguage() {
  currentLang = currentLang === 'hi' ? 'en' : 'hi';
  
  // Update all elements with data-hi and data-en attributes
  document.querySelectorAll('[data-hi]').forEach(el => {
    const newText = el.getAttribute('data-' + currentLang);
    if (newText) {
      if (el.innerHTML.includes('<br>')) {
        el.innerHTML = newText;
      } else {
        el.textContent = newText;
      }
    }
  });
  
  // Update language toggle button text
  const langBtn = document.querySelector('.lang-toggle');
  if (langBtn) {
    langBtn.textContent = currentLang === 'hi' ? '🌐 English' : '🌐 हिंदी';
  }
  
  // Update document language attribute
  document.documentElement.lang = currentLang;
}
