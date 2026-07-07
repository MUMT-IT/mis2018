function initNavbar(root = document) {
    const navbars = Array.from(root.querySelectorAll('.navbar'));

    navbars.forEach((navbar, navbarIndex) => {
        const burgers = Array.from(navbar.querySelectorAll('.navbar-burger[data-target]'));
        const dropdownLinks = Array.from(navbar.querySelectorAll('.navbar-item.has-dropdown > .navbar-link'));

        burgers.forEach((burger, burgerIndex) => {
            const targetId = burger.dataset.target;
            const targetMenu = targetId ? document.getElementById(targetId) : null;

            burger.setAttribute('role', 'button');
            burger.setAttribute('tabindex', '0');
            burger.setAttribute('aria-label', burger.getAttribute('aria-label') || 'Toggle navigation menu');
            burger.setAttribute('aria-controls', targetId || '');
            burger.setAttribute('aria-expanded', burger.classList.contains('is-active') ? 'true' : 'false');

            if (!burger.id) {
                burger.id = `navbar-burger-${navbarIndex}-${burgerIndex}`;
            }

            if (!targetMenu) {
                return;
            }

            const closeDropdowns = () => {
                navbar.querySelectorAll('.navbar-item.has-dropdown.is-active').forEach((item) => {
                    item.classList.remove('is-active');
                    const link = item.querySelector(':scope > .navbar-link');
                    if (link) {
                        link.setAttribute('aria-expanded', 'false');
                    }
                });
            };

            const toggleBurger = () => {
                const isActive = burger.classList.toggle('is-active');
                targetMenu.classList.toggle('is-active', isActive);
                burger.setAttribute('aria-expanded', String(isActive));

                if (!isActive) {
                    closeDropdowns();
                }
            };

            burger.addEventListener('click', toggleBurger);
            burger.addEventListener('keydown', (event) => {
                if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault();
                    toggleBurger();
                }
            });
        });

        const setExpanded = (item, expanded) => {
            item.classList.toggle('is-active', expanded);
            const link = item.querySelector(':scope > .navbar-link');
            if (link) {
                link.setAttribute('aria-expanded', String(expanded));
            }
        };

        const closeDropdowns = (exceptItem = null) => {
            navbar.querySelectorAll('.navbar-item.has-dropdown.is-active').forEach((item) => {
                if (item !== exceptItem) {
                    setExpanded(item, false);
                }
            });
        };

        dropdownLinks.forEach((link, linkIndex) => {
            const item = link.closest('.navbar-item.has-dropdown');
            if (!item) {
                return;
            }

            const dropdown = item.querySelector(':scope > .navbar-dropdown');
            if (!dropdown) {
                return;
            }

            link.setAttribute('role', link.getAttribute('role') || 'button');
            link.setAttribute('tabindex', link.getAttribute('tabindex') || '0');
            link.setAttribute('aria-haspopup', 'true');
            link.setAttribute('aria-expanded', item.classList.contains('is-active') ? 'true' : 'false');

            if (!link.id) {
                link.id = `navbar-dropdown-trigger-${navbarIndex}-${linkIndex}`;
            }

            if (!dropdown.id) {
                dropdown.id = `navbar-dropdown-menu-${navbarIndex}-${linkIndex}`;
            }

            link.setAttribute('aria-controls', dropdown.id);
            dropdown.setAttribute('aria-labelledby', link.id);

            const isDesktop = () => window.matchMedia('(min-width: 1024px)').matches;

            const toggleDropdown = (event) => {
                if (link.tagName === 'A' && link.hasAttribute('href')) {
                    return;
                }

                event.preventDefault();

                if (isDesktop() && item.classList.contains('is-hoverable')) {
                    return;
                }

                const willOpen = !item.classList.contains('is-active');
                closeDropdowns(willOpen ? item : null);
                setExpanded(item, willOpen);
            };

            link.addEventListener('click', toggleDropdown);
            link.addEventListener('keydown', (event) => {
                if (event.key === 'Enter' || event.key === ' ') {
                    toggleDropdown(event);
                } else if (event.key === 'Escape') {
                    setExpanded(item, false);
                    link.focus();
                }
            });
        });

        document.addEventListener('click', (event) => {
            if (!navbar.contains(event.target)) {
                closeDropdowns();
            }
        });

        navbar.addEventListener('keydown', (event) => {
            if (event.key === 'Escape') {
                closeDropdowns();
            }
        });

        navbar.querySelectorAll('.navbar-dropdown .navbar-item').forEach((dropdownItem) => {
            dropdownItem.addEventListener('click', () => {
                const parentItem = dropdownItem.closest('.navbar-item.has-dropdown');
                if (parentItem) {
                    setExpanded(parentItem, false);
                }
            });
        });
    });
}

document.addEventListener('DOMContentLoaded', () => {
    initNavbar();
});
