document.addEventListener('DOMContentLoaded', () => {
    const searchInput = document.getElementById('search-input');
    const searchBtn = document.getElementById('search-btn');
    const resultsDiv = document.getElementById('results');
    const modal = document.getElementById('player-modal');
    const closeBtn = document.querySelector('.close');
    const videoPlayer = document.getElementById('video-player');
    const downloadBtn = document.getElementById('download-btn');
    const modalTitle = document.getElementById('modal-title');

    // Recherche de vidéos
    searchBtn.addEventListener('click', searchVideos);
    searchInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') searchVideos();
    });

    // Fermer le modal
    closeBtn.addEventListener('click', () => {
        modal.style.display = 'none';
        videoPlayer.pause();
    });

    async function searchVideos() {
        const query = searchInput.value.trim();
        if (!query) return;

        try {
            const response = await fetch(`/search?q=${encodeURIComponent(query)}`);
            const data = await response.json();
            
            if (data.error) {
                alert(data.error);
                return;
            }

            displayResults(data.videos);
        } catch (error) {
            console.error('Error:', error);
            alert('Erreur lors de la recherche');
        }
    }

    function displayResults(videos) {
        resultsDiv.innerHTML = '';
        
        videos.forEach(video => {
            const videoCard = document.createElement('div');
            videoCard.className = 'video-card';
            videoCard.innerHTML = `
                <img src="${video.thumbnail}" alt="${video.title}">
                <h3>${video.title}</h3>
                <p>${video.channel}</p>
                <button class="play-btn" data-id="${video.id}">Écouter</button>
            `;
            
            videoCard.querySelector('.play-btn').addEventListener('click', () => playVideo(video.id));
            resultsDiv.appendChild(videoCard);
        });
    }

    async function playVideo(videoId) {
        try {
            const response = await fetch(`/download?url=https://youtube.com/watch?v=${videoId}`);
            const data = await response.json();
            
            if (data.error) {
                alert(data.error);
                return;
            }

            modalTitle.textContent = data.title;
            videoPlayer.src = data.stream_url;
            downloadBtn.href = data.stream_url;
            downloadBtn.download = `${data.title}.mp4`;
            modal.style.display = 'block';
        } catch (error) {
            console.error('Error:', error);
            alert('Erreur lors du chargement de la vidéo');
        }
    }
});