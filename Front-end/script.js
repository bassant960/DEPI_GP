document.addEventListener('DOMContentLoaded', () => {
    
    // ==========================================
    // 1. Active Navigation Link Script
    // ==========================================
    const sections = document.querySelectorAll('section');
    const navLinks = document.querySelectorAll('.nav-link');

    window.addEventListener('scroll', () => {
        let current = '';

        sections.forEach(section => {
            const sectionTop = section.offsetTop;
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

// ==========================================
// Contact Us Form Script (Direct Submit)
// ==========================================
async function handleContactSubmit(event) {
    event.preventDefault(); // السطر ده هو اللي بيمنع الريفرش

    const submitBtn = document.getElementById("sendMessageBtn");
    const originalText = submitBtn.innerText;
    
    // تغيير شكل الزرار
    submitBtn.innerText = "Sending...";
    submitBtn.disabled = true;
    submitBtn.classList.add("opacity-70", "cursor-not-allowed");

    try {
        const response = await fetch("http://127.0.0.1:8000/contact", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                name: document.getElementById("contact-name").value || "VWear Guest",
                email: document.getElementById("contact-email").value,
                subject: "New Message from VWear Website",
                message: document.getElementById("contact-message").value
            })
        });

        const data = await response.json();

        if (response.ok) {
            alert("Message sent successfully!");
            document.getElementById("contactForm").reset(); // تفريغ الفورم
        } else {
            alert("Error: " + (data.detail || "Failed to send message"));
        }
    } catch (error) {
        alert("Network error. Is the backend server running?");
        console.error("Contact Form Error:", error);
    } finally {
        // إرجاع الزرار لحالته
        submitBtn.innerText = originalText;
        submitBtn.disabled = false;
        submitBtn.classList.remove("opacity-70", "cursor-not-allowed");
    }
}
});