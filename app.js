// Citation Rates Visualization
// D3.js v7

const DATA_PATH = 'data/citation_rates.json';

// Configuration
const config = {
    name: 'Trevor Bedford',
    scholar: 'RIi-1pAAAAAJ',
    minYear: 2012  // Minimum year to show in plots
};

// Chart dimensions
const margin = { top: 20, right: 30, bottom: 40, left: 60 };
const lineChartHeight = 300;
const streamChartHeight = 400;
const hIndexChartHeight = 250;
const treemapHeight = 400;

// Nextstrain color ramp
// From https://github.com/nextstrain/auspice/blob/master/src/util/globals.js#L109
const colors = [
  ["#4C90C0"],
  ["#4C90C0", "#CBB742"],
  ["#4988C5", "#7EB876", "#CBB742"],
  ["#4580CA", "#6BB28D", "#AABD52", "#DFA43B"],
  ["#4377CD", "#61AB9D", "#94BD61", "#CDB642", "#E68133"],
  ["#416DCE", "#59A3AA", "#84BA6F", "#BBBC49", "#E29D39", "#E1502A"],
  ["#3F63CF", "#529AB6", "#75B681", "#A6BE55", "#D4B13F", "#E68133", "#DC2F24"],
  ["#3E58CF", "#4B8EC1", "#65AE96", "#8CBB69", "#B8BC4A", "#DCAB3C", "#E67932", "#DC2F24"],
  ["#3F4DCB", "#4681C9", "#5AA4A8", "#78B67E", "#9EBE5A", "#C5B945", "#E0A23A", "#E67231", "#DC2F24"],
  ["#4042C7", "#4274CE", "#5199B7", "#69B091", "#88BB6C", "#ADBD51", "#CEB541", "#E39B39", "#E56C2F", "#DC2F24"],
  ["#4137C2", "#4066CF", "#4B8DC2", "#5DA8A3", "#77B67F", "#96BD60", "#B8BC4B", "#D4B13F", "#E59638", "#E4672F", "#DC2F24"],
  ["#462EB9", "#3E58CF", "#4580CA", "#549DB2", "#69B091", "#83BA70", "#A2BE57", "#C1BA47", "#D9AD3D", "#E69136", "#E4632E", "#DC2F24"],
  ["#4B26B1", "#3F4ACA", "#4272CE", "#4D92BF", "#5DA8A3", "#74B583", "#8EBC66", "#ACBD51", "#C8B944", "#DDA93C", "#E68B35", "#E3602D", "#DC2F24"],
  ["#511EA8", "#403DC5", "#4063CF", "#4785C7", "#559EB1", "#67AF94", "#7EB877", "#98BD5E", "#B4BD4C", "#CDB642", "#DFA53B", "#E68735", "#E35D2D", "#DC2F24"],
  ["#511EA8", "#403AC4", "#3F5ED0", "#457FCB", "#5098B9", "#60AA9F", "#73B583", "#8BBB6A", "#A4BE56", "#BDBB48", "#D3B240", "#E19F3A", "#E68234", "#E25A2C", "#DC2F24"],
  ["#511EA8", "#4138C3", "#3E59CF", "#4379CD", "#4D92BE", "#5AA5A8", "#6BB18E", "#7FB975", "#96BD5F", "#AFBD4F", "#C5B945", "#D8AE3E", "#E39B39", "#E67D33", "#E2572B", "#DC2F24"],
  ["#511EA8", "#4236C1", "#3F55CE", "#4273CE", "#4A8CC2", "#569FAF", "#64AD98", "#76B680", "#8BBB6A", "#A1BE58", "#B7BC4B", "#CCB742", "#DCAB3C", "#E59638", "#E67932", "#E1552B", "#DC2F24"],
  ["#511EA8", "#4335BF", "#3F51CC", "#416ECE", "#4887C6", "#529BB6", "#5FA9A0", "#6EB389", "#81B973", "#95BD61", "#AABD52", "#BFBB48", "#D1B340", "#DEA63B", "#E69237", "#E67531", "#E1522A", "#DC2F24"],
  ["#511EA8", "#4333BE", "#3F4ECB", "#4169CF", "#4682C9", "#4F96BB", "#5AA5A8", "#68AF92", "#78B77D", "#8BBB6A", "#9EBE59", "#B3BD4D", "#C5B945", "#D5B03F", "#E0A23A", "#E68D36", "#E67231", "#E1502A", "#DC2F24"],
  ["#511EA8", "#4432BD", "#3F4BCA", "#4065CF", "#447ECC", "#4C91BF", "#56A0AE", "#63AC9A", "#71B486", "#81BA72", "#94BD62", "#A7BE54", "#BABC4A", "#CBB742", "#D9AE3E", "#E29E39", "#E68935", "#E56E30", "#E14F2A", "#DC2F24"],
  ["#511EA8", "#4531BC", "#3F48C9", "#3F61D0", "#4379CD", "#4A8CC2", "#539CB4", "#5EA9A2", "#6BB18E", "#7AB77B", "#8BBB6A", "#9CBE5B", "#AFBD4F", "#C0BA47", "#CFB541", "#DCAB3C", "#E39B39", "#E68534", "#E56B2F", "#E04D29", "#DC2F24"],
  ["#511EA8", "#4530BB", "#3F46C8", "#3F5ED0", "#4375CD", "#4988C5", "#5098B9", "#5AA5A8", "#66AE95", "#73B583", "#82BA71", "#93BC62", "#A4BE56", "#B5BD4C", "#C5B945", "#D3B240", "#DEA73B", "#E59738", "#E68234", "#E4682F", "#E04C29", "#DC2F24"],
  ["#511EA8", "#462FBA", "#3F44C8", "#3E5BD0", "#4270CE", "#4784C8", "#4E95BD", "#57A1AD", "#61AB9C", "#6DB38A", "#7BB879", "#8BBB6A", "#9BBE5C", "#ABBD51", "#BBBC49", "#CBB843", "#D6AF3E", "#DFA43B", "#E69537", "#E67F33", "#E4662E", "#E04A29", "#DC2F24"],
  ["#511EA8", "#462EB9", "#4042C7", "#3E58CF", "#416DCE", "#4580CA", "#4C90C0", "#549DB2", "#5DA8A3", "#69B091", "#75B681", "#83BA70", "#92BC63", "#A2BE57", "#B2BD4D", "#C1BA47", "#CEB541", "#D9AD3D", "#E1A03A", "#E69136", "#E67C32", "#E4632E", "#E04929", "#DC2F24"],
  ["#511EA8", "#462EB9", "#4040C6", "#3F55CE", "#4169CF", "#447DCC", "#4A8CC2", "#529AB7", "#5AA5A8", "#64AD98", "#70B487", "#7DB878", "#8BBB6A", "#99BD5D", "#A9BD53", "#B7BC4B", "#C5B945", "#D1B340", "#DCAB3C", "#E29D39", "#E68D36", "#E67932", "#E3612D", "#E04828", "#DC2F24"],
  ["#511EA8", "#472DB8", "#403EC6", "#3F53CD", "#4066CF", "#4379CD", "#4989C5", "#4F97BB", "#57A1AD", "#61AA9E", "#6BB18E", "#77B67F", "#84BA70", "#92BC64", "#A0BE58", "#AFBD4F", "#BCBB49", "#CAB843", "#D4B13F", "#DEA83C", "#E39B39", "#E68A35", "#E67732", "#E35F2D", "#DF4728", "#DC2F24"],
  ["#511EA8", "#472CB7", "#403DC5", "#3F50CC", "#4063CF", "#4375CD", "#4785C7", "#4D93BE", "#559EB1", "#5DA8A3", "#67AF94", "#72B485", "#7EB877", "#8BBB6A", "#98BD5E", "#A6BE55", "#B4BD4C", "#C1BA47", "#CDB642", "#D7AF3E", "#DFA53B", "#E49838", "#E68735", "#E67431", "#E35D2D", "#DF4628", "#DC2F24"],
  ["#511EA8", "#482CB7", "#403BC5", "#3F4ECB", "#3F61D0", "#4272CE", "#4682C9", "#4C90C0", "#529BB5", "#5AA5A8", "#63AC9A", "#6DB28B", "#78B77D", "#84BA6F", "#91BC64", "#9EBE59", "#ACBD51", "#B9BC4A", "#C5B945", "#D0B441", "#DAAD3D", "#E0A23A", "#E59637", "#E68434", "#E67231", "#E35C2C", "#DF4528", "#DC2F24"],
  ["#511EA8", "#482BB6", "#403AC4", "#3F4CCB", "#3F5ED0", "#426FCE", "#457FCB", "#4A8CC2", "#5098B9", "#58A2AC", "#60AA9F", "#69B091", "#73B583", "#7FB976", "#8BBB6A", "#97BD5F", "#A4BE56", "#B1BD4E", "#BDBB48", "#C9B843", "#D3B240", "#DCAB3C", "#E19F3A", "#E69337", "#E68234", "#E67030", "#E25A2C", "#DF4428", "#DC2F24"],
  ["#511EA8", "#482BB6", "#4039C3", "#3F4ACA", "#3E5CD0", "#416CCE", "#447CCD", "#4989C4", "#4E96BC", "#559FB0", "#5DA8A4", "#66AE96", "#6FB388", "#7AB77C", "#85BA6F", "#91BC64", "#9DBE5A", "#AABD53", "#B6BD4B", "#C2BA46", "#CDB642", "#D6B03F", "#DDA83C", "#E29D39", "#E69036", "#E67F33", "#E56D30", "#E2592C", "#DF4428", "#DC2F24"],
  ["#511EA8", "#482AB5", "#4138C3", "#3F48C9", "#3E59CF", "#4169CF", "#4379CD", "#4886C6", "#4D92BE", "#539CB4", "#5AA5A8", "#62AB9B", "#6BB18E", "#75B581", "#7FB975", "#8BBB6A", "#96BD5F", "#A2BE57", "#AFBD4F", "#BABC4A", "#C5B945", "#CFB541", "#D8AE3E", "#DFA63B", "#E39B39", "#E68D36", "#E67D33", "#E56B2F", "#E2572B", "#DF4328", "#DC2F24"],
  ["#511EA8", "#492AB5", "#4137C2", "#3F47C9", "#3E57CE", "#4067CF", "#4376CD", "#4783C8", "#4C8FC0", "#519AB7", "#58A2AC", "#5FA9A0", "#68AF93", "#70B486", "#7BB77A", "#85BA6F", "#90BC65", "#9CBE5B", "#A8BE54", "#B3BD4D", "#BEBB48", "#C9B843", "#D2B340", "#DAAD3D", "#E0A33B", "#E49838", "#E68B35", "#E67B32", "#E5692F", "#E2562B", "#DF4227", "#DC2F24"],
  ["#511EA8", "#492AB5", "#4236C1", "#3F45C8", "#3F55CE", "#4064CF", "#4273CE", "#4681CA", "#4A8CC2", "#4F97BA", "#569FAF", "#5CA7A4", "#64AD98", "#6DB28B", "#76B680", "#80B974", "#8BBB6A", "#96BD60", "#A1BE58", "#ACBD51", "#B7BC4B", "#C2BA46", "#CCB742", "#D4B13F", "#DCAB3C", "#E1A13A", "#E59638", "#E68835", "#E67932", "#E4672F", "#E1552B", "#DF4227", "#DC2F24"],
  ["#511EA8", "#4929B4", "#4235C0", "#3F44C8", "#3F53CD", "#3F62CF", "#4270CE", "#457ECB", "#4989C4", "#4E95BD", "#549DB3", "#5AA5A8", "#61AB9C", "#69B090", "#72B485", "#7BB879", "#85BA6E", "#90BC65", "#9BBE5C", "#A6BE55", "#B1BD4E", "#BBBC49", "#C5B945", "#CEB541", "#D6AF3E", "#DDA93C", "#E29F39", "#E69537", "#E68634", "#E67732", "#E4662E", "#E1532B", "#DF4127", "#DC2F24"],
  ["#511EA8", "#4929B4", "#4335BF", "#3F42C7", "#3F51CC", "#3F60D0", "#416ECE", "#447CCD", "#4887C6", "#4D92BF", "#529BB6", "#58A2AB", "#5FA9A0", "#66AE95", "#6EB389", "#77B67E", "#81B973", "#8BBB6A", "#95BD61", "#A0BE59", "#AABD52", "#B5BD4C", "#BFBB48", "#C9B843", "#D1B340", "#D8AE3E", "#DEA63B", "#E29C39", "#E69237", "#E68434", "#E67531", "#E4642E", "#E1522A", "#DF4127", "#DC2F24"],
  ["#511EA8", "#4928B4", "#4334BF", "#4041C7", "#3F50CC", "#3F5ED0", "#416CCE", "#4379CD", "#4784C7", "#4B8FC1", "#5098B9", "#56A0AF", "#5CA7A4", "#63AC99", "#6BB18E", "#73B583", "#7CB878", "#86BB6E", "#90BC65", "#9ABD5C", "#A4BE56", "#AFBD4F", "#B9BC4A", "#C2BA46", "#CCB742", "#D3B240", "#DAAC3D", "#DFA43B", "#E39B39", "#E68F36", "#E68234", "#E67431", "#E4632E", "#E1512A", "#DF4027", "#DC2F24"]
];

