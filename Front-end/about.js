 // Mobile menu toggle
        const menuBtn = document.getElementById('menu-btn');
        const mobileMenu = document.getElementById('mobile-menu');
        menuBtn.addEventListener('click', () => {
            mobileMenu.classList.toggle('hidden');
            mobileMenu.classList.toggle('flex');
        });

        // Scroll reveal
        const reveals = document.querySelectorAll('.reveal');
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.classList.add('visible');
                    observer.unobserve(entry.target);
                }
            });
        }, { threshold: 0.12 });

        reveals.forEach(el => observer.observe(el));

        // Stagger children within revealed sections
        document.querySelectorAll('.reveal').forEach(section => {
            const cards = section.querySelectorAll('.value-card, .stat-card, .team-card');
            cards.forEach((card, i) => {
                card.style.transitionDelay = `${i * 80}ms`;
            });
        });
