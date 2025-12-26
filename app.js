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

// Color scales
const smoothedColor = '#4a90d9';
const empiricalColor = '#e74c3c';

// Paper color mapping (built after data loads)
let paperColors = {};

// Global state
let data = null;
let papers = [];
let allYears = [];
let selectedPaperIndex = 0;
let useAccumulated = false;

// Build color mapping for papers based on publication year
function buildPaperColors() {
    // Get unique publication years (first citation year for each paper)
    const pubYears = [...new Set(papers.map(p => Math.min(...p.years)))].sort((a, b) => a - b);

    // Filter to years >= streamMinYear for color assignment
    const colorYears = pubYears.filter(y => y >= config.minYear);

    // Group papers by publication year
    const papersByYear = {};
    papers.forEach((paper, idx) => {
        const pubYear = Math.min(...paper.years);
        if (!papersByYear[pubYear]) {
            papersByYear[pubYear] = [];
        }
        papersByYear[pubYear].push(idx);
    });

    // Select color palette based on number of years
    // colors[n] has n+1 entries, so use colors[colorYears.length - 1]
    const paletteIndex = Math.min(colorYears.length - 1, colors.length - 1);
    const colorPalette = colors[Math.max(0, paletteIndex)];

    // Assign colors: each year gets a base color, papers within year get tints/shades
    colorYears.forEach((year, yearIdx) => {
        const baseColor = colorPalette[yearIdx];
        const papersInYear = papersByYear[year] || [];
        const count = papersInYear.length;

        papersInYear.forEach((paperIdx, i) => {
            if (count === 1) {
                // Single paper in year: use base color
                paperColors[paperIdx] = baseColor;
            } else {
                // Multiple papers: create tint/shade gradient
                // Range from -20 (darker) to +20 (lighter)
                const lightnessOffset = ((i / (count - 1)) - 0.5) * 40;
                paperColors[paperIdx] = adjustLightness(baseColor, lightnessOffset);
            }
        });
    });

    // Papers before streamMinYear get a gray color
    pubYears.filter(y => y < config.minYear).forEach(year => {
        (papersByYear[year] || []).forEach(paperIdx => {
            paperColors[paperIdx] = '#888888';
        });
    });
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
        papers = data.papers;

        // Set updated date in footer
        if (data.scraped_at) {
            const scrapedDate = new Date(data.scraped_at);
            const formatted = scrapedDate.toLocaleDateString('en-US', {
                year: 'numeric',
                month: 'long',
                day: 'numeric'
            });
            document.getElementById('updated-date').textContent = `Updated ${formatted}`;
        }

        // Sort papers by first publication year (oldest first for streamplot)
        papers.sort((a, b) => Math.min(...a.years) - Math.min(...b.years));

        // Compute global year range
        const yearSet = new Set();
        papers.forEach(p => p.years.forEach(y => yearSet.add(y)));
        allYears = Array.from(yearSet).sort((a, b) => a - b);

        // Build color mapping
        buildPaperColors();

        // Find most cited paper
        let maxCitations = -1;
        papers.forEach((paper, i) => {
            const total = paper.observed_citations.reduce((a, b) => a + b, 0);
            if (total > maxCitations) {
                maxCitations = total;
                selectedPaperIndex = i;
            }
        });

        // Populate dropdown
        populateDropdown();

        // Draw initial charts
        drawLinePlot(papers[selectedPaperIndex]);
        drawStreamPlot();
        drawHIndexPlot();

        // Handle window resize
        window.addEventListener('resize', debounce(() => {
            drawLinePlot(papers[selectedPaperIndex]);
            drawStreamPlot();
            drawHIndexPlot();
        }, 250));

        // Toggle event listener
        document.getElementById('accumulated-toggle').addEventListener('change', (e) => {
            useAccumulated = e.target.checked;
            drawLinePlot(papers[selectedPaperIndex]);
            drawStreamPlot();
        });

    } catch (error) {
        console.error('Error loading data:', error);
    }
});