// Color utility functions
function hexToHSL(hex) {
    const r = parseInt(hex.slice(1, 3), 16) / 255;
    const g = parseInt(hex.slice(3, 5), 16) / 255;
    const b = parseInt(hex.slice(5, 7), 16) / 255;

    const max = Math.max(r, g, b);
    const min = Math.min(r, g, b);
    let h, s, l = (max + min) / 2;

    if (max === min) {
        h = s = 0;
    } else {
        const d = max - min;
        s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
        switch (max) {
            case r: h = ((g - b) / d + (g < b ? 6 : 0)) / 6; break;
            case g: h = ((b - r) / d + 2) / 6; break;
            case b: h = ((r - g) / d + 4) / 6; break;
        }
    }
    return { h: h * 360, s: s * 100, l: l * 100 };
}

function hslToHex(h, s, l) {
    s /= 100;
    l /= 100;
    const a = s * Math.min(l, 1 - l);
    const f = n => {
        const k = (n + h / 30) % 12;
        const color = l - a * Math.max(Math.min(k - 3, 9 - k, 1), -1);
        return Math.round(255 * color).toString(16).padStart(2, '0');
    };
    return `#${f(0)}${f(8)}${f(4)}`;
}

function adjustLightness(hex, amount) {
    const hsl = hexToHSL(hex);
    // Clamp lightness between 25% and 85%
    const newL = Math.max(25, Math.min(85, hsl.l + amount));
    return hslToHex(hsl.h, hsl.s, newL);
}

