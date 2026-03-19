document.addEventListener('DOMContentLoaded', () => {
    const settingsLink = document.querySelector('a[href="#settings"]'); // Updated selector target
    const modal = document.getElementById('settings-modal');
    const closeBtn = document.querySelector('.close-modal');
    const themeToggle = document.getElementById('theme-toggle');

    // 1. Check LocalStorage for theme preference
    const currentTheme = localStorage.getItem('theme');
    if (currentTheme) {
        document.documentElement.setAttribute('data-theme', currentTheme);
        if (currentTheme === 'light') {
            themeToggle.checked = true;
        }
    }

    // 2. Open Modal
    if (settingsLink) {
        settingsLink.addEventListener('click', (e) => {
            e.preventDefault();
            modal.style.display = 'flex';
        });
    }

    // 3. Close Modal
    if (closeBtn) {
        closeBtn.addEventListener('click', () => {
            modal.style.display = 'none';
        });
    }

    // Close on outside click
    window.addEventListener('click', (e) => {
        if (e.target === modal) {
            modal.style.display = 'none';
        }
    });

    // 4. Toggle Theme
    if (themeToggle) {
        themeToggle.addEventListener('change', (e) => {
            if (e.target.checked) {
                document.documentElement.setAttribute('data-theme', 'light');
                localStorage.setItem('theme', 'light');
            } else {
                document.documentElement.setAttribute('data-theme', 'dark');
                localStorage.setItem('theme', 'dark');
            }
            // Dispatch event for charts to update
            window.dispatchEvent(new Event('themeChanged'));
        });
    }
});
