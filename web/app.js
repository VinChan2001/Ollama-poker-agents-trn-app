const PLAYER_ORDER = ["Vin", "Sam", "Kai", "Pap", "Nik"];
const MODEL_BY_PLAYER = {
  Vin: "llama3.1:8b",
  Sam: "qwen2.5:7b",
  Kai: "mistral:7b",
  Pap: "gemma2:9b",
  Nik: "deepseek-r1:8b",
};
const PLAYER_META = {
  Vin: {
    title: "Table Bully",
    accent: "#ff4d6d",
    personality:
      "Fearless pressure player. Likes big bets, fast tempo, and controlled intimidation when the table looks weak.",
    tell: "Pulse spikes before raises.",
  },
  Sam: {
    title: "Pot Odds Planner",
    accent: "#ffd166",
    personality:
      "Disciplined calculator. Tracks risk, price, stack depth, and usually waits for clean mathematical spots.",
    tell: "Only lights up when the numbers work.",
  },
  Kai: {
    title: "Casino Pro",
    accent: "#4cc9f0",
    personality:
      "Balanced and calm. Mixes value bets, traps, and careful aggression without giving away much timing.",
    tell: "Slow glow, steady hands.",
  },
  Pap: {
    title: "Chaos Caller",
    accent: "#f15bb5",
    personality:
      "Unorthodox and loose. Chases strange lines, sees extra flops, and turns marginal spots into pressure tests.",
    tell: "Static flickers before weird calls.",
  },
  Nik: {
    title: "Silent Assassin",
    accent: "#80ed99",
    personality:
      "Patient and surgical. Folds quietly, waits for leverage, then attacks weakness with precise bets.",
    tell: "The screen gets colder when he wakes up.",
  },
};
const SUITS = { s: "♠", h: "♥", d: "♦", c: "♣" };
const SPRITES = {
  Vin: [
    "00111100",
    "01111110",
    "01100110",
    "01111110",
    "00111100",
    "01111110",
    "01011010",
    "01000010",
  ],
  Sam: [
    "00111100",
    "01000010",
    "01111110",
    "01011010",
    "01111110",
    "00111100",
    "01100110",
    "01000010",
  ],
  Kai: [
    "00011000",
    "00111100",
    "01111110",
    "01100110",
    "00111100",
    "01111110",
    "00100100",
    "01100110",
  ],
  Pap: [
    "01111110",
    "01011010",
    "01111110",
    "00111100",
    "01111110",
    "01011010",
    "01100110",
    "01000010",
  ],
  Nik: [
    "00111100",
    "01111110",
    "01011010",
    "01111110",
    "00011000",
    "00111100",
    "01100110",
    "01000010",
  ],
};

const state = {
  runMode: "Single Hand",
  events: [],
  eventIndex: 0,
  playing: false,
  applying: false,
  streamOpen: false,
  autoTimer: null,
  eventSource: null,
  streamFinished: false,
  players: previewPlayers(300),
  modelStatus: null,
  visibleHoleCards: {},
  latestActionByPlayer: {},
  currentActor: null,
  communityCards: [],
  pot: 0,
  handNumber: 1,
  street: "preflop",
  smallBlind: 10,
  bigBlind: 20,
  winner: null,
  dialogue: [],
  timeline: [],
  lastPot: 0,
  musicPlaying: false,
  musicOptOut: false,
  musicAudio: null,
  musicUrl: null,
  musicWatchdogTimer: null,
  musicStep: 0,
  musicVolume: 0.85,
};

