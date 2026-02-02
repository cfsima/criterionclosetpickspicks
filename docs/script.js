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

    rows.forEach(row => {
        if (row.length < 4) return;

        const title = row[0];
        const director = row[1];
        const count = parseInt(row[2], 10);
        const pickedBy = row[3]; // Not strictly needed for stats but displayed in movies tab

        // Movies List
        movies.push({
            title,
            director,
            count,
            pickedBy
        });

        // Directors Aggregation
        // Sometimes director field has " and " or multiple directors.
        // For simplicity, we stick to the main director string as the key,
        // or we could split. The Python script normalizes some but leaves pairs like "Powell and Pressburger".
        // Let's treat the string as the unique key for now to match the CSV logic.

        if (!directorsMap[director]) {
            directorsMap[director] = {
                name: director,
                totalPicks: 0,
                movies: []
            };
        }

        directorsMap[director].totalPicks += count;
        directorsMap[director].movies.push({ title, count });
    });

    // Sort Movies
    movies.sort((a, b) => b.count - a.count);

    // Sort Directors
    const directors = Object.values(directorsMap);
    directors.sort((a, b) => b.totalPicks - a.totalPicks);

    renderMovies(movies);
    renderDirectors(directors);
}

function renderMovies(movies) {
    const tbody = document.querySelector('#movies-table tbody');
    tbody.innerHTML = '';
    document.querySelector('#movies .loading').style.display = 'none';

    movies.forEach((movie, index) => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>${index + 1}</td>
            <td style="font-weight: bold;">${escapeHtml(movie.title)}</td>
            <td>${escapeHtml(movie.director)}</td>
            <td>${movie.count}</td>
            <td style="font-size: 0.9em; color: #555;">${escapeHtml(movie.pickedBy)}</td>
        `;
        tbody.appendChild(tr);
    });
}

function renderDirectors(directors) {
    const tbody = document.querySelector('#directors-table tbody');
    tbody.innerHTML = '';
    document.querySelector('#directors .loading').style.display = 'none';

    directors.forEach((dir, index) => {
        // Format top movies string
        // Sort director's movies by count desc
        dir.movies.sort((a, b) => b.count - a.count);

        const movieStr = dir.movies.map(m => `${m.title} (${m.count})`).join(', ');

        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>${index + 1}</td>
            <td style="font-weight: bold;">${escapeHtml(dir.name)}</td>
            <td>${dir.totalPicks}</td>
            <td style="font-size: 0.9em; color: #555;">${escapeHtml(movieStr)}</td>
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
