(() => {
  const language = document.getElementById('secondary-language');
  const translations = document.getElementById('setup-translations');
  const languageUpdate = () => {
    translations.hidden = !language.value;
    document.getElementById('translation-language').textContent = language.value
      ? `— ${language.selectedOptions[0].textContent}` : '';
  };
  language.addEventListener('change', languageUpdate);
  languageUpdate();

  const password = document.getElementById('admin_password');
  const confirmation = document.getElementById('password_confirmation');
  const warning = document.getElementById('password-mismatch');
  const requiredWarning = document.getElementById('password-required');
  const passwordDescription = password.getAttribute('aria-describedby');
  const passwordInvalid = password.getAttribute('aria-invalid');
  let passwordTouched = false;
  const checkRequiredPassword = () => {
    const missing = passwordTouched && password.value === '';
    requiredWarning.hidden = !missing;
    password.setAttribute('aria-describedby', missing
      ? `${passwordDescription} password-required` : passwordDescription);
    if (missing) password.setAttribute('aria-invalid', 'true');
    else if (passwordInvalid !== null) password.setAttribute('aria-invalid', passwordInvalid);
    else password.removeAttribute('aria-invalid');
  };
  const check = () => {
    checkRequiredPassword();
    const mismatch = password.value !== '' && confirmation.value !== '' && password.value !== confirmation.value;
    warning.hidden = !mismatch;
    confirmation.setCustomValidity(mismatch ? 'Enter the same password in both fields.' : '');
  };
  password.addEventListener('input', check);
  confirmation.addEventListener('input', check);
  ['blur', 'invalid'].forEach(event => {
    password.addEventListener(event, () => {
      passwordTouched = true;
      check();
    });
  });
  document.querySelectorAll('[data-password]').forEach(button => {
    button.hidden = false;
    const input = document.getElementById(button.dataset.password);
    const label = document.querySelector(`label[for="${input.id}"]`).textContent.toLowerCase();
    button.addEventListener('click', () => {
      const visible = input.type === 'password';
      input.type = visible ? 'text' : 'password';
      button.textContent = visible ? 'Hide' : 'Show';
      button.setAttribute('aria-pressed', String(visible));
      button.setAttribute('aria-label', `${visible ? 'Hide' : 'Show'} ${label}`);
    });
  });

  const preview = () => {
    const value = id => document.getElementById(id).value.trim();
    document.getElementById('preview-kicker').textContent = value('hero_kicker_en');
    document.getElementById('preview-title').textContent = value('hero_title_en') || value('site_name') || 'Your website';
    document.getElementById('preview-copy').textContent = value('hero_copy_en');
  };
  ['site_name', 'hero_kicker_en', 'hero_title_en', 'hero_copy_en'].forEach(id => {
    document.getElementById(id).addEventListener('input', preview);
  });
  preview();

  if ('IntersectionObserver' in window) {
    const links = [...document.querySelectorAll('.setup-nav a')];
    const observer = new IntersectionObserver(entries => {
      entries.forEach(entry => {
        if (!entry.isIntersecting) return;
        links.forEach(link => {
          if (link.hash === `#${entry.target.id}`) link.setAttribute('aria-current', 'location');
          else link.removeAttribute('aria-current');
        });
      });
    }, { rootMargin: '-5% 0px -55% 0px' });
    document.querySelectorAll('.card h2').forEach(heading => observer.observe(heading));
  }
  document.querySelector('.error-summary')?.focus();
  const form = document.getElementById('setup-form');
  form.addEventListener('submit', () => {
    const button = form.querySelector('[type="submit"]');
    button.disabled = true;
    button.textContent = 'Creating your website…';
    form.setAttribute('aria-busy', 'true');
  });
  window.addEventListener('pageshow', () => {
    const button = form.querySelector('[type="submit"]');
    button.disabled = false;
    button.textContent = 'Create my website →';
    form.removeAttribute('aria-busy');
    check();
  });
})();
