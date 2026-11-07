let globalPickers = [];

function switchTab(tabName) {
    const tabs = document.querySelectorAll('.tab-btn');
    const contents = document.querySelectorAll('.tab-content');

    tabs.forEach(t => t.classList.toggle('active', t.dataset.tab === tabName));
    contents.forEach(c => c.classList.toggle('active', c.id === tabName));
}

document.addEventListener('DOMContentLoaded', () => {
    const tabs = document.querySelectorAll('.tab-btn');

    // Tab Switching
    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            switchTab(tab.dataset.tab);
        });
    });

    // Delegated click handler for expandable lists and cross-links
    document.addEventListener('click', (e) => {
        const pickerLink = e.target.closest('.picker-link');
        if (pickerLink) {
            e.preventDefault();
            const pickerName = pickerLink.dataset.picker;
            navigateToPicker(pickerName);
            return;
        }

        const movieLink = e.target.closest('.movie-link');
        if (movieLink) {
            e.preventDefault();
            const movieTitle = movieLink.dataset.movie;
            const director = movieLink.dataset.director;
            navigateToMovie(movieTitle, director);
            return;
        }

        if (e.target.classList.contains('picker-toggle')) {
            const list = e.target.nextElementSibling;
            if (list && list.classList.contains('pickers-list')) {
                list.classList.toggle('hidden');
                const isHidden = list.classList.contains('hidden');
                const count = e.target.dataset.count;
                const label = e.target.dataset.label;
                e.target.textContent = isHidden ? `View ${count} ${label}` : `Hide ${label}`;
            }
        }
    });

    // Picker Ranking Mode Toggle
    document.querySelectorAll('input[name="ranking-mode"]').forEach(radio => {
        radio.addEventListener('change', () => {
            renderPickers();
        });
    });

    // Fetch and Process Data
    fetchData();
});

async function fetchData() {
    try {
        const response = await fetch('closet_picks.csv');
        if (!response.ok) throw new Error("Failed to load data");
        const text = await response.text();
        const data = parseCSV(text);

        // Remove header
        const header = data.shift(); // Movie Title, Director, Count, Picked By

        processAndRender(data);
    } catch (err) {
        console.error(err);
        document.querySelectorAll('.loading').forEach(el => el.textContent = "Error loading data.");
    }
}

function parseCSV(text) {
    const rows = [];
    let currentRow = [];
    let currentCell = '';
    let insideQuote = false;

    // Normalize newlines
    text = text.replace(/\r\n/g, '\n').replace(/\r/g, '\n');

    for (let i = 0; i < text.length; i++) {
        const char = text[i];

        if (char === '"') {
            if (insideQuote && text[i+1] === '"') {
                currentCell += '"';
                i++; // skip escaped quote
            } else {
                insideQuote = !insideQuote;
            }
        } else if (char === ',' && !insideQuote) {
            currentRow.push(currentCell.trim());
            currentCell = '';
        } else if (char === '\n' && !insideQuote) {
            currentRow.push(currentCell.trim());
            if (currentRow.length > 1 || (currentRow.length === 1 && currentRow[0] !== '')) {
                rows.push(currentRow);
            }
            currentRow = [];
            currentCell = '';
        } else {
            currentCell += char;
        }
    }

    // Last row
    if (currentCell || currentRow.length > 0) {
        currentRow.push(currentCell.trim());
        rows.push(currentRow);
    }

    return rows;
}

