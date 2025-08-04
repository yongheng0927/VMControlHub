document.addEventListener('DOMContentLoaded', function() {

    // --- 1. User menu dropdown ---
    const userMenuButton = document.getElementById('user-menu-button');
    const userDropdown = document.getElementById('user-dropdown');
    
    if (userMenuButton && userDropdown) {
        userMenuButton.addEventListener('click', (event) => {
            event.stopPropagation();
            userDropdown.classList.toggle('hidden');
        });

        document.addEventListener('click', (event) => {
            if (!userMenuButton.contains(event.target) && !userDropdown.contains(event.target)) {
                userDropdown.classList.add('hidden');
            }
        });
    }

    // --- 2. Sidebar submenu handling ---
    const submenuButtons = document.querySelectorAll('button[id^="btn-"][id$="-submenu"]');

    // On page load, sync the active state of buttons with the open state of submenus
    submenuButtons.forEach(button => {
        const submenuId = button.id.replace('btn-', '');
        const submenu = document.getElementById(submenuId);
        if (submenu && submenu.classList.contains('open')) {
            button.classList.add('sidebar-item-active');
        }
    });

    // Add click listeners
    submenuButtons.forEach(button => {
        button.addEventListener('click', function() {
            const submenuId = this.id.replace('btn-', '');
            const submenu = document.getElementById(submenuId);
            const icon = document.getElementById('icon-' + submenuId);
            
            // Check if the current menu is already open
            const isOpening = !submenu.classList.contains('open');

            // First, close all other submenus and deactivate their buttons
            submenuButtons.forEach(otherButton => {
                if (otherButton !== this) {
                    const otherSubmenuId = otherButton.id.replace('btn-', '');
                    const otherSubmenu = document.getElementById(otherSubmenuId);
                    const otherIcon = document.getElementById('icon-' + otherSubmenuId);
                    
                    otherButton.classList.remove('sidebar-item-active');
                    
                    if (otherSubmenu && otherSubmenu.classList.contains('open')) {
                        otherSubmenu.classList.remove('open');
                        otherIcon?.classList.remove('transform', 'rotate-180');
                    }
                }
            });

            // Then, toggle the current submenu and its active state
            if (isOpening) {
                submenu.classList.add('open');
                icon?.classList.add('transform', 'rotate-180');
                this.classList.add('sidebar-item-active');
            } else {
                submenu.classList.remove('open');
                icon?.classList.remove('transform', 'rotate-180');
                this.classList.remove('sidebar-item-active');
            }
        });
    });
});