function populateDropdown() {
    const select = document.getElementById('paper-select');

    papers.forEach((paper, i) => {
        const option = document.createElement('option');
        option.value = i;
        option.textContent = paper.title;
        select.appendChild(option);
    });

    // Set most cited paper as selected
    select.value = selectedPaperIndex;

    select.addEventListener('change', (e) => {
        selectedPaperIndex = parseInt(e.target.value);
        drawLinePlot(papers[selectedPaperIndex]);
    });
}

function drawLinePlot(paper) {
    const container = document.getElementById('line-plot');
    const width = container.clientWidth;
    const height = lineChartHeight;
    const innerWidth = width - margin.left - margin.right;
    const innerHeight = height - margin.top - margin.bottom;

    // Clear previous
    d3.select('#line-plot').selectAll('*').remove();

    const svg = d3.select('#line-plot')
        .append('svg')
        .attr('width', width)
        .attr('height', height);

    const g = svg.append('g')
        .attr('transform', `translate(${margin.left},${margin.top})`);

    // Prepare historical data
    let lineData = paper.years.map((year, i) => ({
        year,
        empirical: paper.empirical_rate[i],
        smoothed: paper.smoothed_rate[i],
        std: paper.smoothed_rate_std[i]
    }));

    // Prepare forecast data (if available)
    const hasForecast = paper.forecast_years && paper.forecast_years.length > 0;
    let forecastData = hasForecast ? paper.forecast_years.map((year, i) => ({
        year,
        mean: paper.forecast_rate_median[i],
        std: paper.forecast_rate_std[i],
        sampled: paper.forecast_sampled_rate ? paper.forecast_sampled_rate[i] : null
    })) : [];

    // Apply accumulated transformation if enabled
    if (useAccumulated) {
        // Cumulative sum for historical data
        let cumEmpirical = 0;
        let cumSmoothed = 0;
        lineData = lineData.map(d => {
            cumEmpirical += d.empirical;
            cumSmoothed += d.smoothed;
            return {
                year: d.year,
                empirical: cumEmpirical,
                smoothed: cumSmoothed,
                std: d.std  // Keep yearly std for display (accumulating variance is complex)
            };
        });

        // Continue cumulative sum for forecast
        if (hasForecast) {
            let cumForecast = cumSmoothed;
            let cumSampled = cumEmpirical;
            forecastData = forecastData.map(d => {
                cumForecast += d.mean;
                if (d.sampled !== null) {
                    cumSampled += d.sampled;
                }
                return {
                    year: d.year,
                    mean: cumForecast,
                    std: d.std,  // Keep yearly std
                    sampled: d.sampled !== null ? cumSampled : null
                };
            });
        }
    }

    // Last historical year for demarcation
    const lastHistoricalYear = paper.years[paper.years.length - 1];

    // Compute combined year range
    const allPlotYears = hasForecast
        ? [...paper.years, ...paper.forecast_years]
        : paper.years;

    // Scales - extend to include forecast years
    const xScale = d3.scaleLinear()
        .domain(d3.extent(allPlotYears))
        .range([0, innerWidth]);

    // Y max includes forecast uncertainty
    const historicalYMax = d3.max(lineData, d => Math.max(d.empirical, d.smoothed + d.std));
    const forecastYMax = hasForecast ? d3.max(forecastData, d => d.mean + d.std) : 0;
    const yMax = Math.max(historicalYMax, forecastYMax) * 1.1;
    const yScale = d3.scaleLinear()
        .domain([0, yMax])
        .range([innerHeight, 0]);

    // Axes
    const xAxis = d3.axisBottom(xScale)
        .tickFormat(d3.format('d'))
        .ticks(Math.min(lineData.length, 10));

    const yAxis = d3.axisLeft(yScale)
        .ticks(6);

    g.append('g')
        .attr('class', 'axis x-axis')
        .attr('transform', `translate(0,${innerHeight})`)
        .call(xAxis);

    g.append('g')
        .attr('class', 'axis y-axis')
        .call(yAxis);

    // Y-axis label
    g.append('text')
        .attr('class', 'axis-label')
        .attr('transform', 'rotate(-90)')
        .attr('x', -innerHeight / 2)
        .attr('y', -45)
        .attr('text-anchor', 'middle')
        .text(useAccumulated ? 'Accumulated citations' : 'Citations per year');

    // Uncertainty band
    const areaGenerator = d3.area()
        .x(d => xScale(d.year))
        .y0(d => yScale(Math.max(0, d.smoothed - d.std)))
        .y1(d => yScale(d.smoothed + d.std))
        .curve(d3.curveMonotoneX);

    g.append('path')
        .datum(lineData)
        .attr('class', 'uncertainty-area')
        .attr('d', areaGenerator);

    // Smoothed rate line
    const lineGenerator = d3.line()
        .x(d => xScale(d.year))
        .y(d => yScale(d.smoothed))
        .curve(d3.curveMonotoneX);

    g.append('path')
        .datum(lineData)
        .attr('class', 'smoothed-line')
        .attr('d', lineGenerator);

    // Empirical points
    const tooltip = d3.select('#tooltip');

    g.selectAll('.empirical-point')
        .data(lineData)
        .join('circle')
        .attr('class', 'empirical-point')
        .attr('cx', d => xScale(d.year))
        .attr('cy', d => yScale(d.empirical))
        .attr('r', 5)
        .on('mouseover', (event, d) => {
            tooltip
                .classed('visible', true)
                .html(`
                    <div class="title">${d.year}</div>
                    <div class="value">Empirical: ${d.empirical.toFixed(1)}</div>
                    <div class="value">Smoothed: ${d.smoothed.toFixed(1)} ± ${d.std.toFixed(1)}</div>
                `);
        })
        .on('mousemove', (event) => {
            tooltip
                .style('left', (event.pageX + 15) + 'px')
                .style('top', (event.pageY - 10) + 'px');
        })
        .on('mouseout', () => {
            tooltip.classed('visible', false);
        });

    // Forecast elements (if available)
    if (hasForecast && forecastData.length > 0) {
        // Create bridge point for smooth connection
        const lastHistorical = lineData[lineData.length - 1];
        const forecastWithBridge = [
            { year: lastHistorical.year, mean: lastHistorical.smoothed, std: lastHistorical.std },
            ...forecastData
        ];

        // Forecast uncertainty band
        const forecastAreaGenerator = d3.area()
            .x(d => xScale(d.year))
            .y0(d => yScale(Math.max(0, d.mean - d.std)))
            .y1(d => yScale(d.mean + d.std))
            .curve(d3.curveMonotoneX);

        g.append('path')
            .datum(forecastWithBridge)
            .attr('class', 'forecast-area')
            .attr('d', forecastAreaGenerator);

        // Forecast line (dashed)
        const forecastLineGenerator = d3.line()
            .x(d => xScale(d.year))
            .y(d => yScale(d.mean))
            .curve(d3.curveMonotoneX);

        g.append('path')
            .datum(forecastWithBridge)
            .attr('class', 'forecast-line')
            .attr('d', forecastLineGenerator);

        // Demarcation line between historical and forecast
        const demarcationX = xScale(lastHistoricalYear + 0.5);
        g.append('line')
            .attr('class', 'demarcation-line')
            .attr('x1', demarcationX)
            .attr('x2', demarcationX)
            .attr('y1', 0)
            .attr('y2', innerHeight);

        // Forecast sampled points (open red circles)
        const sampledData = forecastData.filter(d => d.sampled !== null);
        if (sampledData.length > 0) {
            g.selectAll('.forecast-sample-point')
                .data(sampledData)
                .join('circle')
                .attr('class', 'forecast-sample-point')
                .attr('cx', d => xScale(d.year))
                .attr('cy', d => yScale(d.sampled))
                .attr('r', 5)
                .on('mouseover', (event, d) => {
                    const label = useAccumulated ? 'Accumulated' : 'Sampled rate';
                    tooltip
                        .classed('visible', true)
                        .html(`
                            <div class="title">${d.year} (forecast sample)</div>
                            <div class="value">${label}: ${d.sampled.toFixed(1)}</div>
                        `);
                })
                .on('mousemove', (event) => {
                    tooltip
                        .style('left', (event.pageX + 15) + 'px')
                        .style('top', (event.pageY - 10) + 'px');
                })
                .on('mouseout', () => {
                    tooltip.classed('visible', false);
                });
        }
    }
}