function processAndRender(rows) {
    const movies = [];
    const directorsMap = {};
    const pickersMap = {};

    rows.forEach(row => {
        if (row.length < 4) return;

        const title = row[0];
        const director = row[1];
        const count = parseInt(row[2], 10);
        const pickedBy = row[3];
        const currentPickers = pickedBy.split(',').map(s => s.trim()).filter(s => s.length > 0);

        // Movies List
        movies.push({
            title,
            director,
            count,
            pickedBy,
            pickers: currentPickers
        });

        // Directors Aggregation
        if (!directorsMap[director]) {
            directorsMap[director] = {
                name: director,
                totalPicks: 0,
                movies: []
            };
        }
        directorsMap[director].totalPicks += count;
        directorsMap[director].movies.push({ title, count, director });

        // Pickers Aggregation
        // Split by comma, trimming whitespace
        currentPickers.forEach(p => {
            if (!pickersMap[p]) {
                pickersMap[p] = {
                    name: p,
                    picks: []
                };
            }
            pickersMap[p].picks.push({ title, count, director });
        });
    });

    // Sort Movies
    movies.sort((a, b) => b.count - a.count);

    // Sort Directors
    const directors = Object.values(directorsMap);
    directors.sort((a, b) => b.totalPicks - a.totalPicks);

    // Calculate Scores for Pickers
    globalPickers = Object.values(pickersMap).map(picker => {
        const canonScore = calculateCanonScore(picker.picks);
        const originalScore = calculateOriginalityScore(picker.picks);
        return {
            ...picker,
            canonScore,
            originalScore
        };
    });

    renderMovies(movies);
    renderDirectors(directors);
    renderPickers();
}

function calculateCanonScore(picks) {
    if (!picks.length) return 0;

    const { sum1, sum2 } = picks.reduce((acc, pick) => {
        const { count } = pick;
        // Bins
        if (count >= 15) acc.sum1 += 10;
        else if (count >= 10) acc.sum1 += 8;
        else if (count >= 7) acc.sum1 += 6;
        else if (count >= 5) acc.sum1 += 4;
        else if (count >= 3) acc.sum1 += 2;

        // Smooth
        acc.sum2 += 10 * (count / (count + 8));
        return acc;
    }, { sum1: 0, sum2: 0 });

    const avg1 = sum1 / picks.length;
    const avg2 = sum2 / picks.length;
    return (avg1 + avg2) / 2;
}

function calculateOriginalityScore(picks) {
    const n = picks.length;
    if (!n) return 0;

    const { countRare3, countRare4 } = picks.reduce((counts, pick) => {
        if (pick.count <= 3) {
            counts.countRare3++;
            counts.countRare4++;
        } else if (pick.count === 4) {
            counts.countRare4++;
        }
        return counts;
    }, { countRare3: 0, countRare4: 0 });
        
    return ((countRare3 / n) + (countRare4 / n)) / 2;
}

function createToggleHtml(count, content, label) {
    return `
       <div class="picker-container">
           <button class="picker-toggle" data-count="${count}" data-label="${label}">View ${count} ${label}</button>
           <div class="pickers-list hidden">${content}</div>
       </div>
   `;
}

function renderMovies(movies) {
    const tbody = document.querySelector('#movies-table tbody');
    tbody.innerHTML = '';
    document.querySelector('#movies .loading').style.display = 'none';

    movies.forEach((movie, index) => {
        const tr = document.createElement('tr');
        tr.dataset.movieTitle = movie.title;
        tr.dataset.director = movie.director;

        const pickersListHtml = movie.pickers.map(p => {
            return `<a href="#" class="item-link picker-link" data-picker="${escapeHtml(p)}">${escapeHtml(p)}</a>`;
        }).join(', ');

        const pickersHtml = createToggleHtml(movie.count, pickersListHtml, 'Pickers');

        tr.innerHTML = `
            <td>${index + 1}</td>
            <td style="font-weight: bold;">${escapeHtml(movie.title)}</td>
            <td>${escapeHtml(movie.director)}</td>
            <td>${movie.count}</td>
            <td>${pickersHtml}</td>
        `;
        tbody.appendChild(tr);
    });
}

function renderDirectors(directors) {
    const tbody = document.querySelector('#directors-table tbody');
    tbody.innerHTML = '';
    document.querySelector('#directors .loading').style.display = 'none';

    directors.forEach((dir, index) => {
        // Sort director's movies by count desc
        dir.movies.sort((a, b) => b.count - a.count);

        const moviesListHtml = dir.movies.map(m => {
            const dirAttr = ` data-director="${escapeHtml(dir.name)}"`;
            return `<a href="#" class="item-link movie-link" data-movie="${escapeHtml(m.title)}"${dirAttr}>${escapeHtml(m.title)}</a> <span class="pick-count">(${m.count})</span>`;
        }).join(', ');

        // Count of unique movies picked for this director
        const movieCount = dir.movies.length;
        const moviesHtml = createToggleHtml(movieCount, moviesListHtml, 'Movies');

        const tr = document.createElement('tr');
        tr.dataset.directorName = dir.name;
        tr.innerHTML = `
            <td>${index + 1}</td>
            <td style="font-weight: bold;">${escapeHtml(dir.name)}</td>
            <td>${dir.totalPicks}</td>
            <td>${moviesHtml}</td>
        `;
        tbody.appendChild(tr);
    });
}