const els = {
  topStatus: document.querySelector("#topStatus"),
  modeButtons: Array.from(document.querySelectorAll(".seg")),
  startingChips: document.querySelector("#startingChips"),
  handsPerLevel: document.querySelector("#handsPerLevel"),
  maxHands: document.querySelector("#maxHands"),
  delay: document.querySelector("#delay"),
  delayValue: document.querySelector("#delayValue"),
  revealCards: document.querySelector("#revealCards"),
  tournamentOnly: Array.from(document.querySelectorAll(".tournament-only")),
  startBtn: document.querySelector("#startBtn"),
  stepBtn: document.querySelector("#stepBtn"),
  autoBtn: document.querySelector("#autoBtn"),
  musicBtn: document.querySelector("#musicBtn"),
  musicVolume: document.querySelector("#musicVolume"),
  musicVolumeValue: document.querySelector("#musicVolumeValue"),
  resetBtn: document.querySelector("#resetBtn"),
  seats: document.querySelector("#seats"),
  handBadge: document.querySelector("#handBadge"),
  streetBadge: document.querySelector("#streetBadge"),
  blindBadge: document.querySelector("#blindBadge"),
  potDisplay: document.querySelector("#potDisplay"),
  communityCards: document.querySelector("#communityCards"),
  leaderboard: document.querySelector("#leaderboard"),
  winnerPanel: document.querySelector("#winnerPanel"),
  winnerText: document.querySelector("#winnerText"),
  modelStatus: document.querySelector("#modelStatus"),
  dialogueLog: document.querySelector("#dialogueLog"),
  eventLog: document.querySelector("#eventLog"),
  seatTemplate: document.querySelector("#seatTemplate"),
  agentDossier: document.querySelector("#agentDossier"),
};