// Colors for line plots
const smoothedColor = '#4a90d9';
const observedColor = '#e74c3c';
const earlyCohortColor = '#888888';

// Paper color mapping (built after data loads)
let paperColors = {};
let cohortColors = [];  // [{label, color}] for the stream plot legend

// Global state
let data = null;
let papers = [];
let selectedPaperIndex = 0;
let useAccumulated = false;
let selectedTreemapYear = null;
let currentYear = null;  // Final, partially observed year of the data
let forecastYears = [];  // [currentYear (year-end projection), currentYear + 1, ...]
let scrapedDate = null;

// Formatting
const sum = arr => arr.reduce((a, b) => a + b, 0);
const formatInt = d3.format(',.0f');
const formatRate = v => (v >= 10 ? d3.format(',.0f')(v) : d3.format('.1f')(v));
const formatRange = (lo, hi, fmt = formatInt) => `${fmt(lo)}–${fmt(hi)}`;
const formatDate = (date, options) => date.toLocaleDateString('en-US', { timeZone: 'UTC', ...options });
const intervalLabel = () => `${Math.round((data.model.interval || 0.8) * 100)}%`;

// Prepare papers: drop uncited entries and derive display fields
function preparePapers(rawPapers) {
    return rawPapers
        .filter(p => p.observed_citations.some(c => c > 0))
        .map(p => {
            const firstCited = p.years[p.observed_citations.findIndex(c => c > 0)];
            let running = 0;
            return {
                ...p,
                startYear: p.pub_year ?? firstCited,
                total: p.total_citations ?? sum(p.observed_citations),
                cumulativeObserved: p.observed_citations.map(c => (running += c))
            };
        })
        .sort((a, b) => a.startYear - b.startYear || b.total - a.total);
}

