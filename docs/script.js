let globalPickers = [];

document.addEventListener('DOMContentLoaded', () => {
    const tabs = document.querySelectorAll('.tab-btn');
    const contents = document.querySelectorAll('.tab-content');

    // Tab Switching
    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            tabs.forEach(t => t.classList.remove('active'));
            contents.forEach(c => c.classList.remove('active'));

            tab.classList.add('active');
            document.getElementById(tab.dataset.tab).classList.add('active');
        });
    });

    // Toggle Expandable Lists (Pickers / Movies)
    document.addEventListener('click', (e) => {
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

        // Movies List
        movies.push({
            title,
            director,
            count,
            pickedBy
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
        directorsMap[director].movies.push({ title, count });

        // Pickers Aggregation
        // Split by comma, trimming whitespace
        const currentPickers = pickedBy.split(',').map(s => s.trim()).filter(s => s.length > 0);
        currentPickers.forEach(p => {
            if (!pickersMap[p]) {
                pickersMap[p] = {
                    name: p,
                    picks: []
                };
            }
            pickersMap[p].picks.push({ title, count });
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
    let score = 0;
    picks.forEach(pick => {
        const count = pick.count;
        if (count >= 15) score += 15;
        else if (count >= 10 && count <= 14) score += 10;
        else if (count >= 7 && count <= 9) score += 5;
        else if (count <= 3) score -= 5;
    });
    return picks.length > 0 ? (score / picks.length) : 0;
}

function calculateOriginalityScore(picks) {
    const w_unique = 10;
    const w_rare = 5;
    let unique_score = 0;
    let rare_score = 0;
    let total_pick_count_sum = 0;

    picks.forEach(pick => {
        const count = pick.count;
        total_pick_count_sum += count;

        if (count === 1) unique_score += w_unique;
        else if (count >= 2 && count <= 3) rare_score += w_rare;
    });

    const avg_popularity_penalty = picks.length > 0 ? (total_pick_count_sum / picks.length) : 0;
    return (unique_score + rare_score) - avg_popularity_penalty;
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

        const pickersHtml = createToggleHtml(movie.count, escapeHtml(movie.pickedBy), 'Pickers');

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

        const movieStr = dir.movies.map(m => `${m.title} (${m.count})`).join(', ');

        // Count of unique movies picked for this director
        const movieCount = dir.movies.length;
        const moviesHtml = createToggleHtml(movieCount, escapeHtml(movieStr), 'Movies');

        const tr = document.createElement('tr');
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

        const picksStr = picker.picks.map(p => `${p.title} (${p.count})`).join(', ');
        const count = picker.picks.length;
        const picksHtml = createToggleHtml(count, escapeHtml(picksStr), 'Picks');

        const score = mode === 'canon' ? picker.canonScore.toFixed(2) : picker.originalScore.toFixed(2);

        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>${index + 1}</td>
            <td style="font-weight: bold;">${escapeHtml(picker.name)}</td>
            <td>${score}</td>
            <td>${picksHtml}</td>
        `;
        tbody.appendChild(tr);
    });
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
