document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.alert').forEach((alert) => {
    window.setTimeout(() => alert.classList.remove('show'), 5000);
  });
});