// Smoothed yearly citation rate (posterior mean), continuing into forecast years
function yearlyValue(paper, year) {
    if (year <= currentYear) {
        const i = paper.years.indexOf(year);
        return i >= 0 ? paper.smoothed_rate_mean[i] : 0;
    }
    const h = forecastYears.indexOf(year);
    return h >= 0 ? paper.forecast.rate_mean[h] : 0;
}

// Expected cumulative citations through the end of a year
function cumulativeValue(paper, year) {
    if (year < paper.years[0]) return 0;
    if (year < currentYear) return paper.cumulativeObserved[paper.years.indexOf(year)];

    const last = paper.years.length - 1;
    let total = paper.cumulativeObserved[last]
        + (1 - paper.exposure_fraction[last]) * paper.smoothed_rate_mean[last];
    for (let h = 1; h < forecastYears.length && forecastYears[h] <= year; h++) {
        total += paper.forecast.rate_mean[h];
    }
    return total;
}

const valueAt = (paper, year) => (useAccumulated ? cumulativeValue(paper, year) : yearlyValue(paper, year));

// Build color mapping for papers based on publication year
function buildPaperColors() {
    const papersByYear = d3.group(papers.map((p, i) => ({ year: p.startYear, i })), d => d.year);
    const colorYears = [...papersByYear.keys()].filter(y => y >= config.minYear).sort((a, b) => a - b);

    // colors[n] has n+1 entries, so use colors[colorYears.length - 1]
    const paletteIndex = Math.min(colorYears.length - 1, colors.length - 1);
    const colorPalette = colors[Math.max(0, paletteIndex)];

    // Each year gets a base color, papers within year get tints/shades
    cohortColors = [];
    colorYears.forEach((year, yearIdx) => {
        const baseColor = colorPalette[Math.min(yearIdx, colorPalette.length - 1)];
        const papersInYear = papersByYear.get(year).map(d => d.i);
        const count = papersInYear.length;
        cohortColors.push({ label: String(year), color: baseColor });

        papersInYear.forEach((paperIdx, i) => {
            // Range from -20 (darker) to +20 (lighter)
            const lightnessOffset = count === 1 ? 0 : ((i / (count - 1)) - 0.5) * 40;
            paperColors[paperIdx] = adjustLightness(baseColor, lightnessOffset);
        });
    });

    // Papers before minYear get a gray color
    papers.forEach((p, i) => {
        if (p.startYear < config.minYear) paperColors[i] = earlyCohortColor;
    });
    if (papers.some(p => p.startYear < config.minYear)) {
        cohortColors.unshift({ label: `Before ${config.minYear}`, color: earlyCohortColor });
    }
}

// Initialize
document.addEventListener('DOMContentLoaded', async () => {
    // Set page title with Google Scholar link
    const scholarUrl = `https://scholar.google.com/citations?user=${config.scholar}`;
    document.getElementById('page-title').innerHTML =
        `${config.name} <span class="scholar-link">(<a href="${scholarUrl}" target="_blank" rel="noopener">Google Scholar</a>)</span>`;

    try {
        const response = await fetch(DATA_PATH);
        data = await response.json();

        currentYear = data.current_year;
        forecastYears = data.forecast.years;
        scrapedDate = new Date(data.scraped_at);
        papers = preparePapers(data.papers);

        document.getElementById('updated-date').textContent =
            `Updated ${formatDate(scrapedDate, { year: 'numeric', month: 'long', day: 'numeric' })}`;

        buildPaperColors();

        // Select most cited paper
        selectedPaperIndex = d3.maxIndex(papers, p => p.total);

        renderSubtitle();
        renderStats();
        populateDropdown();
        populateYearDropdown();
        renderStreamLegend();
        drawAll();

        // Handle window resize
        window.addEventListener('resize', debounce(drawAll, 250));

        // Toggle event listener
        document.getElementById('accumulated-toggle').addEventListener('change', (e) => {
            useAccumulated = e.target.checked;
            drawAll();
        });

    } catch (error) {
        console.error('Error loading data:', error);
    }
});

