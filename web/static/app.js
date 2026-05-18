const state = {
  indexData: null,
  pageSize: 10,
  page: 1,
  selectedTicker: null,
  tickerDetails: new Map(),
};

const tickerGrid = document.getElementById("tickerGrid");
const pagination = document.getElementById("pagination");
const metaLine = document.getElementById("metaLine");
const detailTitle = document.getElementById("detailTitle");
const detailMeta = document.getElementById("detailMeta");
const detailEmpty = document.getElementById("detailEmpty");
const detailContent = document.getElementById("detailContent");
const detailAvatar = document.getElementById("detailAvatar");
const consensusBadge = document.getElementById("consensusBadge");
const predictionDateText = document.getElementById("predictionDateText");
const comparisonText = document.getElementById("comparisonText");
const featureWindowMeta = document.getElementById("featureWindowMeta");
const horizonCards = document.getElementById("horizonCards");
const featureTableHead = document.querySelector("#featureTable thead");
const featureTableBody = document.querySelector("#featureTable tbody");
const newsMeta = document.getElementById("newsMeta");
const newsEmpty = document.getElementById("newsEmpty");
const newsContent = document.getElementById("newsContent");
const newsSentimentValue = document.getElementById("newsSentimentValue");
const newsImpactValue = document.getElementById("newsImpactValue");
const newsConfidenceValue = document.getElementById("newsConfidenceValue");
const newsScoreValue = document.getElementById("newsScoreValue");
const newsArticleCountValue = document.getElementById("newsArticleCountValue");
const newsSummaryText = document.getElementById("newsSummaryText");
const bullPointsList = document.getElementById("bullPointsList");
const bearPointsList = document.getElementById("bearPointsList");
const riskFlagsList = document.getElementById("riskFlagsList");

function getQueryState() {
  const params = new URLSearchParams(window.location.search);
  return {
    page: Number.parseInt(params.get("page") || "1", 10),
    ticker: params.get("ticker"),
  };
}

function updateQueryState() {
  const params = new URLSearchParams();
  params.set("page", String(state.page));
  if (state.selectedTicker) {
    params.set("ticker", state.selectedTicker);
  }
  const next = `${window.location.pathname}?${params.toString()}`;
  window.history.replaceState({}, "", next);
}

function formatScore(value) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "-";
  }
  return Number(value).toFixed(4);
}

function formatSignedScore(value) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "-";
  }
  const numeric = Number(value);
  return `${numeric >= 0 ? "+" : ""}${numeric.toFixed(2)}`;
}

function formatPercent(value) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "-";
  }
  return `${(Number(value) * 100).toFixed(1)}%`;
}

function formatPred(value) {
  return Number(value) === 1 ? "BUY" : "SELL";
}

