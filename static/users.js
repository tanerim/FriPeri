(() => {
  'use strict';
  const bind = form => {
    const role = form.querySelector('[data-user-role]');
    const grants = form.querySelector('[data-creator-grants]');
    if (!role || !grants) return;
    const update = () => {
      const creator = role.value === 'cc';
      grants.hidden = !creator;
      grants.querySelectorAll('input[type="checkbox"]').forEach(input => { input.disabled = !creator; });
    };
    role.addEventListener('change', update);
    update();
  };
  document.querySelectorAll('.users-workspace .users-form').forEach(bind);
})();