function drawAll() {
    drawHIndexPlot();
    drawStreamPlot();
    drawTreemap();
    drawLinePlot(papers[selectedPaperIndex]);
}

function selectPaper(paperIndex, scroll = true) {
    selectedPaperIndex = paperIndex;
    document.getElementById('paper-select').value = paperIndex;
    drawLinePlot(papers[paperIndex]);
    if (scroll) {
        document.getElementById('line-plot-section').scrollIntoView({ behavior: 'smooth' });
    }
}

function renderSubtitle() {
    document.getElementById('subtitle').textContent =
        'Yearly citation rates smoothed with a Poisson state-space model.';
}

function renderStats() {
    const s = data.summary;
    const f = data.forecast;
    const thisYear = s.citations[s.years.indexOf(currentYear)] ?? 0;
    const stats = [
        { label: 'Citations', value: formatInt(s.citations_to_date) },
        { label: 'h-index', value: s.h_index_to_date },
        { label: 'i10-index', value: s.i10_index_to_date },
        {
            label: `${currentYear} citations`,
            value: formatInt(thisYear),
            note: `projected ${formatInt(f.citations_q50[0])} ` +
                `(${intervalLabel()}: ${formatRange(f.citations_q10[0], f.citations_q90[0])})`
        }
    ];

    d3.select('#stats').selectAll('.stat')
        .data(stats)
        .join('div')
        .attr('class', 'stat')
        .html(d => `
            <div class="stat-value">${d.value}</div>
            <div class="stat-label">${d.label}</div>
            ${d.note ? `<div class="stat-note">${d.note}</div>` : ''}
        `);
}

function populateDropdown() {
    const select = document.getElementById('paper-select');

    // Option values are indices into papers; list most cited first
    d3.sort(papers.map((p, i) => i), i => -papers[i].total).forEach(i => {
        const paper = papers[i];
        const option = document.createElement('option');
        option.value = i;
        option.textContent = `${paper.title} (${paper.startYear} · ${formatInt(paper.total)})`;
        select.appendChild(option);
    });

    select.value = selectedPaperIndex;
    select.addEventListener('change', (e) => selectPaper(parseInt(e.target.value), false));
}

function populateYearDropdown() {
    const select = document.getElementById('year-select');
    const years = d3.range(config.minYear, currentYear + 1).reverse();

    years.forEach(year => {
        const option = document.createElement('option');
        option.value = year;
        option.textContent = year === currentYear ? `${year} (projected)` : year;
        select.appendChild(option);
    });

    selectedTreemapYear = currentYear;
    select.value = selectedTreemapYear;
    select.addEventListener('change', (e) => {
        selectedTreemapYear = parseInt(e.target.value);
        drawTreemap();
    });
}

function renderStreamLegend() {
    d3.select('#stream-legend').selectAll('.legend-item')
        .data(cohortColors)
        .join('span')
        .attr('class', 'legend-item')
        .html(d => `<span class="legend-swatch" style="background:${d.color}"></span>${d.label}`);
}

// Shared chart helpers

function createChart(containerId, height) {
    const container = document.getElementById(containerId);
    const width = container.clientWidth;
    d3.select(container).selectAll('*').remove();

    const svg = d3.select(container)
        .append('svg')
        .attr('width', width)
        .attr('height', height);

    const g = svg.append('g')
        .attr('transform', `translate(${margin.left},${margin.top})`);

    return {
        g,
        width,
        innerWidth: width - margin.left - margin.right,
        innerHeight: height - margin.top - margin.bottom
    };
}

function drawAxes(g, xScale, yScale, innerHeight, yLabel, yFormat = d3.format(',.0f')) {
    const [x0, x1] = xScale.domain();
    const [r0, r1] = xScale.range();
    const maxTicks = Math.max(2, Math.floor((r1 - r0) / 55));  // keep year labels from colliding
    const xTicks = xScale.ticks(Math.min(10, maxTicks, Math.max(1, x1 - x0))).filter(Number.isInteger);

    g.append('g')
        .attr('class', 'axis x-axis')
        .attr('transform', `translate(0,${innerHeight})`)
        .call(d3.axisBottom(xScale).tickValues(xTicks).tickFormat(d3.format('d')));

    g.append('g')
        .attr('class', 'axis y-axis')
        .call(d3.axisLeft(yScale).ticks(6).tickFormat(yFormat));

    g.append('text')
        .attr('class', 'axis-label')
        .attr('transform', 'rotate(-90)')
        .attr('x', -innerHeight / 2)
        .attr('y', -45)
        .attr('text-anchor', 'middle')
        .text(yLabel);
}

// Shade the projected region (partial current year and forecasts)
function drawProjectedRegion(g, xScale, innerHeight) {
    const [, x1] = xScale.range();
    const start = Math.max(0, xScale(currentYear - 0.5));
    if (start >= x1) return;

    g.append('rect')
        .attr('class', 'projected-region')
        .attr('x', start)
        .attr('y', 0)
        .attr('width', x1 - start)
        .attr('height', innerHeight);

    g.append('text')
        .attr('class', 'projected-label')
        .attr('x', start + 4)
        .attr('y', 12)
        .text('projected');
}