function previewPlayers(startingChips) {
  return PLAYER_ORDER.map((name, index) => ({
    name,
    model: MODEL_BY_PLAYER[name],
    personality: PLAYER_META[name]?.personality || "",
    chips: startingChips,
    cards: [],
    folded: false,
    current_bet: 0,
    total_committed: 0,
    status: "active",
    is_dealer: index === 0,
  }));
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function normalizeInt(value, fallback) {
  const parsed = Number.parseInt(value, 10);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function setRunMode(mode) {
  state.runMode = mode;
  els.modeButtons.forEach((button) => {
    button.classList.toggle("active", button.dataset.mode === mode);
  });
  els.tournamentOnly.forEach((item) => {
    item.style.display = mode === "Full Tournament" ? "grid" : "none";
  });
  els.startBtn.textContent = mode === "Single Hand" ? "Start Single Hand" : "Start Tournament";
  render();
}

function cardMarkup(card) {
  if (!card) {
    return '<div class="card empty">.</div>';
  }
  if (card === "BACK") {
    return '<div class="card back">?</div>';
  }

  const rank = card.slice(0, -1);
  const suitKey = card.slice(-1);
  const suit = SUITS[suitKey] || suitKey;
  const suitClass = ["h", "d"].includes(suitKey) ? "warm" : "cool";
  return `<div class="card ${suitClass}">${escapeHtml(rank)}${suit}</div>`;
}

function spriteMarkup(name) {
  const rows = SPRITES[name] || SPRITES.Vin;
  return rows
    .flatMap((row, rowIndex) =>
      row.split("").map((pixel, colIndex) => {
        const mid = (rowIndex + colIndex) % 7 === 0;
        const className = pixel === "1" ? (mid ? "px on" : "px on") : "px";
        return `<span class="${className}"></span>`;
      }),
    )
    .join("");
}

function playerLookup() {
  return Object.fromEntries(state.players.map((player) => [player.name, player]));
}

function orderedPlayers() {
  const lookup = playerLookup();
  return PLAYER_ORDER.filter((name) => lookup[name]).map((name) => lookup[name]);
}

function metaForPlayer(name) {
  const fallback = PLAYER_META[name] || PLAYER_META.Vin;
  const apiPlayer = state.modelStatus?.players?.find((player) => player.name === name);
  return {
    ...fallback,
    personality: apiPlayer?.personality || fallback.personality,
  };
}

function positionDossierAt(x, y) {
  const panel = els.agentDossier;
  if (!panel) {
    return;
  }

  const padding = 16;
  const rect = panel.getBoundingClientRect();
  const left = Math.min(window.innerWidth - rect.width - padding, Math.max(padding, x + 18));
  const top = Math.min(window.innerHeight - rect.height - padding, Math.max(padding, y + 18));
  panel.style.left = `${left}px`;
  panel.style.top = `${top}px`;
}

function showAgentDossier(playerName, x, y) {
  const meta = metaForPlayer(playerName);
  const player = playerLookup()[playerName] || {};

  els.agentDossier.style.setProperty("--accent", meta.accent);
  els.agentDossier.innerHTML = `
    <div class="dossier-kicker">${escapeHtml(playerName)} / ${escapeHtml(player.model || MODEL_BY_PLAYER[playerName] || "local model")}</div>
    <strong>${escapeHtml(meta.title)}</strong>
    <span>${escapeHtml(meta.personality)}</span>
    <em>${escapeHtml(meta.tell)}</em>
  `;
  els.agentDossier.classList.add("visible");
  els.agentDossier.setAttribute("aria-hidden", "false");
  positionDossierAt(x, y);
}

function hideAgentDossier() {
  els.agentDossier.classList.remove("visible");
  els.agentDossier.setAttribute("aria-hidden", "true");
}

function visibleCardsForPlayer(player) {
  if (player.status === "busted") {
    return [];
  }

  const visible = state.visibleHoleCards[player.name];
  if (visible && visible.length > 0) {
    return visible;
  }

  if (player.cards?.length && els.revealCards.checked) {
    return [...player.cards];
  }

  if (player.cards?.length) {
    return player.cards.map(() => "BACK");
  }

  return [];
}

function renderSeats() {
  els.seats.innerHTML = "";

  orderedPlayers().forEach((player) => {
    const node = els.seatTemplate.content.firstElementChild.cloneNode(true);
    const status = player.status || "active";
    const action = state.latestActionByPlayer[player.name] || "";
    const cards = visibleCardsForPlayer(player);
    const meta = metaForPlayer(player.name);

    node.dataset.seat = player.name;
    node.tabIndex = 0;
    node.setAttribute("aria-label", `${player.name}, ${meta.title}`);
    node.style.setProperty("--accent", meta.accent);
    node.classList.toggle("actor", state.currentActor === player.name);
    node.classList.toggle("busted", status === "busted");
    node.querySelector(".character").innerHTML = spriteMarkup(player.name);
    node.querySelector("h3").textContent = player.name;
    node.querySelector(".model").textContent = player.model || "unknown";
    node.querySelector(".chips").textContent = `${player.chips ?? 0} chips`;
    node.querySelector(".status").textContent = status;
    node.querySelector(".status").className = `status ${status}`;
    node.querySelector(".commit").textContent =
      `committed ${player.total_committed ?? 0} | bet ${player.current_bet ?? 0}`;
    node.querySelector(".hole-cards").innerHTML =
      (cards.length ? cards : ["", ""]).map(cardMarkup).join("");
    node.querySelector(".bubble").textContent = action;
    node.querySelector(".dealer-dot").classList.toggle("hidden", !player.is_dealer);
    node.addEventListener("mouseenter", (event) => {
      showAgentDossier(player.name, event.clientX, event.clientY);
    });
    node.addEventListener("mousemove", (event) => {
      if (els.agentDossier.classList.contains("visible")) {
        positionDossierAt(event.clientX, event.clientY);
      }
    });
    node.addEventListener("mouseleave", hideAgentDossier);
    node.addEventListener("focus", () => {
      const rect = node.getBoundingClientRect();
      showAgentDossier(player.name, rect.right, rect.top);
    });
    node.addEventListener("blur", hideAgentDossier);

    els.seats.appendChild(node);
  });
}

function renderBoard() {
  els.handBadge.textContent = `Hand ${state.handNumber || 1}`;
  els.streetBadge.textContent = (state.street || "preflop").toUpperCase();
  els.blindBadge.textContent = `${state.smallBlind} / ${state.bigBlind}`;
  els.potDisplay.textContent = `POT ${state.pot}`;

  if (state.pot !== state.lastPot) {
    els.potDisplay.classList.remove("bump");
    void els.potDisplay.offsetWidth;
    els.potDisplay.classList.add("bump");
    state.lastPot = state.pot;
  }

  const community = [...state.communityCards];
  while (community.length < 5) {
    community.push("");
  }
  els.communityCards.innerHTML = community.map(cardMarkup).join("");

  const leaders = [...state.players].sort((a, b) => (b.chips ?? 0) - (a.chips ?? 0));
  els.leaderboard.innerHTML = leaders
    .map((player) => `<span>${escapeHtml(player.name)} ${escapeHtml(player.chips ?? 0)}</span>`)
    .join("");
}

function renderWinner() {
  els.winnerPanel.classList.toggle("active", Boolean(state.winner));
  if (!state.winner) {
    els.winnerText.textContent = "No winner yet.";
    return;
  }

  els.winnerText.innerHTML = `
    <strong>${escapeHtml(state.winner.scope)} Winner: ${escapeHtml(state.winner.name)}</strong>
    <br />
    ${escapeHtml(state.winner.model || "")}
    <br />
    ${escapeHtml(state.winner.chips ?? 0)} chips after ${escapeHtml(state.winner.handsPlayed ?? 1)} hand(s)
  `;
}

function renderModelStatus() {
  const status = state.modelStatus;

  if (!status) {
    els.modelStatus.innerHTML = '<div class="model-row">Checking Ollama...</div>';
    return;
  }

  if (!status.online) {
    els.modelStatus.innerHTML = `
      <div class="model-row missing">Ollama offline</div>
      <div class="model-error">${escapeHtml(status.error || "localhost:11434 unavailable")}</div>
    `;
    return;
  }

  els.modelStatus.innerHTML = status.players
    .map((player) => {
      const className = player.installed ? "model-row installed" : "model-row missing";
      const mark = player.installed ? "OK" : "MISSING";
      const meta = metaForPlayer(player.name);
      return `
        <div class="${className}" style="--accent: ${escapeHtml(meta.accent)}">
          <span>${escapeHtml(player.name)}</span>
          <span title="${escapeHtml(meta.title)}">${escapeHtml(player.model)}</span>
          <strong>${mark}</strong>
        </div>
      `;
    })
    .join("");
}

function renderDialogue() {
  const entries = state.dialogue.slice(-12).reverse();
  if (!entries.length) {
    els.dialogueLog.innerHTML = '<div class="log-line">Waiting for the first decision.</div>';
    return;
  }

  els.dialogueLog.innerHTML = entries
    .map((entry) => {
      const actionClass = `action-${entry.action || "check"}`;
      return `
        <div class="log-line">
          <strong>${escapeHtml(entry.player)} <span class="${actionClass}">${escapeHtml(entry.actionLabel)}</span></strong>
          <div class="reason">${escapeHtml(entry.reason)}</div>
        </div>
      `;
    })
    .join("");
}

function renderTimeline() {
  const entries = state.timeline.slice(-16).reverse();
  if (!entries.length) {
    els.eventLog.innerHTML = '<div class="log-line">Ready at the table.</div>';
    return;
  }

  els.eventLog.innerHTML = entries
    .map(
      (entry) => `
        <div class="log-line">
          <strong>${escapeHtml(entry.prefix)}</strong>
          ${escapeHtml(entry.message)}
        </div>
      `,
    )
    .join("");
}

function renderButtons() {
  const hasQueuedEvents = state.events.length > 0;
  const done = !state.streamOpen && !hasQueuedEvents;
  els.stepBtn.disabled = !hasQueuedEvents || state.playing;
  els.autoBtn.disabled = done;
  els.autoBtn.textContent = state.playing ? "Pause" : "Auto Play";
}

function render() {
  renderSeats();
  renderBoard();
  renderWinner();
  renderModelStatus();
  renderDialogue();
  renderTimeline();
  renderButtons();
}

function resetState() {
  stopAuto();
  if (state.eventSource) {
    state.eventSource.close();
  }
  const chips = normalizeInt(els.startingChips.value, 300);
  state.events = [];
  state.eventIndex = 0;
  state.playing = false;
  state.applying = false;
  state.streamOpen = false;
  state.streamFinished = false;
  state.eventSource = null;
  state.players = previewPlayers(chips);
  state.visibleHoleCards = {};
  state.latestActionByPlayer = {};
  state.currentActor = null;
  state.communityCards = [];
  state.pot = 0;
  state.handNumber = 1;
  state.street = "preflop";
  state.smallBlind = 10;
  state.bigBlind = 20;
  state.winner = null;
  state.dialogue = [];
  state.timeline = [];
  state.lastPot = 0;
  els.topStatus.textContent = "idle";
  els.startBtn.disabled = false;
  render();
}

function revealAllHoleCards() {
  const visible = { ...state.visibleHoleCards };
  state.players.forEach((player) => {
    if (player.status !== "busted" && player.cards?.length) {
      visible[player.name] = [...player.cards];
    }
  });
  state.visibleHoleCards = visible;
}

function updateVisibleCards(event) {
  if (event.event_type === "hand_start") {
    state.visibleHoleCards = {};
    state.players.forEach((player) => {
      if (player.status !== "busted") {
        state.visibleHoleCards[player.name] = [];
      }
    });
    return;
  }

  if (event.event_type === "deal_hole_card") {
    const name = event.player;
    const cardIndex = Math.max(1, Number.parseInt(event.card_index || 1, 10));
    const cards = [...(state.visibleHoleCards[name] || [])];
    while (cards.length < cardIndex) {
      cards.push("BACK");
    }
    state.visibleHoleCards[name] = cards;
    return;
  }

  if (event.event_type === "reveal_hole_cards" && els.revealCards.checked) {
    revealAllHoleCards();
    return;
  }

  if (["showdown", "hand_end", "tournament_end"].includes(event.event_type)) {
    revealAllHoleCards();
  }
}

function eventMessage(event) {
  const player = event.player || "";
  switch (event.event_type) {
    case "tournament_start":
      return "Tournament start.";
    case "single_hand_start":
      return "Single hand start.";
    case "blind_level":
      return event.message || "Blinds updated.";
    case "hand_start":
      return `Hand ${event.hand_number} started.`;
    case "blind_posted":
      return event.message || `${player} posts blind.`;
    case "deal_hole_card":
      return `Card dealt to ${player}.`;
    case "reveal_hole_cards":
      return els.revealCards.checked ? "Hole cards revealed." : "Hole cards hidden.";
    case "street_start":
      return `${String(event.street || "").toUpperCase()} begins.`;
    case "deal_flop_card":
    case "deal_turn_card":
    case "deal_river_card":
      return `Board card: ${event.card}.`;
    case "thinking":
      return `${player} is thinking.`;
    case "player_action":
      return event.message || `${player} acts.`;
    case "showdown":
      return "Showdown reached.";
    case "hand_end":
      return `Hand winner: ${(event.winners || [event.winner]).join(", ")}.`;
    case "player_busted":
      return event.message || `${player} busted.`;
    case "leaderboard":
      return event.message || "Leaderboard updated.";
    case "tournament_end":
      return event.message || "Tournament complete.";
    default:
      return event.event_type || "Event.";
  }
}

function actionLabel(action, amount) {
  if (!action) {
    return "";
  }
  return amount ? `${action.toUpperCase()} ${amount}` : action.toUpperCase();
}

function truncate(value, limit = 88) {
  const text = String(value || "");
  return text.length <= limit ? text : `${text.slice(0, limit - 3)}...`;
}

function tableBubbleText(action, reason, amount) {
  const label = actionLabel(action, amount);
  if (!reason) {
    return label;
  }
  return `${label}: ${truncate(reason, 54)}`;
}

function writeString(view, offset, value) {
  for (let index = 0; index < value.length; index += 1) {
    view.setUint8(offset + index, value.charCodeAt(index));
  }
}

function squareAt(time, frequency) {
  return Math.sin(Math.PI * 2 * frequency * time) >= 0 ? 1 : -1;
}

function buildRetroLoopUrl() {
  if (state.musicUrl) {
    return state.musicUrl;
  }

  const sampleRate = 22050;
  const loopSeconds = 8;
  const totalSamples = sampleRate * loopSeconds;
  const headerBytes = 44;
  const buffer = new ArrayBuffer(headerBytes + totalSamples * 2);
  const view = new DataView(buffer);
  const melody = [392, 523, 659, 523, 440, 587, 784, 587, 349, 440, 523, 440, 330, 392, 494, 392];
  const bass = [98, 98, 131, 131, 110, 110, 147, 147];
  const stepLength = 0.25;

  writeString(view, 0, "RIFF");
  view.setUint32(4, 36 + totalSamples * 2, true);
  writeString(view, 8, "WAVE");
  writeString(view, 12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  writeString(view, 36, "data");
  view.setUint32(40, totalSamples * 2, true);

  for (let sample = 0; sample < totalSamples; sample += 1) {
    const time = sample / sampleRate;
    const step = Math.floor(time / stepLength);
    const local = (time % stepLength) / stepLength;
    const gate = local < 0.82 ? 1 : 0;
    const fade = Math.min(1, local * 12) * Math.min(1, (0.82 - local) * 18 + 1);
    const lead = squareAt(time, melody[step % melody.length]) * 0.46 * gate * fade;
    const low = squareAt(time, bass[Math.floor(step / 2) % bass.length]) * 0.26;
    const tick = local < 0.06 ? squareAt(time, 1568) * 0.16 * (1 - local / 0.06) : 0;
    const value = Math.max(-1, Math.min(1, lead + low + tick));
    view.setInt16(headerBytes + sample * 2, value * 32767, true);
  }

  state.musicUrl = URL.createObjectURL(new Blob([buffer], { type: "audio/wav" }));
  return state.musicUrl;
}

function ensureMusicAudio() {
  if (!state.musicAudio) {
    state.musicAudio = new Audio(buildRetroLoopUrl());
    state.musicAudio.loop = true;
    state.musicAudio.preload = "auto";
    state.musicAudio.addEventListener("ended", () => {
      if (state.musicPlaying) {
        resumeMusicPlayback();
      }
    });
    state.musicAudio.addEventListener("pause", () => {
      if (state.musicPlaying) {
        window.setTimeout(resumeMusicPlayback, 80);
      }
    });
  }

  state.musicAudio.volume = state.musicVolume;
  return state.musicAudio;
}

function syncMusicButton(isPlaying) {
  document.body.classList.toggle("music-active", isPlaying);
  els.musicBtn.textContent = isPlaying ? "Music On" : "Music Off";
  els.musicBtn.setAttribute("aria-pressed", String(isPlaying));
  els.musicBtn.classList.toggle("music-on", isPlaying);
}

async function resumeMusicPlayback() {
  if (!state.musicPlaying || !state.musicAudio) {
    return false;
  }

  try {
    if (state.musicAudio.ended || state.musicAudio.currentTime >= state.musicAudio.duration - 0.2) {
      state.musicAudio.currentTime = 0;
    }
    await state.musicAudio.play();
    syncMusicButton(true);
    return true;
  } catch (error) {
    state.musicPlaying = false;
    stopMusicWatchdog();
    syncMusicButton(false);
    els.musicBtn.textContent = "Click Music";
    return false;
  }
}

function startMusicWatchdog() {
  if (state.musicWatchdogTimer) {
    return;
  }

  state.musicWatchdogTimer = window.setInterval(() => {
    if (!state.musicPlaying || !state.musicAudio) {
      return;
    }

    if (state.musicAudio.paused || state.musicAudio.ended) {
      resumeMusicPlayback();
      return;
    }

    if (
      Number.isFinite(state.musicAudio.duration) &&
      state.musicAudio.duration > 0 &&
      state.musicAudio.currentTime >= state.musicAudio.duration - 0.12
    ) {
      state.musicAudio.currentTime = 0;
      resumeMusicPlayback();
    }
  }, 500);
}

function stopMusicWatchdog() {
  if (state.musicWatchdogTimer) {
    window.clearInterval(state.musicWatchdogTimer);
    state.musicWatchdogTimer = null;
  }
}

async function startMusic() {
  if (state.musicPlaying) {
    startMusicWatchdog();
    return resumeMusicPlayback();
  }

  const audio = ensureMusicAudio();
  try {
    audio.currentTime = audio.currentTime || 0;
    await audio.play();
    state.musicPlaying = true;
    state.musicOptOut = false;
    syncMusicButton(true);
    startMusicWatchdog();
  } catch (error) {
    state.musicPlaying = false;
    stopMusicWatchdog();
    syncMusicButton(false);
    els.musicBtn.textContent = "Click Music";
  }
}

function stopMusic(markOptOut = true) {
  state.musicPlaying = false;
  if (markOptOut) {
    state.musicOptOut = true;
  }
  if (state.musicAudio) {
    state.musicAudio.pause();
  }
  stopMusicWatchdog();
  syncMusicButton(false);
}

function toggleMusic() {
  if (state.musicPlaying) {
    stopMusic(true);
  } else {
    startMusic();
  }
}

function updateMusicVolume() {
  state.musicVolume = Number(els.musicVolume.value) / 100;
  els.musicVolumeValue.textContent = `${els.musicVolume.value}%`;
  if (state.musicAudio) {
    state.musicAudio.volume = state.musicVolume;
  }
}

function updateWinner(event) {
  if (!["hand_end", "tournament_end"].includes(event.event_type) || !event.winner) {
    return;
  }

  const player = playerLookup()[event.winner] || {};
  state.winner = {
    scope: event.event_type === "tournament_end" ? "Tournament" : "Hand",
    name: event.winner,
    model: player.model || "",
    chips: event.final_chips ?? player.chips ?? 0,
    handsPlayed: event.hands_played ?? event.hand_number ?? 1,
  };

  if (event.event_type === "tournament_end" || state.runMode === "Single Hand") {
    stopAuto();
    burstConfetti();
  }
}

function applyEvent(event) {
  state.handNumber = event.hand_number ?? state.handNumber;
  state.street = event.street ?? state.street;
  state.pot = event.pot ?? state.pot;
  state.communityCards = event.community_cards ?? state.communityCards;
  state.smallBlind = event.small_blind ?? state.smallBlind;
  state.bigBlind = event.big_blind ?? state.bigBlind;

  if (event.players?.length) {
    state.players = event.players;
  }

  if (["tournament_start", "single_hand_start"].includes(event.event_type)) {
    state.winner = null;
    state.visibleHoleCards = {};
    state.latestActionByPlayer = {};
    state.currentActor = null;
  }

  if (event.event_type === "hand_start") {
    state.winner = null;
    state.communityCards = [];
    state.pot = event.pot ?? 0;
    state.latestActionByPlayer = {};
  }

  updateVisibleCards(event);

  if (event.event_type === "thinking") {
    state.currentActor = event.player;
    state.latestActionByPlayer[event.player] = "THINKING...";
  } else if (event.event_type === "player_action") {
    const label = actionLabel(event.action, event.amount);
    state.currentActor = null;
    state.latestActionByPlayer[event.player] = tableBubbleText(
      event.action,
      event.reason,
      event.amount,
    );
    state.dialogue.push({
      player: event.player,
      action: event.action,
      actionLabel: label,
      reason: event.reason || "",
    });
  } else if (event.event_type === "blind_posted") {
    state.latestActionByPlayer[event.player] = actionLabel(event.action, event.amount);
  } else if (["street_start", "showdown", "hand_end"].includes(event.event_type)) {
    state.currentActor = null;
  } else if (event.event_type === "player_busted") {
    state.currentActor = null;
    state.latestActionByPlayer[event.player] = "BUSTED";
  }

  const prefix = state.handNumber ? `Hand ${state.handNumber}` : "Setup";
  state.timeline.push({ prefix, message: eventMessage(event) });
  updateWinner(event);
}

function stepOnce() {
  if (!state.events.length) {
    return;
  }

  const event = state.events.shift();
  state.eventIndex += 1;
  applyEvent(event);
  els.topStatus.textContent =
    !state.streamOpen && !state.events.length
      ? "complete"
      : `${state.eventIndex} shown / ${state.events.length} queued`;
  render();
}

function processQueue() {
  if (!state.playing || state.applying) {
    return;
  }

  if (!state.events.length) {
    render();
    return;
  }

  stepOnce();
  state.applying = true;
  state.autoTimer = window.setTimeout(() => {
    state.applying = false;
    processQueue();
  }, normalizeInt(els.delay.value, 360));
}

function startAuto() {
  if (!state.streamOpen && !state.events.length) {
    return;
  }
  state.playing = true;
  renderButtons();
  processQueue();
}

function stopAuto() {
  state.playing = false;
  state.applying = false;
  if (state.autoTimer) {
    window.clearTimeout(state.autoTimer);
    state.autoTimer = null;
  }
  renderButtons();
}

function enqueueStreamEvent(event) {
  if (event.event_type === "error") {
    state.timeline.push({ prefix: "Error", message: event.message || "Stream error." });
    stopAuto();
    render();
    return;
  }

  state.events.push(event);
  els.topStatus.textContent = `${state.eventIndex} shown / ${state.events.length} queued`;
  renderButtons();
  processQueue();
}

function closeStream(statusText = "complete") {
  state.streamOpen = false;
  state.streamFinished = true;
  if (state.eventSource) {
    state.eventSource.close();
    state.eventSource = null;
  }
  els.startBtn.disabled = false;
  if (!state.events.length) {
    els.topStatus.textContent = statusText;
  }
  renderButtons();
}

async function startRun() {
  stopAuto();
  resetState();
  refreshModelStatus();
  if (!state.musicOptOut) {
    await startMusic();
  }

  const payload = {
    run_mode: state.runMode,
    starting_chips: normalizeInt(els.startingChips.value, 300),
    hands_per_level: normalizeInt(els.handsPerLevel.value, 1),
    max_hands: normalizeInt(els.maxHands.value, 12),
  };

  els.topStatus.textContent = "connecting";
  els.startBtn.disabled = true;
  state.streamOpen = true;
  state.playing = true;
  renderButtons();

  const params = new URLSearchParams({
    run_mode: payload.run_mode,
    starting_chips: String(payload.starting_chips),
    hands_per_level: String(payload.hands_per_level),
    max_hands: String(payload.max_hands),
  });

  const source = new EventSource(`/api/events?${params.toString()}`);
  state.eventSource = source;

  source.onopen = () => {
    els.topStatus.textContent = "streaming";
  };

  source.onmessage = (message) => {
    const event = JSON.parse(message.data);
    enqueueStreamEvent(event);
  };

  source.addEventListener("done", () => {
    closeStream("complete");
  });

  source.onerror = () => {
    if (!state.streamOpen || state.streamFinished) {
      return;
    }
    state.timeline.push({
      prefix: "Stream",
      message: "Connection closed or failed. Check that Ollama is running if no actions appeared.",
    });
    closeStream("stream closed");
    render();
  };
}

async function refreshModelStatus() {
  try {
    const response = await fetch("/api/models");
    state.modelStatus = await response.json();
  } catch (error) {
    state.modelStatus = {
      online: false,
      error: error.message,
      players: [],
    };
  }
  render();
}

function burstConfetti() {
  const colors = ["#f4f4f4", "#ffd166", "#4cc9f0", "#f15bb5", "#80ed99"];
  for (let index = 0; index < 42; index += 1) {
    const piece = document.createElement("div");
    piece.className = "confetti";
    piece.style.left = `${Math.random() * 100}%`;
    piece.style.animationDelay = `${Math.random() * 0.6}s`;
    piece.style.background = colors[index % colors.length];
    document.body.appendChild(piece);
    window.setTimeout(() => piece.remove(), 2200);
  }
}

els.modeButtons.forEach((button) => {
  button.addEventListener("click", () => setRunMode(button.dataset.mode));
});

els.delay.addEventListener("input", () => {
  els.delayValue.textContent = `${(Number(els.delay.value) / 1000).toFixed(2)}s`;
});

els.musicVolume.addEventListener("input", updateMusicVolume);

els.startingChips.addEventListener("change", () => {
  if (!state.events.length) {
    state.players = previewPlayers(normalizeInt(els.startingChips.value, 300));
    render();
  }
});

els.revealCards.addEventListener("change", () => {
  if (els.revealCards.checked) {
    revealAllHoleCards();
  }
  render();
});

els.startBtn.addEventListener("click", startRun);
els.resetBtn.addEventListener("click", resetState);
els.stepBtn.addEventListener("click", stepOnce);
els.musicBtn.addEventListener("click", toggleMusic);
els.autoBtn.addEventListener("click", () => {
  if (state.playing) {
    stopAuto();
  } else {
    startAuto();
  }
});

document.addEventListener(
  "pointerdown",
  (event) => {
    if (event.target.closest("#musicBtn")) {
      return;
    }
    if (!state.musicOptOut && !state.musicPlaying) {
      startMusic();
    }
  },
  { passive: true },
);

setRunMode("Single Hand");
resetState();
updateMusicVolume();
els.musicBtn.setAttribute("aria-pressed", "false");
refreshModelStatus();
