document.addEventListener('DOMContentLoaded', function() {
    // Elements
    const searchInput = document.getElementById('search-input');
    const videosGrid = document.getElementById('videos-grid');
    const loadingContainer = document.getElementById('loading-container');
    const errorContainer = document.getElementById('error-container');
    const warningContainer = document.getElementById('warning-container');
    const errorMessage = document.getElementById('error-message');
    const warningMessage = document.getElementById('warning-message');
    const retryBtn = document.getElementById('retry-btn');
    const videoModal = document.getElementById('video-modal');
    const modalClose = document.getElementById('modal-close');
    const videoPlayer = document.getElementById('video-player');
    const modalVideoTitle = document.getElementById('modal-video-title');
    const modalVideoChannel = document.getElementById('modal-video-channel');
    const modalVideoStats = document.getElementById('modal-video-stats');
    const addToPlaylistBtn = document.getElementById('add-to-playlist');
    const likeVideoBtn = document.getElementById('like-video');

    // State
    let currentVideos = [];
    let currentSearch = '';
    let isLoading = false;
    let hasError = false;

    // Functions
    function showLoading() {
        loadingContainer.style.display = 'flex';
        videosGrid.style.display = 'none';
        errorContainer.style.display = 'none';
        warningContainer.style.display = 'none';
        isLoading = true;
        hasError = false;
    }

    function hideLoading() {
        loadingContainer.style.display = 'none';
        videosGrid.style.display = 'grid';
        isLoading = false;
    }

    function showError(message) {
        errorMessage.textContent = message || 'Une erreur inattendue s\'est produite';
        errorContainer.style.display = 'flex';
        videosGrid.style.display = 'none';
        loadingContainer.style.display = 'none';
        hasError = true;
    }

    function hideError() {
        errorContainer.style.display = 'none';
        hasError = false;
    }

    function showWarning(message) {
        warningMessage.textContent = message;
        warningContainer.style.display = 'flex';
    }

    function hideWarning() {
        warningContainer.style.display = 'none';
    }

    function renderVideos(videos) {
        videosGrid.innerHTML = '';
        
        if (videos.length === 0) {
            showWarning('Aucun résultat trouvé. Essayez une autre recherche.');
            return;
        } else {
            hideWarning();
        }

        videos.forEach(video => {
            const videoCard = document.createElement('div');
            videoCard.className = 'video-card';
            videoCard.innerHTML = `
                <div class="video-thumbnail">
                    <img src="${video.thumbnail}" alt="${video.title}" onerror="this.src='https://i.ytimg.com/vi/default.jpg'">
                    <span class="video-duration">${video.duration}</span>
                </div>
                <div class="video-info">
                    <h3 class="video-title">${video.title}</h3>
                    <p class="video-channel">${video.channel}</p>
                    <div class="video-stats">
                        <span>${video.views} vues</span>
                        <i class="fas fa-circle"></i>
                        <span>${formatDate(video.publishedAt)}</span>
                    </div>
                </div>
            `;
            
            videoCard.addEventListener('click', () => openVideoModal(video));
            videosGrid.appendChild(videoCard);
        });
    }

    function formatDate(dateString) {
        if (!dateString) return '';
        
        const date = new Date(dateString);
        const now = new Date();
        const diffInDays = Math.floor((now - date) / (1000 * 60 * 60 * 24));
        
        if (diffInDays < 1) return "Aujourd'hui";
        if (diffInDays < 7) return `Il y a ${diffInDays} jour${diffInDays > 1 ? 's' : ''}`;
        if (diffInDays < 30) {
            const weeks = Math.floor(diffInDays / 7);
            return `Il y a ${weeks} semaine${weeks > 1 ? 's' : ''}`;
        }
        if (diffInDays < 365) {
            const months = Math.floor(diffInDays / 30);
            return `Il y a ${months} mois`;
        }
        
        const years = Math.floor(diffInDays / 365);
        return `Il y a ${years} an${years > 1 ? 's' : ''}`;
    }

    function openVideoModal(video) {
        modalVideoTitle.textContent = video.title;
        modalVideoChannel.textContent = video.channel;
        modalVideoStats.textContent = `${video.views} vues • ${formatDate(video.publishedAt)}`;
        
        videoPlayer.src = `https://www.youtube.com/embed/${video.id}?autoplay=1&rel=0&enablejsapi=1`;
        videoModal.classList.add('active');
        
        // Store current video for actions
        addToPlaylistBtn.dataset.videoId = video.id;
        likeVideoBtn.dataset.videoId = video.id;
    }

    function closeVideoModal() {
        videoModal.classList.remove('active');
        videoPlayer.src = '';
    }

    async function searchVideos(query) {
        if (isLoading) return;
        
        currentSearch = query.trim();
        if (!currentSearch) {
            showWarning('Veuillez entrer un terme de recherche');
            return;
        }
        
        showLoading();
        hideError();
        
        try {
            const response = await fetch(`/search?q=${encodeURIComponent(currentSearch)}`);
            
            if (!response.ok) {
                throw new Error(`Erreur HTTP: ${response.status}`);
            }
            
            const data = await response.json();
            
            if (data.error) {
                throw new Error(data.error);
            }
            
            currentVideos = data.videos || [];
            renderVideos(currentVideos);
            hideLoading();
        } catch (error) {
            console.error('Erreur lors de la recherche:', error);
            showError(error.message || 'Échec de la recherche. Vérifiez votre connexion Internet.');
            hideLoading();
        }
    }

    // Event Listeners
    searchInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            searchVideos(searchInput.value);
        }
    });

    modalClose.addEventListener('click', closeVideoModal);
    videoModal.addEventListener('click', (e) => {
        if (e.target === videoModal) {
            closeVideoModal();
        }
    });

    retryBtn.addEventListener('click', () => {
        if (currentSearch) {
            searchVideos(currentSearch);
        }
    });

    addToPlaylistBtn.addEventListener('click', async () => {
        const videoId = addToPlaylistBtn.dataset.videoId;
        const video = currentVideos.find(v => v.id === videoId);
        
        try {
            const response = await fetch('/api/playlists', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    videoId,
                    title: video.title,
                    thumbnail: video.thumbnail
                })
            });
            
            if (response.ok) {
                alert('Vidéo ajoutée à la playlist avec succès');
            } else {
                throw new Error('Échec de l\'ajout à la playlist');
            }
        } catch (error) {
            console.error('Erreur:', error);
            alert('Erreur lors de l\'ajout à la playlist');
        }
    });

    likeVideoBtn.addEventListener('click', async () => {
        const videoId = likeVideoBtn.dataset.videoId;
        
        try {
            const response = await fetch('/api/favorites', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ videoId })
            });
            
            if (response.ok) {
                alert('Vidéo ajoutée aux favoris avec succès');
            } else {
                throw new Error('Échec de l\'ajout aux favoris');
            }
        } catch (error) {
            console.error('Erreur:', error);
            alert('Erreur lors de l\'ajout aux favoris');
        }
    });

    // Initial load with popular music
    searchVideos('musique populaire');
});