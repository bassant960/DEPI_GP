document.getElementById('generateBtn').onclick = async () => {
    if (!selectedFile || !selectedOutfitUrl) {
        return alert("Please upload your photo and select an outfit first!");
    }

    const token = localStorage.getItem("token");
    if (!token) {
        alert("Session expired. Please login again.");
        window.location.href = "login.html";
        return;
    }

    const btn = document.getElementById('generateBtn');
    const resultBox = document.getElementById('result-box');

    btn.innerText = "Processing AI Magic... Please Wait";
    btn.disabled = true;
    btn.classList.add("opacity-75", "cursor-not-allowed");
    
    resultBox.innerHTML = `
        <div class="flex flex-col items-center gap-3 text-brand-600">
            <svg class="animate-spin h-10 w-10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="10" stroke-opacity="0.25"></circle>
                <path d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            <span class="font-bold animate-pulse">AI is mapping the outfit...</span>
        </div>`;

    const formData = new FormData();
    formData.append("person_image", selectedFile);
    formData.append("outfit_url", selectedOutfitUrl);

    try {
        const response = await fetch('http://127.0.0.1:8000/generate-tryon', {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}` // توكن الحماية الخاص بالـ Auth API
            },
            body: formData
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || "AI Generation Failed");
        }

        resultBox.innerHTML = `<img src="${data.result_url}" class="w-full h-full object-cover rounded-2xl shadow-lg border-2 border-brand-500">`;
        
        const historyGrid = document.getElementById('history-grid');
        if (historyGrid.innerText.includes("No History Yet")) {
            historyGrid.innerHTML = ""; 
        }
        historyGrid.innerHTML = `
            <div class="aspect-square bg-gray-100 rounded-2xl overflow-hidden shadow-sm border border-gray-200">
                <img src="${data.result_url}" class="w-full h-full object-cover">
            </div>
        ` + historyGrid.innerHTML; 

    } catch (error) {
        console.error("Integration Error:", error);
        alert(error.message || "Failed to connect to the AI model.");
        resultBox.innerHTML = `<span class="text-red-500 font-bold">❌ Generation Failed</span>`;
    } finally {
        btn.innerText = "Generate Virtual Try-On";
        btn.disabled = false;
        btn.classList.remove("opacity-75", "cursor-not-allowed");
    }
};