function drawStreamPlot() {
    const container = document.getElementById('stream-plot');
    const width = container.clientWidth;
    const height = streamChartHeight;
    const innerWidth = width - margin.left - margin.right;
    const innerHeight = height - margin.top - margin.bottom;

    // Clear previous
    d3.select('#stream-plot').selectAll('*').remove();

    const svg = d3.select('#stream-plot')
        .append('svg')
        .attr('width', width)
        .attr('height', height);

    const g = svg.append('g')
        .attr('transform', `translate(${margin.left},${margin.top})`);

    // Filter years to start from config.minYear
    const streamYears = allYears.filter(y => y >= config.minYear);

    // Determine forecast years from first paper that has them
    const samplePaper = papers.find(p => p.forecast_years && p.forecast_years.length > 0);
    const forecastYears = samplePaper ? samplePaper.forecast_years : [];
    const lastHistoricalYear = streamYears.length > 0 ? streamYears[streamYears.length - 1] : null;

    // Combine historical and forecast years
    const allStreamYears = [...streamYears, ...forecastYears];

    // Build stacked data: for each year, get smoothed rate
    // Papers are already sorted by first publication year
    let stackData = allStreamYears.map(year => {
        const row = { year, isForecast: forecastYears.includes(year) };
        papers.forEach((paper, i) => {
            const yearIndex = paper.years.indexOf(year);
            if (yearIndex >= 0) {
                // Historical year
                row[`paper_${i}`] = paper.smoothed_rate[yearIndex];
            } else if (paper.forecast_years && paper.forecast_years.includes(year)) {
                // Forecast year
                const forecastIndex = paper.forecast_years.indexOf(year);
                row[`paper_${i}`] = paper.forecast_rate_median[forecastIndex];
            } else {
                // Year not in paper's range
                row[`paper_${i}`] = 0;
            }
        });
        return row;
    });

    // Apply accumulated transformation if enabled
    if (useAccumulated) {
        // Track cumulative values for each paper
        const cumulative = {};
        papers.forEach((_, i) => { cumulative[`paper_${i}`] = 0; });

        stackData = stackData.map(row => {
            const newRow = { year: row.year, isForecast: row.isForecast };
            papers.forEach((_, i) => {
                const key = `paper_${i}`;
                cumulative[key] += row[key];
                newRow[key] = cumulative[key];
            });
            return newRow;
        });
    }

    const keys = papers.map((_, i) => `paper_${i}`);

    // Stack generator - stackOffsetNone for bottom-up stacking
    // Papers are already sorted by first publication year (oldest first)
    const stack = d3.stack()
        .keys(keys)
        .offset(d3.stackOffsetNone)
        .order(d3.stackOrderNone);

    const series = stack(stackData);

    // Scales
    const xScale = d3.scaleLinear()
        .domain(d3.extent(allStreamYears))
        .range([0, innerWidth]);

    const yMin = d3.min(series, s => d3.min(s, d => d[0]));
    const yMax = d3.max(series, s => d3.max(s, d => d[1]));
    const yScale = d3.scaleLinear()
        .domain([yMin, yMax])
        .range([innerHeight, 0]);

    // Area generator
    const areaGenerator = d3.area()
        .x(d => xScale(d.data.year))
        .y0(d => yScale(d[0]))
        .y1(d => yScale(d[1]))
        .curve(d3.curveBasis);

    // Draw layers
    const tooltip = d3.select('#tooltip');
    const layers = g.selectAll('.stream-layer')
        .data(series)
        .join('path')
        .attr('class', 'stream-layer')
        .attr('d', areaGenerator)
        .attr('fill', (d, i) => paperColors[i] || '#888888')
        .on('mouseover', (event, d) => {
            const paperIndex = parseInt(d.key.split('_')[1]);
            const paper = papers[paperIndex];

            // Fade other layers
            layers.classed('faded', true);
            d3.select(event.currentTarget).classed('faded', false);

            tooltip
                .classed('visible', true)
                .html(`
                    <div class="title">${paper.title}</div>
                    <div class="value">First cited: ${Math.min(...paper.years)}</div>
                    <div class="value">Total citations: ${paper.observed_citations.reduce((a, b) => a + b, 0).toFixed(0)}</div>
                `);
        })
        .on('mousemove', (event) => {
            tooltip
                .style('left', (event.pageX + 15) + 'px')
                .style('top', (event.pageY - 10) + 'px');
        })
        .on('mouseout', () => {
            layers.classed('faded', false);
            tooltip.classed('visible', false);
        })
        .on('click', (event, d) => {
            const paperIndex = parseInt(d.key.split('_')[1]);
            document.getElementById('paper-select').value = paperIndex;
            selectedPaperIndex = paperIndex;
            drawLinePlot(papers[paperIndex]);

            // Scroll to line plot
            document.getElementById('line-plot-section').scrollIntoView({
                behavior: 'smooth'
            });
        });

    // X-axis
    const xAxis = d3.axisBottom(xScale)
        .tickFormat(d3.format('d'))
        .ticks(10);

    g.append('g')
        .attr('class', 'axis x-axis')
        .attr('transform', `translate(0,${innerHeight})`)
        .call(xAxis);

    // Y-axis
    const yAxis = d3.axisLeft(yScale)
        .ticks(6)
        .tickFormat(d => d3.format('.0f')(d));

    g.append('g')
        .attr('class', 'axis y-axis')
        .call(yAxis);

    // Y-axis label
    g.append('text')
        .attr('class', 'axis-label')
        .attr('transform', 'rotate(-90)')
        .attr('x', -innerHeight / 2)
        .attr('y', -45)
        .attr('text-anchor', 'middle')
        .text(useAccumulated ? 'Accumulated citations' : 'Citations per year');

    // Demarcation line between historical and forecast
    if (forecastYears.length > 0 && lastHistoricalYear) {
        const demarcationX = xScale(lastHistoricalYear + 0.5);

        g.append('line')
            .attr('class', 'demarcation-line')
            .attr('x1', demarcationX)
            .attr('x2', demarcationX)
            .attr('y1', 0)
            .attr('y2', innerHeight);
    }
}