function renderPickers() {
    const tbody = document.querySelector('#pickers-table tbody');
    tbody.innerHTML = '';
    const loadingEl = document.querySelector('#pickers .loading');
    if(loadingEl) loadingEl.style.display = 'none';

    // Get current mode
    const modeEl = document.querySelector('input[name="ranking-mode"]:checked');
    const mode = modeEl ? modeEl.value : 'canon';

    // Sort
    const sortedPickers = [...globalPickers];
    if (mode === 'canon') {
        sortedPickers.sort((a, b) => b.canonScore - a.canonScore);
    } else {
        sortedPickers.sort((a, b) => b.originalScore - a.originalScore);
    }

    sortedPickers.forEach((picker, index) => {
        // Sort picks by count descending for display
        picker.picks.sort((a, b) => b.count - a.count);

        const picksListHtml = picker.picks.map(p => {
            const dirAttr = p.director ? ` data-director="${escapeHtml(p.director)}"` : '';
            return `<a href="#" class="item-link movie-link" data-movie="${escapeHtml(p.title)}"${dirAttr}>${escapeHtml(p.title)}</a> <span class="pick-count">(${p.count})</span>`;
        }).join(', ');

        const count = picker.picks.length;
        const picksHtml = createToggleHtml(count, picksListHtml, 'Picks');

        const score = mode === 'canon' ? picker.canonScore.toFixed(2) : picker.originalScore.toFixed(2);

        const tr = document.createElement('tr');
        tr.dataset.pickerName = picker.name;
        tr.innerHTML = `
            <td>${index + 1}</td>
            <td style="font-weight: bold;">${escapeHtml(picker.name)}</td>
            <td>${score}</td>
            <td>${picksHtml}</td>
        `;
        tbody.appendChild(tr);
    });
}

function highlightRow(row) {
    document.querySelectorAll('.highlight-target').forEach(el => el.classList.remove('highlight-target'));
    void row.offsetWidth;
    row.classList.add('highlight-target');
    setTimeout(() => {
        row.classList.remove('highlight-target');
    }, 3000);
}

function navigateToPicker(pickerName) {
    switchTab('pickers');
    const targetRow = Array.from(document.querySelectorAll('#pickers-table tbody tr')).find(
        tr => tr.dataset.pickerName === pickerName
    );

    if (targetRow) {
        const toggleBtn = targetRow.querySelector('.picker-toggle');
        const list = targetRow.querySelector('.pickers-list');
        if (list && list.classList.contains('hidden')) {
            list.classList.remove('hidden');
            if (toggleBtn) {
                toggleBtn.textContent = `Hide ${toggleBtn.dataset.label}`;
            }
        }

        setTimeout(() => {
            targetRow.scrollIntoView({ behavior: 'smooth', block: 'center' });
            highlightRow(targetRow);
        }, 50);
    }
}

function navigateToMovie(movieTitle, director) {
    switchTab('movies');
    const rows = Array.from(document.querySelectorAll('#movies-table tbody tr'));
    let targetRow = null;
    if (director) {
        targetRow = rows.find(tr => tr.dataset.movieTitle === movieTitle && tr.dataset.director === director);
    }
    if (!targetRow) {
        targetRow = rows.find(tr => tr.dataset.movieTitle === movieTitle);
    }

    if (targetRow) {
        const toggleBtn = targetRow.querySelector('.picker-toggle');
        const list = targetRow.querySelector('.pickers-list');
        if (list && list.classList.contains('hidden')) {
            list.classList.remove('hidden');
            if (toggleBtn) {
                toggleBtn.textContent = `Hide ${toggleBtn.dataset.label}`;
            }
        }

        setTimeout(() => {
            targetRow.scrollIntoView({ behavior: 'smooth', block: 'center' });
            highlightRow(targetRow);
        }, 50);
    }
}

function escapeHtml(text) {
    if (!text) return '';
    return text
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}
