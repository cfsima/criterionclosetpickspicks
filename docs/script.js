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
    let sum1 = 0;
    let sum2 = 0;

    picks.forEach(pick => {
        const count = pick.count;
        // Bins
        if (count >= 15) sum1 += 10;
        else if (count >= 10) sum1 += 8;
        else if (count >= 7) sum1 += 6;
        else if (count >= 5) sum1 += 4;
        else if (count >= 3) sum1 += 2;

        // Smooth
        sum2 += 10 * (count / (count + 8));
    });

    const avg1 = picks.length ? sum1 / picks.length : 0;
    const avg2 = picks.length ? sum2 / picks.length : 0;
    return (avg1 + avg2) / 2;
}

function calculateOriginalityScore(picks) {
    const n = picks.length;
    if (!n) return 0;

    const countRare3 = picks.filter(pick => pick.count <= 3).length;
    const countRare4 = picks.filter(pick => pick.count <= 4).length;

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