function titleCase(value) {
  if (!value) {
    return "-";
  }
  return String(value)
    .replaceAll("_", " ")
    .toLowerCase()
    .replace(/(^|\s)\S/g, (match) => match.toUpperCase());
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function getBadgeClass(decision) {
  if (decision === "STRONG_BUY") {
    return "badge badge-strong";
  }
  if (decision === "BUY") {
    return "badge badge-buy";
  }
  if (decision === "HOLD") {
    return "badge badge-hold";
  }
  return "badge badge-sell";
}

function getNewsToneClass(sentiment) {
  if (sentiment === "positive") {
    return "news-pill news-positive";
  }
  if (sentiment === "negative") {
    return "news-pill news-negative";
  }
  if (sentiment === "neutral") {
    return "news-pill news-neutral";
  }
  return "news-pill news-none";
}

function renderGrid() {
  const tickers = state.indexData.tickers;
  const totalPages = Math.max(1, Math.ceil(tickers.length / state.pageSize));
  if (state.page > totalPages) {
    state.page = totalPages;
  }

  const start = (state.page - 1) * state.pageSize;
  const currentPageItems = tickers.slice(start, start + state.pageSize);

  tickerGrid.innerHTML = currentPageItems
    .map((item) => {
      const selectedClass = item.ticker === state.selectedTicker ? "ticker-card is-selected" : "ticker-card";
      const badgeClass = getBadgeClass(item.consensusDecision);
      const avatar = item.avatarPath ? `<img src="${item.avatarPath}" alt="${item.ticker} logo">` : `<div class="avatar-fallback">${item.ticker}</div>`;
      const newsSentiment = item.newsSentiment ? titleCase(item.newsSentiment) : "No Analysis";
      const newsClass = getNewsToneClass(item.newsSentiment);
      const newsScore = item.hasNewsAnalysis ? formatSignedScore(item.newsScore) : "-";
      return `
        <button class="${selectedClass}" data-ticker="${item.ticker}">
          <div class="ticker-card-top">
            ${avatar}
            <div>
              <div class="ticker-name">${escapeHtml(item.ticker)}</div>
              <div class="ticker-card-labels">
                <div class="${badgeClass}">${escapeHtml(item.consensusDecision)}</div>
                <div class="${newsClass}">News ${escapeHtml(newsSentiment)}</div>
              </div>
            </div>
          </div>
          <div class="ticker-card-metrics">
            <span>1D ${formatScore(item.ensemble1d)}</span>
            <span>5D ${formatScore(item.ensemble5d)}</span>
            <span>10D ${formatScore(item.ensemble10d)}</span>
          </div>
          <div class="ticker-card-caption">News score ${escapeHtml(newsScore)}</div>
        </button>
      `;
    })
    .join("");

  pagination.innerHTML = `
    <button class="page-button" ${state.page <= 1 ? "disabled" : ""} data-page-move="-1">Prev</button>
    <span class="page-indicator">Page ${state.page}/${totalPages}</span>
    <button class="page-button" ${state.page >= totalPages ? "disabled" : ""} data-page-move="1">Next</button>
  `;

  tickerGrid.querySelectorAll("[data-ticker]").forEach((button) => {
    button.addEventListener("click", () => {
      selectTicker(button.dataset.ticker);
    });
  });

  pagination.querySelectorAll("[data-page-move]").forEach((button) => {
    button.addEventListener("click", () => {
      const delta = Number.parseInt(button.dataset.pageMove, 10);
      state.page += delta;
      updateQueryState();
      renderGrid();
    });
  });
}

function renderMeta() {
  const firstPredictionDate = state.indexData.tickers[0]?.predictionDate || "-";
  const latestNewsAnalysisDate = state.indexData.latestNewsAnalysisDate || "n/a";
  metaLine.textContent = `${state.indexData.tickerCount} tickers | latest prediction date: ${firstPredictionDate} | news snapshot: ${latestNewsAnalysisDate}`;
}

async function loadTickerDetail(ticker) {
  if (state.tickerDetails.has(ticker)) {
    return state.tickerDetails.get(ticker);
  }

  const response = await fetch(`./data/tickers/${ticker}.json`);
  if (!response.ok) {
    throw new Error(`Cannot load ticker detail for ${ticker}`);
  }

  const data = await response.json();
  state.tickerDetails.set(ticker, data);
  return data;
}

function renderHorizonCards(prediction) {
  const horizons = [
    ["1d", "1 Day"],
    ["5d", "5 Day"],
    ["10d", "10 Day"],
  ];

  horizonCards.innerHTML = horizons
    .map(([key, label]) => {
      const item = prediction.horizons[key];
      return `
        <article class="summary-card">
          <h3>${label}</h3>
          <div class="metric-row"><span>RF</span><strong>${formatScore(item.rf)}</strong></div>
          <div class="metric-row"><span>XGBoost</span><strong>${formatScore(item.xgb)}</strong></div>
          <div class="metric-row"><span>LSTM</span><strong>${formatScore(item.lstm)}</strong></div>
          <div class="metric-row metric-row-highlight"><span>Ensemble</span><strong>${formatScore(item.ensemble)}</strong></div>
          <div class="metric-row"><span>Decision</span><strong>${formatPred(item.pred)}</strong></div>
        </article>
      `;
    })
    .join("");
}

function renderFeatureTable(detail) {
  const columns = ["date", ...detail.featureColumns];
  featureTableHead.innerHTML = `<tr>${columns.map((col) => `<th>${escapeHtml(col)}</th>`).join("")}</tr>`;
  featureTableBody.innerHTML = detail.featureRows
    .map((row) => {
      const cells = columns.map((col) => {
        const value = row[col];
        if (col === "date") {
          return `<td>${escapeHtml(value)}</td>`;
        }
        if (col === "ticker_id") {
          return `<td>${value ?? "-"}</td>`;
        }
        return `<td>${value === null || value === undefined ? "-" : Number(value).toFixed(4)}</td>`;
      });
      return `<tr>${cells.join("")}</tr>`;
    })
    .join("");
}

function renderList(target, items) {
  if (!items || items.length === 0) {
    target.innerHTML = '<li class="news-list-empty">None</li>';
    return;
  }
  target.innerHTML = items.map((item) => `<li>${escapeHtml(item)}</li>`).join("");
}

function renderNewsAnalysis(newsAnalysis) {
  if (!newsAnalysis) {
    newsMeta.textContent = "No Gemini analysis snapshot available for this ticker.";
    newsContent.classList.add("hidden");
    newsEmpty.classList.remove("hidden");
    return;
  }

  newsMeta.textContent = `Analysis date ${newsAnalysis.analysisDate || "-"} | model ${newsAnalysis.modelName || "-"}`;
  newsEmpty.classList.add("hidden");
  newsContent.classList.remove("hidden");

  newsSentimentValue.className = getNewsToneClass(newsAnalysis.sentiment);
  newsSentimentValue.textContent = titleCase(newsAnalysis.sentiment);
  newsImpactValue.textContent = titleCase(newsAnalysis.impactHorizon || "mixed");
  newsConfidenceValue.textContent = formatPercent(newsAnalysis.confidence);
  newsScoreValue.textContent = formatSignedScore(newsAnalysis.newsScore);
  newsArticleCountValue.textContent = newsAnalysis.articleCount ?? "-";
  newsSummaryText.textContent = newsAnalysis.summary || "No summary available.";

  renderList(bullPointsList, newsAnalysis.bullPoints);
  renderList(bearPointsList, newsAnalysis.bearPoints);
  renderList(riskFlagsList, newsAnalysis.riskFlags);
}

function renderDetail(detail) {
  detailEmpty.classList.add("hidden");
  detailContent.classList.remove("hidden");

  detailTitle.textContent = detail.ticker;
  detailMeta.textContent = `Latest feature window ending ${detail.featureEndDate || "-"}`;

  if (detail.avatarPath) {
    detailAvatar.src = detail.avatarPath;
    detailAvatar.alt = `${detail.ticker} logo`;
    detailAvatar.classList.remove("hidden");
  } else {
    detailAvatar.classList.add("hidden");
  }

  consensusBadge.className = getBadgeClass(detail.prediction.consensusDecision);
  consensusBadge.textContent = `${detail.prediction.consensusDecision} (${detail.prediction.consensusVotes}/3)`;
  predictionDateText.textContent = `Prediction date: ${detail.prediction.predictionDate}`;

  if (detail.comparison) {
    comparisonText.textContent = `Last 1D eval: pred=${formatPred(detail.comparison.pred1d)}, actual=${formatPred(detail.comparison.actual1d)}, correct=${detail.comparison.correct ? "yes" : "no"}`;
  } else {
    comparisonText.textContent = "No comparison snapshot for this ticker.";
  }

  featureWindowMeta.textContent = `${detail.featureRows.length} rows x ${detail.featureColumns.length} features`;
  renderHorizonCards(detail.prediction);
  renderNewsAnalysis(detail.newsAnalysis);
  renderFeatureTable(detail);
}

async function selectTicker(ticker) {
  state.selectedTicker = ticker;

  const tickerIndex = state.indexData.tickers.findIndex((item) => item.ticker === ticker);
  if (tickerIndex >= 0) {
    state.page = Math.floor(tickerIndex / state.pageSize) + 1;
  }

  updateQueryState();
  renderGrid();

  detailEmpty.textContent = `Loading ${ticker}...`;
  detailEmpty.classList.remove("hidden");
  detailContent.classList.add("hidden");

  try {
    const detail = await loadTickerDetail(ticker);
    renderDetail(detail);
  } catch (error) {
    detailEmpty.textContent = error.message;
  }
}

async function bootstrap() {
  const response = await fetch("./data/index.json");
  if (!response.ok) {
    throw new Error("Cannot load dashboard index data");
  }

  state.indexData = await response.json();
  state.pageSize = state.indexData.pageSize || 10;

  const queryState = getQueryState();
  if (queryState.page > 0) {
    state.page = queryState.page;
  }
  if (queryState.ticker) {
    state.selectedTicker = queryState.ticker.toUpperCase();
  }

  renderMeta();
  renderGrid();

  if (state.selectedTicker) {
    await selectTicker(state.selectedTicker);
  }
}

bootstrap().catch((error) => {
  metaLine.textContent = error.message;
  tickerGrid.innerHTML = `<div class="empty-state">${escapeHtml(error.message)}</div>`;
});