// Draw a line solid left of the projected region and dashed within it
let clipCounter = 0;
function drawSplitLine(g, datum, line, xScale, innerHeight) {
    const [x0, x1] = xScale.range();
    const split = Math.max(x0, Math.min(x1, xScale(currentYear - 0.5)));
    const pad = 10;  // keep stroke ends at the plot edges
    [
        { cls: 'smoothed-line', x: x0 - pad, width: split - x0 + pad },
        { cls: 'forecast-line', x: split, width: x1 - split + pad }
    ].forEach(({ cls, x, width }) => {
        const id = `line-clip-${++clipCounter}`;
        g.append('clipPath')
            .attr('id', id)
            .append('rect')
            .attr('x', x)
            .attr('y', -pad)
            .attr('width', Math.max(0, width))
            .attr('height', innerHeight + 2 * pad);
        g.append('path')
            .datum(datum)
            .attr('class', cls)
            .attr('clip-path', `url(#${id})`)
            .attr('d', line);
    });
}

function attachTooltip(selection, html) {
    const tooltip = d3.select('#tooltip');
    selection
        .on('mouseover', (event, d) => {
            tooltip.classed('visible', true).html(html(d, event));
            positionTooltip(event);
        })
        .on('mousemove', positionTooltip)
        .on('mouseout', () => tooltip.classed('visible', false));
}

function positionTooltip(event) {
    d3.select('#tooltip')
        .style('left', (event.pageX + 15) + 'px')
        .style('top', (event.pageY - 10) + 'px');
}

function drawHIndexPlot() {
    const { g, innerWidth, innerHeight } = createChart('hindex-plot', hIndexChartHeight);
    const s = data.summary;
    const f = data.forecast;

    // Observed history uses dated citations through each full year
    const history = s.years
        .map((year, i) => ({ year, value: s.h_index[i] }))
        .filter(d => d.year >= config.minYear && d.year < currentYear);
    const projections = f.years.map((year, h) => ({
        year,
        value: f.h_index_q50[h],
        lower: f.h_index_q10[h],
        upper: f.h_index_q90[h]
    }));

    const xScale = d3.scaleLinear()
        .domain([config.minYear, d3.max(f.years)])
        .range([0, innerWidth]);

    const yScale = d3.scaleLinear()
        .domain([0, d3.max(projections, d => d.upper) * 1.05])
        .range([innerHeight, 0]);

    drawProjectedRegion(g, xScale, innerHeight);
    drawAxes(g, xScale, yScale, innerHeight, 'h-index', d3.format('d'));

    const line = d3.line()
        .x(d => xScale(d.year))
        .y(d => yScale(d.value));

    // Projection band, bridged from the last full year
    const bridge = history.length > 0
        ? [{ ...history[history.length - 1], lower: history[history.length - 1].value, upper: history[history.length - 1].value }]
        : [];

    g.append('path')
        .datum([...bridge, ...projections])
        .attr('class', 'forecast-area')
        .attr('d', d3.area()
            .x(d => xScale(d.year))
            .y0(d => yScale(d.lower))
            .y1(d => yScale(d.upper)));

    drawSplitLine(g, [...history, ...projections], line, xScale, innerHeight);

    const interval = intervalLabel();
    attachTooltip(
        g.selectAll('.hindex-point')
            .data(history)
            .join('circle')
            .attr('class', 'hindex-point')
            .attr('cx', d => xScale(d.year))
            .attr('cy', d => yScale(d.value))
            .attr('r', 4.5),
        d => `<div class="title">${d.year}</div><div class="value">h-index: ${d.value}</div>`
    );

    // Projections are open circles, including the partial current year
    attachTooltip(
        g.selectAll('.projection-point')
            .data(projections)
            .join('circle')
            .attr('class', 'projection-point')
            .attr('cx', d => xScale(d.year))
            .attr('cy', d => yScale(d.value))
            .attr('r', 4.5),
        d => d.year === currentYear
            ? `
                <div class="title">${d.year} year-end projection</div>
                <div class="value">h-index: ${d.value} (${interval}: ${formatRange(d.lower, d.upper)})</div>
                <div class="value">To date: ${s.h_index_to_date}</div>
            `
            : `
                <div class="title">${d.year} forecast</div>
                <div class="value">h-index: ${d.value} (${interval}: ${formatRange(d.lower, d.upper)})</div>
            `
    );
}

