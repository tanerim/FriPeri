(() => {
  // Keep the color value beside each picker in sync with the submitted value.
  document.querySelectorAll('.color-field input[type="color"]').forEach(input => {
    input.addEventListener('input', () => {
      const value = input.closest('.color-field').querySelector('code');
      if (value) value.textContent = input.value;
    });
  });
  // Long settings forms can be scanned and navigated by their existing headings.
  document.querySelectorAll('.settings-form-v3:not([data-language-form]):not(.homepage-settings-form):not(.design-settings-form)').forEach(form => {
    const sections = [...form.querySelectorAll(':scope > .settings-card-v3')];
    if (sections.length < 3) return;
    const nav = document.createElement('nav');
    nav.className = 'settings-section-nav';
    const title = form.querySelector('h1, h2');
    nav.setAttribute('aria-label', title?.textContent.trim() || 'Page sections');
    sections.forEach((section, index) => {
      const heading = section.querySelector('h2');
      if (!heading) return;
      section.id ||= 'settings-section-' + index;
      heading.tabIndex = -1;
      const link = document.createElement('a');
      link.href = '#' + section.id;
      link.textContent = heading.textContent.trim();
      link.addEventListener('click', () => heading.focus({ preventScroll: true }));
      nav.append(link);
    });
    const pageHeader = form.querySelector('.settings-page-header');
    if (nav.childElementCount && pageHeader) pageHeader.after(nav);
  });
  const sidebar = document.getElementById('admin-sidebar');
  const sidebarToggle = document.querySelector('.admin-sidebar-toggle');
  const collapsedKey = 'friperi.adminSidebarCollapsed';
  if (sidebar && sidebarToggle) {
    let collapsed = false;
    try { collapsed = localStorage.getItem(collapsedKey) === 'true'; } catch (_) {}
    const applySidebar = () => {
      document.body.classList.toggle('admin-sidebar-collapsed', collapsed);
      sidebarToggle.setAttribute('aria-expanded', String(!collapsed));
      sidebarToggle.setAttribute('aria-label', collapsed ? 'Expand sidebar' : 'Collapse sidebar');
      sidebarToggle.title = collapsed ? 'Expand sidebar' : 'Collapse sidebar';
    };
    applySidebar();
    sidebarToggle.addEventListener('click', () => {
      collapsed = !collapsed;
      applySidebar();
      try { localStorage.setItem(collapsedKey, String(collapsed)); } catch (_) {}
    });
  }
  const navigation = document.querySelector('.admin-navigation');
  if (navigation) {
    const desktop = window.matchMedia('(min-width: 1024px)');
    const update = () => { navigation.open = desktop.matches; };
    update();
    desktop.addEventListener('change', update);
  }
})();
