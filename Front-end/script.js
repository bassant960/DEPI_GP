//    Active Navigation Link Script
        document.addEventListener('DOMContentLoaded', () => {
            const sections = document.querySelectorAll('section');
            const navLinks = document.querySelectorAll('.nav-link');

            window.addEventListener('scroll', () => {
                let current = '';

                sections.forEach(section => {
                    const sectionTop = section.offsetTop;
                    const sectionHeight = section.clientHeight;
                    // Trigger when section is 200px from the top
                    if (window.scrollY >= (sectionTop - 200)) {
                        current = section.getAttribute('id');
                    }
                });

                navLinks.forEach(link => {
                    // Reset all links to default state
                    link.classList.remove('text-brand-600', 'font-bold');
                    link.classList.add('text-gray-600', 'font-semibold');

                    // Set active state for the current section
                    if (link.getAttribute('href') === `#${current}`) {
                        link.classList.remove('text-gray-600', 'font-semibold');
                        link.classList.add('text-brand-600', 'font-bold');
                    }
                });
            });
        });
