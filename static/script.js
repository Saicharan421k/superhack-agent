document.addEventListener('DOMContentLoaded', () => {
    const ticketIdInput = document.getElementById('ticketIdInput');
    const analyzeBtn = document.getElementById('analyzeBtn');
    const resultsDiv = document.getElementById('results');
    const loadingIndicator = document.getElementById('loadingIndicator');
    const closeTicketBtn = document.getElementById('closeTicketBtn');

    let currentTicketId = null;

    const analyzeTicket = async () => {
        const ticketId = ticketIdInput.value.trim();
        if (!ticketId) { alert('Please enter a Ticket ID.'); return; }
        loadingIndicator.classList.remove('hidden');
        resultsDiv.classList.add('hidden');
        const apiUrl = `http://${window.location.hostname}:5000/analyze/${ticketId}`;
        try {
            const response = await fetch(apiUrl);
            if (!response.ok) { throw new Error('Ticket not found or server error.'); }
            const data = await response.json();
            currentTicketId = data.ticket.id;
            displayResults(data);
        } catch (error) {
            alert(error.message);
        } finally {
            loadingIndicator.classList.add('hidden');
        }
    };

    const updateTicketStatus = async (newStatus) => {
        if (!currentTicketId) return;
        const apiUrl = `http://${window.location.hostname}:5000/ticket/${currentTicketId}/status`;
        try {
            const response = await fetch(apiUrl, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ status: newStatus })
            });
            if (!response.ok) { throw new Error('Failed to update status.'); }
            const statusSpan = document.getElementById('resultStatus');
            statusSpan.textContent = newStatus;
            statusSpan.className = `status status-${newStatus.toLowerCase()}`;
            closeTicketBtn.disabled = true;
            closeTicketBtn.textContent = 'Closed';
        } catch (error) {
            alert(error.message);
        }
    };

    const displayResults = (data) => {
        const statusSpan = document.getElementById('resultStatus');
        statusSpan.textContent = data.ticket.status;
        statusSpan.className = `status status-${data.ticket.status.toLowerCase()}`;
        
        if (data.ticket.status === 'Closed') {
            closeTicketBtn.disabled = true;
            closeTicketBtn.textContent = 'Closed';
        } else {
            closeTicketBtn.disabled = false;
            closeTicketBtn.textContent = 'Close Ticket';
        }

        document.getElementById('resultSubject').textContent = `Subject: ${data.ticket.subject}`;
        document.getElementById('resultTicketId').textContent = data.ticket.id;
        document.getElementById('resultAssetId').textContent = data.ticket.asset_id;

        if (data.ai_analysis) {
            document.getElementById('resultAiSummary').textContent = data.ai_analysis.summary;
            document.getElementById('resultRootCause').textContent = data.ai_analysis.probable_root_cause;
            
            // THIS IS THE FIX FOR THE ACTION PLAN
            const stepsList = document.getElementById('resultStepsList');
            stepsList.innerHTML = ''; 
            if (data.ai_analysis.recommended_steps && Array.isArray(data.ai_analysis.recommended_steps)) {
                data.ai_analysis.recommended_steps.forEach(step => {
                    const li = document.createElement('li');
                    li.textContent = step;
                    stepsList.appendChild(li);
                });
            }
        }

        const assetCard = document.getElementById('assetCard');
        if (data.asset_details) {
            assetCard.classList.remove('hidden');
            document.getElementById('resultHostname').textContent = data.asset_details.hostname || 'N/A';
            document.getElementById('resultOs').textContent = data.asset_details.os || 'N/A';
            document.getElementById('resultCpu').textContent = data.asset_details.cpu || 'N/A';
            document.getElementById('resultMemory').textContent = data.asset_details.memory_gb || 'N/A';
        } else {
            assetCard.classList.add('hidden');
        }
        document.getElementById('resultAlertsCount').textContent = data.related_alerts.length;
        resultsDiv.classList.remove('hidden');
    };

    analyzeBtn.addEventListener('click', analyzeTicket);
    ticketIdInput.addEventListener('keyup', (e) => e.key === 'Enter' && analyzeTicket());
    closeTicketBtn.addEventListener('click', () => updateTicketStatus('Closed'));
});