function drawStreamPlot() {
    const { g, innerWidth, innerHeight } = createChart('stream-plot', streamChartHeight);

    const streamYears = d3.range(config.minYear, d3.max(forecastYears) + 1);
    const keys = papers.map((_, i) => i);

    // Papers are sorted by publication year, so stacking puts oldest at the bottom
    const stackData = streamYears.map(year => {
        const row = { year };
        papers.forEach((paper, i) => { row[i] = valueAt(paper, year); });
        return row;
    });
    const series = d3.stack().keys(keys)(stackData);

    const xScale = d3.scaleLinear()
        .domain(d3.extent(streamYears))
        .range([0, innerWidth]);

    const yScale = d3.scaleLinear()
        .domain([0, d3.max(series, s => d3.max(s, d => d[1]))])
        .range([innerHeight, 0]);

    drawProjectedRegion(g, xScale, innerHeight);

    const areaGenerator = d3.area()
        .x(d => xScale(d.data.year))
        .y0(d => yScale(d[0]))
        .y1(d => yScale(d[1]))
        .curve(d3.curveMonotoneX);

    const tooltip = d3.select('#tooltip');
    const hoveredYear = event => {
        const year = Math.round(xScale.invert(d3.pointer(event, g.node())[0]));
        return Math.max(streamYears[0], Math.min(streamYears[streamYears.length - 1], year));
    };
    const tooltipHtml = (paper, year) => {
        const value = valueAt(paper, year);
        const label = useAccumulated ? 'cumulative citations' : 'citations/yr';
        const projected = year >= currentYear ? ' (projected)' : '';
        return `
            <div class="title">${paper.title}</div>
            <div class="value">Published: ${paper.startYear} · Total citations: ${formatInt(paper.total)}</div>
            <div class="value">${year}${projected}: ${formatRate(value)} ${label}</div>
        `;
    };

    const layers = g.selectAll('.stream-layer')
        .data(series)
        .join('path')
        .attr('class', 'stream-layer')
        .attr('d', areaGenerator)
        .attr('fill', d => paperColors[d.key] || earlyCohortColor)
        .on('mouseover', (event, d) => {
            layers.classed('faded', true);
            d3.select(event.currentTarget).classed('faded', false);
            tooltip.classed('visible', true).html(tooltipHtml(papers[d.key], hoveredYear(event)));
            positionTooltip(event);
        })
        .on('mousemove', (event, d) => {
            tooltip.html(tooltipHtml(papers[d.key], hoveredYear(event)));
            positionTooltip(event);
        })
        .on('mouseout', () => {
            layers.classed('faded', false);
            tooltip.classed('visible', false);
        })
        .on('click', (event, d) => selectPaper(d.key));

    drawAxes(g, xScale, yScale, innerHeight,
        useAccumulated ? 'Cumulative citations' : 'Citations per year');
}

function drawTreemap() {
    const container = document.getElementById('treemap-plot');
    const width = container.clientWidth;
    const height = treemapHeight;

    d3.select(container).selectAll('*').remove();
    if (!selectedTreemapYear) return;

    const svg = d3.select(container)
        .append('svg')
        .attr('width', width)
        .attr('height', height);

    const treemapData = papers
        .map((paper, i) => ({ name: paper.title, value: valueAt(paper, selectedTreemapYear), paperIndex: i }))
        .filter(d => d.value > 0)
        .sort((a, b) => b.value - a.value);

    if (treemapData.length === 0) {
        svg.append('text')
            .attr('x', width / 2)
            .attr('y', height / 2)
            .attr('text-anchor', 'middle')
            .attr('fill', '#888')
            .text('No citation data for this year');
        return;
    }

    const root = d3.hierarchy({ children: treemapData }).sum(d => d.value);
    d3.treemap().size([width, height]).padding(2).round(true)(root);

    const cells = svg.selectAll('g')
        .data(root.leaves())
        .join('g')
        .attr('transform', d => `translate(${d.x0},${d.y0})`);

    const projected = selectedTreemapYear >= currentYear ? ' (projected)' : '';
    const modeLabel = useAccumulated ? 'Cumulative citations' : 'Citations per year';

    attachTooltip(
        cells.append('rect')
            .attr('class', 'treemap-cell')
            .attr('width', d => d.x1 - d.x0)
            .attr('height', d => d.y1 - d.y0)
            .attr('fill', d => paperColors[d.data.paperIndex])
            .attr('cursor', 'pointer')
            .on('click', (event, d) => selectPaper(d.data.paperIndex)),
        d => `
            <div class="title">${d.data.name}</div>
            <div class="value">${modeLabel}${projected}: ${formatRate(d.data.value)}</div>
        `
    );

    // Labels for cells large enough
    const labels = cells.append('text')
        .attr('class', 'treemap-label')
        .attr('x', 4)
        .attr('y', 16);

    labels.append('tspan')
        .text(d => {
            const cellWidth = d.x1 - d.x0;
            const cellHeight = d.y1 - d.y0;
            if (cellWidth < 60 || cellHeight < 25) return '';
            const maxChars = Math.floor(cellWidth / 7);
            const title = d.data.name;
            return title.length > maxChars ? title.slice(0, maxChars - 1) + '…' : title;
        });

    labels.append('tspan')
        .attr('class', 'treemap-value')
        .attr('x', 4)
        .attr('dy', 15)
        .text(d => (d.x1 - d.x0 >= 60 && d.y1 - d.y0 >= 42 ? formatRate(d.data.value) : ''));
}