function drawHIndexPlot() {
    const container = document.getElementById('hindex-plot');
    const width = container.clientWidth;
    const height = hIndexChartHeight;
    const innerWidth = width - margin.left - margin.right;
    const innerHeight = height - margin.top - margin.bottom;

    // Clear previous
    d3.select('#hindex-plot').selectAll('*').remove();

    const svg = d3.select('#hindex-plot')
        .append('svg')
        .attr('width', width)
        .attr('height', height);

    const g = svg.append('g')
        .attr('transform', `translate(${margin.left},${margin.top})`);

    // Build year range
    const samplePaper = papers.find(p => p.forecast_years && p.forecast_years.length > 0);
    const forecastYears = samplePaper ? samplePaper.forecast_years : [];

    // Filter years for plotting (but accumulate from all years)
    const filteredYears = allYears.filter(y => y >= config.minYear);
    const lastHistoricalYear = filteredYears.length > 0 ? filteredYears[filteredYears.length - 1] : null;
    const plotYears = [...filteredYears, ...forecastYears];

    // Track accumulated citations per paper
    const accumulated = {};
    papers.forEach((_, i) => { accumulated[i] = 0; });

    // Pre-accumulate citations from years before minYear
    allYears.filter(y => y < config.minYear).forEach(year => {
        papers.forEach((paper, i) => {
            const yearIdx = paper.years.indexOf(year);
            if (yearIdx >= 0) {
                accumulated[i] += paper.smoothed_rate[yearIdx];
            }
        });
    });

    // Compute h-index at each plotted year
    const hIndexData = plotYears.map(year => {
        // Update accumulated values for this year
        papers.forEach((paper, i) => {
            const yearIdx = paper.years.indexOf(year);
            if (yearIdx >= 0) {
                // Historical year
                accumulated[i] += paper.smoothed_rate[yearIdx];
            } else if (paper.forecast_years && paper.forecast_years.includes(year)) {
                // Forecast year
                const forecastIdx = paper.forecast_years.indexOf(year);
                accumulated[i] += paper.forecast_rate_median[forecastIdx];
            }
            // If year is before paper started, accumulated stays at previous value
        });

        // Compute h-index from accumulated values
        const citations = Object.values(accumulated).sort((a, b) => b - a);
        let h = 0;
        for (let i = 0; i < citations.length; i++) {
            if (citations[i] >= i + 1) {
                h = i + 1;
            } else {
                break;
            }
        }

        return {
            year,
            hIndex: h,
            isForecast: forecastYears.includes(year)
        };
    });

    // Split into historical and forecast data
    const historicalData = hIndexData.filter(d => !d.isForecast);
    const forecastData = hIndexData.filter(d => d.isForecast);

    // Scales
    const xScale = d3.scaleLinear()
        .domain(d3.extent(plotYears))
        .range([0, innerWidth]);

    const yMax = d3.max(hIndexData, d => d.hIndex) * 1.1;
    const yScale = d3.scaleLinear()
        .domain([0, Math.max(yMax, 1)])
        .range([innerHeight, 0]);

    // Axes
    const xAxis = d3.axisBottom(xScale)
        .tickFormat(d3.format('d'))
        .ticks(10);

    const yAxis = d3.axisLeft(yScale)
        .ticks(Math.min(6, d3.max(hIndexData, d => d.hIndex) || 6))
        .tickFormat(d3.format('d'));

    g.append('g')
        .attr('class', 'axis x-axis')
        .attr('transform', `translate(0,${innerHeight})`)
        .call(xAxis);

    g.append('g')
        .attr('class', 'axis y-axis')
        .call(yAxis);

    // Y-axis label
    g.append('text')
        .attr('class', 'axis-label')
        .attr('transform', 'rotate(-90)')
        .attr('x', -innerHeight / 2)
        .attr('y', -45)
        .attr('text-anchor', 'middle')
        .text('H-Index');

    // Line generator
    const lineGenerator = d3.line()
        .x(d => xScale(d.year))
        .y(d => yScale(d.hIndex))
        .curve(d3.curveMonotoneX);

    // Historical line
    if (historicalData.length > 0) {
        g.append('path')
            .datum(historicalData)
            .attr('class', 'smoothed-line')
            .attr('d', lineGenerator);
    }

    // Forecast line (with bridge point for continuity)
    if (forecastData.length > 0 && historicalData.length > 0) {
        const lastHistorical = historicalData[historicalData.length - 1];
        const forecastWithBridge = [lastHistorical, ...forecastData];

        g.append('path')
            .datum(forecastWithBridge)
            .attr('class', 'forecast-line')
            .attr('d', lineGenerator);

        // Demarcation line
        const demarcationX = xScale(lastHistoricalYear + 0.5);
        g.append('line')
            .attr('class', 'demarcation-line')
            .attr('x1', demarcationX)
            .attr('x2', demarcationX)
            .attr('y1', 0)
            .attr('y2', innerHeight);
    }

    // Tooltip for data points
    const tooltip = d3.select('#tooltip');

    // Add blue circles at each data point
    g.selectAll('.hindex-point')
        .data(hIndexData)
        .join('circle')
        .attr('class', 'hindex-point')
        .attr('cx', d => xScale(d.year))
        .attr('cy', d => yScale(d.hIndex))
        .attr('r', 5)
        .attr('fill', d => d.isForecast ? 'none' : '#4a90d9')
        .attr('stroke', '#4a90d9')
        .attr('stroke-width', 1.5)
        .attr('cursor', 'pointer')
        .on('mouseover', (event, d) => {
            const label = d.isForecast ? ' (forecast)' : '';
            tooltip
                .classed('visible', true)
                .html(`
                    <div class="title">${d.year}${label}</div>
                    <div class="value">H-Index: ${d.hIndex}</div>
                `);
        })
        .on('mousemove', (event) => {
            tooltip
                .style('left', (event.pageX + 15) + 'px')
                .style('top', (event.pageY - 10) + 'px');
        })
        .on('mouseout', () => {
            tooltip.classed('visible', false);
        });
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