function drawLinePlot(paper) {
    const { g, innerWidth, innerHeight } = createChart('line-plot', lineChartHeight);
    const f = paper.forecast;
    const interval = intervalLabel();
    const isPartial = d => d.exposure < 1;

    const observed = paper.years.map((year, i) => ({
        year,
        count: paper.observed_citations[i],
        exposure: paper.exposure_fraction[i],
        rate: paper.empirical_rate[i],
        cumulative: paper.cumulativeObserved[i],
        median: paper.smoothed_rate[i],
        lower: paper.smoothed_rate_lower[i],
        upper: paper.smoothed_rate_upper[i]
    }));
    const projections = forecastYears.map((year, h) => ({
        year,
        median: useAccumulated ? f.cumulative_q50[h] : f.rate_q50[h],
        lower: useAccumulated ? f.cumulative_q10[h] : f.rate_q10[h],
        upper: useAccumulated ? f.cumulative_q90[h] : f.rate_q90[h]
    }));

    let solid, band, fan;
    if (useAccumulated) {
        // Observed cumulative counts are exact for full years
        solid = observed.filter(d => !isPartial(d)).map(d => ({ year: d.year, median: d.cumulative }));
        band = [];
        const last = solid[solid.length - 1];
        fan = last ? [{ ...last, lower: last.median, upper: last.median }, ...projections] : projections;
    } else {
        solid = observed;
        band = observed;
        fan = projections;
    }

    const yValue = d => (useAccumulated ? d.cumulative : d.rate);
    const xScale = d3.scaleLinear()
        .domain([paper.years[0], d3.max(forecastYears)])
        .range([0, innerWidth]);

    const yMax = d3.max([...observed.map(yValue), ...band.map(d => d.upper), ...fan.map(d => d.upper)]);
    const yScale = d3.scaleLinear()
        .domain([0, Math.max(1, yMax * 1.05)])
        .range([innerHeight, 0]);

    drawProjectedRegion(g, xScale, innerHeight);
    drawAxes(g, xScale, yScale, innerHeight,
        useAccumulated ? 'Cumulative citations' : 'Citations per year');

    const area = d3.area()
        .x(d => xScale(d.year))
        .y0(d => yScale(d.lower))
        .y1(d => yScale(d.upper))
        .curve(d3.curveMonotoneX);
    const line = d3.line()
        .x(d => xScale(d.year))
        .y(d => yScale(d.median))
        .curve(d3.curveMonotoneX);

    g.append('path').datum(band).attr('class', 'uncertainty-area').attr('d', area);
    g.append('path').datum(fan).attr('class', 'forecast-area').attr('d', area);
    // The current year's forecast median equals its smoothed median, so join them
    const medians = useAccumulated
        ? [...solid, ...projections]
        : [...observed, ...projections.filter(d => d.year > currentYear)];
    drawSplitLine(g, medians, line, xScale, innerHeight);

    // Forecast medians (hover targets)
    attachTooltip(
        g.selectAll('.projection-point')
            .data(projections.filter(d => d.year > currentYear || useAccumulated))
            .join('circle')
            .attr('class', 'projection-point')
            .attr('cx', d => xScale(d.year))
            .attr('cy', d => yScale(d.median))
            .attr('r', 3.5),
        d => {
            const what = d.year === currentYear ? 'year-end projection' : 'forecast';
            const unit = useAccumulated ? 'cumulative citations' : 'citations/yr';
            return `
                <div class="title">${d.year} ${what}</div>
                <div class="value">${formatRate(d.median)} ${unit} (${interval}: ${formatRange(d.lower, d.upper, formatRate)})</div>
            `;
        }
    );

    // Observed points; the partial current year is annualized in yearly mode
    attachTooltip(
        g.selectAll('.observed-point')
            .data(observed)
            .join('circle')
            .attr('class', d => (isPartial(d) ? 'partial-point' : 'observed-point'))
            .attr('cx', d => xScale(d.year))
            .attr('cy', d => yScale(yValue(d)))
            .attr('r', 5),
        d => {
            const through = formatDate(scrapedDate, { month: 'short', day: 'numeric' });
            const lines = [];
            if (isPartial(d)) {
                lines.push(`${formatInt(d.count)} citations through ${through} (${Math.round(d.exposure * 100)}% of year)`);
                if (!useAccumulated) lines.push(`Annualized: ${formatRate(d.rate)}/yr`);
            } else {
                lines.push(`Citations: ${formatInt(d.count)}`);
            }
            if (useAccumulated) {
                lines.push(`Cumulative${isPartial(d) ? ' to date' : ''}: ${formatInt(d.cumulative)}`);
            } else {
                lines.push(`Smoothed rate: ${formatRate(d.median)}/yr (${interval}: ${formatRange(d.lower, d.upper, formatRate)})`);
            }
            return `<div class="title">${d.year}</div>` + lines.map(l => `<div class="value">${l}</div>`).join('');
        }
    );

    renderLineLegend(observed.some(isPartial));
}

function renderLineLegend(hasPartial) {
    const interval = intervalLabel();
    const items = useAccumulated
        ? [
            { cls: 'observed', label: 'Observed cumulative' },
            hasPartial && { cls: 'partial', label: `${currentYear} to date` },
            { cls: 'forecast', label: 'Projection' },
            { cls: 'uncertainty', label: `${interval} interval` }
        ]
        : [
            { cls: 'observed', label: 'Observed' },
            hasPartial && { cls: 'partial', label: `${currentYear} annualized` },
            { cls: 'smoothed', label: 'Smoothed rate' },
            { cls: 'uncertainty', label: `${interval} interval` },
            { cls: 'forecast', label: 'Forecast' }
        ];

    d3.select('#line-legend').selectAll('.legend-item')
        .data(items.filter(Boolean))
        .join('span')
        .attr('class', 'legend-item')
        .html(d => `<span class="legend-color ${d.cls}"></span> ${d.label}`);
}

// Utility: debounce function
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}
